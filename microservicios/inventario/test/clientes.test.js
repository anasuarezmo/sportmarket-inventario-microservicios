const test = require('node:test');
const assert = require('node:assert');
const { crearClientes } = require('../src/clientes');

const config = { tokenInterno: 'tok', timeoutMs: 3000, reintentos: 3, urls: { catalogo: 'http://c', bodegas: 'http://b', reportes: 'http://r' } };
const silencio = { error() {} };
const resp = (status, cuerpo) => ({ status, ok: status < 400, text: async () => (cuerpo === undefined ? '' : JSON.stringify(cuerpo)) });

function conRespuestas(lista) {
  const llamadas = []; let i = 0;
  const fn = async (url, op) => {
    llamadas.push({ url, op });
    const x = lista[Math.min(i++, lista.length - 1)];
    if (x instanceof Error) throw x;
    return x;
  };
  fn.llamadas = llamadas; return fn;
}
const esperas = []; const esperar = async (ms) => { esperas.push(ms); };

test('producto existente: 200 -> true, con credencial interna y correlation id', async () => {
  const f = conRespuestas([resp(200, { id: 1 })]);
  assert.strictEqual(await crearClientes(config, f, esperar, silencio).productoExiste(1, 'abc-12345678'), true);
  assert.strictEqual(f.llamadas[0].url, 'http://c/api/productos/1');
  assert.strictEqual(f.llamadas[0].op.headers['X-Internal-Token'], 'tok');
  assert.strictEqual(f.llamadas[0].op.headers['X-Correlation-ID'], 'abc-12345678');
});

test('404 -> false y no se reintenta', async () => {
  const f = conRespuestas([resp(404, {})]);
  assert.strictEqual(await crearClientes(config, f, esperar, silencio).bodegaExiste(9), false);
  assert.strictEqual(f.llamadas.length, 1);
});

test('fallos transitorios: reintenta con espera creciente y al final responde', async () => {
  esperas.length = 0;
  const f = conRespuestas([new TypeError('fetch failed'), resp(503, {}), resp(200, {})]);
  assert.strictEqual(await crearClientes(config, f, esperar, silencio).productoExiste(1), true);
  assert.strictEqual(f.llamadas.length, 3);
  assert.deepStrictEqual(esperas, [200, 400]);
});

test('sin respuesta tras 1 intento + 3 reintentos -> 503', async () => {
  esperas.length = 0;
  const f = conRespuestas([new TypeError('fetch failed')]);
  await assert.rejects(() => crearClientes(config, f, esperar, silencio).productoExiste(1), (e) => e.status === 503 && e.codigo === 'SERVICIO_NO_DISPONIBLE');
  assert.strictEqual(f.llamadas.length, 4);
  assert.deepStrictEqual(esperas, [200, 400, 800]);
});

test('timeout tambien cuenta como fallo transitorio', async () => {
  const e = new Error('t'); e.name = 'TimeoutError';
  const f = conRespuestas([e, resp(200, {})]);
  assert.strictEqual(await crearClientes(config, f, esperar, silencio).bodegaExiste(1), true);
});

test('respuesta inesperada (401) se trata como servicio no disponible, sin reintentos', async () => {
  const f = conRespuestas([resp(401, {})]);
  await assert.rejects(() => crearClientes(config, f, esperar, silencio).productoExiste(1), (e) => e.status === 503);
  assert.strictEqual(f.llamadas.length, 1);
});

test('aviso de stock: POST con el cuerpo a /api/interno/alertas/stock', async () => {
  const f = conRespuestas([resp(201, {})]);
  const aviso = { evento: 'STOCK_BAJO', producto_id: 1, bodega_id: 2, cantidad_disponible: 3, stock_minimo: 5 };
  await crearClientes(config, f, esperar, silencio).avisarStock(aviso, 'abc-12345678');
  assert.strictEqual(f.llamadas[0].url, 'http://r/api/interno/alertas/stock');
  assert.strictEqual(f.llamadas[0].op.method, 'POST');
  assert.deepStrictEqual(JSON.parse(f.llamadas[0].op.body), aviso);
  assert.strictEqual(f.llamadas[0].op.headers['Content-Type'], 'application/json');
});

test('aviso de stock rechazado por Reportes (400) lanza error', async () => {
  const f = conRespuestas([resp(400, {})]);
  await assert.rejects(() => crearClientes(config, f, esperar, silencio).avisarStock({}, 'x'));
});
