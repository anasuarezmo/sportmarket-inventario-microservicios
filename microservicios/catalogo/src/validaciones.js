// Validaciones puras (sin base de datos). Lanzan ErrorApi 400 (formato) o 422 (regla de negocio).
const { ErrorApi, solicitudInvalida } = require('./errores');

const esEntero = (v) => Number.isInteger(v) && v > 0;

function parseId(texto) {
  if (!/^\d+$/.test(texto) || Number(texto) < 1) throw solicitudInvalida([{ campo: 'id', error: 'Debe ser un entero positivo' }]);
  return Number(texto);
}

// ---- parametros de consulta (llegan siempre como texto) ----
function qEntero(q, campo, detalles) {
  if (q[campo] === undefined) return undefined;
  if (typeof q[campo] !== 'string' || !/^\d+$/.test(q[campo]) || Number(q[campo]) < 1) {
    detalles.push({ campo, error: 'Debe ser un entero positivo' });
    return undefined;
  }
  return Number(q[campo]);
}
function qBool(q, campo, detalles) {
  if (q[campo] === undefined) return undefined;
  if (q[campo] === 'true') return true;
  if (q[campo] === 'false') return false;
  detalles.push({ campo, error: 'Debe ser true o false' });
  return undefined;
}
function qTexto(q, campo, detalles) {
  if (q[campo] === undefined) return undefined;
  if (typeof q[campo] !== 'string' || q[campo].trim() === '') { detalles.push({ campo, error: 'Debe ser un texto' }); return undefined; }
  return q[campo].trim();
}
function paginacion(q, detalles) {
  const page = qEntero(q, 'page', detalles) || 1;
  const limit = qEntero(q, 'limit', detalles) || 20;
  if (limit > 100) detalles.push({ campo: 'limit', error: 'Maximo 100' });
  return { page, limit };
}

function filtrosProductos(q = {}) {
  const d = [];
  const f = {
    nombre: qTexto(q, 'nombre', d), codigo: qTexto(q, 'codigo', d),
    categoria_id: qEntero(q, 'categoria_id', d), proveedor_id: qEntero(q, 'proveedor_id', d),
    producto_activo: qBool(q, 'producto_activo', d), ...paginacion(q, d),
  };
  if (d.length) throw solicitudInvalida(d);
  return f;
}
function filtrosCategorias(q = {}) {
  const d = [];
  const f = { categoria_padre_id: qEntero(q, 'categoria_padre_id', d), categoria_activa: qBool(q, 'categoria_activa', d), ...paginacion(q, d) };
  if (d.length) throw solicitudInvalida(d);
  return f;
}

// ---- cuerpos ----
function cuerpoObjeto(b) {
  if (b === null || typeof b !== 'object' || Array.isArray(b)) throw solicitudInvalida([{ campo: 'cuerpo', error: 'Debe ser un objeto JSON' }]);
  return b;
}
function texto(b, campo, max, obligatorio, d, nulo = false) {
  if (b[campo] === undefined) { if (obligatorio) d.push({ campo, error: 'Es obligatorio' }); return undefined; }
  if (b[campo] === null && nulo) return null;
  if (typeof b[campo] !== 'string' || b[campo].trim() === '') { d.push({ campo, error: 'Debe ser un texto no vacio' }); return undefined; }
  if (max && b[campo].trim().length > max) { d.push({ campo, error: `Maximo ${max} caracteres` }); return undefined; }
  return b[campo].trim();
}
function enteroCampo(b, campo, obligatorio, d, nulo = false) {
  if (b[campo] === undefined) { if (obligatorio) d.push({ campo, error: 'Es obligatorio' }); return undefined; }
  if (b[campo] === null && nulo) return null;
  if (!esEntero(b[campo])) { d.push({ campo, error: 'Debe ser un entero positivo' }); return undefined; }
  return b[campo];
}

// completo=true (POST: campos obligatorios) | completo=false (PUT: basta con enviar los que cambian)
function validarProducto(body, completo) {
  const b = cuerpoObjeto(body); const d = [];
  const v = {
    codigo_producto: texto(b, 'codigo_producto', 40, completo, d),
    nombre_producto: texto(b, 'nombre_producto', 120, completo, d),
    descripcion_producto: texto(b, 'descripcion_producto', 0, false, d, true),
    categoria_id: enteroCampo(b, 'categoria_id', completo, d),
    unidad_medida: texto(b, 'unidad_medida', 20, completo, d),
    proveedor_principal_id: enteroCampo(b, 'proveedor_principal_id', false, d, true),
  };
  if (b.precio_venta === undefined) { if (completo) d.push({ campo: 'precio_venta', error: 'Es obligatorio' }); }
  else if (typeof b.precio_venta !== 'number' || !Number.isFinite(b.precio_venta)) d.push({ campo: 'precio_venta', error: 'Debe ser un numero' });
  else v.precio_venta = b.precio_venta;
  if (d.length) throw solicitudInvalida(d);
  const limpio = Object.fromEntries(Object.entries(v).filter(([, x]) => x !== undefined));
  if (Object.keys(limpio).length === 0) throw solicitudInvalida([{ campo: 'cuerpo', error: 'No se envio ningun campo para actualizar' }]);
  if (limpio.precio_venta !== undefined && limpio.precio_venta < 0) {
    throw new ErrorApi(422, 'PRECIO_INVALIDO', 'El precio de venta debe ser mayor o igual a cero', [{ campo: 'precio_venta', error: 'No puede ser negativo' }]);
  }
  return limpio;
}

function validarCategoria(body, completo) {
  const b = cuerpoObjeto(body); const d = [];
  const v = {
    nombre: texto(b, 'nombre', 80, completo, d),
    descripcion: texto(b, 'descripcion', 200, false, d, true),
    categoria_padre_id: enteroCampo(b, 'categoria_padre_id', false, d, true),
  };
  if (d.length) throw solicitudInvalida(d);
  const limpio = Object.fromEntries(Object.entries(v).filter(([, x]) => x !== undefined));
  if (Object.keys(limpio).length === 0) throw solicitudInvalida([{ campo: 'cuerpo', error: 'No se envio ningun campo para actualizar' }]);
  return limpio;
}

function validarEstado(body, campo) {
  const b = cuerpoObjeto(body);
  if (typeof b[campo] !== 'boolean') throw solicitudInvalida([{ campo, error: 'Es obligatorio y debe ser true o false' }]);
  return b[campo];
}
module.exports = { parseId, filtrosProductos, filtrosCategorias, validarProducto, validarCategoria, validarEstado };
