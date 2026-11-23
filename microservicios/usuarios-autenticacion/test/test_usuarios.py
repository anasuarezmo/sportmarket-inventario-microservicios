"""Pruebas unitarias: repositorio simulado. No sustituyen la prueba con MySQL real."""
import hashlib
import unittest
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
import mysql.connector

from app.web import crear_app

NOMBRES = {1: "Administrador", 2: "Inventario", 3: "Compras", 4: "Bodega", 5: "Consulta"}


class FakeRepo:
    def __init__(self, password_hash):
        self.password_hash = password_hash
        self.items = {1: self.nuevo(1, "Administrador", "admin@sportmarket.com", 1)}
        self.tokens = {}
        self.last_id = 1
        self.ha_actualizado_acceso = False

    def nuevo(self, uid, nombre, email, rol):
        return {"id": uid, "nombre": nombre, "email": email, "rol_id": rol,
                "rol_nombre": NOMBRES[rol], "password_hash": self.password_hash,
                "usuario_activo": True, "fecha_registro": datetime(2026, 11, 21), "fecha_ultimo_acceso": None}

    def usuario_email(self, email):
        return next((u.copy() for u in self.items.values() if u["email"] == email), None)

    def usuario_id(self, uid):
        return self.items[uid].copy() if uid in self.items else None

    def guardar_ultimo_acceso(self, uid):
        self.items[uid]["fecha_ultimo_acceso"] = datetime(2026, 11, 21)
        self.ha_actualizado_acceso = True

    def roles(self):
        return [{"id": idr, "nombre": nombre, "descripcion": "Rol de " + nombre} for idr, nombre in NOMBRES.items()]

    def rol_existe(self, idr):
        return idr in NOMBRES

    def usuarios(self, filtros):
        rows = list(self.items.values())
        if filtros["rol_id"] is not None:
            rows = [r for r in rows if r["rol_id"] == filtros["rol_id"]]
        if filtros["usuario_activo"] is not None:
            rows = [r for r in rows if r["usuario_activo"] == filtros["usuario_activo"]]
        if filtros["q"]:
            rows = [r for r in rows if filtros["q"].lower() in (r["nombre"] + r["email"]).lower()]
        total = len(rows)
        offset = (filtros["page"] - 1) * filtros["limit"]
        return [r.copy() for r in rows[offset:offset + filtros["limit"]]], total

    def crear_usuario(self, nombre, email, password_hash, rol_id):
        if self.usuario_email(email):
            raise mysql.connector.IntegrityError("duplicado")
        self.last_id += 1
        u = self.nuevo(self.last_id, nombre, email, rol_id)
        u["password_hash"] = password_hash
        self.items[self.last_id] = u
        return self.last_id

    def actualizar_usuario(self, uid, nombre, email):
        if any(r["email"] == email and r["id"] != uid for r in self.items.values()):
            raise mysql.connector.IntegrityError("duplicado")
        self.items[uid].update(nombre=nombre, email=email)

    def actualizar_rol(self, uid, rol_id):
        self.items[uid].update(rol_id=rol_id, rol_nombre=NOMBRES[rol_id])

    def actualizar_estado(self, uid, activo):
        self.items[uid]["usuario_activo"] = activo

    def actualizar_password(self, uid, password_hash):
        self.items[uid]["password_hash"] = password_hash
        self.tokens.clear()

    def guardar_token(self, uid, token_hash, vencimiento):
        self.tokens = {token_hash: {"usuario_id": uid, "exp": vencimiento}}

    def consumir_token(self, token_hash, password_hash):
        item = self.tokens.get(token_hash)
        if not item or item["exp"] <= datetime.now(timezone.utc).replace(tzinfo=None):
            return False
        self.items[item["usuario_id"]]["password_hash"] = password_hash
        self.tokens.clear()
        return True


class UsuariosTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.hash_admin = bcrypt.hashpw(b"Ejemplo123", bcrypt.gensalt(rounds=4)).decode()

    def setUp(self):
        self.repo = FakeRepo(self.hash_admin)
        self.notificados = []
        cfg = {
            "jwt_secret": "un_secreto_test_con_mas_de_32_caracteres", "internal_token": "token_interno_de_pruebas",
            "jwt_exp_minutes": 60, "recovery_minutes": 30, "smtp": {}, "mysql": {},
        }
        self.app = crear_app(cfg, self.repo, lambda email, token, mins: self.notificados.append((email, token, mins)))
        self.cliente = self.app.test_client()
        self.token = {"X-Internal-Token": "token_interno_de_pruebas"}
        self.admin = {**self.token, "X-User-Role": "ADM", "X-User-Id": "1"}
        self.consulta = {**self.token, "X-User-Role": "CON", "X-User-Id": "1"}

    def post(self, ruta, data, headers=None):
        return self.cliente.post(ruta, json=data, headers=self.token if headers is None else headers)

    def test_01_salud_publica(self):
        self.assertEqual(self.cliente.get("/health").json, {"estado": "UP"})

    def test_02_sin_token_rechazado(self):
        r = self.cliente.get("/api/usuarios")
        self.assertEqual(r.status_code, 401)
        self.assertEqual(set(r.json), {"codigo", "mensaje", "detalles", "correlation_id"})

    def test_03_token_falso(self):
        r = self.cliente.get("/api/usuarios", headers={"X-Internal-Token": "incorrecto"})
        self.assertEqual(r.status_code, 401)

    def test_04_login_correcto_y_claims(self):
        r = self.post("/api/auth/login", {"email": "ADMIN@SPORTMARKET.COM", "contrasena": "Ejemplo123"})
        self.assertEqual(r.status_code, 200)
        claims = jwt.decode(r.json["token"], "un_secreto_test_con_mas_de_32_caracteres", algorithms=["HS256"])
        self.assertEqual((claims["sub"], claims["rol"]), ("1", "ADM"))
        self.assertEqual(r.json["expira_en"], 3600)
        self.assertTrue(self.repo.ha_actualizado_acceso)

    def test_05_login_incorrecto(self):
        self.assertEqual(self.post("/api/auth/login", {"email": "admin@sportmarket.com", "contrasena": "incorrecta"}).status_code, 401)

    def test_06_login_cuenta_inactiva(self):
        self.repo.actualizar_estado(1, False)
        self.assertEqual(self.post("/api/auth/login", {"email": "admin@sportmarket.com", "contrasena": "Ejemplo123"}).status_code, 403)

    def test_07_login_campo_faltante(self):
        self.assertEqual(self.post("/api/auth/login", {"email": "admin@sportmarket.com"}).status_code, 400)

    def test_08_logout_requiere_usuario(self):
        self.assertEqual(self.post("/api/auth/logout", {}, self.token).status_code, 401)
        self.assertEqual(self.post("/api/auth/logout", {}, self.admin).status_code, 204)

    def test_09_forgot_oculta_existencia_de_correo(self):
        existe = self.post("/api/auth/forgot-password", {"email": "admin@sportmarket.com"})
        no_existe = self.post("/api/auth/forgot-password", {"email": "desconocido@sportmarket.com"})
        self.assertEqual(existe.status_code, 202)
        self.assertEqual(no_existe.status_code, 202)
        self.assertEqual(existe.json, no_existe.json)
        self.assertEqual(len(self.notificados), 1)

    def test_10_forgot_guarda_solo_hash(self):
        self.post("/api/auth/forgot-password", {"email": "admin@sportmarket.com"})
        token = self.notificados[0][1]
        self.assertNotIn(token, repr(self.repo.tokens))
        self.assertIn(hashlib.sha256(token.encode()).hexdigest(), self.repo.tokens)

    def test_11_reset_token_unico(self):
        self.post("/api/auth/forgot-password", {"email": "admin@sportmarket.com"})
        token = self.notificados[0][1]
        datos = {"token": token, "contrasena_nueva": "NuevaClave123"}
        self.assertEqual(self.post("/api/auth/reset-password", datos).status_code, 204)
        self.assertEqual(self.post("/api/auth/reset-password", datos).status_code, 422)
        self.assertEqual(self.post("/api/auth/login", {"email": "admin@sportmarket.com", "contrasena": "NuevaClave123"}).status_code, 200)

    def test_12_reset_token_invalido(self):
        self.assertEqual(self.post("/api/auth/reset-password", {"token": "x" * 20, "contrasena_nueva": "NuevaClave123"}).status_code, 422)

    def test_13_reset_contrasena_corta(self):
        self.assertEqual(self.post("/api/auth/reset-password", {"token": "x" * 20, "contrasena_nueva": "123"}).status_code, 422)

    def test_14_change_password(self):
        r = self.post("/api/auth/change-password", {"contrasena_actual": "Ejemplo123", "contrasena_nueva": "Actualizada123"}, self.admin)
        self.assertEqual(r.status_code, 204)
        self.assertEqual(self.post("/api/auth/login", {"email": "admin@sportmarket.com", "contrasena": "Actualizada123"}).status_code, 200)

    def test_15_change_password_actual_invalida(self):
        r = self.post("/api/auth/change-password", {"contrasena_actual": "mala", "contrasena_nueva": "Actualizada123"}, self.admin)
        self.assertEqual(r.status_code, 422)

    def test_16_no_admin_no_puede_listar_usuarios(self):
        self.assertEqual(self.cliente.get("/api/usuarios", headers=self.consulta).status_code, 403)

    def test_17_lista_y_no_expone_hash(self):
        r = self.cliente.get("/api/usuarios", headers=self.admin)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(set(r.json), {"items", "page", "limit", "total"})
        self.assertEqual(r.json["total"], 1)
        self.assertNotIn("password_hash", str(r.json))

    def test_18_crear_usuario(self):
        data = {"nombre": "Operador", "email": "operador@test.com", "contrasena": "ClaveSegura123", "rol_id": 4}
        r = self.post("/api/usuarios", data, self.admin)
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.json["usuario"]["rol"], "Bodega")
        self.assertNotIn("password_hash", str(r.json))

    def test_19_correo_duplicado(self):
        data = {"nombre": "Otro", "email": "admin@sportmarket.com", "contrasena": "ClaveSegura123", "rol_id": 1}
        self.assertEqual(self.post("/api/usuarios", data, self.admin).status_code, 409)

    def test_20_rol_inexistente(self):
        data = {"nombre": "Otro", "email": "otro@test.com", "contrasena": "ClaveSegura123", "rol_id": 99}
        self.assertEqual(self.post("/api/usuarios", data, self.admin).status_code, 422)

    def test_21_consultar_no_encontrado(self):
        self.assertEqual(self.cliente.get("/api/usuarios/999", headers=self.admin).status_code, 404)

    def test_22_actualizar_usuario(self):
        r = self.cliente.put("/api/usuarios/1", json={"nombre": "Ana", "email": "ana@ejemplo.com"}, headers=self.admin)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json["usuario"]["nombre"], "Ana")

    def test_23_cambiar_rol(self):
        r = self.cliente.patch("/api/usuarios/1/rol", json={"rol_id": 2}, headers=self.admin)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json["usuario"]["rol_id"], 2)

    def test_24_cambiar_estado(self):
        r = self.cliente.patch("/api/usuarios/1/estado", json={"usuario_activo": False}, headers=self.admin)
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.json["usuario"]["usuario_activo"])

    def test_25_estado_rechaza_string(self):
        r = self.cliente.patch("/api/usuarios/1/estado", json={"usuario_activo": "false"}, headers=self.admin)
        self.assertEqual(r.status_code, 400)

    def test_26_roles(self):
        r = self.cliente.get("/api/roles", headers=self.admin)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json["total"], 5)
        self.assertEqual(r.json["items"][0]["codigo"], "ADM")

    def test_27_paginacion_invalida(self):
        self.assertEqual(self.cliente.get("/api/usuarios?page=0", headers=self.admin).status_code, 400)

    def test_28_correlation_id_respetado(self):
        r = self.cliente.get("/api/usuarios", headers={**self.admin, "X-Correlation-ID": "prueba-abcd-1234"})
        self.assertEqual(r.headers["X-Correlation-ID"], "prueba-abcd-1234")

    def test_29_documentacion_con_token(self):
        self.assertEqual(self.cliente.get("/openapi.yaml").status_code, 401)
        self.assertEqual(self.cliente.get("/openapi.yaml", headers=self.token).status_code, 200)

    def test_30_doce_operaciones_contrato(self):
        routes = {(r.rule, m) for r in self.app.url_map.iter_rules() for m in r.methods if m in ("GET", "POST", "PUT", "PATCH")}
        self.assertEqual(len([x for x in routes if x[0].startswith("/api/")]), 12)

    def test_31_json_malformado(self):
        r = self.cliente.post("/api/auth/login", data="{mal", headers={**self.token, "Content-Type": "application/json"})
        self.assertEqual(r.status_code, 400)


if __name__ == "__main__":
    unittest.main()
