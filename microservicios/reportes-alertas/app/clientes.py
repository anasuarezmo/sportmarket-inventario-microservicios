"""Llamadas REST a Inventario y Catalogo (solo lecturas).
RNF18: espera maxima de 3 s por intento y hasta 3 reintentos (200, 400, 800 ms) ante errores de red, timeout o 5xx."""
import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request

from .errores import ErrorApi

log = logging.getLogger("reportes")
POR_PAGINA = 100
MAX_PAGINAS = 200


def _http(url, headers, timeout):
    """Devuelve (status, texto). Solo lanza excepcion por errores de red/timeout."""
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")


def crear_clientes(config, http=_http, esperar=time.sleep):
    def llamar(base, ruta, params, cid):
        qs = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
        url = f"{base}{ruta}" + (f"?{qs}" if qs else "")
        headers = {"Accept": "application/json", "X-Internal-Token": config["token_interno"]}
        if cid:
            headers["X-Correlation-ID"] = cid
        ultimo = None
        for intento in range(config["reintentos"] + 1):
            if intento > 0:
                esperar(0.2 * 2 ** (intento - 1))
            try:
                status, texto = http(url, headers, config["timeout"])
            except Exception as e:  # red, timeout...
                ultimo = e
                continue
            if status >= 500:
                ultimo = Exception(f"HTTP {status}")
                continue
            if status != 200:
                raise ErrorApi(503, "SERVICIO_NO_DISPONIBLE", "Respuesta inesperada de un servicio necesario",
                               [{"campo": "servicio", "error": f"{base} respondio {status}"}])
            try:
                return json.loads(texto)
            except ValueError:
                raise ErrorApi(503, "SERVICIO_NO_DISPONIBLE", "Respuesta invalida de un servicio necesario",
                               [{"campo": "servicio", "error": base}])
        log.error("Fallo llamando a %s: %s", url, ultimo)
        raise ErrorApi(503, "SERVICIO_NO_DISPONIBLE", "Un servicio necesario no esta disponible",
                       [{"campo": "servicio", "error": base}])

    def todas_las_paginas(base, ruta, params, cid):
        """Recorre las paginas {items,total,page,limit} y devuelve todos los items."""
        items = []
        for pagina in range(1, MAX_PAGINAS + 1):
            r = llamar(base, ruta, {**params, "page": pagina, "limit": POR_PAGINA}, cid)
            if not isinstance(r, dict) or not isinstance(r.get("items"), list):
                raise ErrorApi(503, "SERVICIO_NO_DISPONIBLE", "Formato de lista inesperado en un servicio necesario",
                               [{"campo": "servicio", "error": base}])
            items.extend(r["items"])
            if len(items) >= int(r.get("total", 0)) or not r["items"]:
                break
        return items

    inv, cat = config["urls"]["inventario"], config["urls"]["catalogo"]
    return {
        "existencias": lambda cid, bodega_id=None: todas_las_paginas(inv, "/api/inventario/existencias", {"bodega_id": bodega_id}, cid),
        "salidas": lambda desde, hasta, cid: todas_las_paginas(
            inv, "/api/inventario/movimientos", {"tipo_movimiento": "SALIDA", "desde": desde, "hasta": hasta}, cid),
        "movimientos": lambda desde, hasta, cid: todas_las_paginas(
            inv, "/api/inventario/movimientos", {"desde": desde, "hasta": hasta}, cid),
        "productos": lambda cid, categoria_id=None: todas_las_paginas(cat, "/api/productos", {"categoria_id": categoria_id}, cid),
    }
