"""Pruebas aisladas: sin MySQL, sin Gateway y sin hacer peticiones de red."""
import unittest
from unittest.mock import Mock

from app import crear_app
from inventario import ClienteInventario
from validaciones import ErrorApi, filtros, registro


class RepositorioFalso:
    def __init__(self):
        self.datos = {}
        self.ultimo_id = 0
        self.ping_error = False
        self.marca_error = False

    def ping(self):
        if self.ping_error:
            raise RuntimeError('Sin MySQL')

    def crear(self, datos, usuario_id):
        self.ultimo_id += 1
        dev = {'id': self.ultimo_id, 'tipo': datos['tipo'], 'motivo': datos['motivo'],
               'bodega_id': datos['bodega_id'], 'proveedor_id': datos['proveedor_id'],
               'documento_ref': datos['documento_ref'], 'fecha': '2026-11-21T00:00:00',
               'estado_inventario': 'PENDIENTE', 'usuario_id': usuario_id, 'detalles': []}
        for n, linea in enumerate(datos['detalles'], 1):
            uuid = None if linea['condicion'] == 'DEFECTUOSO' else f'123e4567-e89b-12d3-a456-{(self.ultimo_id*100+n):012d}'
            dev['detalles'].append(dict(id=n, **linea, operacion_id=uuid))
        self.datos[dev['id']] = dev
        return self.obtener(dev['id'])

    def obtener(self, dev_id):
        import copy
        return copy.deepcopy(self.datos.get(dev_id))

    def listar(self, f):
        items = list(self.datos.values())
        for k in ('tipo', 'estado_inventario'):
            if f[k] is not None:
                items = [x for x in items if x[k] == f[k]]
        if f['producto_id'] is not None:
            items = [x for x in items if any(l['producto_id'] == f['producto_id'] for l in x['detalles'])]
        total = len(items)
        return {'items': items[(f['page']-1)*f['limit']:f['page']*f['limit']],
                'total': total, 'page': f['page'], 'limit': f['limit']}

    def marcar_aplicada(self, dev_id):
        if self.marca_error or self.datos[dev_id]['estado_inventario'] == 'APLICADA':
            return False
        self.datos[dev_id]['estado_inventario'] = 'APLICADA'
        return True


CLIENTE = {'tipo': 'CLIENTE', 'motivo': 'Producto devuelto', 'bodega_id': 1,
           'detalles': [{'producto_id': 1, 'cantidad': 2, 'condicion': 'BUEN_ESTADO'}]}
PROVEEDOR = {'tipo': 'PROVEEDOR', 'motivo': 'Producto para proveedor', 'bodega_id': 2,
             'proveedor_id': 10, 'detalles': [{'producto_id': 2, 'cantidad': 1}]}


class TestFlaskDevoluciones(unittest.TestCase):
    def setUp(self):
        self.repo = RepositorioFalso()
        self.inv = Mock()
        self.inv.movimiento.return_value = None
        self.cfg = {'internal_token': 'token-interno-para-pruebas', 'db_host': 'mysql', 'db_name': 'devoluciones_db',
                    'db_port': 3306, 'db_user': 'dev', 'db_password': '', 'port': 5006,
                    'url_inventario': 'http://inventario:3004', 'timeout_seg': 3, 'reintentos': 3}
        self.app = crear_app(self.cfg, self.repo, self.inv).test_client()
        self.lectura = {'X-Internal-Token': 'token-interno-para-pruebas', 'X-User-Role': 'CON',
                        'X-Correlation-ID': 'correlacion-12345'}
        self.admin = {**self.lectura, 'X-User-Role': 'ADM', 'X-User-Id': '14'}

    def _crear(self, body=CLIENTE, hdr=None):
        return self.app.post('/api/devoluciones', json=body, headers=hdr or self.admin)

    def test_01_salud(self):
        self.assertEqual(self.app.get('/health').json, {'estado': 'UP'})

    def test_02_salud_falla_bd(self):
        self.repo.ping_error = True
        self.assertEqual(self.app.get('/health').status_code, 503)

    def test_03_sin_token_401(self):
        self.assertEqual(self.app.get('/api/devoluciones').status_code, 401)

    def test_04_token_errado_401(self):
        self.assertEqual(self.app.get('/api/devoluciones', headers={'X-Internal-Token': 'mal'}).status_code, 401)

    def test_05_rol_desconocido_403(self):
        h = {**self.lectura, 'X-User-Role': 'XXX'}
        self.assertEqual(self.app.get('/api/devoluciones', headers=h).status_code, 403)

    def test_06_listado_200(self):
        r = self.app.get('/api/devoluciones', headers=self.lectura)
        self.assertEqual((r.status_code, r.json), (200, {'items': [], 'total': 0, 'page': 1, 'limit': 20}))

    def test_07_crear_cliente_201(self):
        r = self._crear()
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.json['devolucion']['estado_inventario'], 'PENDIENTE')
        self.assertEqual(r.json['devolucion']['usuario_id'], 14)
        self.assertIsNotNone(r.json['devolucion']['detalles'][0]['operacion_id'])

    def test_08_crear_proveedor_201(self):
        r = self._crear(PROVEEDOR)
        self.assertEqual(r.status_code, 201)
        self.assertIsNone(r.json['devolucion']['detalles'][0]['condicion'])

    def test_09_crear_con_rol_consulta_403(self):
        self.assertEqual(self._crear(hdr=self.lectura).status_code, 403)

    def test_10_crear_con_rol_compras_201(self):
        self.assertEqual(self._crear(hdr={**self.admin, 'X-User-Role': 'COM'}).status_code, 201)

    def test_11_crear_con_rol_bodega_201(self):
        self.assertEqual(self._crear(hdr={**self.admin, 'X-User-Role': 'BOD'}).status_code, 201)

    def test_12a_crear_sin_usuario_id_rechazado(self):
        hdr = {k: v for k, v in self.admin.items() if k != 'X-User-Id'}
        self.assertEqual(self._crear(hdr=hdr).status_code, 401)

    def test_12_sin_cuerpo_400(self):
        self.assertEqual(self.app.post('/api/devoluciones', headers=self.admin).status_code, 400)

    def test_13_json_no_objeto_400(self):
        self.assertEqual(self._crear(['invalido']).status_code, 400)

    def test_14_tipo_invalido_422(self):
        self.assertEqual(self._crear({**CLIENTE, 'tipo': 'OTRO'}).status_code, 422)

    def test_15_cantidad_cero_400(self):
        b = {**CLIENTE, 'detalles': [{**CLIENTE['detalles'][0], 'cantidad': 0}]}
        self.assertEqual(self._crear(b).status_code, 400)

    def test_16_condicion_cliente_requerida_422(self):
        b = {**CLIENTE, 'detalles': [{'producto_id': 1, 'cantidad': 2}]}
        self.assertEqual(self._crear(b).status_code, 422)

    def test_17_condicion_proveedor_prohibida_422(self):
        b = {**PROVEEDOR, 'detalles': [{'producto_id': 1, 'cantidad': 2, 'condicion': 'BUEN_ESTADO'}]}
        self.assertEqual(self._crear(b).status_code, 422)

    def test_18_proveedor_exigido_para_tipo_proveedor(self):
        b = {k: v for k, v in PROVEEDOR.items() if k != 'proveedor_id'}
        self.assertEqual(self._crear(b).status_code, 400)

    def test_19_listar_filtra_estado(self):
        self._crear()
        r = self.app.get('/api/devoluciones?estado_inventario=PENDIENTE&producto_id=1', headers=self.lectura)
        self.assertEqual(r.json['total'], 1)

    def test_20_paginacion_invalida(self):
        r = self.app.get('/api/devoluciones?page=0', headers=self.lectura)
        self.assertEqual(r.status_code, 400)

    def test_21_consultar_existente(self):
        self._crear()
        self.assertEqual(self.app.get('/api/devoluciones/1', headers=self.lectura).json['id'], 1)

    def test_22_consultar_inexistente_404(self):
        self.assertEqual(self.app.get('/api/devoluciones/999', headers=self.lectura).status_code, 404)

    def test_23_procesar_cliente_buen_estado(self):
        self._crear()
        r = self.app.post('/api/devoluciones/1/procesar', headers=self.admin)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.repo.obtener(1)['estado_inventario'], 'APLICADA')
        self.inv.movimiento.assert_called_once()
        self.assertEqual(self.inv.movimiento.call_args[0][1]['producto_id'], 1)

    def test_24_procesar_proveedor(self):
        self._crear(PROVEEDOR)
        r = self.app.post('/api/devoluciones/1/procesar', headers=self.admin)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.inv.movimiento.call_count, 1)

    def test_25_defectuoso_no_altera_stock(self):
        b = {**CLIENTE, 'detalles': [{'producto_id': 2, 'cantidad': 1, 'condicion': 'DEFECTUOSO'}]}
        self._crear(b)
        r = self.app.post('/api/devoluciones/1/procesar', headers=self.admin)
        self.assertEqual(r.status_code, 200)
        self.inv.movimiento.assert_not_called()

    def test_26_con_rol_compras_no_procesa(self):
        self._crear()
        r = self.app.post('/api/devoluciones/1/procesar', headers={**self.admin, 'X-User-Role': 'COM'})
        self.assertEqual(r.status_code, 403)

    def test_27_procesar_inexistente_404(self):
        self.assertEqual(self.app.post('/api/devoluciones/1/procesar', headers=self.admin).status_code, 404)

    def test_28_repetir_aplicada_409(self):
        self._crear()
        self.app.post('/api/devoluciones/1/procesar', headers=self.admin)
        self.assertEqual(self.app.post('/api/devoluciones/1/procesar', headers=self.admin).status_code, 409)

    def test_29_falla_stock_mantiene_pendiente(self):
        self._crear(PROVEEDOR)
        self.inv.movimiento.side_effect = ErrorApi(409, 'STOCK_INSUFICIENTE', 'Falta stock')
        r = self.app.post('/api/devoluciones/1/procesar', headers=self.admin)
        self.assertEqual(r.status_code, 409)
        self.assertEqual(self.repo.obtener(1)['estado_inventario'], 'PENDIENTE')

    def test_30_falla_503_mantiene_pendiente(self):
        self._crear()
        self.inv.movimiento.side_effect = ErrorApi(503, 'SERVICIO_NO_DISPONIBLE', 'Inventario caido')
        r = self.app.post('/api/devoluciones/1/procesar', headers=self.admin)
        self.assertEqual(r.status_code, 503)
        self.assertEqual(self.repo.obtener(1)['estado_inventario'], 'PENDIENTE')

    def test_31_reintenta_con_mismo_operacion_id(self):
        self._crear()
        op_id = self.repo.obtener(1)['detalles'][0]['operacion_id']
        self.inv.movimiento.side_effect = [ErrorApi(503, 'CAIDO', 'caido'), None]
        self.app.post('/api/devoluciones/1/procesar', headers=self.admin)
        r = self.app.post('/api/devoluciones/1/procesar', headers=self.admin)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.inv.movimiento.call_args_list[0].args[1]['operacion_id'], op_id)
        self.assertEqual(self.inv.movimiento.call_args_list[1].args[1]['operacion_id'], op_id)

    def test_32_correlation_id(self):
        r = self.app.get('/api/devoluciones', headers=self.lectura)
        self.assertEqual(r.headers['X-Correlation-ID'], 'correlacion-12345')

    def test_33_formato_error(self):
        r = self.app.get('/api/devoluciones/999', headers=self.lectura)
        self.assertEqual(set(r.json), {'codigo', 'mensaje', 'detalles', 'correlation_id'})

    def test_34_documentacion_con_token(self):
        r = self.app.get('/openapi.yaml', headers=self.admin)
        self.assertEqual(r.status_code, 200)
        self.assertIn('openapi: 3.0.3', r.data.decode())

    def test_35_documentacion_protegida(self):
        self.assertEqual(self.app.get('/openapi.yaml').status_code, 401)

    def test_36_marcar_aplicada_falla_concurrencia(self):
        self._crear()
        self.repo.marca_error = True
        self.assertEqual(self.app.post('/api/devoluciones/1/procesar', headers=self.admin).status_code, 409)


class TestClienteInventario(unittest.TestCase):
    def setUp(self):
        self.cfg = {'internal_token': 'clave', 'url_inventario': 'http://inventario:3004',
                    'timeout_seg': 3, 'reintentos': 1}
        self.dev = {'id': 8, 'tipo': 'CLIENTE', 'motivo': 'Devolucion', 'bodega_id': 2, 'documento_ref': None}
        self.linea = {'operacion_id': '123e4567-e89b-12d3-a456-426614174000', 'producto_id': 9, 'cantidad': 2}

    def test_37_llamada_entrada_interna(self):
        f = Mock(return_value=(201, {'mensaje': 'OK'}))
        ClienteInventario(self.cfg, solicitar=f).movimiento(self.dev, self.linea, 'correlacion-123')
        url, body, headers, timeout = f.call_args.args
        self.assertEqual(url, 'http://inventario:3004/api/inventario/entradas')
        self.assertEqual(body['origen_movimiento'], 'DEVOLUCION')
        self.assertEqual(body['operacion_id'], self.linea['operacion_id'])
        self.assertEqual(body['bodega_destino_id'], 2)
        self.assertNotIn('X-User-Role', headers)
        self.assertEqual(headers['X-Correlation-ID'], 'correlacion-123')

    def test_38_llamada_salida_proveedor(self):
        f = Mock(return_value=(201, {}))
        ClienteInventario(self.cfg, solicitar=f).movimiento({**self.dev, 'tipo': 'PROVEEDOR'}, self.linea, 'correlacion-123')
        self.assertIn('/salidas', f.call_args.args[0])
        self.assertEqual(f.call_args.args[1]['bodega_origen_id'], 2)

    def test_39_inventario_operacion_repetida(self):
        f = Mock(return_value=(200, {}))
        ClienteInventario(self.cfg, solicitar=f).movimiento(self.dev, self.linea, 'correlacion-123')
        self.assertEqual(f.call_count, 1)

    def test_40_inventario_conflicto(self):
        f = Mock(return_value=(409, {'codigo': 'STOCK_INSUFICIENTE', 'mensaje': 'Falta stock'}))
        with self.assertRaises(ErrorApi) as cm:
            ClienteInventario(self.cfg, solicitar=f).movimiento(self.dev, self.linea, 'correlacion-123')
        self.assertEqual((cm.exception.status, cm.exception.codigo), (409, 'STOCK_INSUFICIENTE'))

    def test_41_inventario_validacion(self):
        f = Mock(return_value=(422, {'codigo': 'PRODUCTO_INEXISTENTE', 'mensaje': 'No existe'}))
        with self.assertRaises(ErrorApi) as cm:
            ClienteInventario(self.cfg, solicitar=f).movimiento(self.dev, self.linea, 'correlacion-123')
        self.assertEqual(cm.exception.status, 422)

    def test_42_reintenta_error_transitorio(self):
        f = Mock(side_effect=[OSError('down'), (201, {})])
        sleep = Mock()
        ClienteInventario(self.cfg, solicitar=f, dormir=sleep).movimiento(self.dev, self.linea, 'correlacion-123')
        self.assertEqual(f.call_count, 2)
        sleep.assert_called_once()

    def test_43_reintenta_5xx_y_devuelve_503(self):
        f = Mock(return_value=(503, {}))
        with self.assertRaises(ErrorApi) as cm:
            ClienteInventario(self.cfg, solicitar=f, dormir=lambda _: None).movimiento(self.dev, self.linea, 'correlacion-123')
        self.assertEqual(cm.exception.status, 503)
        self.assertEqual(f.call_count, 2)


class TestValidaciones(unittest.TestCase):
    def test_44_cliente_sin_proveedor(self):
        self.assertIsNone(registro(CLIENTE)['proveedor_id'])

    def test_45_proveedor_sin_condicion(self):
        self.assertIsNone(registro(PROVEEDOR)['detalles'][0]['condicion'])

    def test_46_fecha_desde_hasta(self):
        x = filtros({'desde': '2026-11-01', 'hasta': '2026-11-21'})
        self.assertLess(x['desde'], x['hasta'])

    def test_47_fechas_invalidas(self):
        with self.assertRaises(ErrorApi):
            filtros({'desde': '2026-11-99'})

    def test_48_hasta_antes_desde(self):
        with self.assertRaises(ErrorApi):
            filtros({'desde': '2026-11-21', 'hasta': '2026-11-01'})

    def test_49_filtro_tipo_invalido(self):
        with self.assertRaises(ErrorApi):
            filtros({'tipo': 'OTRO'})

    def test_50_paginacion(self):
        self.assertEqual(filtros({'page': '3', 'limit': '10'})['page'], 3)


if __name__ == '__main__':
    unittest.main()
