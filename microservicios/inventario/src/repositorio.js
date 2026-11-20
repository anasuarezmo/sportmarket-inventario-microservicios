// Acceso a MySQL (inventario_db). Unica capa que escribe SQL. pool.query evita problemas de LIMIT con prepared statements.
function crearRepositorio(pool) {
  const filas = async (sql, params) => (await pool.query(sql, params))[0];

  function armarTx(conn) {
    const q = async (sql, params) => (await conn.query(sql, params))[0];
    return {
      async movimientoPorOperacion(op) { return (await q('SELECT * FROM movimiento WHERE operacion_id = ?', [op]))[0] || null; },
      // Crea el saldo (cantidad 0) si no existe y lo bloquea (FOR UPDATE) hasta el commit: serializa los cambios del mismo saldo.
      async saldoBloqueado(p, b) {
        await q('INSERT IGNORE INTO saldo (producto_id, bodega_id) VALUES (?, ?)', [p, b]);
        return (await q('SELECT * FROM saldo WHERE producto_id = ? AND bodega_id = ? FOR UPDATE', [p, b]))[0];
      },
      async fijarCantidad(p, b, cantidad) { await q('UPDATE saldo SET cantidad_disponible = ? WHERE producto_id = ? AND bodega_id = ?', [cantidad, p, b]); },
      async fijarMinimo(p, b, minimo) { await q('UPDATE saldo SET stock_minimo = ? WHERE producto_id = ? AND bodega_id = ?', [minimo, p, b]); },
      async insertarMovimiento(m) {
        const cols = ['operacion_id', 'tipo_movimiento', 'producto_id', 'bodega_origen_id', 'bodega_destino_id', 'cantidad_movimiento', 'saldo_resultante', 'motivo_movimiento', 'origen_movimiento', 'documento_ref', 'usuario_id'];
        const r = await conn.query(`INSERT INTO movimiento (${cols.join(', ')}) VALUES (${cols.map(() => '?').join(', ')})`, cols.map((c) => m[c]));
        return r[0].insertId;
      },
    };
  }

  const paginar = async (tabla, donde, params, orden, f) => {
    const w = donde.length ? `WHERE ${donde.join(' AND ')}` : '';
    const [{ total }] = await filas(`SELECT COUNT(*) AS total FROM ${tabla} ${w}`, params);
    return { filas: await filas(`SELECT * FROM ${tabla} ${w} ORDER BY ${orden} LIMIT ? OFFSET ?`, [...params, f.limit, (f.page - 1) * f.limit]), total };
  };

  return {
    ping: () => pool.query('SELECT 1'),
    // Ejecuta fn dentro de una transaccion: commit si termina bien, rollback si lanza cualquier error.
    async transaccion(fn) {
      const conn = await pool.getConnection();
      try {
        await conn.beginTransaction();
        const r = await fn(armarTx(conn));
        await conn.commit();
        return r;
      } catch (e) {
        await conn.rollback();
        throw e;
      } finally { conn.release(); }
    },
    async movimientoPorOperacion(op) { return (await filas('SELECT * FROM movimiento WHERE operacion_id = ?', [op]))[0] || null; },
    async movimientoPorId(id) { return (await filas('SELECT * FROM movimiento WHERE id = ?', [id]))[0] || null; },
    async obtenerSaldo(p, b) { return (await filas('SELECT * FROM saldo WHERE producto_id = ? AND bodega_id = ?', [p, b]))[0] || null; },
    saldosDeProducto: (p) => filas('SELECT * FROM saldo WHERE producto_id = ? ORDER BY bodega_id', [p]),
    listarExistencias(f) {
      const d = []; const p = [];
      if (f.producto_id) { d.push('producto_id = ?'); p.push(f.producto_id); }
      if (f.bodega_id) { d.push('bodega_id = ?'); p.push(f.bodega_id); }
      if (f.bajo_minimo === true) d.push('cantidad_disponible < stock_minimo');
      if (f.bajo_minimo === false) d.push('cantidad_disponible >= stock_minimo');
      return paginar('saldo', d, p, 'producto_id, bodega_id', f);
    },
    listarMovimientos(f) {
      const d = []; const p = [];
      if (f.producto_id) { d.push('producto_id = ?'); p.push(f.producto_id); }
      if (f.bodega_id) { d.push('(bodega_origen_id = ? OR bodega_destino_id = ?)'); p.push(f.bodega_id, f.bodega_id); }
      if (f.tipo_movimiento) { d.push('tipo_movimiento = ?'); p.push(f.tipo_movimiento); }
      if (f.origen_movimiento) { d.push('origen_movimiento = ?'); p.push(f.origen_movimiento); }
      if (f.usuario_id) { d.push('usuario_id = ?'); p.push(f.usuario_id); }
      if (f.desde) { d.push('fecha_registro_movimiento >= ?'); p.push(f.desde); }
      if (f.hasta) { d.push('fecha_registro_movimiento <= ?'); p.push(f.hasta); }
      return paginar('movimiento', d, p, 'id DESC', f);
    },
  };
}
module.exports = { crearRepositorio };
