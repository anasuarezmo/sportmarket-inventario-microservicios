"""Pruebas de carga de Edwin (15 pruebas), siempre a traves del API Gateway.
Catalogo (4), Inventario (6), Reportes (4) y Alertas (1). Los nombres con numero salen ordenados en la tabla de Locust.
Variables: TOKEN (JWT de un ADM, obligatorio) y PRODUCTO_ID (por defecto 2)."""
import os
import uuid

from locust import HttpUser, between, task

TOKEN = os.environ.get("TOKEN", "")
PRODUCTO = int(os.environ.get("PRODUCTO_ID", "2"))


class UsuarioSportMarket(HttpUser):
    wait_time = between(0.5, 1.5)

    def on_start(self):
        if not TOKEN:
            raise SystemExit("Falta la variable de entorno TOKEN (JWT de un usuario ADM)")
        self.client.headers.update({"Authorization": f"Bearer {TOKEN}"})

    def _escribir(self, ruta, cuerpo, nombre):
        with self.client.post(ruta, json=cuerpo, name=nombre, catch_response=True) as r:
            if r.status_code == 201:
                r.success()
            else:
                r.failure(f"HTTP {r.status_code}: {r.text[:120]}")

    # ---------- Catalogo (4) ----------
    @task(4)
    def p01_listar_productos(self):
        self.client.get("/api/productos?limit=20", name="01 Catalogo: listar productos")

    @task(3)
    def p02_buscar_productos(self):
        self.client.get("/api/productos?nombre=Balon&limit=20", name="02 Catalogo: buscar por nombre")

    @task(3)
    def p03_consultar_producto(self):
        self.client.get(f"/api/productos/{PRODUCTO}", name="03 Catalogo: consultar un producto")

    @task(2)
    def p04_listar_categorias(self):
        self.client.get("/api/categorias", name="04 Catalogo: listar categorias")

    # ---------- Inventario (6) ----------
    @task(4)
    def p05_existencias(self):
        self.client.get("/api/inventario/existencias?limit=20", name="05 Inventario: existencias")

    @task(3)
    def p06_existencias_producto(self):
        self.client.get(f"/api/inventario/existencias/{PRODUCTO}", name="06 Inventario: existencias de un producto")

    @task(3)
    def p07_movimientos(self):
        self.client.get("/api/inventario/movimientos?limit=20", name="07 Inventario: movimientos")

    @task(3)
    def p08_entrada(self):
        self._escribir("/api/inventario/entradas", {
            "operacion_id": str(uuid.uuid4()), "producto_id": PRODUCTO, "bodega_destino_id": 1,
            "cantidad_movimiento": 1, "origen_movimiento": "MANUAL"}, "08 Inventario: registrar entrada")

    @task(1)
    def p09_salida(self):
        self._escribir("/api/inventario/salidas", {
            "operacion_id": str(uuid.uuid4()), "producto_id": PRODUCTO, "bodega_origen_id": 1,
            "cantidad_movimiento": 1, "origen_movimiento": "MANUAL"}, "09 Inventario: registrar salida")

    @task(1)
    def p10_traslado(self):
        self._escribir("/api/inventario/traslados", {
            "operacion_id": str(uuid.uuid4()), "producto_id": PRODUCTO, "bodega_origen_id": 1,
            "bodega_destino_id": 2, "cantidad_movimiento": 1, "origen_movimiento": "MANUAL"}, "10 Inventario: registrar traslado")

    # ---------- Reportes (4) ----------
    @task(2)
    def p11_dashboard(self):
        self.client.get("/api/reportes/dashboard", name="11 Reportes: dashboard")

    @task(2)
    def p12_reporte_inventario(self):
        self.client.get("/api/reportes/inventario", name="12 Reportes: existencias")

    @task(2)
    def p13_valorizacion(self):
        self.client.get("/api/reportes/valorizacion", name="13 Reportes: valorizacion")

    @task(1)
    def p14_rotacion(self):
        self.client.get("/api/reportes/rotacion?limite=5", name="14 Reportes: rotacion")

    # ---------- Alertas (1) ----------
    @task(2)
    def p15_alertas(self):
        self.client.get("/api/alertas?limit=20", name="15 Alertas: consultar")
