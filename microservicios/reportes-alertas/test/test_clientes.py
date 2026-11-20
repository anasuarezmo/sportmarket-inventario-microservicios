import json
import unittest

from app.clientes import crear_clientes
from app.errores import ErrorApi

CFG = {"token_interno": "tk", "timeout": 1, "reintentos": 3, "urls": {"inventario": "http://inv", "catalogo": "http://cat"}}


class PruebasClientes(unittest.TestCase):
    def crear(self, guion):
        self.urls, self.esperas, self.cabeceras = [], [], []

        def http(url, headers, timeout):
            self.urls.append(url)
            self.cabeceras.append(headers)
            r = guion.pop(0)
            if isinstance(r, Exception):
                raise r
            return r

        return crear_clientes(CFG, http=http, esperar=self.esperas.append)

    def pagina(self, items, total, page=1):
        return 200, json.dumps({"items": items, "total": total, "page": page, "limit": 100})

    def test_envia_token_interno_y_correlation_id(self):
        c = self.crear([self.pagina([], 0)])
        c["existencias"]("cid-12345678")
        self.assertEqual(self.cabeceras[0]["X-Internal-Token"], "tk")
        self.assertEqual(self.cabeceras[0]["X-Correlation-ID"], "cid-12345678")
        self.assertNotIn("X-User-Role", self.cabeceras[0])  # llamada entre servicios: sin rol de usuario

    def test_recorre_todas_las_paginas(self):
        c = self.crear([self.pagina([{"a": 1}] * 100, 150, 1), self.pagina([{"a": 2}] * 50, 150, 2)])
        self.assertEqual(len(c["existencias"]("c")), 150)
        self.assertIn("page=1&limit=100", self.urls[0])
        self.assertIn("page=2&limit=100", self.urls[1])

    def test_filtros_en_la_url(self):
        c = self.crear([self.pagina([], 0), self.pagina([], 0), self.pagina([], 0)])
        c["existencias"]("c", 2)
        c["salidas"]("2026-11-01", "2026-11-20", "c")
        c["productos"]("c", 5)
        self.assertIn("/api/inventario/existencias?bodega_id=2", self.urls[0])
        self.assertIn("tipo_movimiento=SALIDA", self.urls[1])
        self.assertIn("desde=2026-11-01", self.urls[1])
        self.assertIn("hasta=2026-11-20", self.urls[1])
        self.assertTrue(self.urls[2].startswith("http://cat/api/productos?categoria_id=5"))

    def test_reintenta_con_espera_creciente_y_se_recupera(self):
        c = self.crear([OSError("red"), (500, "x"), self.pagina([{"a": 1}], 1)])
        self.assertEqual(len(c["existencias"]("c")), 1)
        self.assertEqual(self.esperas, [0.2, 0.4])

    def test_tres_reintentos_y_503(self):
        c = self.crear([OSError("a")] * 4)
        with self.assertRaises(ErrorApi) as e:
            c["existencias"]("c")
        self.assertEqual((e.exception.status, e.exception.codigo), (503, "SERVICIO_NO_DISPONIBLE"))
        self.assertEqual(len(self.urls), 4)
        self.assertEqual(self.esperas, [0.2, 0.4, 0.8])

    def test_respuesta_inesperada_o_formato_viejo_503(self):
        for resp in ((404, "{}"), (200, "no es json"), (200, json.dumps({"datos": [], "total": 0}))):
            c = self.crear([resp])
            with self.assertRaises(ErrorApi) as e:
                c["productos"]("c")
            self.assertEqual(e.exception.status, 503)


if __name__ == "__main__":
    unittest.main()
