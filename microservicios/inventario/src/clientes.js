// Llamadas REST a otros servicios: Catalogo, Bodegas y Reportes y Alertas.
// RNF18: espera maxima de 3 s por intento y hasta 3 reintentos (con espera creciente) ante fallos transitorios.
const { ErrorApi } = require('./errores');

const dormir = (ms) => new Promise((r) => setTimeout(r, ms));

function crearClientes(config, fetchFn = fetch, esperar = dormir, log = console) {
  // Devuelve {status, cuerpo}. Reintenta solo si hay error de red, timeout o respuesta 5xx.
  async function llamar(base, ruta, { metodo = 'GET', cuerpo, cid } = {}) {
    const headers = { Accept: 'application/json', 'X-Internal-Token': config.tokenInterno };
    if (cid) headers['X-Correlation-ID'] = cid;
    if (cuerpo !== undefined) headers['Content-Type'] = 'application/json';
    let ultimo;
    for (let intento = 0; intento <= config.reintentos; intento++) {
      if (intento > 0) await esperar(200 * 2 ** (intento - 1));   // 200 ms, 400 ms, 800 ms
      try {
        const r = await fetchFn(`${base}${ruta}`, {
          method: metodo, headers, signal: AbortSignal.timeout(config.timeoutMs),
          body: cuerpo === undefined ? undefined : JSON.stringify(cuerpo),
        });
        if (r.status >= 500) { ultimo = new Error(`HTTP ${r.status}`); continue; }
        const texto = await r.text();
        let datos = null;
        if (texto) { try { datos = JSON.parse(texto); } catch { datos = null; } }
        return { status: r.status, cuerpo: datos };
      } catch (e) { ultimo = e; }
    }
    log.error(`Fallo llamando a ${base}${ruta}:`, ultimo && ultimo.message);
    throw new ErrorApi(503, 'SERVICIO_NO_DISPONIBLE', 'Un servicio necesario no esta disponible', [{ campo: 'servicio', error: base }]);
  }

  // Existe el recurso? true | false. Cualquier otra respuesta inesperada se trata como servicio no disponible.
  async function existe(base, ruta, cid) {
    const r = await llamar(base, ruta, { cid });
    if (r.status === 200) return true;
    if (r.status === 404) return false;
    throw new ErrorApi(503, 'SERVICIO_NO_DISPONIBLE', 'Respuesta inesperada de un servicio necesario', [{ campo: 'servicio', error: `${base} respondio ${r.status}` }]);
  }

  return {
    productoExiste: (id, cid) => existe(config.urls.catalogo, `/api/productos/${id}`, cid),
    bodegaExiste: (id, cid) => existe(config.urls.bodegas, `/api/bodegas/${id}`, cid),
    // Aviso a Reportes y Alertas (solo cruces del minimo). El que llama decide que hacer si falla.
    async avisarStock(aviso, cid) {
      const r = await llamar(config.urls.reportes, '/api/interno/alertas/stock', { metodo: 'POST', cuerpo: aviso, cid });
      if (r.status !== 200 && r.status !== 201) throw new Error(`Reportes respondio ${r.status}`);
    },
  };
}
module.exports = { crearClientes };
