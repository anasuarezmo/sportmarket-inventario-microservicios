// Repositorio y clientes falsos (en memoria) para probar Inventario sin MySQL ni red.
const { crearManejador } = require('../src/manejador');

function repoMemoria() {
  let st = { saldos: [], movs: [], mid: 1 };
  let cola = Promise.resolve();   // simula el bloqueo de filas: las transacciones se ejecutan una a la vez
  const clonar = (x) => JSON.parse(JSON.stringify(x));
  const rep = {
    falloAlInsertar: false,
    get estado() { return st; },
    async transaccion(fn) {
      const turno = cola; let liberar; cola = new Promise((r) => { liberar = r; }); await turno;
      const copia = clonar(st);
      try {
        const tx = {
          movimientoPorOperacion: async (op) => st.movs.find((m) => m.operacion_id === op) || null,
          async saldoBloqueado(p, b) {
            let s = st.saldos.find((x) => x.producto_id === p && x.bodega_id === b);
            if (!s) { s = { producto_id: p, bodega_id: b, cantidad_disponible: 0, stock_minimo: 0 }; st.saldos.push(s); }
            return { ...s };
          },
          async fijarCantidad(p, b, c) { st.saldos.find((x) => x.producto_id === p && x.bodega_id === b).cantidad_disponible = c; },
          async fijarMinimo(p, b, m) { st.saldos.find((x) => x.producto_id === p && x.bodega_id === b).stock_minimo = m; },
          async insertarMovimiento(m) {
            if (rep.falloAlInsertar) throw new Error('fallo simulado al insertar el movimiento');
            if (st.movs.some((x) => x.operacion_id === m.operacion_id)) { const e = new Error('dup'); e.code = 'ER_DUP_ENTRY'; throw e; }
            const fila = { id: st.mid++, ...m, fecha_registro_movimiento: new Date(Date.now() + st.mid * 1000) };
            st.movs.push(fila); return fila.id;
          },
        };
        return await fn(tx);
      } catch (e) { st = copia; throw e; } finally { liberar(); }
    },
    async movimientoPorOperacion(op) { return st.movs.find((m) => m.operacion_id === op) || null; },
    async movimientoPorId(id) { return st.movs.find((m) => m.id === id) || null; },
    async obtenerSaldo(p, b) { return st.saldos.find((s) => s.producto_id === p && s.bodega_id === b) || null; },
    async saldosDeProducto(p) { return st.saldos.filter((s) => s.producto_id === p).sort((a, b) => a.bodega_id - b.bodega_id); },
    async listarExistencias(f) {
      let r = st.saldos;
      if (f.producto_id) r = r.filter((s) => s.producto_id === f.producto_id);
      if (f.bodega_id) r = r.filter((s) => s.bodega_id === f.bodega_id);
      if (f.bajo_minimo === true) r = r.filter((s) => s.cantidad_disponible < s.stock_minimo);
      if (f.bajo_minimo === false) r = r.filter((s) => s.cantidad_disponible >= s.stock_minimo);
      return { filas: r.slice((f.page - 1) * f.limit, f.page * f.limit), total: r.length };
    },
    async listarMovimientos(f) {
      let r = [...st.movs].reverse();
      if (f.producto_id) r = r.filter((m) => m.producto_id === f.producto_id);
      if (f.bodega_id) r = r.filter((m) => m.bodega_origen_id === f.bodega_id || m.bodega_destino_id === f.bodega_id);
      if (f.tipo_movimiento) r = r.filter((m) => m.tipo_movimiento === f.tipo_movimiento);
      if (f.origen_movimiento) r = r.filter((m) => m.origen_movimiento === f.origen_movimiento);
      if (f.usuario_id) r = r.filter((m) => m.usuario_id === f.usuario_id);
      if (f.desde) r = r.filter((m) => m.fecha_registro_movimiento >= f.desde);
      if (f.hasta) r = r.filter((m) => m.fecha_registro_movimiento <= f.hasta);
      return { filas: r.slice((f.page - 1) * f.limit, f.page * f.limit), total: r.length };
    },
  };
  return rep;
}

function clientesFalsos() {
  const c = {
    productos: new Set([1, 2]), bodegas: new Set([1, 2, 3]), avisos: [], caido: false, falloAviso: false,
    async productoExiste(id) { if (c.caido) { const { ErrorApi } = require('../src/errores'); throw new ErrorApi(503, 'SERVICIO_NO_DISPONIBLE', 'caido'); } return c.productos.has(id); },
    async bodegaExiste(id) { return c.bodegas.has(id); },
    async avisarStock(a) { if (c.falloAviso) throw new Error('Reportes caido'); c.avisos.push(a); },
  };
  return c;
}

const config = { tokenInterno: 'tok-interno' };
function nuevo() {
  const repo = repoMemoria(); const clientes = clientesFalsos();
  const h = crearManejador(config, repo, clientes, { error() {} });
  const llamar = (metodo, ruta, { cuerpo, consulta = {}, rol = 'INV', usuario = '3', token = 'tok-interno' } = {}) => h.manejar({
    metodo, ruta, consulta, cuerpo,
    headers: { ...(token ? { 'x-internal-token': token } : {}), ...(rol ? { 'x-user-role': rol } : {}), ...(usuario && rol ? { 'x-user-id': usuario } : {}) },
  });
  return { llamar, repo, clientes, esperar: h.esperarAvisos };
}
let n = 0;
const uuid = () => `00000000-0000-4000-8000-${String(++n).padStart(12, '0')}`;
const entrada = (extra = {}) => ({ operacion_id: uuid(), producto_id: 1, bodega_destino_id: 2, cantidad_movimiento: 20, origen_movimiento: 'MANUAL', ...extra });
const salida = (extra = {}) => ({ operacion_id: uuid(), producto_id: 1, bodega_origen_id: 2, cantidad_movimiento: 5, origen_movimiento: 'MANUAL', ...extra });
module.exports = { nuevo, uuid, entrada, salida, repoMemoria, clientesFalsos };
