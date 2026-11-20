// Formato de error unico de todo el sistema: {codigo, mensaje, detalles, correlation_id}
function error(status, codigo, mensaje, correlationId, detalles = []) {
  return { status, cuerpo: { codigo, mensaje, detalles, correlation_id: correlationId } };
}
module.exports = { error };
