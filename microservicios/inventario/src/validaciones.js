// Validaciones puras. 400 = formato/campos ausentes; 422 = regla de negocio.
const { ErrorApi, solicitudInvalida } = require('./errores');

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const ORIGENES = ['MANUAL', 'COMPRA', 'DEVOLUCION'];
const esEntero = (v) => Number.isInteger(v);
const unprocesable = (codigo, mensaje, campo, error) => new ErrorApi(422, codigo, mensaje, [{ campo, error }]);

function parseId(texto, campo = 'id') {
  if (!/^\d+$/.test(texto) || Number(texto) < 1) throw solicitudInvalida([{ campo, error: 'Debe ser un entero positivo' }]);
  return Number(texto);
}

// ---- consultas ----
const qEntero = (q, c, d) => {
  if (q[c] === undefined) return undefined;
  if (typeof q[c] !== 'string' || !/^\d+$/.test(q[c]) || Number(q[c]) < 1) { d.push({ campo: c, error: 'Debe ser un entero positivo' }); return undefined; }
  return Number(q[c]);
};
const qBool = (q, c, d) => {
  if (q[c] === undefined) return undefined;
  if (q[c] === 'true') return true;
  if (q[c] === 'false') return false;
  d.push({ campo: c, error: 'Debe ser true o false' }); return undefined;
};
const qEnum = (q, c, valores, d) => {
  if (q[c] === undefined) return undefined;
  if (!valores.includes(q[c])) { d.push({ campo: c, error: `Debe ser uno de: ${valores.join(', ')}` }); return undefined; }
  return q[c];
};
const qFecha = (q, c, esHasta, d) => {
  if (q[c] === undefined) return undefined;
  const t = q[c];
  const ok = typeof t === 'string' && /^\d{4}-\d{2}-\d{2}([T ][\d:.]+Z?)?$/.test(t) && !Number.isNaN(Date.parse(t));
  if (!ok) { d.push({ campo: c, error: 'Fecha invalida (use AAAA-MM-DD o ISO 8601)' }); return undefined; }
  // "hasta" con solo fecha incluye todo ese dia
  return new Date(/^\d{4}-\d{2}-\d{2}$/.test(t) ? `${t}T${esHasta ? '23:59:59.999' : '00:00:00.000'}Z` : t);
};
function paginacion(q, d) {
  const page = qEntero(q, 'page', d) || 1; const limit = qEntero(q, 'limit', d) || 20;
  if (limit > 100) d.push({ campo: 'limit', error: 'Maximo 100' });
  return { page, limit };
}
const cerrar = (f, d) => { if (d.length) throw solicitudInvalida(d); return f; };

function filtrosExistencias(q = {}) {
  const d = [];
  return cerrar({ producto_id: qEntero(q, 'producto_id', d), bodega_id: qEntero(q, 'bodega_id', d), bajo_minimo: qBool(q, 'bajo_minimo', d), ...paginacion(q, d) }, d);
}
function filtrosMovimientos(q = {}) {
  const d = [];
  return cerrar({
    producto_id: qEntero(q, 'producto_id', d), bodega_id: qEntero(q, 'bodega_id', d),
    tipo_movimiento: qEnum(q, 'tipo_movimiento', ['ENTRADA', 'SALIDA', 'AJUSTE', 'TRASLADO'], d),
    origen_movimiento: qEnum(q, 'origen_movimiento', ORIGENES, d),
    usuario_id: qEntero(q, 'usuario_id', d), desde: qFecha(q, 'desde', false, d), hasta: qFecha(q, 'hasta', true, d), ...paginacion(q, d),
  }, d);
}

// ---- cuerpos de los movimientos ----
function objeto(b) {
  if (b === null || typeof b !== 'object' || Array.isArray(b)) throw solicitudInvalida([{ campo: 'cuerpo', error: 'Debe ser un objeto JSON' }]);
  return b;
}
function comunes(b, d) {
  const v = {};
  if (b.operacion_id === undefined) d.push({ campo: 'operacion_id', error: 'Es obligatorio' });
  else if (typeof b.operacion_id !== 'string' || !UUID.test(b.operacion_id)) d.push({ campo: 'operacion_id', error: 'Debe ser un UUID de 36 caracteres' });
  else v.operacion_id = b.operacion_id.toLowerCase();
  for (const c of ['producto_id', 'cantidad_movimiento']) {
    if (b[c] === undefined) d.push({ campo: c, error: 'Es obligatorio' });
    else if (!esEntero(b[c])) d.push({ campo: c, error: 'Debe ser un entero' });
    else v[c] = b[c];
  }
  if (v.producto_id !== undefined && v.producto_id < 1) d.push({ campo: 'producto_id', error: 'Debe ser un entero positivo' });
  for (const [c, max] of [['motivo_movimiento', 200], ['documento_ref', 40]]) {
    if (b[c] === undefined || b[c] === null) continue;
    if (typeof b[c] !== 'string' || b[c].length > max) d.push({ campo: c, error: `Debe ser un texto de maximo ${max} caracteres` });
    else v[c] = b[c];
  }
  return v;
}
function bodega(b, c, obligatoria, d) {
  if (b[c] === undefined || b[c] === null) { if (obligatoria) d.push({ campo: c, error: 'Es obligatorio' }); return undefined; }
  if (!esEntero(b[c]) || b[c] < 1) { d.push({ campo: c, error: 'Debe ser un entero positivo' }); return undefined; }
  return b[c];
}
function cantidadPositiva(v) {
  if (v.cantidad_movimiento !== undefined && v.cantidad_movimiento <= 0) {
    throw unprocesable('CANTIDAD_INVALIDA', 'La cantidad debe ser mayor que cero', 'cantidad_movimiento', 'Debe ser mayor que cero');
  }
}

// tipo: 'ENTRADA' | 'SALIDA'
function validarEntradaSalida(body, tipo) {
  const b = objeto(body); const d = []; const v = comunes(b, d);
  const campo = tipo === 'ENTRADA' ? 'bodega_destino_id' : 'bodega_origen_id';
  v[campo] = bodega(b, campo, true, d);
  if (b.origen_movimiento === undefined) d.push({ campo: 'origen_movimiento', error: 'Es obligatorio' });
  else if (!ORIGENES.includes(b.origen_movimiento)) d.push({ campo: 'origen_movimiento', error: `Debe ser uno de: ${ORIGENES.join(', ')}` });
  else v.origen_movimiento = b.origen_movimiento;
  if (d.length) throw solicitudInvalida(d);
  cantidadPositiva(v);
  return { tipo_movimiento: tipo, ...v };
}

function validarAjuste(body) {
  const b = objeto(body); const d = []; const v = comunes(b, d);
  if (b.sentido_ajuste === undefined) d.push({ campo: 'sentido_ajuste', error: 'Es obligatorio' });
  else if (!['POSITIVO', 'NEGATIVO'].includes(b.sentido_ajuste)) d.push({ campo: 'sentido_ajuste', error: 'Debe ser POSITIVO o NEGATIVO' });
  const positivo = b.sentido_ajuste === 'POSITIVO';
  const dest = bodega(b, 'bodega_destino_id', positivo, d);
  const orig = bodega(b, 'bodega_origen_id', b.sentido_ajuste === 'NEGATIVO', d);
  if (d.length) throw solicitudInvalida(d);
  cantidadPositiva(v);
  if (typeof v.motivo_movimiento !== 'string' || v.motivo_movimiento.trim() === '') {
    throw unprocesable('MOTIVO_REQUERIDO', 'El motivo del ajuste es obligatorio', 'motivo_movimiento', 'Es obligatorio para auditoria');
  }
  if (positivo && orig !== undefined) throw unprocesable('BODEGA_NO_CORRESPONDE', 'La bodega indicada no corresponde al sentido del ajuste', 'bodega_origen_id', 'Un ajuste POSITIVO usa bodega_destino_id');
  if (!positivo && dest !== undefined) throw unprocesable('BODEGA_NO_CORRESPONDE', 'La bodega indicada no corresponde al sentido del ajuste', 'bodega_destino_id', 'Un ajuste NEGATIVO usa bodega_origen_id');
  return { tipo_movimiento: 'AJUSTE', ...v, origen_movimiento: 'MANUAL', ...(positivo ? { bodega_destino_id: dest } : { bodega_origen_id: orig }) };
}

function validarTraslado(body) {
  const b = objeto(body); const d = []; const v = comunes(b, d);
  const o = bodega(b, 'bodega_origen_id', true, d); const t = bodega(b, 'bodega_destino_id', true, d);
  if (d.length) throw solicitudInvalida(d);
  cantidadPositiva(v);
  if (o === t) throw unprocesable('BODEGAS_IGUALES', 'La bodega de origen y la de destino deben ser distintas', 'bodega_destino_id', 'Igual a la bodega de origen');
  return { tipo_movimiento: 'TRASLADO', ...v, bodega_origen_id: o, bodega_destino_id: t, origen_movimiento: 'MANUAL' };
}

function validarMinimo(body) {
  const b = objeto(body);
  if (!esEntero(b.stock_minimo) || b.stock_minimo < 0) throw solicitudInvalida([{ campo: 'stock_minimo', error: 'Es obligatorio y debe ser un entero mayor o igual a cero' }]);
  return b.stock_minimo;
}
module.exports = { parseId, filtrosExistencias, filtrosMovimientos, validarEntradaSalida, validarAjuste, validarTraslado, validarMinimo };
