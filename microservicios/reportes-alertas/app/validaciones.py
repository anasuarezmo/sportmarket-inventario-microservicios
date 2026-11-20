"""Validacion de entradas. Todo error de formato es 400; las reglas de negocio del aviso de stock son 422."""
from datetime import date, datetime, timedelta, timezone

from .errores import ErrorApi, solicitud_invalida

EVENTOS = ("STOCK_BAJO", "STOCK_RECUPERADO")
ESTADOS = ("ACTIVA", "ATENDIDA")
DIAS_POR_DEFECTO = 30


def _entero(q, campo, d, minimo=None, maximo=None):
    if q.get(campo) in (None, ""):
        return None
    try:
        v = int(str(q[campo]), 10)
    except ValueError:
        d.append({"campo": campo, "error": "Debe ser un entero"})
        return None
    if minimo is not None and v < minimo:
        d.append({"campo": campo, "error": f"Debe ser mayor o igual a {minimo}"})
    if maximo is not None and v > maximo:
        d.append({"campo": campo, "error": f"Maximo {maximo}"})
    return v


def _fecha(q, campo, d):
    t = q.get(campo)
    if t in (None, ""):
        return None
    try:
        return date.fromisoformat(str(t))
    except ValueError:
        d.append({"campo": campo, "error": "Fecha invalida (use AAAA-MM-DD)"})
        return None


def _cerrar(valor, d):
    if d:
        raise solicitud_invalida(d)
    return valor


def filtros_alertas(q):
    d = []
    estado = q.get("estado_alerta")
    if estado is not None and estado not in ESTADOS:
        d.append({"campo": "estado_alerta", "error": "Debe ser ACTIVA o ATENDIDA"})
    f = {
        "estado_alerta": estado,
        "producto_id": _entero(q, "producto_id", d, 1),
        "bodega_id": _entero(q, "bodega_id", d, 1),
        "page": _entero(q, "page", d, 1) or 1,
        "limit": _entero(q, "limit", d, 1, 100) or 20,
    }
    return _cerrar(f, d)


def filtros_inventario(q):
    d = []
    f = {"categoria_id": _entero(q, "categoria_id", d, 1), "bodega_id": _entero(q, "bodega_id", d, 1)}
    return _cerrar(f, d)


def filtros_valorizacion(q):
    d = []
    return _cerrar({"categoria_id": _entero(q, "categoria_id", d, 1)}, d)


def periodo(q, hoy=None):
    """desde/hasta (AAAA-MM-DD). Sin fechas: ultimos 30 dias. Ambos limites incluyen el dia completo."""
    d = []
    hoy = hoy or datetime.now(timezone.utc).date()
    desde, hasta = _fecha(q, "desde", d), _fecha(q, "hasta", d)
    if not d:
        if hasta is None:
            hasta = hoy
        if desde is None:
            desde = hasta - timedelta(days=DIAS_POR_DEFECTO)
        if desde > hasta:
            d.append({"campo": "desde", "error": "No puede ser posterior a hasta"})
    return _cerrar((desde, hasta), d)


def filtros_rotacion(q, hoy=None):
    d = []
    limite = _entero(q, "limite", d, 1, 50) or 5
    _cerrar(None, d)
    desde, hasta = periodo(q, hoy)
    return {"desde": desde, "hasta": hasta, "limite": limite}


def parse_id(texto, campo="id"):
    try:
        v = int(str(texto), 10)
        if v < 1:
            raise ValueError
        return v
    except ValueError:
        raise solicitud_invalida([{"campo": campo, "error": "Debe ser un entero positivo"}])


def _entero_cuerpo(b, campo, d, minimo):
    v = b.get(campo)
    if v is None:
        d.append({"campo": campo, "error": "Es obligatorio"})
    elif isinstance(v, bool) or not isinstance(v, int):
        d.append({"campo": campo, "error": "Debe ser un entero"})
    elif v < minimo:
        d.append({"campo": campo, "error": f"Debe ser mayor o igual a {minimo}"})
    return v


def aviso_stock(b):
    if not isinstance(b, dict):
        raise solicitud_invalida([{"campo": "cuerpo", "error": "Debe ser un objeto JSON"}])
    d = []
    evento = b.get("evento")
    if evento is None:
        d.append({"campo": "evento", "error": "Es obligatorio"})
    elif evento not in EVENTOS:
        d.append({"campo": "evento", "error": "Debe ser STOCK_BAJO o STOCK_RECUPERADO"})
    p = _entero_cuerpo(b, "producto_id", d, 1)
    bo = _entero_cuerpo(b, "bodega_id", d, 1)
    c = _entero_cuerpo(b, "cantidad_disponible", d, 0)
    m = _entero_cuerpo(b, "stock_minimo", d, 0)
    _cerrar(None, d)
    # Reglas de negocio (422): la cantidad debe corresponder al evento
    if evento == "STOCK_BAJO" and not c < m:
        raise ErrorApi(422, "CANTIDAD_NO_CORRESPONDE_AL_EVENTO", "La cantidad no corresponde al evento",
                       [{"campo": "cantidad_disponible", "error": "STOCK_BAJO exige cantidad_disponible menor que stock_minimo"}])
    if evento == "STOCK_RECUPERADO" and not c >= m:
        raise ErrorApi(422, "CANTIDAD_NO_CORRESPONDE_AL_EVENTO", "La cantidad no corresponde al evento",
                       [{"campo": "cantidad_disponible", "error": "STOCK_RECUPERADO exige cantidad_disponible mayor o igual que stock_minimo"}])
    return {"evento": evento, "producto_id": p, "bodega_id": bo, "cantidad_disponible": c, "stock_minimo": m}


def cambio_estado(b):
    if not isinstance(b, dict):
        raise solicitud_invalida([{"campo": "cuerpo", "error": "Debe ser un objeto JSON"}])
    e = b.get("estado_alerta")
    if e is None:
        raise solicitud_invalida([{"campo": "estado_alerta", "error": "Es obligatorio"}])
    if e != "ATENDIDA":
        raise solicitud_invalida([{"campo": "estado_alerta", "error": "Solo se permite ATENDIDA"}])
    return e
