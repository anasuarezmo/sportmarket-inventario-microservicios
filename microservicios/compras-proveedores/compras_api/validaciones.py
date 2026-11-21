import re
from decimal import Decimal, InvalidOperation
from datetime import datetime
from .errores import requerido

def entero(v, campo):
    if isinstance(v, bool) or not (isinstance(v, int) or isinstance(v, str) and v.isdigit()):
        raise requerido(campo, 'Debe ser un entero positivo')
    n = int(v)
    if n < 1:
        raise requerido(campo, 'Debe ser un entero positivo')
    return n

def texto(v, campo, maximo=150):
    if not isinstance(v, str) or not v.strip() or len(v.strip()) > maximo:
        raise requerido(campo, f'Debe tener entre 1 y {maximo} caracteres')
    return v.strip()

def booleano(v, campo):
    if not isinstance(v, bool):
        raise requerido(campo, 'Debe ser booleano')
    return v

def costo(v, campo):
    if isinstance(v, bool) or v is None:
        raise requerido(campo, 'Costo inválido')
    try:
        d = Decimal(str(v))
        if not d.is_finite() or d < 0 or d.as_tuple().exponent < -2 or d > Decimal('9999999999.99'):
            raise ValueError()
        return d
    except (InvalidOperation, ValueError):
        raise requerido(campo, 'Debe ser decimal no negativo con máximo 2 decimales')

def email(v):
    if v is None or v == '':
        return None
    s = texto(v, 'email', 120)
    if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', s):
        raise requerido('email', 'Formato de correo inválido')
    return s

def paginar(params):
    page = entero(params.get('page', 1), 'page')
    limit = entero(params.get('limit', 20), 'limit')
    if limit > 100:
        raise requerido('limit', 'Máximo 100')
    return page, limit

def fecha_iso(v, campo):
    if not v: return None
    try:
        return datetime.fromisoformat(v.replace('Z', '+00:00')).replace(tzinfo=None)
    except (ValueError, AttributeError):
        raise requerido(campo, 'Formato de fecha inválido')

def datos_proveedor(body, parcial=False):
    if not isinstance(body, dict): raise requerido('body', 'Se espera objeto JSON')
    out = {}
    for k, n in [('nit', 20), ('razon_social', 150)]:
        if not parcial or k in body: out[k] = texto(body.get(k), k, n)
    for k, n in [('contacto', 100), ('telefono', 30), ('direccion', 150)]:
        if k in body: out[k] = texto(body[k], k, n) if body[k] is not None else None
    if 'email' in body: out['email'] = email(body['email'])
    return out

def validar_detalles_orden(body):
    if not isinstance(body, dict): raise requerido('body')
    proveedor_id = entero(body.get('proveedor_id'), 'proveedor_id')
    bodega_id = entero(body.get('bodega_destino_id'), 'bodega_destino_id')
    lineas = body.get('detalles')
    if not isinstance(lineas, list) or not lineas: raise requerido('detalles', 'Debe incluir al menos una línea')
    resultado, ids = [], set()
    for i, d in enumerate(lineas):
        if not isinstance(d, dict): raise requerido(f'detalles[{i}]')
        p = entero(d.get('producto_id'), f'detalles[{i}].producto_id')
        if p in ids: raise requerido('detalles', 'No se puede repetir producto_id en una orden')
        ids.add(p)
        resultado.append({'producto_id': p, 'cantidad_solicitada': entero(d.get('cantidad_solicitada'), f'detalles[{i}].cantidad_solicitada'), 'costo_unitario': costo(d.get('costo_unitario'), f'detalles[{i}].costo_unitario')})
    return proveedor_id, bodega_id, resultado

def validar_recepcion(body):
    if not isinstance(body, dict): raise requerido('body')
    lineas = body.get('detalles')
    if not isinstance(lineas, list) or not lineas: raise requerido('detalles', 'Debe incluir al menos una línea')
    resultado, ids = [], set()
    for i, d in enumerate(lineas):
        if not isinstance(d, dict): raise requerido(f'detalles[{i}]')
        ident = entero(d.get('orden_detalle_id'), f'detalles[{i}].orden_detalle_id')
        if ident in ids: raise requerido('detalles', 'Línea repetida')
        ids.add(ident)
        resultado.append({'orden_detalle_id': ident, 'cantidad_recibida': entero(d.get('cantidad_recibida'), f'detalles[{i}].cantidad_recibida')})
    return resultado
