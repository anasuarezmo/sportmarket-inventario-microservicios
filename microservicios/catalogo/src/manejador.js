// Capa HTTP independiente de Express: valida credencial interna y rol, enruta y da formato a los errores.
const crypto = require('crypto');
const { ErrorApi } = require('./errores');
const { crearServicio } = require('./servicio');

const ESCRITURA = ['ADM', 'INV'];   // roles que pueden crear/modificar (el Gateway ya lo valida; aqui se repite por seguridad)

function crearManejador(config, repo, log = console) {
  const s = crearServicio(repo);
  // [metodo, regex, funcion, escritura?]
  const rutas = [
    ['GET', /^\/api\/productos$/, (m) => s.productos.listar(m.consulta), false],
    ['POST', /^\/api\/productos$/, (m) => s.productos.crear(m.cuerpo), true],
    ['GET', /^\/api\/productos\/([^/]+)$/, (m, id) => s.productos.obtener(id), false],
    ['PUT', /^\/api\/productos\/([^/]+)$/, (m, id) => s.productos.actualizar(id, m.cuerpo), true],
    ['PATCH', /^\/api\/productos\/([^/]+)\/estado$/, (m, id) => s.productos.cambiarEstado(id, m.cuerpo), true],
    ['GET', /^\/api\/categorias$/, (m) => s.categorias.listar(m.consulta), false],
    ['POST', /^\/api\/categorias$/, (m) => s.categorias.crear(m.cuerpo), true],
    ['GET', /^\/api\/categorias\/([^/]+)$/, (m, id) => s.categorias.obtener(id), false],
    ['PUT', /^\/api\/categorias\/([^/]+)$/, (m, id) => s.categorias.actualizar(id, m.cuerpo), true],
    ['PATCH', /^\/api\/categorias\/([^/]+)\/estado$/, (m, id) => s.categorias.cambiarEstado(id, m.cuerpo), true],
  ];

  const tokenValido = (recibido) => {
    const a = Buffer.from(String(recibido || '')); const b = Buffer.from(config.tokenInterno || '');
    return b.length > 0 && a.length === b.length && crypto.timingSafeEqual(a, b);
  };

  async function manejar(m) {
    const headers = m.headers || {};
    const cid = /^[\w-]{8,64}$/.test(headers['x-correlation-id'] || '') ? headers['x-correlation-id'] : crypto.randomUUID();
    const resp = (status, cuerpo) => ({ status, cuerpo, headers: { 'X-Correlation-ID': cid } });
    const error = (status, codigo, mensaje, detalles = []) => resp(status, { codigo, mensaje, detalles, correlation_id: cid });

    try {
      if (m.metodo === 'GET' && m.ruta === '/health') {
        if (repo.ping) { try { await repo.ping(); } catch { return resp(503, { estado: 'DOWN', servicio: 'catalogo' }); } }
        return resp(200, { estado: 'UP', servicio: 'catalogo' });
      }
      // Solo el Gateway (u otro servicio) conoce la credencial interna
      if (!tokenValido(headers['x-internal-token'])) return error(401, 'NO_AUTENTICADO', 'Falta o es invalida la credencial interna');

      const coinciden = rutas.filter(([, rx]) => rx.test(m.ruta));
      if (coinciden.length === 0) return error(404, 'RECURSO_NO_ENCONTRADO', 'Ruta no encontrada');
      const ruta = coinciden.find(([met]) => met === m.metodo);
      if (!ruta) return error(405, 'METODO_NO_PERMITIDO', 'Metodo no permitido para esta ruta');
      const [, rx, fn, escritura] = ruta;
      if (escritura && !ESCRITURA.includes(headers['x-user-role'])) return error(403, 'PROHIBIDO', 'Tu rol no tiene permiso para esta operacion');

      const r = await fn(m, ...(rx.exec(m.ruta).slice(1)));
      return resp(r.status, r.cuerpo);
    } catch (e) {
      if (e instanceof ErrorApi) return error(e.status, e.codigo, e.message, e.detalles);
      if (e && e.code === 'ER_DUP_ENTRY') return error(409, 'CODIGO_DUPLICADO', 'Ya existe un registro con ese valor unico');
      log.error('Error interno:', e);
      return error(500, 'ERROR_INTERNO', 'Error interno del servicio');
    }
  }
  return { manejar };
}
module.exports = { crearManejador };
