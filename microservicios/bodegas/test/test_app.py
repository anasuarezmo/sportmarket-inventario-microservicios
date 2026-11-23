"""Pruebas de contrato y autorizacion SIN requerir MySQL, con acceso simulado a repositorio.

La integracion real con MySQL y Gateway se prueba por separado en Ubuntu.
"""
import os
import unittest
from unittest.mock import patch

from app import app

BODEGA = {"id": 1, "codigo": "BOD-01", "nombre": "Central", "direccion": "Calle 1",
          "ciudad": "Manizales", "bodega_activa": 1}
UBICACION = {"id": 2, "bodega_id": 1, "codigo": "A1", "descripcion": "Pasillo A",
             "ubicacion_activa": 1}


class PruebasBodegas(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.env = patch.dict(os.environ, {"INTERNAL_TOKEN": "token-de-prueba"})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.headers = {"X-Internal-Token": "token-de-prueba", "X-Correlation-ID": "cid-bodegas-123456",
                        "X-User-Role": "ADM"}
        self.read = patch("app.db_uno", side_effect=self.fake_read)
        self.list = patch("app.db_todos", side_effect=self.fake_list)
        self.write = patch("app.db_escribir", return_value=(2, 1))
        self.read.start()
        self.list.start()
        self.write.start()
        self.addCleanup(self.read.stop)
        self.addCleanup(self.list.stop)
        self.addCleanup(self.write.stop)

    @staticmethod
    def fake_read(sql, parametros=()):
        if "COUNT(*)" in sql:
            return {"total": 1}
        if "FROM ubicacion" in sql:
            return UBICACION.copy()
        if "FROM bodega" in sql:
            return BODEGA.copy()
        raise AssertionError(f"Consulta no esperada: {sql}")

    @staticmethod
    def fake_list(sql, parametros=()):
        if "FROM ubicacion" in sql:
            return [UBICACION.copy()]
        if "FROM bodega" in sql:
            return [BODEGA.copy()]
        raise AssertionError(f"Consulta no esperada: {sql}")

    def llamar(self, verbo, ruta, body=None, headers=None):
        kw = {"headers": self.headers if headers is None else headers}
        if body is not None:
            kw["json"] = body
        return self.client.open(ruta, method=verbo, **kw)

    def test_00_salud_publica(self):
        self.assertEqual(self.client.get("/health").json, {"estado": "UP"})

    def test_01_rechaza_sin_token(self):
        r = self.llamar("GET", "/api/bodegas/1", headers={})
        self.assertEqual(r.status_code, 401)
        self.assertEqual(r.json["codigo"], "NO_AUTENTICADO")

    def test_02_rol_consulta_no_puede_escribir(self):
        h = {**self.headers, "X-User-Role": "CON"}
        r = self.llamar("POST", "/api/bodegas", {"codigo": "B2"}, headers=h)
        self.assertEqual(r.status_code, 403)

    def test_03_listar_bodegas(self):
        r = self.llamar("GET", "/api/bodegas?ciudad=Manizales&bodega_activa=true&page=1&limit=5")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(set(r.json), {"items", "total", "page", "limit"})
        self.assertTrue(r.json["items"][0]["bodega_activa"])

    def test_04_crear_bodega(self):
        r = self.llamar("POST", "/api/bodegas", {"codigo": "BOD-02", "nombre": "Auxiliar",
                                                "direccion": "Calle 2", "ciudad": "Manizales"})
        self.assertEqual(r.status_code, 201)
        self.assertIn("bodega", r.json)

    def test_05_consultar_bodega(self):
        r = self.llamar("GET", "/api/bodegas/1")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json["id"], 1)
        self.assertEqual(r.headers["X-Correlation-ID"], "cid-bodegas-123456")

    def test_06_actualizar_bodega(self):
        r = self.llamar("PUT", "/api/bodegas/1", {"codigo": "BOD-01", "nombre": "Otro",
                                                   "direccion": "Calle 3", "ciudad": "Pereira"})
        self.assertEqual(r.status_code, 200)
        self.assertIn("bodega", r.json)

    def test_07_estado_bodega(self):
        r = self.llamar("PATCH", "/api/bodegas/1/estado", {"bodega_activa": False})
        self.assertEqual(r.status_code, 200)

    def test_08_listar_ubicaciones(self):
        r = self.llamar("GET", "/api/bodegas/1/ubicaciones")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.json["items"]), 1)

    def test_09_crear_ubicacion(self):
        r = self.llamar("POST", "/api/bodegas/1/ubicaciones", {"codigo": "B2", "descripcion": "Estante"})
        self.assertEqual(r.status_code, 201)

    def test_10_actualizar_ubicacion(self):
        r = self.llamar("PUT", "/api/bodegas/1/ubicaciones/2", {"codigo": "A2", "descripcion": "Pasillo"})
        self.assertEqual(r.status_code, 200)

    def test_11_estado_ubicacion(self):
        r = self.llamar("PATCH", "/api/bodegas/1/ubicaciones/2/estado", {"ubicacion_activa": False})
        self.assertEqual(r.status_code, 200)

    @patch("app.pedir_existencias", return_value={"items": [], "total": 0, "page": 1, "limit": 20})
    def test_12_existencias_usa_inventario(self, mock_inv):
        r = self.llamar("GET", "/api/bodegas/1/existencias?producto_id=4")
        self.assertEqual(r.status_code, 200)
        mock_inv.assert_called_once_with(1, 4)

    def test_13_validacion_paginacion(self):
        r = self.llamar("GET", "/api/bodegas?page=0")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json["detalles"][0]["campo"], "page")

    def test_14_estado_debe_ser_booleano(self):
        r = self.llamar("PATCH", "/api/bodegas/1/estado", {"bodega_activa": "false"})
        self.assertEqual(r.status_code, 400)

    @patch("app.obtener_bodega", return_value=None)
    def test_15_bodega_que_no_existe(self, _):
        r = self.llamar("GET", "/api/bodegas/999")
        self.assertEqual(r.status_code, 404)

    @patch("app.pedir_existencias", return_value=None)
    def test_16_inventario_caido(self, _):
        r = self.llamar("GET", "/api/bodegas/1/existencias")
        self.assertEqual(r.status_code, 503)

    def test_17_documentacion_con_token(self):
        r = self.llamar("GET", "/openapi.yaml")
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"/api/bodegas", r.data)

    def test_18_falta_campo(self):
        r = self.llamar("POST", "/api/bodegas", {"codigo": "BOD-02"})
        self.assertEqual(r.status_code, 400)


if __name__ == "__main__":
    unittest.main()
