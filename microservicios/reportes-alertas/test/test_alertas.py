import unittest

from app.manejador import crear_manejador
from test.ayudas import CONFIG, H_GATEWAY, H_INTERNO, ClientesFalsos, RepoFalso, peticion

AVISO_BAJO = {"evento": "STOCK_BAJO", "producto_id": 2, "bodega_id": 1, "cantidad_disponible": 3, "stock_minimo": 5}
AVISO_OK = {"evento": "STOCK_RECUPERADO", "producto_id": 2, "bodega_id": 1, "cantidad_disponible": 8, "stock_minimo": 5}


class PruebasAlertas(unittest.TestCase):
    def setUp(self):
        self.repo = RepoFalso()
        self.m = crear_manejador(CONFIG, self.repo, ClientesFalsos().dic())

    def aviso(self, cuerpo, headers=H_INTERNO):
        return self.m(peticion("POST", "/api/interno/alertas/stock", headers, cuerpo=cuerpo))

    # --- credencial y roles ---
    def test_health_sin_token(self):
        r = self.m(peticion("GET", "/health"))
        self.assertEqual((r["status"], r["cuerpo"]["estado"]), (200, "UP"))

    def test_sin_token_interno_401(self):
        r = self.m(peticion("GET", "/api/alertas"))
        self.assertEqual((r["status"], r["cuerpo"]["codigo"]), (401, "NO_AUTENTICADO"))
        self.assertIn("correlation_id", r["cuerpo"])

    def test_token_incorrecto_401(self):
        self.assertEqual(self.m(peticion("GET", "/api/alertas", {"X-Internal-Token": "otro"}))["status"], 401)

    def test_aviso_interno_rechazado_para_usuarios(self):
        # Un usuario, incluso ADM, no puede usar la ruta interna (CA-05)
        self.assertEqual(self.aviso(AVISO_BAJO, H_GATEWAY)["status"], 403)

    def test_ruta_inexistente_y_metodo(self):
        self.assertEqual(self.m(peticion("GET", "/api/nada", H_GATEWAY))["status"], 404)
        self.assertEqual(self.m(peticion("DELETE", "/api/alertas", H_GATEWAY))["status"], 405)

    # --- aviso de stock ---
    def test_stock_bajo_crea_alerta_201(self):
        r = self.aviso(AVISO_BAJO)
        self.assertEqual(r["status"], 201)
        self.assertEqual(r["cuerpo"]["alerta"]["estado_alerta"], "ACTIVA")
        self.assertEqual(r["cuerpo"]["alerta"]["id"], 1)

    def test_stock_bajo_dos_veces_una_sola_alerta_activa(self):  # CA-06
        self.aviso(AVISO_BAJO)
        r = self.aviso(AVISO_BAJO)
        self.assertEqual((r["status"], r["cuerpo"]["alerta"]["id"]), (200, 1))
        self.assertEqual(len(self.repo.alertas), 1)

    def test_recuperado_atiende_con_usuario_nulo(self):  # CA-06
        self.aviso(AVISO_BAJO)
        r = self.aviso(AVISO_OK)
        self.assertEqual(r["status"], 200)
        a = r["cuerpo"]["alerta"]
        self.assertEqual((a["estado_alerta"], a["usuario_atencion_id"]), ("ATENDIDA", None))
        self.assertIsNotNone(a["atendida_en"])

    def test_recuperado_sin_alerta_activa_200_sin_cambios(self):
        r = self.aviso(AVISO_OK)
        self.assertEqual(r["status"], 200)
        self.assertNotIn("alerta", r["cuerpo"])

    def test_nueva_alerta_tras_atendida(self):
        self.aviso(AVISO_BAJO)
        self.aviso(AVISO_OK)
        r = self.aviso(AVISO_BAJO)
        self.assertEqual((r["status"], r["cuerpo"]["alerta"]["id"]), (201, 2))

    def test_aviso_cantidad_no_corresponde_422(self):
        self.assertEqual(self.aviso({**AVISO_BAJO, "cantidad_disponible": 5})["status"], 422)
        self.assertEqual(self.aviso({**AVISO_OK, "cantidad_disponible": 4})["status"], 422)

    def test_aviso_datos_incorrectos_400(self):
        for cuerpo in ({}, {**AVISO_BAJO, "evento": "OTRO"}, {**AVISO_BAJO, "producto_id": "x"}, {**AVISO_BAJO, "stock_minimo": -1},
                       {**AVISO_BAJO, "bodega_id": True}):
            r = self.aviso(cuerpo)
            self.assertEqual((r["status"], r["cuerpo"]["codigo"]), (400, "PETICION_INVALIDA"), cuerpo)
        self.assertEqual(self.m(peticion("POST", "/api/interno/alertas/stock", H_INTERNO, json_invalido=True))["status"], 400)

    # --- consulta ---
    def test_listar_alertas_formato_y_filtros(self):
        self.aviso(AVISO_BAJO)
        self.aviso({**AVISO_BAJO, "producto_id": 3})
        r = self.m(peticion("GET", "/api/alertas", H_GATEWAY, {"producto_id": "3"}))
        self.assertEqual(r["status"], 200)
        self.assertEqual({k: r["cuerpo"][k] for k in ("total", "page", "limit")}, {"total": 1, "page": 1, "limit": 20})
        self.assertEqual(r["cuerpo"]["items"][0]["producto_id"], 3)
        self.assertEqual(self.m(peticion("GET", "/api/alertas", H_GATEWAY, {"estado_alerta": "ATENDIDA"}))["cuerpo"]["total"], 0)

    def test_listar_cualquier_rol(self):
        for rol in ("ADM", "INV", "COM", "BOD", "CON"):
            self.assertEqual(self.m(peticion("GET", "/api/alertas", {**H_GATEWAY, "X-User-Role": rol}))["status"], 200, rol)

    def test_listar_parametros_invalidos_400(self):
        for q in ({"estado_alerta": "X"}, {"page": "0"}, {"limit": "101"}, {"producto_id": "a"}):
            self.assertEqual(self.m(peticion("GET", "/api/alertas", H_GATEWAY, q))["status"], 400, q)

    # --- atender ---
    def patch(self, id_, cuerpo, rol="INV"):
        return self.m(peticion("PATCH", f"/api/alertas/{id_}/estado", {**H_GATEWAY, "X-User-Role": rol}, cuerpo=cuerpo))

    def test_atender_guarda_usuario_200(self):
        self.aviso(AVISO_BAJO)
        r = self.patch(1, {"estado_alerta": "ATENDIDA"})
        self.assertEqual(r["status"], 200)
        self.assertEqual(r["cuerpo"]["alerta"]["usuario_atencion_id"], 7)  # sale de X-User-Id

    def test_atender_dos_veces_409(self):
        self.aviso(AVISO_BAJO)
        self.patch(1, {"estado_alerta": "ATENDIDA"})
        r = self.patch(1, {"estado_alerta": "ATENDIDA"})
        self.assertEqual((r["status"], r["cuerpo"]["codigo"]), (409, "ALERTA_YA_ATENDIDA"))

    def test_atender_inexistente_404_y_datos_400(self):
        self.assertEqual(self.patch(99, {"estado_alerta": "ATENDIDA"})["status"], 404)
        self.assertEqual(self.patch("abc", {"estado_alerta": "ATENDIDA"})["status"], 400)
        self.assertEqual(self.patch(1, {"estado_alerta": "ACTIVA"})["status"], 400)
        self.assertEqual(self.patch(1, {})["status"], 400)

    def test_atender_solo_adm_inv(self):
        self.aviso(AVISO_BAJO)
        for rol in ("COM", "BOD", "CON"):
            self.assertEqual(self.patch(1, {"estado_alerta": "ATENDIDA"}, rol)["status"], 403, rol)
        self.assertEqual(self.patch(1, {"estado_alerta": "ATENDIDA"}, "ADM")["status"], 200)


if __name__ == "__main__":
    unittest.main()
