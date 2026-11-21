import os
import unittest
from unittest.mock import patch
from compras_api import servicio, integraciones
from compras_api.errores import ErrorApi

class RecepcionesTest(unittest.TestCase):
    def setUp(self):
        self.rec = {'id':7, 'orden_id':15, 'estado':'PENDIENTE_DE_SINCRONIZAR',
                    'detalles':[{'id':81,'operacion_id':'abc-123','orden_detalle_id':31,'cantidad_recibida':5,'aplicada':False}]}
        self.orden = {'numero':'OC-0015','bodega_destino_id':2,'detalles':[{'id':31,'producto_id':3}]}

    @patch('compras_api.servicio.repo.fijar_estado_recepcion')
    @patch('compras_api.servicio.repo.aplicar_linea')
    @patch('compras_api.servicio.registrar_entrada',return_value=(201,{}))
    @patch('compras_api.servicio.repo.orden')
    @patch('compras_api.servicio.repo.recepcion')
    def test_recepcion_sincronizada(self, r,o,envio,aplicar,estado):
        r.return_value=self.rec;o.return_value=self.orden;estado.return_value={'estado':'SINCRONIZADA'}
        resultado=servicio.sincronizar_recepcion(7,'cid123456')
        self.assertEqual(resultado['estado'],'SINCRONIZADA')
        self.assertEqual(envio.call_args.args[:4],('abc-123',3,2,5))
        aplicar.assert_called_once_with(81)

    @patch('compras_api.servicio.repo.fijar_estado_recepcion')
    @patch('compras_api.servicio.repo.aplicar_linea')
    @patch('compras_api.servicio.registrar_entrada',side_effect=ErrorApi(503,'FALLA','Sin inventario'))
    @patch('compras_api.servicio.repo.orden')
    @patch('compras_api.servicio.repo.recepcion')
    def test_recepcion_pendiente(self,r,o,envio,aplicar,estado):
        r.return_value=self.rec;o.return_value=self.orden;estado.return_value={'estado':'PENDIENTE_DE_SINCRONIZAR'}
        servicio.sincronizar_recepcion(7,'cid123456')
        aplicar.assert_not_called()
        estado.assert_called_once_with(7,'PENDIENTE_DE_SINCRONIZAR')

    @patch('compras_api.servicio.repo.fijar_estado_recepcion')
    @patch('compras_api.servicio.repo.aplicar_linea')
    @patch('compras_api.servicio.registrar_entrada',return_value=(422,{}))
    @patch('compras_api.servicio.repo.orden')
    @patch('compras_api.servicio.repo.recepcion')
    def test_recepcion_rechazada(self,r,o,envio,aplicar,estado):
        r.return_value=self.rec;o.return_value=self.orden;estado.return_value={'estado':'RECHAZADA'}
        servicio.sincronizar_recepcion(7,'cid123456')
        aplicar.assert_not_called()
        estado.assert_called_once_with(7,'RECHAZADA')

    @patch('compras_api.servicio.repo.recepcion')
    def test_recepcion_reintento_no_vuelve_a_enviar_si_ya_sincronizada(self,r):
        r.return_value={**self.rec,'estado':'SINCRONIZADA'}
        self.assertEqual(servicio.sincronizar_recepcion(7,'cid123456')['estado'],'SINCRONIZADA')

    @patch('compras_api.integraciones.time.sleep')
    @patch('compras_api.integraciones.requests.request')
    def test_retry_preserva_identificador(self,r,sleep):
        class Res:
            status_code=201
            def json(self): return {'mensaje':'ok'}
        import requests
        r.side_effect=[requests.Timeout(),Res()]
        with patch.dict(os.environ,{'INTERNAL_TOKEN':'prueba','URL_INVENTARIO':'http://inv:3004'}):
            code,_=integraciones.registrar_entrada('uuid-demo',3,2,5,'OC-0015','cid123456')
        self.assertEqual(code,201)
        payload1=r.call_args_list[0].kwargs['json']
        payload2=r.call_args_list[1].kwargs['json']
        self.assertEqual(payload1,payload2)
        self.assertEqual(payload1['operacion_id'],'uuid-demo')
        self.assertNotIn('X-User-Role',r.call_args_list[0].kwargs['headers'])

    @patch('compras_api.integraciones.requests.request')
    def test_inventario_rechazo_no_reintenta(self,r):
        class Res:
            status_code=422
            def json(self): return {'codigo':'INVALIDO'}
        r.return_value=Res()
        with patch.dict(os.environ,{'INTERNAL_TOKEN':'prueba','URL_INVENTARIO':'http://inv:3004'}):
            code,_=integraciones.registrar_entrada('uuid-demo',3,2,5,'OC-0015','cid123456')
        self.assertEqual(code,422)
        self.assertEqual(r.call_count,1)
