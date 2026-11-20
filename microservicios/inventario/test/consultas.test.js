const test = require('node:test');
const assert = require('node:assert');
const { nuevo, uuid, entrada, salida } = require('./ayudas');

async function preparar() {
  const t = nuevo();
  await t.llamar('POST', '/api/inventario/entradas', { cuerpo: entrada({ producto_id: 1, bodega_destino_id: 2, cantidad_movimiento: 10 }), usuario: '3' });
  await t.llamar('POST', '/api/inventario/entradas', { cuerpo: entrada({ producto_id: 1, bodega_destino_id: 3, cantidad_movimiento: 4 }), usuario: '5' });
  await t.llamar('POST', '/api/inventario/entradas', { cuerpo: entrada({ producto_id: 2, bodega_destino_id: 2, cantidad_movimiento: 7 }), usuario: '3' });
  await t.llamar('POST', '/api/inventario/salidas', { cuerpo: salida({ producto_id: 1, bodega_origen_id: 2, cantidad_movimiento: 1 }), usuario: '3' });
  return t;
}

test('existencias: filtros por producto y bodega, paginacion {items,total,page,limit}', async () => {
  const { llamar } = await preparar();
  const todo = await llamar('GET', '/api/inventario/existencias');
  assert.deepStrictEqual([todo.cuerpo.total, todo.cuerpo.page, todo.cuerpo.limit], [3, 1, 20]);
  assert.strictEqual((await llamar('GET', '/api/inventario/existencias', { consulta: { producto_id: '1' } })).cuerpo.total, 2);
  assert.strictEqual((await llamar('GET', '/api/inventario/existencias', { consulta: { bodega_id: '3' } })).cuerpo.items[0].cantidad_disponible, 4);
  const p = await llamar('GET', '/api/inventario/existencias', { consulta: { page: '2', limit: '2' } });
  assert.strictEqual(p.cuerpo.items.length, 1);
  for (const q of [{ page: '0' }, { limit: '101' }, { bajo_minimo: 'si' }, { producto_id: 'x' }]) {
    assert.strictEqual((await llamar('GET', '/api/inventario/existencias', { consulta: q })).status, 400, JSON.stringify(q));
  }
});

test('existencias de un producto: total y desglose; 404 si no existe', async () => {
  const { llamar } = await preparar();
  const r = await llamar('GET', '/api/inventario/existencias/1');
  assert.strictEqual(r.status, 200); assert.strictEqual(r.cuerpo.total, 13);
  assert.deepStrictEqual(r.cuerpo.bodegas.map((b) => [b.bodega_id, b.cantidad_disponible]), [[2, 9], [3, 4]]);
  assert.strictEqual((await llamar('GET', '/api/inventario/existencias/99')).status, 404);
  assert.strictEqual((await llamar('GET', '/api/inventario/existencias/abc')).status, 400);
});

test('kardex: filtros, orden mas reciente primero, consulta por id', async () => {
  const { llamar } = await preparar();
  const todos = await llamar('GET', '/api/inventario/movimientos');
  assert.strictEqual(todos.cuerpo.total, 4); assert.strictEqual(todos.cuerpo.items[0].tipo_movimiento, 'SALIDA');
  const f = async (consulta) => (await llamar('GET', '/api/inventario/movimientos', { consulta })).cuerpo.total;
  assert.strictEqual(await f({ tipo_movimiento: 'ENTRADA' }), 3);
  assert.strictEqual(await f({ producto_id: '2' }), 1);
  assert.strictEqual(await f({ bodega_id: '2' }), 3);
  assert.strictEqual(await f({ usuario_id: '5' }), 1);
  assert.strictEqual(await f({ origen_movimiento: 'COMPRA' }), 0);
  assert.strictEqual(await f({ desde: '2000-01-01', hasta: '2999-12-31' }), 4);
  assert.strictEqual(await f({ desde: '2999-01-01' }), 0);
  for (const q of [{ tipo_movimiento: 'X' }, { desde: 'ayer' }, { usuario_id: '0' }]) assert.strictEqual((await llamar('GET', '/api/inventario/movimientos', { consulta: q })).status, 400, JSON.stringify(q));
  const uno = await llamar('GET', '/api/inventario/movimientos/1');
  assert.strictEqual(uno.status, 200); assert.strictEqual(uno.cuerpo.id, 1);
  assert.strictEqual((await llamar('GET', '/api/inventario/movimientos/999')).status, 404);
});

test('stock minimo: GET sin saldo = 0; PUT crea el saldo; validaciones y 404', async () => {
  const { llamar, repo } = nuevo();
  const vacio = await llamar('GET', '/api/inventario/minimos/1/2');
  assert.deepStrictEqual(vacio.cuerpo, { producto_id: 1, bodega_id: 2, stock_minimo: 0, cantidad_disponible: 0 });
  const r = await llamar('PUT', '/api/inventario/minimos/1/2', { cuerpo: { stock_minimo: 5 } });
  assert.strictEqual(r.status, 200); assert.strictEqual(r.cuerpo.minimo.stock_minimo, 5);
  assert.strictEqual(repo.estado.saldos.length, 1);
  assert.strictEqual((await llamar('GET', '/api/inventario/minimos/1/2')).cuerpo.stock_minimo, 5);
  for (const c of [{}, { stock_minimo: -1 }, { stock_minimo: '5' }, { stock_minimo: 1.5 }]) assert.strictEqual((await llamar('PUT', '/api/inventario/minimos/1/2', { cuerpo: c })).status, 400, JSON.stringify(c));
  assert.strictEqual((await llamar('PUT', '/api/inventario/minimos/99/2', { cuerpo: { stock_minimo: 1 } })).status, 404);
  assert.strictEqual((await llamar('GET', '/api/inventario/minimos/1/99')).status, 404);
});

test('bajo_minimo: lista solo los saldos por debajo de su umbral', async () => {
  const { llamar } = await preparar();
  await llamar('PUT', '/api/inventario/minimos/1/2', { cuerpo: { stock_minimo: 20 } });
  const r = await llamar('GET', '/api/inventario/existencias', { consulta: { bajo_minimo: 'true' } });
  assert.deepStrictEqual(r.cuerpo.items.map((s) => [s.producto_id, s.bodega_id]), [[1, 2]]);
  assert.strictEqual((await llamar('GET', '/api/inventario/existencias', { consulta: { bajo_minimo: 'false' } })).cuerpo.total, 2);
});

test('avisos: solo al cruzar el minimo (STOCK_BAJO una vez, STOCK_RECUPERADO al volver)', async () => {
  const { llamar, clientes, esperar } = nuevo();
  await llamar('POST', '/api/inventario/entradas', { cuerpo: entrada({ cantidad_movimiento: 10 }) });
  await llamar('PUT', '/api/inventario/minimos/1/2', { cuerpo: { stock_minimo: 5 } });
  await esperar(); assert.strictEqual(clientes.avisos.length, 0);                       // 10 >= 5: sin aviso
  await llamar('POST', '/api/inventario/salidas', { cuerpo: salida({ cantidad_movimiento: 4 }) });   // 6: sigue sobre el minimo
  await esperar(); assert.strictEqual(clientes.avisos.length, 0);
  await llamar('POST', '/api/inventario/salidas', { cuerpo: salida({ cantidad_movimiento: 2 }) });   // 4 < 5: cruza hacia abajo
  await esperar();
  assert.deepStrictEqual(clientes.avisos, [{ evento: 'STOCK_BAJO', producto_id: 1, bodega_id: 2, cantidad_disponible: 4, stock_minimo: 5 }]);
  await llamar('POST', '/api/inventario/salidas', { cuerpo: salida({ cantidad_movimiento: 1 }) });   // 3: ya estaba bajo, no repite
  await esperar(); assert.strictEqual(clientes.avisos.length, 1);
  await llamar('POST', '/api/inventario/entradas', { cuerpo: entrada({ cantidad_movimiento: 10 }) }); // 13 >= 5: recuperado
  await esperar();
  assert.strictEqual(clientes.avisos.length, 2);
  assert.deepStrictEqual(clientes.avisos[1], { evento: 'STOCK_RECUPERADO', producto_id: 1, bodega_id: 2, cantidad_disponible: 13, stock_minimo: 5 });
});

test('avisos: configurar un minimo que cambia la condicion tambien avisa', async () => {
  const { llamar, clientes, esperar } = nuevo();
  await llamar('POST', '/api/inventario/entradas', { cuerpo: entrada({ cantidad_movimiento: 10 }) });
  await llamar('PUT', '/api/inventario/minimos/1/2', { cuerpo: { stock_minimo: 15 } });   // 10 < 15
  await esperar(); assert.strictEqual(clientes.avisos[0].evento, 'STOCK_BAJO');
  await llamar('PUT', '/api/inventario/minimos/1/2', { cuerpo: { stock_minimo: 8 } });    // 10 >= 8
  await esperar(); assert.strictEqual(clientes.avisos[1].evento, 'STOCK_RECUPERADO');
});

test('si el aviso a Reportes falla, el movimiento NO se revierte', async () => {
  const { llamar, repo, clientes, esperar } = nuevo();
  await llamar('POST', '/api/inventario/entradas', { cuerpo: entrada({ cantidad_movimiento: 10 }) });
  await llamar('PUT', '/api/inventario/minimos/1/2', { cuerpo: { stock_minimo: 5 } });
  clientes.falloAviso = true;
  const r = await llamar('POST', '/api/inventario/salidas', { cuerpo: salida({ cantidad_movimiento: 8 }) });
  await esperar();
  assert.strictEqual(r.status, 201);
  assert.strictEqual(repo.estado.saldos[0].cantidad_disponible, 2);
});

test('traslado que cruza el minimo en el origen avisa del origen', async () => {
  const { llamar, clientes, esperar } = nuevo();
  await llamar('POST', '/api/inventario/entradas', { cuerpo: entrada({ cantidad_movimiento: 10 }) });
  await llamar('PUT', '/api/inventario/minimos/1/2', { cuerpo: { stock_minimo: 6 } });
  await llamar('POST', '/api/inventario/traslados', { cuerpo: { operacion_id: uuid(), producto_id: 1, bodega_origen_id: 2, bodega_destino_id: 3, cantidad_movimiento: 6 } });
  await esperar();
  assert.deepStrictEqual(clientes.avisos.map((a) => [a.evento, a.bodega_id]), [['STOCK_BAJO', 2]]);
});

test('rutas inexistentes 404 y metodo incorrecto 405', async () => {
  const { llamar } = nuevo();
  assert.strictEqual((await llamar('GET', '/api/nada')).status, 404);
  assert.strictEqual((await llamar('DELETE', '/api/inventario/movimientos/1')).status, 405);
});
