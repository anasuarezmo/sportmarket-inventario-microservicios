"""Capa HTTP independiente de Flask: credencial interna, roles, rutas y formato de errores."""
import hmac
import re
import uuid

from .errores import ErrorApi
from .servicio import crear_servicio

TODOS = None
CONSULTA = ["ADM", "INV", "COM", "CON"]
ADM_INV = ["ADM", "INV"]
# roles=[] significa: solo servicios internos (sin X-User-Role)


def crear_manejador(config, repo, clientes, log=None, ahora=None):
    kw = {"ahora": ahora} if ahora else {}
    s = crear_servicio(repo, clientes, config, **kw)
    # (metodo, regex, funcion(m, ctx, *grupos), roles permitidos (None = cualquiera), acepta llamadas internas sin rol)
    rutas = [
        ("GET", r"^/api/reportes/inventario$", lambda m, c: s["inventario"](m["consulta"], c), CONSULTA, False),
        ("GET", r"^/api/reportes/valorizacion$", lambda m, c: s["valorizacion"](m["consulta"], c), CONSULTA, False),
        ("GET", r"^/api/reportes/rotacion$", lambda m, c: s["rotacion"](m["consulta"], c), CONSULTA, False),
        ("GET", r"^/api/reportes/movimientos$", lambda m, c: s["movimientos"](m["consulta"], c), CONSULTA, False),
        ("GET", r"^/api/reportes/dashboard$", lambda m, c: s["dashboard"](m["consulta"], c), TODOS, False),
        ("GET", r"^/api/alertas$", lambda m, c: s["listar_alertas"](m["consulta"]), TODOS, False),
        ("PATCH", r"^/api/alertas/([^/]+)/estado$", lambda m, c, i: s["atender"](i, m["cuerpo"], c), ADM_INV, False),
        ("POST", r"^/api/interno/alertas/stock$", lambda m, c: s["recibir_aviso"](m["cuerpo"]), [], True),
    ]

    def token_valido(t):
        esperado = config.get("token_interno") or ""
        return bool(esperado) and hmac.compare_digest(str(t or "").encode(), esperado.encode())

    def manejar(m):
        h = {k.lower(): v for k, v in (m.get("headers") or {}).items()}
        cid = h.get("x-correlation-id", "")
        if not re.fullmatch(r"[\w-]{8,64}", cid):
            cid = str(uuid.uuid4())

        def resp(status, cuerpo):
            return {"status": status, "cuerpo": cuerpo, "headers": {"X-Correlation-ID": cid}}

        def error(status, codigo, mensaje, detalles=None):
            return resp(status, {"codigo": codigo, "mensaje": mensaje, "detalles": detalles or [], "correlation_id": cid})

        try:
            if m["metodo"] == "GET" and m["ruta"] == "/health":
                if hasattr(repo, "ping"):
                    try:
                        repo.ping()
                    except Exception:
                        return resp(503, {"estado": "DOWN", "servicio": "reportes"})
                return resp(200, {"estado": "UP", "servicio": "reportes"})
            if not token_valido(h.get("x-internal-token")):
                return error(401, "NO_AUTENTICADO", "Falta o es invalida la credencial interna")
            coinciden = [r for r in rutas if re.match(r[1], m["ruta"])]
            if not coinciden:
                return error(404, "RECURSO_NO_ENCONTRADO", "Ruta no encontrada")
            ruta = next((r for r in coinciden if r[0] == m["metodo"]), None)
            if ruta is None:
                return error(405, "METODO_NO_PERMITIDO", "Metodo no permitido para esta ruta")
            _, rx, fn, roles, acepta_interno = ruta

            # Peticion del Gateway = lleva X-User-Role. Llamada entre servicios = no lo lleva.
            rol = h.get("x-user-role")
            interno = rol is None
            if roles is not None:
                if interno:
                    ok = acepta_interno
                else:
                    ok = rol in roles
                if not ok:
                    return error(403, "PROHIBIDO", "Tu rol no tiene permiso para esta operacion")
            elif not interno and rol not in ("ADM", "INV", "COM", "BOD", "CON"):
                return error(403, "PROHIBIDO", "Rol desconocido")

            if m.get("json_invalido") and m["metodo"] in ("POST", "PATCH"):
                return error(400, "PETICION_INVALIDA", "El cuerpo no es un JSON valido",
                             [{"campo": "cuerpo", "error": "JSON invalido"}])
            uid = h.get("x-user-id")
            ctx = {"cid": cid, "usuario_id": int(uid) if uid and uid.isdigit() else None}
            r = fn(m, ctx, *re.match(rx, m["ruta"]).groups())
            return resp(r["status"], r["cuerpo"])
        except ErrorApi as e:
            return error(e.status, e.codigo, e.mensaje, e.detalles)
        except Exception:  # error no previsto: no se filtran detalles internos
            if log:
                log.exception("Error interno")
            return error(500, "ERROR_INTERNO", "Error interno del servidor")

    return manejar
