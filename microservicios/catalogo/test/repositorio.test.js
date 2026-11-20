const test = require('node:test');
const assert = require('node:assert');
const { crearRepositorio } = require('../src/repositorio');

// Pool falso: registra el SQL y los parametros para comprobar que las consultas se arman bien (sin MySQL)
function poolFalso() {
  const llamadas = [];
  return {
    llamadas,
    async query(sql, params) {
      llamadas.push({ sql: sql.replace(/\s+/g, ' ').trim(), params });
      if (/COUNT/.test(sql)) return [[{ total: 0 }]];
      if (/^INSERT/.test(sql)) return [{ insertId: 5 }];
      return [[]];
    },
  };
}

test('listar productos arma WHERE, LIMIT y OFFSET con parametros', async () => {
  const p = poolFalso();
  await crearRepositorio(p).productos.listar({ nombre: 'bal', categoria_id: 2, producto_activo: true, page: 3, limit: 10 });
  assert.strictEqual(p.llamadas[0].sql, 'SELECT COUNT(*) AS total FROM producto WHERE nombre_producto LIKE ? AND categoria_id = ? AND producto_activo = ?');
  assert.deepStrictEqual(p.llamadas[0].params, ['%bal%', 2, 1]);
  assert.strictEqual(p.llamadas[1].sql, 'SELECT * FROM producto WHERE nombre_producto LIKE ? AND categoria_id = ? AND producto_activo = ? ORDER BY id LIMIT ? OFFSET ?');
  assert.deepStrictEqual(p.llamadas[1].params, ['%bal%', 2, 1, 10, 20]);
});

test('listar sin filtros no agrega WHERE', async () => {
  const p = poolFalso();
  await crearRepositorio(p).categorias.listar({ page: 1, limit: 20 });
  assert.strictEqual(p.llamadas[1].sql, 'SELECT * FROM categoria ORDER BY id LIMIT ? OFFSET ?');
});

test('insertar y actualizar solo usan columnas permitidas y enviadas', async () => {
  const p = poolFalso(); const r = crearRepositorio(p);
  assert.strictEqual(await r.productos.insertar({ codigo_producto: 'A', nombre_producto: 'B', categoria_id: 1, unidad_medida: 'u', precio_venta: 1, hack: 'x' }), 5);
  assert.strictEqual(p.llamadas[0].sql, 'INSERT INTO producto (codigo_producto, nombre_producto, categoria_id, unidad_medida, precio_venta) VALUES (?, ?, ?, ?, ?)');
  await r.productos.actualizar(3, { precio_venta: 9, hack: 'x' });
  assert.strictEqual(p.llamadas[1].sql, 'UPDATE producto SET precio_venta = ? WHERE id = ?');
  assert.deepStrictEqual(p.llamadas[1].params, [9, 3]);
});

test('el valor del usuario nunca se concatena en el SQL (evita inyeccion)', async () => {
  const p = poolFalso();
  await crearRepositorio(p).productos.listar({ nombre: "x'; DROP TABLE producto;--", page: 1, limit: 20 });
  for (const l of p.llamadas) assert.ok(!/DROP/.test(l.sql));
});
