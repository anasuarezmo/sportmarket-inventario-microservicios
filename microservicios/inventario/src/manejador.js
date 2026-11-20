// Capa HTTP independiente de Express: credencial interna, roles, rutas y formato de errores.
const crypto = require('crypto');
const { ErrorApi } = require('./errores');
const { crearServicio } = require('./servicio');

function crearManejador(config, repo, clientes, log = console) {
  const s = crearServicio(repo, clientes, log);
  const ADM_INV = ['ADM', 'INV'];
  // [metodo, regex, funcion, roles que pueden usarla (null = cualquiera), acepta llamadas internas sin rol de usuario]
  const rutas = [
    ['GET', /^\/api\/inventario\/existencias$/, (m) => s.existencias.listar(m.consulta), null, false],
    ['GET', /^\/api\/inventario\/existencias\/([^/]+)$/, (m, c, id) => s.existencias.porProducto(id, c), null, false],
    ['POST', /^\/api\/inventario\/entradas$/, (m, c) => s.movimientos.entrada(m.cuerpo, c), ['ADM', 'INV', 'BOD'], true],
    ['POST', /^\/api\/inventario\/salidas$/, (m, c) => s.movimientos.salida(m.cuerpo, c), ['ADM', 'INV', 'BOD'], true],
    ['POST', /^\/api\/inventario\/ajustes$/, (m, c) => s.movimientos.ajuste(m.cuerpo, c), ADM_INV, false],
    ['POST', /^\/api\/inventario\/traslados$/, (m, c) => s.movimientos.traslado(m.cuerpo, c), ['ADM', 'INV', 'BOD'], false],
    ['GET', /^\/api\/inventario\/movimientos$/, (m) => s.movimientos.listar(m.consulta), null, false],
    ['GET', /^\/api\/inventario\/movimientos\/([^/]+)$/, (m, c, id) => s.movimientos.obtener(id), null, false],
    ['GET', /^\/api\/inventario\/minimos\/([^/]+)\/([^/]+)$/, (m, c, p, b) => s.minimos.obtener(p, b, c), null, false],
    ['PUT', /^\/api\/inventario\/minimos\/([^/]+)\/([^/]+)$/, (m, c, p, b) => s.minimos.fijar(p, b, m.cuerpo, c), ADM_INV, false],
  ];

  const tokenValido = (t) => {
    const a = Buffer.from(String(t || '')); const b = Buffer.from(config.tokenInterno || '');
    return b.length > 0 && a.length === b.length && crypto.timingSafeEqual(a, b);
  };

  async function manejar(m) {
    const h = m.headers || {};
    const cid = /^[\w-]{8,64}$/.test(h['x-correlation-id'] || '') ? h['x-correlation-id'] : crypto.randomUUID();
    const resp = (status, cuerpo) => ({ status, cuerpo, headers: { 'X-Correlation-ID': cid } });
    const error = (status, codigo, mensaje, detalles = []) => resp(status, { codigo, mensaje, detalles, correlation_id: cid });
    try {
      if (m.metodo === 'GET' && m.ruta === '/health') {
        if (repo.ping) { try { await repo.ping(); } catch { return resp(503, { estado: 'DOWN', servicio: 'inventario' }); } }
        return resp(200, { estado: 'UP', servicio: 'inventario' });
      }
      if (!tokenValido(h['x-internal-token'])) return error(401, 'NO_AUTENTICADO', 'Falta o es invalida la credencial interna');
      const coinciden = rutas.filter(([, rx]) => rx.test(m.ruta));
      if (coinciden.length === 0) return error(404, 'RECURSO_NO_ENCONTRADO', 'Ruta no encontrada');
      const ruta = coinciden.find(([met]) => met === m.metodo);
      if (!ruta) return error(405, 'METODO_NO_PERMITIDO', 'Metodo no permitido para esta ruta');
      const [, rx, fn, roles, aceptaInterno] = ruta;

      // Peticion del Gateway = lleva X-User-Role. Llamada entre servicios = no lo lleva.
      const rol = h['x-user-role'];
      const interno = rol === undefined;
      if (roles) {
        const ok = interno ? aceptaInterno : roles.includes(rol);
        if (!ok) return error(403, 'PROHIBIDO', 'Tu rol no tiene permiso para esta operacion');
      }
      const ctx = { cid, interno, rol, usuarioId: /^\d+$/.test(h['x-user-id'] || '') ? Number(h['x-user-id']) : null };
      const r = await fn(m, ctx, ...rx.exec(m.ruta).slice(1));
      return resp(r.status, r.cuerpo);
    } catch (e) {
      if (e instanceof ErrorApi) return error(e.status, e.codigo, e.message, e.detalles);
      log.error('Error interno:', e);
      return error(500, 'ERROR_INTERNO', 'Error interno del servicio');
    }
  }
  return { manejar, esperarAvisos: s.esperarAvisos };
}
module.exports = { crearManejador };
