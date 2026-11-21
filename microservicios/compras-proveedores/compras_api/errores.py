class ErrorApi(Exception):
    def __init__(self, status, codigo, mensaje, detalles=None):
        super().__init__(mensaje)
        self.status, self.codigo, self.mensaje = status, codigo, mensaje
        self.detalles = detalles or []

def requerido(campo, mensaje='Campo obligatorio o inválido'):
    return ErrorApi(400, 'DATOS_INVALIDOS', mensaje, [{'campo': campo, 'error': mensaje}])

def no_existe(nombre):
    return ErrorApi(404, 'NO_ENCONTRADO', f'{nombre} no encontrado')
