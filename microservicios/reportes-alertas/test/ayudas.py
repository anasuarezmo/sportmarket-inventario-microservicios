"""Falsos para probar sin MySQL ni otros servicios."""
from datetime import date

from app.errores import ErrorApi

TOKEN = "token-de-prueba"
H_GATEWAY = {"X-Internal-Token": TOKEN, "X-User-Role": "ADM", "X-User-Id": "7"}
H_INTERNO = {"X-Internal-Token": TOKEN}
CONFIG = {"token_interno": TOKEN, "cache_ttl": 0, "timeout": 1, "reintentos": 2,
          "urls": {"inventario": "http://inv", "catalogo": "http://cat"}}


class RepoFalso:
    def __init__(self):
        self.alertas, self.sig = [], 1

    def ping(self):
        pass

    def _copia(self, a):
        return dict(a) if a else None

    def crear_activa(self, p, b, cant, minimo):
        for a in self.alertas:
            if a["producto_id"] == p and a["bodega_id"] == b and a["estado_alerta"] == "ACTIVA":
                return self._copia(a), False
        a = {"id": self.sig, "producto_id": p, "bodega_id": b, "cantidad_disponible_al_generar": cant, "stock_minimo": minimo,
             "estado_alerta": "ACTIVA", "fecha_generacion_alerta": "2026-11-20T10:00:00Z", "atendida_en": None, "usuario_atencion_id": None}
        self.sig += 1
        self.alertas.append(a)
        return self._copia(a), True

    def cerrar_activa(self, p, b):
        for a in self.alertas:
            if a["producto_id"] == p and a["bodega_id"] == b and a["estado_alerta"] == "ACTIVA":
                a.update(estado_alerta="ATENDIDA", atendida_en="2026-11-20T11:00:00Z", usuario_atencion_id=None)
                return self._copia(a)
        return None

    def atender(self, id_, uid):
        for a in self.alertas:
            if a["id"] == id_:
                if a["estado_alerta"] == "ATENDIDA":
                    return "ya_atendida", self._copia(a)
                a.update(estado_alerta="ATENDIDA", atendida_en="2026-11-20T11:00:00Z", usuario_atencion_id=uid)
                return "ok", self._copia(a)
        return "no_existe", None

    def listar(self, f):
        xs = [a for a in self.alertas if all(f.get(c) is None or a[c] == f[c] for c in ("estado_alerta", "producto_id", "bodega_id"))]
        xs = sorted(xs, key=lambda a: -a["id"])
        ini = (f["page"] - 1) * f["limit"]
        return [self._copia(a) for a in xs[ini:ini + f["limit"]]], len(xs)

    def contar_activas(self):
        return sum(1 for a in self.alertas if a["estado_alerta"] == "ACTIVA")


PRODUCTOS = [
    {"id": 1, "codigo_producto": "FUT001", "nombre_producto": "Balon futbol", "categoria_id": 2, "precio_venta": 1000, "producto_activo": True},
    {"id": 2, "codigo_producto": "BAS001", "nombre_producto": "Balon baloncesto", "categoria_id": 1, "precio_venta": 2500.5, "producto_activo": True},
    {"id": 3, "codigo_producto": "GUA001", "nombre_producto": "Guantes", "categoria_id": 1, "precio_venta": 400, "producto_activo": True},
    {"id": 4, "codigo_producto": "OLD001", "nombre_producto": "Viejo", "categoria_id": 1, "precio_venta": 50, "producto_activo": False},
]
EXISTENCIAS = [
    {"producto_id": 1, "bodega_id": 1, "cantidad_disponible": 10, "stock_minimo": 0},
    {"producto_id": 1, "bodega_id": 2, "cantidad_disponible": 5, "stock_minimo": 0},
    {"producto_id": 2, "bodega_id": 1, "cantidad_disponible": 4, "stock_minimo": 0},
]
MOVIMIENTOS = [
    {"tipo_movimiento": "ENTRADA", "producto_id": 1, "cantidad_movimiento": 20},
    {"tipo_movimiento": "SALIDA", "producto_id": 1, "cantidad_movimiento": 3},
    {"tipo_movimiento": "SALIDA", "producto_id": 2, "cantidad_movimiento": 8},
    {"tipo_movimiento": "SALIDA", "producto_id": 1, "cantidad_movimiento": 2},
    {"tipo_movimiento": "AJUSTE", "producto_id": 2, "cantidad_movimiento": 1},
    {"tipo_movimiento": "TRASLADO", "producto_id": 1, "cantidad_movimiento": 99},
]


class ClientesFalsos:
    """Mismo contrato que crear_clientes(): cuatro funciones. Anota las llamadas y puede simular servicios caidos."""

    def __init__(self, caido=False):
        self.caido, self.llamadas = caido, []

    def _r(self, nombre, datos, *args):
        self.llamadas.append((nombre, args))
        if self.caido:
            raise ErrorApi(503, "SERVICIO_NO_DISPONIBLE", "Un servicio necesario no esta disponible", [{"campo": "servicio", "error": "x"}])
        return datos

    def dic(self):
        def productos(cid, categoria_id=None):
            ps = PRODUCTOS if categoria_id is None else [p for p in PRODUCTOS if p["categoria_id"] == categoria_id]
            return self._r("productos", [dict(p) for p in ps], categoria_id)

        def existencias(cid, bodega_id=None):
            xs = EXISTENCIAS if bodega_id is None else [e for e in EXISTENCIAS if e["bodega_id"] == bodega_id]
            return self._r("existencias", [dict(e) for e in xs], bodega_id)

        # Inventario ya filtra por tipo SALIDA: los traslados nunca llegan a la rotacion
        return {
            "productos": productos, "existencias": existencias,
            "salidas": lambda d, h, cid: self._r("salidas", [dict(m) for m in MOVIMIENTOS if m["tipo_movimiento"] == "SALIDA"], d, h),
            "movimientos": lambda d, h, cid: self._r("movimientos", [dict(m) for m in MOVIMIENTOS], d, h),
        }


def peticion(metodo, ruta, headers=None, consulta=None, cuerpo=None, json_invalido=False):
    return {"metodo": metodo, "ruta": ruta, "headers": headers or {}, "consulta": consulta or {}, "cuerpo": cuerpo, "json_invalido": json_invalido}


HOY = date(2026, 11, 20)
