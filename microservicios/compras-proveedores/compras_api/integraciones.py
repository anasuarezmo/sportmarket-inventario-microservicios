import os
import time
import requests
from .errores import ErrorApi

def llamada(servicio, ruta, cid, metodo='GET', payload=None, operacion=False):
    base = os.environ.get('URL_INVENTARIO' if servicio == 'inventario' else 'URL_CATALOGO', '').rstrip('/')
    if not base:
        raise ErrorApi(503, 'SERVICIO_NO_DISPONIBLE', f'No se configuró URL_{servicio.upper()}')
    token = os.environ.get('INTERNAL_TOKEN', '')
    headers = {'X-Internal-Token': token, 'X-Correlation-ID': cid}
    # Importante: SIN X-User-Role, para que Inventario lo reconozca como llamada interna.
    if payload is not None: headers['Content-Type'] = 'application/json'
    for intento in range(4):  # 1 intento + 3 reintentos por errores transitorios
        try:
            r = requests.request(metodo, base + ruta, json=payload, headers=headers, timeout=3)
            if r.status_code < 500:
                try: datos = r.json()
                except ValueError: datos = None
                return r.status_code, datos
        except requests.RequestException:
            pass
        if intento < 3: time.sleep(0.2 * 2 ** intento)
    raise ErrorApi(503, 'SERVICIO_NO_DISPONIBLE', f'No hay respuesta válida de {servicio}')

def validar_producto(producto_id, cid):
    status, _ = llamada('catalogo', f'/api/productos/{producto_id}', cid)
    if status == 404: raise ErrorApi(422, 'PRODUCTO_INEXISTENTE', f'No existe el producto {producto_id}')
    if status != 200: raise ErrorApi(503, 'SERVICIO_NO_DISPONIBLE', f'Catálogo respondió HTTP {status}')

def registrar_entrada(operacion_id, producto_id, bodega_id, cantidad, numero, cid):
    return llamada('inventario', '/api/inventario/entradas', cid, metodo='POST', payload={
        'operacion_id': operacion_id,
        'producto_id': producto_id,
        'bodega_destino_id': bodega_id,
        'cantidad_movimiento': cantidad,
        'origen_movimiento': 'COMPRA',
        'motivo_movimiento': 'Recepción de mercancía',
        'documento_ref': numero,
    }, operacion=True)
