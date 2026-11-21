import unittest
from decimal import Decimal
from compras_api.errores import ErrorApi
from compras_api import validaciones as v

class ValidacionesTest(unittest.TestCase):
    def error(self, funcion, *args):
        with self.assertRaises(ErrorApi): funcion(*args)

    def test_entero(self): self.assertEqual(v.entero('3','id'),3)
    def test_entero_cero(self): self.error(v.entero,0,'id')
    def test_entero_bool(self): self.error(v.entero,True,'id')
    def test_entero_float(self): self.error(v.entero,1.3,'id')
    def test_texto(self): self.assertEqual(v.texto('  valor  ','x'),'valor')
    def test_texto_vacio(self): self.error(v.texto,'','x')
    def test_texto_maximo(self): self.error(v.texto,'a'*160,'x')
    def test_booleano(self): self.assertTrue(v.booleano(True,'activo'))
    def test_booleano_invalido(self): self.error(v.booleano,1,'activo')
    def test_costo_decimal(self): self.assertEqual(v.costo('1.20','costo'),Decimal('1.20'))
    def test_costo_cero(self): self.assertEqual(v.costo(0,'costo'),Decimal('0'))
    def test_costo_negativo(self): self.error(v.costo,-1,'costo')
    def test_costo_tres_decimales(self): self.error(v.costo,'1.999','costo')
    def test_costo_nan(self): self.error(v.costo,'NaN','costo')
    def test_email(self): self.assertEqual(v.email('a@b.co'),'a@b.co')
    def test_email_invalido(self): self.error(v.email,'sin-arroba')
    def test_paginacion(self): self.assertEqual(v.paginar({'page':'2','limit':'5'}),(2,5))
    def test_paginacion_maximo(self): self.error(v.paginar,{'limit':'101'})
    def test_fecha_iso(self): self.assertEqual(v.fecha_iso('2026-11-21','desde').year,2026)
    def test_fecha_invalida(self): self.error(v.fecha_iso,'ayer','desde')
    def test_proveedor_correcto(self):
        self.assertEqual(v.datos_proveedor({'nit':'9001','razon_social':'Almacen'})['nit'],'9001')
    def test_proveedor_sin_nit(self): self.error(v.datos_proveedor,{'razon_social':'A'})
    def test_proveedor_parcial(self):
        self.assertEqual(v.datos_proveedor({'telefono':'123'},True),{'telefono':'123'})
    def test_orden(self):
        data={'proveedor_id':1,'bodega_destino_id':2,'detalles':[{'producto_id':1,'cantidad_solicitada':3,'costo_unitario':'25.50'}]}
        p,b,ds=v.validar_detalles_orden(data)
        self.assertEqual((p,b,ds[0]['cantidad_solicitada']), (1,2,3))
    def test_orden_sin_lineas(self): self.error(v.validar_detalles_orden,{'proveedor_id':1,'bodega_destino_id':2,'detalles':[]})
    def test_orden_linea_repetida(self):
        d={'producto_id':1,'cantidad_solicitada':1,'costo_unitario':4}
        self.error(v.validar_detalles_orden, {'proveedor_id':1,'bodega_destino_id':2,'detalles':[d,d]})
    def test_orden_cantidad_negativa(self):
        self.error(v.validar_detalles_orden,{'proveedor_id':1,'bodega_destino_id':2,'detalles':[{'producto_id':1,'cantidad_solicitada':-1,'costo_unitario':4}]})
    def test_recepcion_valida(self):
        self.assertEqual(v.validar_recepcion({'detalles':[{'orden_detalle_id':3,'cantidad_recibida':2}]}),[{'orden_detalle_id':3,'cantidad_recibida':2}])
    def test_recepcion_linea_repetida(self):
        d={'orden_detalle_id':3,'cantidad_recibida':2}
        self.error(v.validar_recepcion,{'detalles':[d,d]})
    def test_recepcion_cantidad_cero(self):
        self.error(v.validar_recepcion,{'detalles':[{'orden_detalle_id':1,'cantidad_recibida':0}]})
    def test_recepcion_vacia(self): self.error(v.validar_recepcion,{'detalles':[]})
