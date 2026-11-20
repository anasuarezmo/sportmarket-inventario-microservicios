// Error de negocio/validacion: el manejador lo convierte al formato estandar
// {codigo, mensaje, detalles, correlation_id}
class ErrorApi extends Error {
  constructor(status, codigo, mensaje, detalles = []) {
    super(mensaje);
    this.status = status;
    this.codigo = codigo;
    this.detalles = detalles;
  }
}
const solicitudInvalida = (detalles, mensaje = 'La solicitud tiene datos incorrectos') =>
  new ErrorApi(400, 'PETICION_INVALIDA', mensaje, detalles);
const noEncontrado = (que) => new ErrorApi(404, 'RECURSO_NO_ENCONTRADO', `${que} no encontrado`);
module.exports = { ErrorApi, solicitudInvalida, noEncontrado };
