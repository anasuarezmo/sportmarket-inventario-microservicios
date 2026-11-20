const test = require('node:test');
const assert = require('node:assert');
const { crearRepositorio } = require('../src/repositorio');

// Pool falso: registra el SQL y los parametros (sin MySQL)
function poolFalso(respuestas = {}) {
  const llamadas = []; const eventos = [];
  const consulta = async (sql, params) => {
    const s = sql.replace(/\s+/g, ' ').trim(); llamadas.push({ sql: s, params });
    if (/COUNT/.test(s)) return [[{ total: 0 }]];
    if (/^INSERT INTO movimiento/.test(s)) return [{ insertId: 9 }];
    if (respuestas.falla && respuestas.falla.test(s)) throw new Error('fallo simulado');
    return [[]];
  };
  const conn = { query: consulta, beginTransaction: async () => eventos.push('begin'), commit: async () => eventos.push('commit'), rollback: async () => eventos.push('rollback'), release: () => eventos.push('release') };
  return { llamadas, eventos, query: consulta, getConnection: async () => conn };
}

test('listar existencias: bajo_minimo compara cantidad con el umbral', async () => {
  const p = poolFalso();
  await crearRepositorio(p).listarExistencias({ bajo_minimo: true, producto_id: 3, page: 2, limit: 10 });
  assert.strictEqual(p.llamadas[1].sql, 'SELECT * FROM saldo WHERE producto_id = ? AND cantidad_disponible < stock_minimo ORDER BY producto_id, bodega_id LIMIT ? OFFSET ?');
  assert.deepStrictEqual(p.llamadas[1].params, [3, 10, 10]);
});

test('listar movimientos: bodega busca en origen o destino, fechas y orden descendente', async () => {
  const p = poolFalso(); const d = new Date('2026-01-01T00:00:00Z');
  await crearRepositorio(p).listarMovimientos({ bodega_id: 2, desde: d, tipo_movimiento: 'SALIDA', page: 1, limit: 20 });
  assert.strictEqual(p.llamadas[1].sql, 'SELECT * FROM movimiento WHERE (bodega_origen_id = ? OR bodega_destino_id = ?) AND tipo_movimiento = ? AND fecha_registro_movimiento >= ? ORDER BY id DESC LIMIT ? OFFSET ?');
  assert.deepStrictEqual(p.llamadas[1].params, [2, 2, 'SALIDA', d, 20, 0]);
});

test('transaccion: begin, commit y libera la conexion', async () => {
  const p = poolFalso();
  const r = await crearRepositorio(p).transaccion(async (tx) => { await tx.saldoBloqueado(1, 2); return 'ok'; });
  assert.strictEqual(r, 'ok'); assert.deepStrictEqual(p.eventos, ['begin', 'commit', 'release']);
  assert.match(p.llamadas[0].sql, /^INSERT IGNORE INTO saldo/); assert.match(p.llamadas[1].sql, /FOR UPDATE$/);
});

test('transaccion: si algo falla hace rollback, libera y relanza el error', async () => {
  const p = poolFalso();
  await assert.rejects(() => crearRepositorio(p).transaccion(async () => { throw new Error('boom'); }), /boom/);
  assert.deepStrictEqual(p.eventos, ['begin', 'rollback', 'release']);
});

test('insertar movimiento devuelve el id; los valores van como parametros', async () => {
  const p = poolFalso();
  const id = await crearRepositorio(p).transaccion((tx) => tx.insertarMovimiento({ operacion_id: "x'; DROP TABLE saldo;--", tipo_movimiento: 'ENTRADA', producto_id: 1, cantidad_movimiento: 2, saldo_resultante: 2, origen_movimiento: 'MANUAL' }));
  assert.strictEqual(id, 9);
  const ins = p.llamadas.find((l) => /^INSERT INTO movimiento/.test(l.sql));
  assert.ok(!/DROP/.test(ins.sql)); assert.ok(ins.params.includes("x'; DROP TABLE saldo;--"));
});
