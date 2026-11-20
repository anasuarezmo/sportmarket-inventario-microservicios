"""Capa MySQL probada con una conexion falsa (el SQL real se verifica contra MySQL en la maquina del equipo) y adaptador Flask."""
import os
import sys
import types
import unittest
from datetime import datetime

try:
    import pymysql  # noqa: F401
except ImportError:  # entorno sin PyMySQL: un reemplazo minimo basta para estas pruebas
    m = types.ModuleType("pymysql")
    m.__path__ = []
    m.err = types.ModuleType("pymysql.err")
    m.err.IntegrityError = type("IntegrityError", (Exception,), {})
    m.cursors = types.ModuleType("pymysql.cursors")
    m.cursors.DictCursor = object
    m.connect = None
    sys.modules.update({"pymysql": m, "pymysql.err": m.err, "pymysql.cursors": m.cursors})

import pymysql as _pm  # noqa: E402
from app.app import crear_app  # noqa: E402
from app.repositorio import crear_repositorio  # noqa: E402
from test.ayudas import CONFIG, H_GATEWAY, H_INTERNO, ClientesFalsos, RepoFalso  # noqa: E402


class CursorFalso:
    def __init__(self, con):
        self.con, self.rowcount, self.lastrowid = con, 1, 5

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql, params=()):
        self.con.sqls.append((" ".join(sql.split()), list(params)))
        if self.con.fallar_insert and sql.lstrip().startswith("INSERT"):
            raise _pm.err.IntegrityError(1062, "Duplicate entry")

    def fetchone(self):
        return self.con.respuestas.pop(0) if self.con.respuestas else None

    def fetchall(self):
        return self.con.respuestas.pop(0)


class ConexionFalsa:
    def __init__(self, respuestas=None, fallar_insert=False):
        self.sqls, self.respuestas, self.fallar_insert, self.cerrada = [], list(respuestas or []), fallar_insert, False

    def cursor(self):
        return CursorFalso(self)

    def close(self):
        self.cerrada = True


FILA = {"id": 1, "producto_id": 2, "bodega_id": 1, "cantidad_disponible_al_generar": 3, "stock_minimo": 5, "estado_alerta": "ACTIVA",
        "fecha_generacion_alerta": datetime(2026, 11, 20, 10, 0, 0), "atendida_en": None, "usuario_atencion_id": None}


class PruebasRepositorio(unittest.TestCase):
    def repo(self, con):
        return crear_repositorio({}, conectar=lambda: con)

    def test_crear_activa_inserta_y_devuelve_fechas_iso(self):
        con = ConexionFalsa([dict(FILA)])
        alerta, creada = self.repo(con).crear_activa(2, 1, 3, 5)
        self.assertTrue(creada)
        self.assertIn("INSERT INTO alerta", con.sqls[0][0])
        self.assertEqual(con.sqls[0][1], [2, 1, 3, 5])
        self.assertEqual(alerta["fecha_generacion_alerta"], "2026-11-20T10:00:00Z")
        self.assertTrue(con.cerrada)

    def test_crear_activa_duplicada_devuelve_la_existente(self):
        con = ConexionFalsa([dict(FILA)], fallar_insert=True)
        alerta, creada = self.repo(con).crear_activa(2, 1, 3, 5)
        self.assertFalse(creada)
        self.assertEqual(alerta["id"], 1)
        self.assertIn("estado_alerta = 'ACTIVA'", con.sqls[1][0])

    def test_cerrar_activa_sin_alerta_devuelve_none(self):
        self.assertIsNone(self.repo(ConexionFalsa([None])).cerrar_activa(2, 1))

    def test_cerrar_activa_deja_usuario_nulo(self):
        con = ConexionFalsa([dict(FILA), {**FILA, "estado_alerta": "ATENDIDA"}])
        self.assertEqual(self.repo(con).cerrar_activa(2, 1)["estado_alerta"], "ATENDIDA")
        self.assertIn("usuario_atencion_id = NULL", con.sqls[1][0])

    def test_atender_un_solo_update_condicionado(self):
        con = ConexionFalsa([dict(FILA)])
        res, _ = self.repo(con).atender(1, 7)
        self.assertEqual(res, "ok")
        self.assertIn("WHERE id = %s AND estado_alerta = 'ACTIVA'", con.sqls[0][0])
        self.assertEqual(con.sqls[0][1], [7, 1])

    def test_atender_ya_atendida_y_no_existe(self):
        con = ConexionFalsa([dict(FILA)])
        con_cur = con.cursor
        con.cursor = lambda: _sin_cambio(con_cur())
        self.assertEqual(self.repo(con).atender(1, 7)[0], "ya_atendida")
        self.assertEqual(self.repo(ConexionFalsa([None])).atender(9, 7), ("no_existe", None))

    def test_listar_arma_filtros_y_paginacion(self):
        con = ConexionFalsa([{"n": 1}, [dict(FILA)]])
        filas, total = self.repo(con).listar({"estado_alerta": "ACTIVA", "producto_id": 2, "bodega_id": None, "page": 3, "limit": 10})
        self.assertEqual(total, 1)
        self.assertIn("WHERE estado_alerta = %s AND producto_id = %s", con.sqls[0][0])
        self.assertIn("ORDER BY id DESC LIMIT %s OFFSET %s", con.sqls[1][0])
        self.assertEqual(con.sqls[1][1], ["ACTIVA", 2, 10, 20])

    def test_esquema_sin_comentarios_ni_vacios(self):
        con = ConexionFalsa()
        self.repo(con).aplicar_esquema(os.path.join(os.path.dirname(__file__), "..", "sql", "schema.sql"), intentos=1)
        self.assertEqual(len(con.sqls), 1)
        self.assertTrue(con.sqls[0][0].startswith("CREATE TABLE IF NOT EXISTS alerta"))
        self.assertIn("uq_alerta_activa", con.sqls[0][0])


def _sin_cambio(cur):
    cur.rowcount = 0
    return cur


class PruebasFlask(unittest.TestCase):
    def setUp(self):
        self.c = crear_app(CONFIG, RepoFalso(), ClientesFalsos().dic()).test_client()

    def test_health_docs_y_openapi(self):
        r = self.c.get("/health")
        self.assertEqual((r.status_code, r.get_json()), (200, {"estado": "UP", "servicio": "reportes"}))
        self.assertIn("swagger", self.c.get("/docs").get_data(as_text=True).lower())
        o = self.c.get("/openapi.yaml")
        self.assertEqual(o.status_code, 200)
        self.assertIn("/api/alertas", o.get_data(as_text=True))

    def test_sin_token_401_con_correlation_id(self):
        r = self.c.get("/api/alertas")
        self.assertEqual(r.status_code, 401)
        self.assertEqual(r.get_json()["correlation_id"], r.headers["X-Correlation-ID"])

    def test_flujo_completo_por_http(self):
        r = self.c.post("/api/interno/alertas/stock", headers=H_INTERNO, json={"evento": "STOCK_BAJO", "producto_id": 2, "bodega_id": 1,
                                                                           "cantidad_disponible": 3, "stock_minimo": 5})
        self.assertEqual(r.status_code, 201)
        r = self.c.get("/api/alertas?estado_alerta=ACTIVA", headers=H_GATEWAY)
        self.assertEqual(r.get_json()["total"], 1)
        r = self.c.patch("/api/alertas/1/estado", headers=H_GATEWAY, json={"estado_alerta": "ATENDIDA"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.c.get("/api/reportes/dashboard", headers=H_GATEWAY).get_json()["alertas_activas"], 0)

    def test_json_invalido_400(self):
        r = self.c.post("/api/interno/alertas/stock", headers={**H_INTERNO, "Content-Type": "application/json"}, data="{no es json")
        self.assertEqual((r.status_code, r.get_json()["codigo"]), (400, "PETICION_INVALIDA"))


if __name__ == "__main__":
    unittest.main()
