const test = require('node:test');
const assert = require('node:assert');
const { crearGateway } = require('../src/gateway');
const { firmarToken, verificarToken } = require('../src/jwt');
const { reglas } = require('../src/enrutador');

const SECRET = 'secreto-de-prueba';
const config = {
  jwtSecret: SECRET, tokenInterno: 'tok-interno', timeoutMs: 500,
  servicios: { usuarios: 'http://u', bodegas: 'http://b', catalogo: 'http://c', inventario: 'http://i', compras: 'http://co', devoluciones: 'http://d', reportes: 'http://r' },
};
const ahora = () => Math.floor(Date.now() / 1000);
const token = (rol, extra = {}) => firmarToken({ sub: '7', rol, exp: ahora() + 3600, ...extra }, SECRET);

function fakeFetch(respuesta = { status: 200, cuerpo: { ok: true } }) {
  const llamadas = [];
  const fn = async (url, op) => {
    llamadas.push({ url, op });
    if (respuesta.lanza) throw respuesta.lanza;
    return { ok: respuesta.status < 400, status: respuesta.status, text: async () => JSON.stringify(respuesta.cuerpo) };
  };
  fn.llamadas = llamadas;
  return fn;
}
const req = (metodo, ruta, rol, extra = {}) => ({ metodo, ruta, headers: rol ? { authorization: `Bearer ${token(rol)}` } : {}, ...extra });

test('tabla tiene las 66 operaciones publicas de los 7 servicios', () => assert.strictEqual(reglas.length, 66));

test('/health es publico', async () => {
  const r = await crearGateway(config, fakeFetch()).manejar({ metodo: 'GET', ruta: '/health', headers: {} });
  assert.strictEqual(r.status, 200);
  assert.ok(r.headers['X-Correlation-ID']);
});

test('sin token -> 401 con formato de error', async () => {
  const r = await crearGateway(config, fakeFetch()).manejar(req('GET', '/api/productos'));
  assert.strictEqual(r.status, 401);
  assert.deepStrictEqual(Object.keys(r.cuerpo).sort(), ['codigo', 'correlation_id', 'detalles', 'mensaje']);
});

test('token con firma incorrecta o expirado -> 401', async () => {
  const gw = crearGateway(config, fakeFetch());
  const malo = firmarToken({ sub: '1', rol: 'ADM', exp: ahora() + 60 }, 'otro-secreto');
  assert.strictEqual((await gw.manejar({ metodo: 'GET', ruta: '/api/productos', headers: { authorization: `Bearer ${malo}` } })).status, 401);
  const exp = firmarToken({ sub: '1', rol: 'ADM', exp: ahora() - 1 }, SECRET);
  assert.strictEqual((await gw.manejar({ metodo: 'GET', ruta: '/api/productos', headers: { authorization: `Bearer ${exp}` } })).status, 401);
});

test('rechaza alg=none', () => {
  const h = Buffer.from('{"alg":"none"}').toString('base64url');
  const p = Buffer.from(JSON.stringify({ sub: '1', rol: 'ADM', exp: ahora() + 60 })).toString('base64url');
  assert.strictEqual(verificarToken(`${h}.${p}.`, SECRET).ok, false);
});

test('rol sin permiso -> 403 y NO llama al servicio', async () => {
  const f = fakeFetch();
  const r = await crearGateway(config, f).manejar(req('POST', '/api/productos', 'CON', { cuerpo: { nombre: 'x' } }));
  assert.strictEqual(r.status, 403);
  assert.strictEqual(f.llamadas.length, 0);
});

test('rol permitido -> reenvia con cabeceras internas y query', async () => {
  const f = fakeFetch({ status: 201, cuerpo: { id: 1 } });
  const r = await crearGateway(config, f).manejar(req('POST', '/api/productos', 'INV', { consulta: '?a=1', cuerpo: { nombre: 'Balon' } }));
  assert.strictEqual(r.status, 201);
  const l = f.llamadas[0];
  assert.strictEqual(l.url, 'http://c/api/productos?a=1');
  assert.strictEqual(l.op.headers['X-User-Id'], '7');
  assert.strictEqual(l.op.headers['X-User-Role'], 'INV');
  assert.strictEqual(l.op.headers['X-Internal-Token'], 'tok-interno');
  assert.ok(l.op.headers['X-Correlation-ID']);
  assert.strictEqual(l.op.body, JSON.stringify({ nombre: 'Balon' }));
});

test('cliente no puede falsificar X-User-Role', async () => {
  const f = fakeFetch();
  await crearGateway(config, f).manejar({ metodo: 'GET', ruta: '/api/productos', headers: { authorization: `Bearer ${token('CON')}`, 'x-user-role': 'ADM' } });
  assert.strictEqual(f.llamadas[0].op.headers['X-User-Role'], 'CON');
});

test('login es publico y va a usuarios', async () => {
  const f = fakeFetch();
  const r = await crearGateway(config, f).manejar({ metodo: 'POST', ruta: '/api/auth/login', headers: {}, cuerpo: { usuario: 'a', clave: 'b' } });
  assert.strictEqual(r.status, 200);
  assert.strictEqual(f.llamadas[0].url, 'http://u/api/auth/login');
  assert.strictEqual(f.llamadas[0].op.headers['X-User-Id'], undefined);
});

test('enrutamiento de los 7 servicios con rutas con parametros', async () => {
  const casos = [['/api/bodegas/3/ubicaciones', 'http://b'], ['/api/categorias/2', 'http://c'], ['/api/inventario/minimos/1/2', 'http://i'],
    ['/api/compras/9/recepciones', 'http://co'], ['/api/devoluciones/4', 'http://d'], ['/api/alertas', 'http://r'], ['/api/roles', 'http://u']];
  for (const [ruta, base] of casos) {
    const f = fakeFetch();
    await crearGateway(config, f).manejar(req('GET', ruta, 'ADM'));
    assert.ok(f.llamadas[0].url.startsWith(base), `${ruta} -> ${f.llamadas[0] && f.llamadas[0].url}`);
  }
});

test('/api/interno/* no se expone', async () => {
  const r = await crearGateway(config, fakeFetch()).manejar(req('POST', '/api/interno/alertas/stock', 'ADM', { cuerpo: { a: 1 } }));
  assert.strictEqual(r.status, 404);
});

test('ruta inexistente 404 y metodo incorrecto 405', async () => {
  const gw = crearGateway(config, fakeFetch());
  assert.strictEqual((await gw.manejar(req('GET', '/api/nada', 'ADM'))).status, 404);
  assert.strictEqual((await gw.manejar(req('DELETE', '/api/productos', 'ADM'))).status, 405);
});

test('servicio caido -> 503; timeout -> 504', async () => {
  const r1 = await crearGateway(config, fakeFetch({ lanza: new TypeError('fetch failed') })).manejar(req('GET', '/api/productos', 'ADM'));
  assert.strictEqual(r1.status, 503);
  const e = new Error('t'); e.name = 'TimeoutError';
  const r2 = await crearGateway(config, fakeFetch({ lanza: e })).manejar(req('GET', '/api/productos', 'ADM'));
  assert.strictEqual(r2.status, 504);
  assert.strictEqual(r2.cuerpo.codigo, 'TIEMPO_AGOTADO');
});

test('errores del microservicio se devuelven tal cual', async () => {
  const cuerpo = { codigo: 'RECURSO_NO_ENCONTRADO', mensaje: 'x', detalles: [], correlation_id: 'abc' };
  const r = await crearGateway(config, fakeFetch({ status: 404, cuerpo })).manejar(req('GET', '/api/productos/99', 'ADM'));
  assert.strictEqual(r.status, 404);
  assert.deepStrictEqual(r.cuerpo, cuerpo);
});

test('/api/health requiere token y agrega estado de servicios', async () => {
  const gw = crearGateway(config, fakeFetch());
  assert.strictEqual((await gw.manejar({ metodo: 'GET', ruta: '/api/health', headers: {} })).status, 401);
  const r = await gw.manejar(req('GET', '/api/health', 'CON'));
  assert.strictEqual(r.status, 200);
  assert.strictEqual(Object.keys(r.cuerpo.servicios).length, 7);
});

test('se respeta X-Correlation-ID valido del cliente', async () => {
  const r = await crearGateway(config, fakeFetch()).manejar({ metodo: 'GET', ruta: '/health', headers: { 'x-correlation-id': 'abc-12345678' } });
  assert.strictEqual(r.headers['X-Correlation-ID'], 'abc-12345678');
});
