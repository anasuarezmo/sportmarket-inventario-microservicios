"""Validaciones de las entradas del OpenAPI y reglas de negocio de Entrega 2."""
from datetime import datetime, timezone
import re


class ErrorApi(Exception):
    def __init__(self, status, codigo, mensaje, detalles=None):
        super().__init__(mensaje)
        self.status, self.codigo, self.detalles = status, codigo, detalles or []


def invalidar(campo, descripcion, status=400, codigo="PETICION_INVALIDA"):
    raise ErrorApi(status, codigo, "Datos invalidos", [{"campo": campo, "error": descripcion}])


def entero_positivo(v, campo, obligatorio=True):
    if v is None and not obligatorio:
        return None
    if isinstance(v, bool) or not isinstance(v, int) or v < 1:
        invalidar(campo, "Debe ser un entero positivo")
    return v


def texto(v, campo, longitud, obligatorio=True):
    if v is None and not obligatorio:
        return None
    if not isinstance(v, str) or (obligatorio and not v.strip()) or len(v) > longitud:
        invalidar(campo, f"Debe ser texto de 1 a {longitud} caracteres" if obligatorio else f"Maximo {longitud} caracteres")
    return v.strip()


def registro(body):
    if not isinstance(body, dict):
        invalidar("cuerpo", "Debe ser un objeto JSON")
    tipo = body.get("tipo")
    if tipo not in ("CLIENTE", "PROVEEDOR"):
        invalidar("tipo", "Debe ser CLIENTE o PROVEEDOR", 422, "TIPO_INVALIDO")
    motivo = texto(body.get("motivo"), "motivo", 200)
    bodega_id = entero_positivo(body.get("bodega_id"), "bodega_id")
    proveedor_id = entero_positivo(body.get("proveedor_id"), "proveedor_id", obligatorio=tipo == "PROVEEDOR")
    if tipo == "CLIENTE" and proveedor_id is not None:
        invalidar("proveedor_id", "Solo aplica a devoluciones a proveedor", 422, "PROVEEDOR_NO_APLICA")
    documento_ref = texto(body.get("documento_ref"), "documento_ref", 40, obligatorio=False)
    lineas = body.get("detalles")
    if not isinstance(lineas, list) or len(lineas) == 0:
        invalidar("detalles", "Debe ser un arreglo no vacio")
    if len(lineas) > 100:
        invalidar("detalles", "Maximo 100 lineas")
    detalles = []
    for n, linea in enumerate(lineas):
        campo = f"detalles[{n}]"
        if not isinstance(linea, dict):
            invalidar(campo, "Debe ser un objeto JSON")
        pid = entero_positivo(linea.get("producto_id"), campo + ".producto_id")
        cantidad = entero_positivo(linea.get("cantidad"), campo + ".cantidad")
        condicion = linea.get("condicion")
        if tipo == "CLIENTE" and condicion not in ("BUEN_ESTADO", "DEFECTUOSO"):
            invalidar(campo + ".condicion", "Debe ser BUEN_ESTADO o DEFECTUOSO", 422, "CONDICION_INVALIDA")
        if tipo == "PROVEEDOR" and "condicion" in linea:
            invalidar(campo + ".condicion", "Debe omitirse en devoluciones a proveedor", 422, "CONDICION_NO_APLICA")
        detalles.append({"producto_id": pid, "cantidad": cantidad, "condicion": condicion})
    return {"tipo": tipo, "motivo": motivo, "bodega_id": bodega_id,
            "proveedor_id": proveedor_id, "documento_ref": documento_ref, "detalles": detalles}


def filtros(query):
    tipo = query.get('tipo')
    if tipo is not None and tipo not in ('CLIENTE', 'PROVEEDOR'):
        invalidar('tipo', 'Debe ser CLIENTE o PROVEEDOR')
    estado = query.get('estado_inventario')
    if estado is not None and estado not in ('PENDIENTE', 'APLICADA'):
        invalidar('estado_inventario', 'Debe ser PENDIENTE o APLICADA')
    def query_entero(k, predeterminado=None):
        valor = query.get(k)
        if valor is None:
            return predeterminado
        if not re.fullmatch(r'[0-9]+', str(valor)) or int(valor) < 1:
            invalidar(k, 'Debe ser un entero positivo')
        return int(valor)
    page = query_entero('page', 1)
    limit = query_entero('limit', 20)
    if limit > 100:
        invalidar('limit', 'Maximo 100')
    desde, hasta = fecha(query.get('desde'), 'desde'), fecha(query.get('hasta'), 'hasta', fin_dia=True)
    if desde and hasta and desde > hasta:
        invalidar('hasta', 'Debe ser posterior o igual a desde')
    return {"tipo": tipo, "estado_inventario": estado, "producto_id": query_entero('producto_id'),
            "desde": desde, "hasta": hasta, "page": page, "limit": limit}


def fecha(entrada, campo, fin_dia=False):
    if entrada is None:
        return None
    if not isinstance(entrada, str):
        invalidar(campo, 'Fecha invalida')
    try:
        es_fecha_sola = re.fullmatch(r'\d{4}-\d{2}-\d{2}', entrada) is not None
        if es_fecha_sola:
            entrada += 'T23:59:59.999999' if fin_dia else 'T00:00:00'
        t = datetime.fromisoformat(entrada.replace('Z', '+00:00'))
        if t.tzinfo:
            t = t.astimezone(timezone.utc).replace(tzinfo=None)
        return t
    except ValueError:
        invalidar(campo, 'Use fecha AAAA-MM-DD o fecha-hora ISO 8601')
