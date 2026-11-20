// Logica del Gateway, independiente de Express (asi se puede probar sin levantar servidor).
// manejar({metodo, ruta, consulta, headers, cuerpo}) -> {status, headers?, cuerpo}
const crypto = require('crypto');
const { verificarToken } = require('./jwt');
const { buscarRuta, puedeAcceder } = require('./enrutador');
const { error } = require('./errores');

function crearGateway(config, fetchFn = fetch) {
  async function estadoServicios(correlationId) {
    const out = {};
    await Promise.all(Object.entries(config.servicios).map(async ([n, url]) => {
      try {
        const r = await fetchFn(`${url}/health`, { signal: AbortSignal.timeout(2000), headers: { 'X-Correlation-ID': correlationId } });
        out[n] = r.ok ? 'UP' : 'DOWN';
      } catch { out[n] = 'DOWN'; }
    }));
    return out;
  }

  async function manejar(req) {
    const headers = req.headers || {};
    const cid = /^[\w-]{8,64}$/.test(headers['x-correlation-id'] || '') ? headers['x-correlation-id'] : crypto.randomUUID();
    const conCid = (r) => ({ ...r, headers: { 'X-Correlation-ID': cid, ...(r.headers || {}) } });

    // Salud del propio Gateway (publica)
    if (req.metodo === 'GET' && req.ruta === '/health') {
      return conCid({ status: 200, cuerpo: { estado: 'UP', servicio: 'api-gateway' } });
    }
    // Salud agregada (requiere token)
    const esHealthApi = req.metodo === 'GET' && req.ruta === '/api/health';

    // Los endpoints internos jamas se exponen
    if (req.ruta.startsWith('/api/interno')) {
      const e = error(404, 'RECURSO_NO_ENCONTRADO', 'Ruta no encontrada', cid);
      return conCid({ status: e.status, cuerpo: e.cuerpo });
    }

    let regla = null;
    if (!esHealthApi) {
      const r = buscarRuta(req.metodo, req.ruta);
      if (!r) { const e = error(404, 'RECURSO_NO_ENCONTRADO', 'Ruta no encontrada', cid); return conCid({ status: e.status, cuerpo: e.cuerpo }); }
      if (r.noPermitido) { const e = error(405, 'METODO_NO_PERMITIDO', 'Metodo no permitido para esta ruta', cid); return conCid({ status: e.status, cuerpo: e.cuerpo }); }
      regla = r.regla;
    }

    // Autenticacion
    let usuario = null;
    if (esHealthApi || regla.acceso !== 'publica') {
      const m = /^Bearer (.+)$/.exec(headers.authorization || '');
      if (!m) { const e = error(401, 'NO_AUTENTICADO', 'Falta el token Bearer', cid); return conCid({ status: e.status, cuerpo: e.cuerpo }); }
      const v = verificarToken(m[1], config.jwtSecret);
      if (!v.ok) { const e = error(401, 'NO_AUTENTICADO', v.motivo, cid); return conCid({ status: e.status, cuerpo: e.cuerpo }); }
      usuario = v;
      // Autorizacion por rol (tabla generada del OpenAPI)
      if (regla && !puedeAcceder(regla, v.rol)) {
        const e = error(403, 'PROHIBIDO', 'Tu rol no tiene permiso para esta operacion', cid, [`rol=${v.rol}`]);
        return conCid({ status: e.status, cuerpo: e.cuerpo });
      }
    }

    if (esHealthApi) return conCid({ status: 200, cuerpo: { estado: 'UP', servicios: await estadoServicios(cid) } });

    // Reenvio al microservicio
    const destino = `${config.servicios[regla.servicio]}${req.ruta}${req.consulta || ''}`;
    const h = { 'X-Correlation-ID': cid, 'X-Internal-Token': config.tokenInterno, Accept: 'application/json' };
    if (usuario) { h['X-User-Id'] = usuario.usuarioId; h['X-User-Role'] = usuario.rol; }
    if (headers.authorization) h.Authorization = headers.authorization;   // usuarios lo necesita en logout/change-password
    const opciones = { method: req.metodo, headers: h, signal: AbortSignal.timeout(config.timeoutMs) };
    if (!['GET', 'HEAD'].includes(req.metodo) && req.cuerpo !== undefined && req.cuerpo !== null && Object.keys(req.cuerpo).length > 0) {
      h['Content-Type'] = 'application/json';
      opciones.body = JSON.stringify(req.cuerpo);
    }
    try {
      const resp = await fetchFn(destino, opciones);
      const texto = await resp.text();
      let cuerpo = null;
      if (texto) { try { cuerpo = JSON.parse(texto); } catch { cuerpo = { mensaje: texto }; } }
      return conCid({ status: resp.status, cuerpo });
    } catch (err) {
      const timeout = err && (err.name === 'TimeoutError' || err.name === 'AbortError');
      const e = timeout
        ? error(504, 'TIEMPO_AGOTADO', `El servicio ${regla.servicio} no respondio a tiempo`, cid)
        : error(503, 'SERVICIO_NO_DISPONIBLE', `El servicio ${regla.servicio} no esta disponible`, cid);
      return conCid({ status: e.status, cuerpo: e.cuerpo });
    }
  }
  return { manejar };
}
module.exports = { crearGateway };
