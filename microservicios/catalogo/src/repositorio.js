// Acceso a MySQL (catalogo_db). Unica capa que escribe SQL.
// Se usa pool.query (y no execute) para que LIMIT/OFFSET funcionen con cualquier version de MySQL.
const aProducto = (r) => r && { ...r, precio_venta: Number(r.precio_venta), producto_activo: !!r.producto_activo };
const aCategoria = (r) => r && { ...r, categoria_activa: !!r.categoria_activa };

const CAMPOS_PRODUCTO = ['codigo_producto', 'nombre_producto', 'descripcion_producto', 'categoria_id', 'unidad_medida', 'precio_venta', 'proveedor_principal_id', 'producto_activo'];
const CAMPOS_CATEGORIA = ['nombre', 'descripcion', 'categoria_padre_id', 'categoria_activa'];

function crearRepositorio(pool) {
  const insertar = async (tabla, campos, datos) => {
    const cols = campos.filter((c) => datos[c] !== undefined);
    const [r] = await pool.query(`INSERT INTO ${tabla} (${cols.join(', ')}) VALUES (${cols.map(() => '?').join(', ')})`, cols.map((c) => datos[c]));
    return r.insertId;
  };
  const actualizar = async (tabla, campos, id, datos) => {
    const cols = campos.filter((c) => datos[c] !== undefined);
    if (cols.length === 0) return;
    await pool.query(`UPDATE ${tabla} SET ${cols.map((c) => `${c} = ?`).join(', ')} WHERE id = ?`, [...cols.map((c) => datos[c]), id]);
  };
  const listar = async (tabla, donde, params, f, mapa) => {
    const w = donde.length ? `WHERE ${donde.join(' AND ')}` : '';
    const [[{ total }]] = await pool.query(`SELECT COUNT(*) AS total FROM ${tabla} ${w}`, params);
    const [filas] = await pool.query(`SELECT * FROM ${tabla} ${w} ORDER BY id LIMIT ? OFFSET ?`, [...params, f.limit, (f.page - 1) * f.limit]);
    return { filas: filas.map(mapa), total };
  };

  return {
    ping: () => pool.query('SELECT 1'),
    productos: {
      listar(f) {
        const d = []; const p = [];
        if (f.nombre) { d.push('nombre_producto LIKE ?'); p.push(`%${f.nombre}%`); }
        if (f.codigo) { d.push('codigo_producto = ?'); p.push(f.codigo); }
        if (f.categoria_id) { d.push('categoria_id = ?'); p.push(f.categoria_id); }
        if (f.proveedor_id) { d.push('proveedor_principal_id = ?'); p.push(f.proveedor_id); }
        if (f.producto_activo !== undefined) { d.push('producto_activo = ?'); p.push(f.producto_activo ? 1 : 0); }
        return listar('producto', d, p, f, aProducto);
      },
      async obtener(id) { const [r] = await pool.query('SELECT * FROM producto WHERE id = ?', [id]); return aProducto(r[0]) || null; },
      async obtenerPorCodigo(codigo) { const [r] = await pool.query('SELECT * FROM producto WHERE codigo_producto = ?', [codigo]); return aProducto(r[0]) || null; },
      insertar: (datos) => insertar('producto', CAMPOS_PRODUCTO, datos),
      actualizar: (id, datos) => actualizar('producto', CAMPOS_PRODUCTO, id, datos),
    },
    categorias: {
      listar(f) {
        const d = []; const p = [];
        if (f.categoria_padre_id) { d.push('categoria_padre_id = ?'); p.push(f.categoria_padre_id); }
        if (f.categoria_activa !== undefined) { d.push('categoria_activa = ?'); p.push(f.categoria_activa ? 1 : 0); }
        return listar('categoria', d, p, f, aCategoria);
      },
      async obtener(id) { const [r] = await pool.query('SELECT * FROM categoria WHERE id = ?', [id]); return aCategoria(r[0]) || null; },
      insertar: (datos) => insertar('categoria', CAMPOS_CATEGORIA, datos),
      actualizar: (id, datos) => actualizar('categoria', CAMPOS_CATEGORIA, id, datos),
    },
  };
}
module.exports = { crearRepositorio };
