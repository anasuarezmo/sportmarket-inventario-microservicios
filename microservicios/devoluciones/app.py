"""API Flask del microservicio Devoluciones (Entrega 3)."""
import hmac
import logging
import re
import uuid

from flask import Flask, Response, g, jsonify, request
from mysql.connector import Error as MySQLError

from config import configuracion
from inventario import ClienteInventario
from repositorio import Repositorio
from validaciones import ErrorApi, filtros, registro

logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger(__name__)
ROLES = {'ADM', 'INV', 'COM', 'BOD', 'CON'}


def crear_app(config=None, repo=None, inventario=None):
    cfg = config or configuracion()
    repo = repo or Repositorio(cfg)
    inventario = inventario or ClienteInventario(cfg)
    app = Flask(__name__)
    app.json.ensure_ascii = False

    @app.before_request
    def autenticar():
        cid = request.headers.get('X-Correlation-ID', '')
        g.cid = cid if re.fullmatch(r'[\w-]{8,64}', cid) else str(uuid.uuid4())
        if request.path == '/health':
            return None
        secreto = cfg['internal_token']
        recibido = request.headers.get('X-Internal-Token', '')
        if not secreto or not recibido or not hmac.compare_digest(secreto, recibido):
            raise ErrorApi(401, 'NO_AUTENTICADO', 'Credencial interna ausente o incorrecta')
        rol = request.headers.get('X-User-Role')
        if rol is not None and rol not in ROLES:
            raise ErrorApi(403, 'PROHIBIDO', 'Rol invalido')
        return None

    @app.after_request
    def correlacion(resp):
        resp.headers['X-Correlation-ID'] = getattr(g, 'cid', str(uuid.uuid4()))
        return resp

    @app.errorhandler(ErrorApi)
    def error_api(err):
        return jsonify({'codigo': err.codigo, 'mensaje': str(err),
                        'detalles': err.detalles, 'correlation_id': getattr(g, 'cid', str(uuid.uuid4()))}), err.status

    @app.errorhandler(MySQLError)
    def error_bd(err):
        LOG.exception('Error de MySQL en Devoluciones')
        return error_api(ErrorApi(503, 'BASE_NO_DISPONIBLE', 'Base de datos no disponible'))

    @app.errorhandler(404)
    def no_encontrado(err):
        return error_api(ErrorApi(404, 'RECURSO_NO_ENCONTRADO', 'Recurso no encontrado'))

    @app.errorhandler(405)
    def no_permitido(err):
        return error_api(ErrorApi(405, 'METODO_NO_PERMITIDO', 'Metodo no permitido'))

    @app.errorhandler(Exception)
    def error_inesperado(err):
        LOG.exception('Error inesperado en Devoluciones')
        return error_api(ErrorApi(500, 'ERROR_INTERNO', 'Error interno del servicio'))

    def roles_permitidos(permitidos):
        if request.headers.get('X-User-Role') not in permitidos:
            raise ErrorApi(403, 'PROHIBIDO', 'No tiene permisos para esta operacion')

    @app.get('/health')
    def health():
        try:
            repo.ping()
        except Exception:
            return jsonify({'estado': 'DOWN'}), 503
        return jsonify({'estado': 'UP'})

    @app.get('/openapi.yaml')
    def contrato():
        import pathlib
        file = pathlib.Path(__file__).with_name('openapi.yaml')
        return Response(file.read_text(encoding='utf8'), content_type='text/yaml; charset=utf-8')

    @app.get('/docs')
    def docs():
        return Response('<!doctype html><html lang="es"><meta charset="utf-8"><title>Devoluciones API</title><body>'
                        '<h1>Contrato OpenAPI – Devoluciones</h1><p><a href="/openapi.yaml">Ver openapi.yaml</a></p></body></html>',
                        content_type='text/html; charset=utf-8')

    @app.get('/api/devoluciones')
    def listar():
        return jsonify(repo.listar(filtros(request.args)))

    @app.get('/api/devoluciones/<int:dev_id>')
    def detalle(dev_id):
        if dev_id < 1:
            raise ErrorApi(400, 'PETICION_INVALIDA', 'El id debe ser positivo')
        d = repo.obtener(dev_id)
        if d is None:
            raise ErrorApi(404, 'NO_ENCONTRADO', 'Devolucion no encontrada')
        return jsonify(d)

    @app.post('/api/devoluciones')
    def crear():
        roles_permitidos({'ADM', 'INV', 'COM', 'BOD'})
        data = request.get_json(silent=True)
        if data is None:
            raise ErrorApi(400, 'PETICION_INVALIDA', 'Se requiere un cuerpo JSON valido')
        datos = registro(data)
        usuario_texto = request.headers.get('X-User-Id', '')
        if not usuario_texto.isdecimal() or int(usuario_texto) < 1:
            raise ErrorApi(401, 'NO_AUTENTICADO', 'Falta un identificador de usuario valido del Gateway')
        usuario_id = int(usuario_texto)
        creada = repo.crear(datos, usuario_id)
        return jsonify({'mensaje': 'Devolucion registrada', 'devolucion': creada}), 201

    @app.post('/api/devoluciones/<int:dev_id>/procesar')
    def procesar(dev_id):
        roles_permitidos({'ADM', 'INV'})
        if dev_id < 1:
            raise ErrorApi(400, 'PETICION_INVALIDA', 'El id debe ser positivo')
        dev = repo.obtener(dev_id)
        if dev is None:
            raise ErrorApi(404, 'NO_ENCONTRADO', 'Devolucion no encontrada')
        if dev['estado_inventario'] == 'APLICADA':
            raise ErrorApi(409, 'DEVOLUCION_APLICADA', 'La devolucion ya esta aplicada')
        # Cada linea conserva su operacion_id; Inventario permite 200 para reintentos idempotentes.
        for linea in dev['detalles']:
            if linea['operacion_id'] is not None:
                inventario.movimiento(dev, linea, g.cid)
        # La transicion ocurre SOLO tras confirmar todos los movimientos.
        if not repo.marcar_aplicada(dev_id):
            raise ErrorApi(409, 'DEVOLUCION_APLICADA', 'La devolucion ya esta aplicada')
        return jsonify({'mensaje': 'Devolucion procesada', 'devolucion': {
            'id': dev_id, 'estado_inventario': 'APLICADA'}})

    return app


app = crear_app()

if __name__ == '__main__':
    import os
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', '5006')))
