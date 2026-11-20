import unittest
from datetime import datetime, timezone

from app.cache import Cache
from app.manejador import crear_manejador
from app.servicio import crear_servicio
from test.ayudas import CONFIG, H_GATEWAY, ClientesFalsos, RepoFalso, peticion


def ahora():
    return datetime(2026, 11, 20, 15, 0, 0, tzinfo=timezone.utc)


class PruebasInformes(unittest.TestCase):
    def setUp(self):
        self.clientes = ClientesFalsos()
        self.repo = RepoFalso()
        self.m = crear_manejador(CONFIG, self.repo, self.clientes.dic(), ahora=ahora)

    def get(self, ruta, q=None, rol="ADM"):
        return self.m(peticion("GET", ruta, {**H_GATEWAY, "X-User-Role": rol}, q))

    def test_inventario_incluye_codigo_nombre_bodega_cantidad(self):
        r = self.get("/api/reportes/inventario")
        self.assertEqual(r["status"], 200)
        self.assertEqual(r["cuerpo"]["total"], 3)
        self.assertEqual(r["cuerpo"]["items"][0], {"producto_id": 1, "codigo_producto": "FUT001", "nombre_producto": "Balon futbol",
                                                   "bodega_id": 1, "cantidad_disponible": 10})
        self.assertEqual(r["cuerpo"]["generado_en"], "2026-11-20T15:00:00Z")

    def test_inventario_filtros_bodega_y_categoria(self):
        self.assertEqual(self.get("/api/reportes/inventario", {"bodega_id": "2"})["cuerpo"]["total"], 1)
        r = self.get("/api/reportes/inventario", {"categoria_id": "1"})
        self.assertEqual([i["producto_id"] for i in r["cuerpo"]["items"]], [2])

    def test_valorizacion_precio_de_venta_por_producto_y_total(self):
        r = self.get("/api/reportes/valorizacion")
        c = r["cuerpo"]
        self.assertEqual([(i["producto_id"], i["cantidad_disponible"], i["valor"]) for i in c["items"]], [(1, 15, 15000), (2, 4, 10002.0)])
        self.assertEqual(c["valor_total"], 25002.0)
        self.assertIn("precio de venta", c["descripcion"])
        self.assertEqual(self.get("/api/reportes/valorizacion", {"categoria_id": "2"})["cuerpo"]["valor_total"], 15000)

    def test_rotacion_solo_cuenta_salidas_y_no_traslados(self):  # CA-07
        r = self.get("/api/reportes/rotacion", {"desde": "2026-11-01", "hasta": "2026-11-20", "limite": "2"})
        c = r["cuerpo"]
        self.assertEqual([(x["producto_id"], x["unidades_salida"]) for x in c["mayor_rotacion"]], [(2, 8), (1, 5)])
        # menor rotacion: productos activos, incluidos los que no tuvieron salidas (3 -> 0)
        self.assertEqual([(x["producto_id"], x["unidades_salida"]) for x in c["menor_rotacion"]], [(3, 0), (1, 5)])
        # Inventario se consulta solo por SALIDA: el traslado de 99 unidades nunca cuenta como demanda
        self.assertTrue(all(n != "movimientos" for n, _ in self.clientes.llamadas))

    def test_rotacion_por_defecto_ultimos_30_dias(self):
        self.get("/api/reportes/rotacion")
        llamada = [x for x in self.clientes.llamadas if x[0] == "salidas"][0]
        self.assertEqual(llamada[1], ("2026-10-21", "2026-11-20"))

    def test_resumen_movimientos_traslados_aparte(self):
        r = self.get("/api/reportes/movimientos", {"desde": "2026-11-01", "hasta": "2026-11-20"})
        res = r["cuerpo"]["resumen"]
        self.assertEqual(res["SALIDA"], {"movimientos": 3, "unidades": 13})
        self.assertEqual(res["ENTRADA"], {"movimientos": 1, "unidades": 20})
        self.assertEqual(res["TRASLADO"], {"movimientos": 1, "unidades": 99})
        self.assertEqual(res["AJUSTE"], {"movimientos": 1, "unidades": 1})

    def test_periodo_invalido_400(self):
        for ruta in ("/api/reportes/rotacion", "/api/reportes/movimientos"):
            self.assertEqual(self.get(ruta, {"desde": "2026-11-20", "hasta": "2026-11-01"})["status"], 400)
            self.assertEqual(self.get(ruta, {"desde": "ayer"})["status"], 400)
        self.assertEqual(self.get("/api/reportes/rotacion", {"limite": "0"})["status"], 400)
        self.assertEqual(self.get("/api/reportes/inventario", {"bodega_id": "x"})["status"], 400)

    def test_dashboard(self):
        self.repo.crear_activa(2, 1, 1, 5)
        r = self.get("/api/reportes/dashboard")
        c = r["cuerpo"]
        self.assertEqual(c["valor_total_inventario"], 25002.0)
        self.assertEqual(c["productos_en_quiebre"], 1)  # solo el producto 3 esta activo y sin existencias (el 4 esta inactivo)
        self.assertEqual(c["alertas_activas"], 1)
        self.assertEqual(c["mayor_rotacion"][0], {"producto_id": 2, "nombre_producto": "Balon baloncesto", "unidades_salida": 8})
        self.assertEqual(set(c["menor_rotacion"][0]), {"producto_id", "nombre_producto", "unidades_salida"})

    def test_dashboard_todos_los_roles_y_reportes_no_para_bodega(self):
        self.assertEqual(self.get("/api/reportes/dashboard", rol="BOD")["status"], 200)
        for ruta in ("inventario", "valorizacion", "rotacion", "movimientos"):
            self.assertEqual(self.get(f"/api/reportes/{ruta}", rol="BOD")["status"], 403, ruta)
            self.assertEqual(self.get(f"/api/reportes/{ruta}", rol="CON")["status"], 200, ruta)

    def test_servicio_caido_503(self):
        m = crear_manejador(CONFIG, self.repo, ClientesFalsos(caido=True).dic())
        for ruta in ("inventario", "valorizacion", "rotacion", "movimientos", "dashboard"):
            r = m(peticion("GET", f"/api/reportes/{ruta}", H_GATEWAY))
            self.assertEqual((r["status"], r["cuerpo"]["codigo"]), (503, "SERVICIO_NO_DISPONIBLE"), ruta)

    def test_cache_reutiliza_y_caduca(self):
        t = [0.0]
        cache = Cache(30, reloj=lambda: t[0])
        s = crear_servicio(self.repo, self.clientes.dic(), {"cache_ttl": 30}, ahora=ahora, cache=cache)
        ctx = {"cid": "c"}
        s["inventario"]({}, ctx)
        s["inventario"]({}, ctx)
        self.assertEqual(sum(1 for n, _ in self.clientes.llamadas if n == "existencias"), 1)
        t[0] = 31
        s["inventario"]({}, ctx)
        self.assertEqual(sum(1 for n, _ in self.clientes.llamadas if n == "existencias"), 2)


if __name__ == "__main__":
    unittest.main()
