const test = require('node:test');
const assert = require('node:assert');
const { nuevo, uuid, entrada, salida } = require('./ayudas');

const saldo = (repo, p, b) => (repo.estado.saldos.find((s) => s.producto_id === p && s.bodega_id === b) || {}).cantidad_disponible;

test('/health publico; sin credencial interna -> 401', async () => {
  const { llamar } = nuevo();
  assert.strictEqual((await llamar('GET', '/health', { token: null, rol: null })).status, 200);
  assert.strictEqual((await llamar('GET', '/api/inventario/existencias', { token: null })).status, 401);
  assert.strictEqual((await llamar('GET', '/api/inventario/existencias', { token: 'otro' })).status, 401);
});

test('permisos por rol y llamadas internas', async () => {
  const { llamar } = nuevo();
  assert.strictEqual((await llamar('POST', '/api/inventario/salidas', { cuerpo: salida(), rol: 'CON' })).status, 403);
  assert.strictEqual((await llamar('POST', '/api/inventario/ajustes', { cuerpo: {}, rol: 'BOD' })).status, 403);
  assert.strictEqual((await llamar('POST', '/api/inventario/ajustes', { cuerpo: {}, rol: null })).status, 403);     // interno no puede ajustar
  assert.strictEqual((await llamar('POST', '/api/inventario/traslados', { cuerpo: {}, rol: null })).status, 403);
  assert.strictEqual((await llamar('PUT', '/api/inventario/minimos/1/2', { cuerpo: { stock_minimo: 1 }, rol: 'BOD' })).status, 403);
  assert.strictEqual((await llamar('GET', '/api/inventario/existencias', { rol: 'CON' })).status, 200);
});

test('entrada: 201, actualiza el saldo y guarda el usuario del Gateway', async () => {
  const { llamar, repo } = nuevo();
  const r = await llamar('POST', '/api/inventario/entradas', { cuerpo: entrada(), usuario: '7' });
  assert.strictEqual(r.status, 201);
  assert.strictEqual(r.cuerpo.mensaje, 'Movimiento registrado correctamente');
  assert.strictEqual(r.cuerpo.movimiento.tipo_movimiento, 'ENTRADA');
  assert.strictEqual(r.cuerpo.movimiento.saldo_resultante, 20);
  assert.strictEqual(r.cuerpo.movimiento.usuario_id, 7);
  assert.strictEqual(saldo(repo, 1, 2), 20);
  const r2 = await llamar('POST', '/api/inventario/entradas', { cuerpo: entrada({ cantidad_movimiento: 30 }) });
  assert.strictEqual(r2.cuerpo.movimiento.saldo_resultante, 50);
});

test('un campo usuario_id enviado en el JSON no sustituye la identidad del Gateway', async () => {
  const { llamar } = nuevo();
  const r = await llamar('POST', '/api/inventario/entradas', { cuerpo: entrada({ usuario_id: 999 }), usuario: '4' });
  assert.strictEqual(r.cuerpo.movimiento.usuario_id, 4);
});

test('salida: descuenta; stock insuficiente -> 409 sin efectos', async () => {
  const { llamar, repo } = nuevo();
  await llamar('POST', '/api/inventario/entradas', { cuerpo: entrada({ cantidad_movimiento: 5 }) });
  const ok = await llamar('POST', '/api/inventario/salidas', { cuerpo: salida({ cantidad_movimiento: 2 }) });
  assert.strictEqual(ok.status, 201); assert.strictEqual(ok.cuerpo.movimiento.saldo_resultante, 3);
  const mal = await llamar('POST', '/api/inventario/salidas', { cuerpo: salida({ cantidad_movimiento: 10 }) });
  assert.strictEqual(mal.status, 409);
  assert.strictEqual(mal.cuerpo.codigo, 'STOCK_INSUFICIENTE');
  assert.strictEqual(mal.cuerpo.detalles[0].error, 'Solicitadas 10, disponibles 3');
  assert.strictEqual(saldo(repo, 1, 2), 3);
  assert.strictEqual(repo.estado.movs.length, 2);
});

test('origen COMPRA/DEVOLUCION: usuario -> 403; servicio interno -> 201 (sin rol)', async () => {
  const { llamar } = nuevo();
  const u = await llamar('POST', '/api/inventario/entradas', { cuerpo: entrada({ origen_movimiento: 'COMPRA', documento_ref: 'OC-0015' }) });
  assert.strictEqual(u.status, 403); assert.strictEqual(u.cuerpo.codigo, 'ORIGEN_NO_PERMITIDO');
  const i = await llamar('POST', '/api/inventario/entradas', { cuerpo: entrada({ origen_movimiento: 'COMPRA', documento_ref: 'OC-0015' }), rol: null });
  assert.strictEqual(i.status, 201); assert.strictEqual(i.cuerpo.movimiento.origen_movimiento, 'COMPRA'); assert.strictEqual(i.cuerpo.movimiento.usuario_id, null);
});

test('idempotencia: misma operacion -> 200 sin tocar saldos; datos distintos -> 409', async () => {
  const { llamar, repo, clientes } = nuevo();
  const cuerpo = entrada();
  assert.strictEqual((await llamar('POST', '/api/inventario/entradas', { cuerpo })).status, 201);
  const rep = await llamar('POST', '/api/inventario/entradas', { cuerpo });
  assert.strictEqual(rep.status, 200); assert.strictEqual(rep.cuerpo.movimiento.cantidad_movimiento, 20);
  assert.strictEqual(saldo(repo, 1, 2), 20); assert.strictEqual(repo.estado.movs.length, 1);
  clientes.caido = true;   // el reintento responde aunque Catalogo no este disponible
  assert.strictEqual((await llamar('POST', '/api/inventario/entradas', { cuerpo })).status, 200);
  const otra = await llamar('POST', '/api/inventario/entradas', { cuerpo: { ...cuerpo, cantidad_movimiento: 99 } });
  assert.strictEqual(otra.status, 409); assert.strictEqual(otra.cuerpo.codigo, 'OPERACION_DUPLICADA');
  assert.strictEqual(saldo(repo, 1, 2), 20);
});

test('validaciones: 400 por formato y 422 por reglas de negocio', async () => {
  const { llamar } = nuevo();
  const casos = [
    [{}, 400], [entrada({ operacion_id: 'abc' }), 400], [entrada({ cantidad_movimiento: '5' }), 400],
    [entrada({ origen_movimiento: 'OTRO' }), 400], [entrada({ bodega_destino_id: undefined }), 400], [entrada({ producto_id: 1.5 }), 400],
    [entrada({ cantidad_movimiento: 0 }), 422], [entrada({ cantidad_movimiento: -3 }), 422],
    [entrada({ producto_id: 99 }), 422], [entrada({ bodega_destino_id: 99 }), 422],
  ];
  for (const [cuerpo, esperado] of casos) assert.strictEqual((await llamar('POST', '/api/inventario/entradas', { cuerpo })).status, esperado, JSON.stringify(cuerpo));
  assert.strictEqual((await llamar('POST', '/api/inventario/entradas', { cuerpo: 'texto' })).status, 400);
  const r = await llamar('POST', '/api/inventario/entradas', { cuerpo: entrada({ producto_id: 99 }) });
  assert.strictEqual(r.cuerpo.codigo, 'PRODUCTO_INEXISTENTE');
});

test('Catalogo no disponible -> 503 y no se registra nada', async () => {
  const { llamar, repo, clientes } = nuevo(); clientes.caido = true;
  const r = await llamar('POST', '/api/inventario/entradas', { cuerpo: entrada() });
  assert.strictEqual(r.status, 503); assert.strictEqual(r.cuerpo.codigo, 'SERVICIO_NO_DISPONIBLE');
  assert.strictEqual(repo.estado.movs.length, 0);
});

test('ajustes: positivo, negativo, motivo obligatorio y sentido', async () => {
  const { llamar, repo } = nuevo();
  const ajuste = (extra) => ({ operacion_id: uuid(), producto_id: 1, sentido_ajuste: 'POSITIVO', bodega_destino_id: 2, cantidad_movimiento: 10, motivo_movimiento: 'Conteo fisico', ...extra });
  const pos = await llamar('POST', '/api/inventario/ajustes', { cuerpo: ajuste() });
  assert.strictEqual(pos.status, 201); assert.strictEqual(pos.cuerpo.mensaje, 'Ajuste registrado correctamente');
  assert.strictEqual(pos.cuerpo.movimiento.tipo_movimiento, 'AJUSTE'); assert.strictEqual(saldo(repo, 1, 2), 10);
  const neg = await llamar('POST', '/api/inventario/ajustes', { cuerpo: ajuste({ sentido_ajuste: 'NEGATIVO', bodega_destino_id: undefined, bodega_origen_id: 2, cantidad_movimiento: 4, motivo_movimiento: 'Merma' }) });
  assert.strictEqual(neg.status, 201); assert.strictEqual(saldo(repo, 1, 2), 6);
  const demasiado = await llamar('POST', '/api/inventario/ajustes', { cuerpo: ajuste({ sentido_ajuste: 'NEGATIVO', bodega_destino_id: undefined, bodega_origen_id: 2, cantidad_movimiento: 50 }) });
  assert.strictEqual(demasiado.status, 409);
  assert.strictEqual((await llamar('POST', '/api/inventario/ajustes', { cuerpo: ajuste({ motivo_movimiento: undefined }) })).status, 422);
  assert.strictEqual((await llamar('POST', '/api/inventario/ajustes', { cuerpo: ajuste({ bodega_origen_id: 3 }) })).status, 422);   // POSITIVO con bodega de origen
  assert.strictEqual((await llamar('POST', '/api/inventario/ajustes', { cuerpo: ajuste({ sentido_ajuste: 'X' }) })).status, 400);
  assert.strictEqual((await llamar('POST', '/api/inventario/ajustes', { cuerpo: ajuste({ bodega_destino_id: undefined }) })).status, 400);
});

test('traslado: mueve entre bodegas, un solo movimiento y saldos de ambas', async () => {
  const { llamar, repo } = nuevo();
  await llamar('POST', '/api/inventario/entradas', { cuerpo: entrada({ cantidad_movimiento: 50 }) });
  const t = { operacion_id: uuid(), producto_id: 1, bodega_origen_id: 2, bodega_destino_id: 3, cantidad_movimiento: 5, motivo_movimiento: 'Reubicacion' };
  const r = await llamar('POST', '/api/inventario/traslados', { cuerpo: t, rol: 'BOD' });
  assert.strictEqual(r.status, 201); assert.strictEqual(r.cuerpo.movimiento.tipo_movimiento, 'TRASLADO');
  assert.strictEqual(r.cuerpo.movimiento.saldo_resultante, 45); assert.strictEqual(r.cuerpo.movimiento.origen_movimiento, 'MANUAL');
  assert.deepStrictEqual(r.cuerpo.saldos, { origen: { bodega_id: 2, cantidad_disponible: 45 }, destino: { bodega_id: 3, cantidad_disponible: 5 } });
  assert.strictEqual(repo.estado.movs.length, 2);
  assert.strictEqual((await llamar('POST', '/api/inventario/traslados', { cuerpo: t })).status, 200);   // repeticion idempotente
  assert.strictEqual(saldo(repo, 1, 3), 5);
});

test('traslado: sin stock 409, bodegas iguales 422, inexistente 422; sin efectos parciales', async () => {
  const { llamar, repo } = nuevo();
  await llamar('POST', '/api/inventario/entradas', { cuerpo: entrada({ cantidad_movimiento: 3 }) });
  const base = { producto_id: 1, bodega_origen_id: 2, bodega_destino_id: 3, cantidad_movimiento: 5 };
  assert.strictEqual((await llamar('POST', '/api/inventario/traslados', { cuerpo: { operacion_id: uuid(), ...base } })).status, 409);
  assert.strictEqual((await llamar('POST', '/api/inventario/traslados', { cuerpo: { operacion_id: uuid(), ...base, bodega_destino_id: 2 } })).status, 422);
  assert.strictEqual((await llamar('POST', '/api/inventario/traslados', { cuerpo: { operacion_id: uuid(), ...base, bodega_destino_id: 99 } })).status, 422);
  assert.strictEqual(saldo(repo, 1, 2), 3); assert.strictEqual(saldo(repo, 1, 3), undefined);
});

test('atomicidad: si falla el registro del movimiento, el saldo se revierte', async () => {
  const { llamar, repo } = nuevo();
  await llamar('POST', '/api/inventario/entradas', { cuerpo: entrada({ cantidad_movimiento: 10 }) });
  repo.falloAlInsertar = true;
  const r = await llamar('POST', '/api/inventario/salidas', { cuerpo: salida({ cantidad_movimiento: 4 }) });
  assert.strictEqual(r.status, 500);
  assert.strictEqual(saldo(repo, 1, 2), 10); assert.strictEqual(repo.estado.movs.length, 1);
});

test('concurrencia: 5 salidas simultaneas de 1 unidad con 3 en stock -> 3 exitosas y 2 con 409', async () => {
  const { llamar, repo } = nuevo();
  await llamar('POST', '/api/inventario/entradas', { cuerpo: entrada({ cantidad_movimiento: 3 }) });
  const r = await Promise.all(Array.from({ length: 5 }, () => llamar('POST', '/api/inventario/salidas', { cuerpo: salida({ cantidad_movimiento: 1 }) })));
  assert.strictEqual(r.filter((x) => x.status === 201).length, 3);
  assert.strictEqual(r.filter((x) => x.status === 409).length, 2);
  assert.strictEqual(saldo(repo, 1, 2), 0);
});
