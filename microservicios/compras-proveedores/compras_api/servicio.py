from . import repositorio as repo
from .integraciones import registrar_entrada
from .errores import ErrorApi

def sincronizar_recepcion(identificador, cid):
    rec = repo.recepcion(identificador)
    if rec['estado'] != 'PENDIENTE_DE_SINCRONIZAR':
        return rec
    orden = repo.orden(rec['orden_id'])
    detalle_orden = {d['id']: d for d in orden['detalles']}
    rechazado = False
    pendiente = False
    for detalle in rec['detalles']:
        if detalle['aplicada']:
            continue
        linea = detalle_orden[detalle['orden_detalle_id']]
        try:
            status, _ = registrar_entrada(detalle['operacion_id'], linea['producto_id'], orden['bodega_destino_id'], detalle['cantidad_recibida'], orden['numero'], cid)
            if status in (200, 201):
                repo.aplicar_linea(detalle['id'])
            elif 400 <= status < 500:
                rechazado = True
            else:
                pendiente = True
        except ErrorApi as e:
            if e.status == 503:
                pendiente = True
            else:
                rechazado = True
    if rechazado:
        estado = 'RECHAZADA'
    elif pendiente:
        estado = 'PENDIENTE_DE_SINCRONIZAR'
    else:
        estado = 'SINCRONIZADA'
    return repo.fijar_estado_recepcion(identificador, estado)
