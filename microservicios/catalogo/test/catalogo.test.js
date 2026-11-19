const test = require('node:test');
const assert = require('node:assert');
const { crearManejador } = require('../src/manejador');

// Repositorio en memoria con la misma interfaz que repositorio.js (sin MySQL)
function repoMemoria() {
  const t = { prod: [], cat: [], pid: 1, cid: 1 };
  const pag = (arr, f) => ({ filas: arr.slice((f.page - 1) * f.limit, f.page * f.limit), total: arr.length });
  return {
    productos: {
      async listar(f) {
        let r = t.prod;
        if (f.nombre) r = r.filter((p) => p.nombre_producto.toLowerCase().includes(f.nombre.toLowerCase()));
        if (f.codigo) r = r.filter((p) => p.codigo_producto === f.codigo);
        if (f.categoria_id) r = r.filter((p) => p.categoria_id === f.categoria_id);
        if (f.proveedor_id) r = r.filter((p) => p.proveedor_principal_id === f.proveedor_id);
        if (f.producto_activo !== undefined) r = r.filter((p) => p.producto_activo === f.producto_activo);
        return pag(r, f);
      },
      async obtener(id) { return t.prod.find((p) => p.id === id) || null; },
      async obtenerPorCodigo(c) { return t.prod.find((p) => p.codigo_producto === c) || null; },
      async insertar(d) { const p = { id: t.pid++, descripcion_producto: null, proveedor_principal_id: null, producto_activo: true, ...d }; t.prod.push(p); return p.id; },
      async actualizar(id, d) { Object.assign(t.prod.find((p) => p.id === id), d); },
    },
    categorias: {
      async listar(f) {
        let r = t.cat;
        if (f.categoria_padre_id) r = r.filter((c) => c.categoria_padre_id === f.categoria_padre_id);
        if (f.categoria_activa !== undefined) r = r.filter((c) => c.categoria_activa === f.categoria_activa);
        return pag(r, f);
      },
      async obtener(id) { return t.cat.find((c) => c.id === id) || null; },
      async insertar(d) { const c = { id: t.cid++, descripcion: null, categoria_padre_id: null, categoria_activa: true, ...d }; t.cat.push(c); return c.id; },
      async actualizar(id, d) { Object.assign(t.cat.find((c) => c.id === id), d); },
    },
  };
}

const config = { tokenInterno: 'tok-interno' };
const silencio = { error() {} };
function nuevo() {
  const h = crearManejador(config, repoMemoria(), silencio);
  const llamar = (metodo, ruta, { cuerpo, consulta = {}, rol = 'ADM', token = 'tok-interno' } = {}) => h.manejar({
    metodo, ruta, consulta, cuerpo,
    headers: { ...(token ? { 'x-internal-token': token } : {}), ...(rol ? { 'x-user-role': rol } : {}) },
  });
  return llamar;
}
const prod = (extra = {}) => ({ codigo_producto: 'DEP001', nombre_producto: 'Balon de baloncesto', categoria_id: 1, unidad_medida: 'unidad', precio_venta: 120000, ...extra });

async function conCategoria(llamar) { await llamar('POST', '/api/categorias', { cuerpo: { nombre: 'Balones' } }); }

test('/health es publico', async () => {
  const r = await nuevo()('GET', '/health', { token: null, rol: null });
  assert.strictEqual(r.status, 200); assert.strictEqual(r.cuerpo.estado, 'UP');
});

test('sin credencial interna o con credencial incorrecta -> 401', async () => {
  const ll = nuevo();
  assert.strictEqual((await ll('GET', '/api/productos', { token: null })).status, 401);
  assert.strictEqual((await ll('GET', '/api/productos', { token: 'otra' })).status, 401);
});

test('escritura sin rol ADM/INV -> 403; lectura con cualquier rol -> 200', async () => {
  const ll = nuevo();
  assert.strictEqual((await ll('POST', '/api/categorias', { cuerpo: { nombre: 'X' }, rol: 'CON' })).status, 403);
  assert.strictEqual((await ll('POST', '/api/categorias', { cuerpo: { nombre: 'X' }, rol: null })).status, 403);
  assert.strictEqual((await ll('GET', '/api/categorias', { rol: 'CON' })).status, 200);
});

test('crear producto -> 201 con mensaje y producto activo', async () => {
  const ll = nuevo(); await conCategoria(ll);
  const r = await ll('POST', '/api/productos', { cuerpo: prod() });
  assert.strictEqual(r.status, 201);
  assert.strictEqual(r.cuerpo.mensaje, 'Producto registrado correctamente');
  assert.strictEqual(r.cuerpo.producto.producto_activo, true);
  assert.ok(r.headers['X-Correlation-ID']);
});

test('producto: faltan campos o tipos incorrectos -> 400 con detalles', async () => {
  const ll = nuevo(); await conCategoria(ll);
  const r = await ll('POST', '/api/productos', { cuerpo: { nombre_producto: 5 } });
  assert.strictEqual(r.status, 400);
  assert.strictEqual(r.cuerpo.codigo, 'PETICION_INVALIDA');
  const campos = r.cuerpo.detalles.map((d) => d.campo);
  for (const c of ['codigo_producto', 'nombre_producto', 'categoria_id', 'unidad_medida', 'precio_venta']) assert.ok(campos.includes(c), c);
  assert.strictEqual((await ll('POST', '/api/productos', { cuerpo: 'texto' })).status, 400);
});

test('producto: codigo duplicado -> 409', async () => {
  const ll = nuevo(); await conCategoria(ll);
  await ll('POST', '/api/productos', { cuerpo: prod() });
  const r = await ll('POST', '/api/productos', { cuerpo: prod({ nombre_producto: 'Otro' }) });
  assert.strictEqual(r.status, 409); assert.strictEqual(r.cuerpo.codigo, 'CODIGO_DUPLICADO');
});

test('producto: categoria inexistente, inactiva o precio negativo -> 422', async () => {
  const ll = nuevo(); await conCategoria(ll);
  assert.strictEqual((await ll('POST', '/api/productos', { cuerpo: prod({ categoria_id: 99 }) })).status, 422);
  await ll('PATCH', '/api/categorias/1/estado', { cuerpo: { categoria_activa: false } });
  assert.strictEqual((await ll('POST', '/api/productos', { cuerpo: prod() })).status, 422);
  await ll('PATCH', '/api/categorias/1/estado', { cuerpo: { categoria_activa: true } });
  const r = await ll('POST', '/api/productos', { cuerpo: prod({ precio_venta: -1 }) });
  assert.strictEqual(r.status, 422); assert.strictEqual(r.cuerpo.codigo, 'PRECIO_INVALIDO');
  assert.strictEqual((await ll('POST', '/api/productos', { cuerpo: prod({ precio_venta: 0 }) })).status, 201);
});

test('consultar producto: 200, 404 y id invalido 400', async () => {
  const ll = nuevo(); await conCategoria(ll);
  await ll('POST', '/api/productos', { cuerpo: prod() });
  assert.strictEqual((await ll('GET', '/api/productos/1')).cuerpo.codigo_producto, 'DEP001');
  assert.strictEqual((await ll('GET', '/api/productos/99')).status, 404);
  assert.strictEqual((await ll('GET', '/api/productos/abc')).status, 400);
});

test('busqueda: combina filtros nombre, codigo, categoria, proveedor y estado', async () => {
  const ll = nuevo(); await conCategoria(ll);
  await ll('POST', '/api/categorias', { cuerpo: { nombre: 'Futbol', categoria_padre_id: 1 } });
  await ll('POST', '/api/productos', { cuerpo: prod() });
  await ll('POST', '/api/productos', { cuerpo: prod({ codigo_producto: 'FUT001', nombre_producto: 'Balon de futbol', categoria_id: 2, proveedor_principal_id: 7 }) });
  const n = async (consulta) => (await ll('GET', '/api/productos', { consulta })).cuerpo.total;
  assert.strictEqual(await n({}), 2);
  assert.strictEqual(await n({ nombre: 'FUTBOL' }), 1);
  assert.strictEqual(await n({ codigo: 'DEP001' }), 1);
  assert.strictEqual(await n({ categoria_id: '2' }), 1);
  assert.strictEqual(await n({ proveedor_id: '7' }), 1);
  assert.strictEqual(await n({ nombre: 'balon', categoria_id: '1' }), 1);
  await ll('PATCH', '/api/productos/1/estado', { cuerpo: { producto_activo: false } });
  assert.strictEqual(await n({ producto_activo: 'true' }), 1);
  assert.strictEqual(await n({ producto_activo: 'false' }), 1);
});

test('paginacion y filtros invalidos -> 400', async () => {
  const ll = nuevo(); await conCategoria(ll);
  for (let i = 1; i <= 3; i++) await ll('POST', '/api/productos', { cuerpo: prod({ codigo_producto: `C${i}` }) });
  const r = await ll('GET', '/api/productos', { consulta: { page: '2', limit: '2' } });
  assert.strictEqual(r.cuerpo.datos.length, 1); assert.strictEqual(r.cuerpo.total, 3); assert.strictEqual(r.cuerpo.pagina, 2);
  for (const q of [{ page: '0' }, { limit: '101' }, { producto_activo: 'si' }, { categoria_id: 'x' }, { page: ['1', '2'] }]) {
    assert.strictEqual((await ll('GET', '/api/productos', { consulta: q })).status, 400, JSON.stringify(q));
  }
});

test('actualizar producto: parcial, 404, codigo repetido 409, sin campos 400', async () => {
  const ll = nuevo(); await conCategoria(ll);
  await ll('POST', '/api/productos', { cuerpo: prod() });
  await ll('POST', '/api/productos', { cuerpo: prod({ codigo_producto: 'B2' }) });
  const ok = await ll('PUT', '/api/productos/1', { cuerpo: { precio_venta: 99000, nombre_producto: 'Nuevo' } });
  assert.strictEqual(ok.status, 200); assert.strictEqual(ok.cuerpo.producto.precio_venta, 99000); assert.strictEqual(ok.cuerpo.producto.codigo_producto, 'DEP001');
  assert.strictEqual((await ll('PUT', '/api/productos/1', { cuerpo: { codigo_producto: 'DEP001' } })).status, 200);   // mismo codigo propio: permitido
  assert.strictEqual((await ll('PUT', '/api/productos/1', { cuerpo: { codigo_producto: 'B2' } })).status, 409);
  assert.strictEqual((await ll('PUT', '/api/productos/99', { cuerpo: { precio_venta: 1 } })).status, 404);
  assert.strictEqual((await ll('PUT', '/api/productos/1', { cuerpo: {} })).status, 400);
  assert.strictEqual((await ll('PUT', '/api/productos/1', { cuerpo: { precio_venta: -5 } })).status, 422);
});

test('activar/desactivar producto', async () => {
  const ll = nuevo(); await conCategoria(ll);
  await ll('POST', '/api/productos', { cuerpo: prod() });
  const r = await ll('PATCH', '/api/productos/1/estado', { cuerpo: { producto_activo: false } });
  assert.strictEqual(r.status, 200); assert.strictEqual(r.cuerpo.producto.producto_activo, false);
  assert.strictEqual((await ll('PATCH', '/api/productos/1/estado', { cuerpo: { producto_activo: 'no' } })).status, 400);
  assert.strictEqual((await ll('PATCH', '/api/productos/9/estado', { cuerpo: { producto_activo: true } })).status, 404);
});

test('categorias: jerarquia, padre inexistente 422, ciclo 422, propio padre 422', async () => {
  const ll = nuevo();
  assert.strictEqual((await ll('POST', '/api/categorias', { cuerpo: { nombre: 'Balones' } })).status, 201);
  assert.strictEqual((await ll('POST', '/api/categorias', { cuerpo: { nombre: 'Futbol', categoria_padre_id: 1 } })).status, 201);
  assert.strictEqual((await ll('POST', '/api/categorias', { cuerpo: { nombre: 'Sala', categoria_padre_id: 2 } })).status, 201);
  assert.strictEqual((await ll('POST', '/api/categorias', { cuerpo: { nombre: 'X', categoria_padre_id: 99 } })).status, 422);
  assert.strictEqual((await ll('POST', '/api/categorias', { cuerpo: {} })).status, 400);
  assert.strictEqual((await ll('PUT', '/api/categorias/1', { cuerpo: { categoria_padre_id: 1 } })).status, 422);
  assert.strictEqual((await ll('PUT', '/api/categorias/1', { cuerpo: { categoria_padre_id: 3 } })).status, 422);   // ciclo 1->3->2->1
  assert.strictEqual((await ll('PUT', '/api/categorias/3', { cuerpo: { nombre: 'Futsal' } })).status, 200);
  assert.strictEqual((await ll('GET', '/api/categorias', { consulta: { categoria_padre_id: '1' } })).cuerpo.total, 1);
  assert.strictEqual((await ll('GET', '/api/categorias/99')).status, 404);
  assert.strictEqual((await ll('PATCH', '/api/categorias/2/estado', { cuerpo: { categoria_activa: 1 } })).status, 400);
});

test('rutas inexistentes 404 y metodo incorrecto 405', async () => {
  const ll = nuevo();
  assert.strictEqual((await ll('GET', '/api/nada')).status, 404);
  assert.strictEqual((await ll('DELETE', '/api/productos/1')).status, 405);
});

test('error inesperado del repositorio -> 500 con formato estandar', async () => {
  const repo = repoMemoria(); repo.productos.listar = async () => { throw new Error('bd caida'); };
  const h = crearManejador(config, repo, silencio);
  const r = await h.manejar({ metodo: 'GET', ruta: '/api/productos', consulta: {}, headers: { 'x-internal-token': 'tok-interno' } });
  assert.strictEqual(r.status, 500); assert.strictEqual(r.cuerpo.codigo, 'ERROR_INTERNO');
});

test('duplicado detectado por MySQL (carrera) -> 409', async () => {
  const repo = repoMemoria(); await repo.categorias.insertar({ nombre: 'B' });
  repo.productos.insertar = async () => { const e = new Error('dup'); e.code = 'ER_DUP_ENTRY'; throw e; };
  const h = crearManejador(config, repo, silencio);
  const r = await h.manejar({ metodo: 'POST', ruta: '/api/productos', consulta: {}, cuerpo: prod(), headers: { 'x-internal-token': 'tok-interno', 'x-user-role': 'ADM' } });
  assert.strictEqual(r.status, 409);
});
