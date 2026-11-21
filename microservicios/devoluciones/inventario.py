"""Cliente REST hacia Inventario: sin acceso a su BD y con operacion_id estable."""
import json
import logging
import time
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from validaciones import ErrorApi

logger = logging.getLogger(__name__)


class ClienteInventario:
    def __init__(self, config, solicitar=None, dormir=None):
        self.config = config
        self.solicitar = solicitar or self._solicitar
        self.dormir = dormir or time.sleep

    @staticmethod
    def _solicitar(url, body, headers, timeout):
        request = Request(url, data=json.dumps(body).encode('utf-8'), headers=headers, method='POST')
        try:
            with urlopen(request, timeout=timeout) as resp:
                payload = resp.read().decode('utf-8')
                return resp.status, json.loads(payload) if payload else None
        except HTTPError as e:
            raw = e.read().decode('utf-8')
            try:
                body = json.loads(raw)
            except (ValueError, TypeError):
                body = None
            return e.code, body

    def movimiento(self, dev, linea, correlation_id):
        es_cliente = dev['tipo'] == 'CLIENTE'
        ruta = 'entradas' if es_cliente else 'salidas'
        data = {
            'operacion_id': linea['operacion_id'],
            'producto_id': linea['producto_id'],
            'cantidad_movimiento': linea['cantidad'],
            'origen_movimiento': 'DEVOLUCION',
            'motivo_movimiento': dev['motivo'],
            'documento_ref': (dev.get('documento_ref') or f"DEV-{dev['id']}")[:40],
            ('bodega_destino_id' if es_cliente else 'bodega_origen_id'): dev['bodega_id'],
        }
        headers = {'Content-Type': 'application/json', 'Accept': 'application/json',
                   'X-Internal-Token': self.config['internal_token'],
                   'X-Correlation-ID': correlation_id}
        # No incluir X-User-Role; Inventario identifica así una llamada entre servicios.
        url = self.config['url_inventario'] + '/api/inventario/' + ruta
        ultimo = None
        for intento in range(max(0, self.config['reintentos']) + 1):
            if intento:
                self.dormir(0.2 * 2**(intento - 1))
            try:
                status, respuesta = self.solicitar(url, data, headers, self.config['timeout_seg'])
            except (URLError, OSError, TimeoutError, ValueError) as exc:
                logger.warning('Inventario no disponible: %s', exc)
                ultimo = exc
                continue
            if status in (200, 201):
                return
            if status >= 500:
                ultimo = f'HTTP {status}'
                continue
            if status == 409:
                raise ErrorApi(409, (respuesta or {}).get('codigo', 'CONFLICTO_INVENTARIO'),
                               (respuesta or {}).get('mensaje', 'Inventario rechazo el movimiento'),
                               (respuesta or {}).get('detalles', []))
            if status in (400, 422):
                raise ErrorApi(422, (respuesta or {}).get('codigo', 'MOVIMIENTO_INVALIDO'),
                               (respuesta or {}).get('mensaje', 'Inventario rechazo los datos'),
                               (respuesta or {}).get('detalles', []))
            raise ErrorApi(503, 'SERVICIO_NO_DISPONIBLE', f'Inventario respondio HTTP {status}')
        logger.error('Inventario sin respuesta: %s', ultimo)
        raise ErrorApi(503, 'SERVICIO_NO_DISPONIBLE', 'Inventario no esta disponible')
