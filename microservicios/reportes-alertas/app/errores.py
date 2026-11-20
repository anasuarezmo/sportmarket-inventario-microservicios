"""Error de negocio/validacion: el manejador lo convierte al formato {codigo, mensaje, detalles, correlation_id}."""


class ErrorApi(Exception):
    def __init__(self, status, codigo, mensaje, detalles=None):
        super().__init__(mensaje)
        self.status = status
        self.codigo = codigo
        self.mensaje = mensaje
        self.detalles = detalles or []


def solicitud_invalida(detalles, mensaje="La solicitud tiene datos incorrectos"):
    return ErrorApi(400, "PETICION_INVALIDA", mensaje, detalles)


def no_encontrado(que):
    return ErrorApi(404, "RECURSO_NO_ENCONTRADO", f"{que} no encontrada" if que == "Alerta" else f"{que} no encontrado")
