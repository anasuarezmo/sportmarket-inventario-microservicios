import json
import os
import re
import secrets
import uuid
from functools import wraps
from pathlib import Path
from django.db import DatabaseError, connection
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.core.serializers.json import DjangoJSONEncoder
from . import repositorio as repo
from . import integraciones, servicio
from .validaciones import (paginar, datos_proveedor, entero, booleano, costo,
                           validar_detalles_orden, validar_recepcion, fecha_iso)
from .errores import ErrorApi, requerido

LECTORES = {'ADM', 'INV', 'COM', 'CON'}
ESCRITORES = {'ADM', 'COM'}
RECEPTORES = {'ADM', 'COM', 'BOD'}
CONSULTA_RECEPCIONES = {'ADM', 'COM', 'INV', 'BOD'}

def responder(datos, status=200, cid=None):
    def convertir_booleanos(obj):
        from decimal import Decimal
        if isinstance(obj, Decimal): return float(obj)
        if isinstance(obj, dict):
            return {k: (bool(v) if k in ('proveedor_activo', 'aplicada') and v is not None else convertir_booleanos(v)) for k, v in obj.items()}
        if isinstance(obj, list):
            return [convertir_booleanos(v) for v in obj]
        return obj
    datos = convertir_booleanos(datos)
    r = JsonResponse(datos, status=status, encoder=DjangoJSONEncoder, safe=isinstance(datos, dict), json_dumps_params={'ensure_ascii': False})
    r['X-Correlation-ID'] = cid or str(uuid.uuid4())
    return r

def api(func):
    @csrf_exempt
    @wraps(func)
    def decorada(request, *args, **kwargs):
        recibido = request.headers.get('X-Correlation-ID', '')
        cid = recibido if re.fullmatch(r'[\w-]{8,64}', recibido) else str(uuid.uuid4())
        request.cid = cid
        try:
            token = os.environ.get('INTERNAL_TOKEN', '')
            enviado = request.headers.get('X-Internal-Token', '')
            if not token or not enviado or not secrets.compare_digest(token, enviado):
                raise ErrorApi(401, 'NO_AUTENTICADO', 'Credencial interna ausente o incorrecta')
            rol = request.headers.get('X-User-Role')
            if rol not in {'ADM','INV','COM','BOD','CON'}:
                raise ErrorApi(403, 'PROHIBIDO', 'Rol inválido o ausente')
            request.rol = rol
            uid = request.headers.get('X-User-Id')
            request.usuario_id = int(uid) if uid and uid.isdigit() and int(uid)>0 else None
            resultado, status = func(request, *args, **kwargs)
            if isinstance(resultado, HttpResponse):
                resultado['X-Correlation-ID'] = cid
                return resultado
            return responder(resultado, status, cid)
        except ErrorApi as exc:
            return responder({'codigo':exc.codigo,'mensaje':exc.mensaje,'detalles':exc.detalles,'correlation_id':cid}, exc.status, cid)
        except DatabaseError:
            return responder({'codigo':'BASE_NO_DISPONIBLE','mensaje':'No se pudo acceder a la base de datos','detalles':[],'correlation_id':cid},503,cid)
        except Exception:
            # No filtrar datos privados ni trazas al cliente.
            return responder({'codigo':'ERROR_INTERNO','mensaje':'Error interno del servicio','detalles':[],'correlation_id':cid},500,cid)
    return decorada

def comprobar_rol(request, roles):
    if request.rol not in roles:
        raise ErrorApi(403, 'PROHIBIDO', 'Tu rol no tiene permisos para esta operación')

def datos_json(request):
    try:
        if not request.content_type.startswith('application/json'):
            raise requerido('Content-Type','Se requiere application/json')
        body = json.loads(request.body)
    except (ValueError, UnicodeDecodeError):
        raise requerido('body', 'JSON inválido')
    if not isinstance(body, dict): raise requerido('body','Se espera objeto JSON')
    return body

def metodo(request, valido):
    if request.method not in valido:
        raise ErrorApi(405, 'METODO_NO_PERMITIDO', 'Método HTTP no permitido')

def health(request):
    if request.method != 'GET':
        return responder({'estado':'DOWN'},405)
    try:
        with connection.cursor() as c:
            c.execute('SELECT 1')
            c.fetchone()
        return responder({'estado':'UP'}, 200)
    except DatabaseError:
        return responder({'estado':'DOWN'},503)

@api
def documentacion(request):
    metodo(request, {'GET'})
    # Se sirve la copia del contrato de la Entrega 2.
    with open(Path(__file__).resolve().parent.parent/'openapi.yaml', encoding='utf-8') as f:
        return HttpResponse(f.read(), content_type='application/yaml'),200

@api
def proveedores(request):
    metodo(request, {'GET','POST'})
    if request.method == 'GET':
        comprobar_rol(request, LECTORES)
        p,l = paginar(request.GET)
        return repo.listar_proveedores(request.GET,p,l),200
    comprobar_rol(request, ESCRITORES)
    datos = datos_proveedor(datos_json(request))
    return {'mensaje':'Proveedor registrado','proveedor':repo.crear_proveedor(datos)},201

@api
def proveedor(request, identificador):
    metodo(request, {'GET','PUT'})
    if request.method == 'GET':
        comprobar_rol(request, LECTORES)
        return repo.proveedor(identificador),200
    comprobar_rol(request, ESCRITORES)
    datos = datos_proveedor(datos_json(request),parcial=True)
    if not datos: raise requerido('body','Debe actualizar al menos un campo')
    return {'mensaje':'Proveedor actualizado','proveedor':repo.actualizar_proveedor(identificador, datos)},200

@api
def proveedor_estado(request, identificador):
    metodo(request, {'PATCH'})
    comprobar_rol(request, ESCRITORES)
    body = datos_json(request)
    activo = booleano(body.get('proveedor_activo'),'proveedor_activo')
    return {'mensaje':'Estado actualizado','proveedor':repo.actualizar_proveedor(identificador,{'proveedor_activo':activo})},200

@api
def proveedor_productos(request, identificador):
    metodo(request, {'GET','POST'})
    if request.method == 'GET':
        comprobar_rol(request, LECTORES)
        items = repo.productos_proveedor(identificador)
        return {'items':items,'total':len(items),'page':1,'limit':len(items)},200
    comprobar_rol(request, ESCRITORES)
    body = datos_json(request)
    pid = entero(body.get('producto_id'),'producto_id')
    precio = costo(body.get('costo_referencia'),'costo_referencia')
    repo.proveedor(identificador)
    integraciones.validar_producto(pid,request.cid)
    return {'mensaje':'Producto asociado','producto_proveedor':repo.asociar_producto(identificador,pid,precio)},201

@api
def compras(request):
    metodo(request, {'GET','POST'})
    if request.method == 'GET':
        comprobar_rol(request, LECTORES)
        p,l = paginar(request.GET)
        return repo.listar_ordenes(request.GET,p,l,fecha_iso),200
    comprobar_rol(request, ESCRITORES)
    proveedor_id,bodega_id,detalles = validar_detalles_orden(datos_json(request))
    repo.proveedor(proveedor_id)
    for d in detalles:
        integraciones.validar_producto(d['producto_id'],request.cid)
    return {'mensaje':'Orden de compra registrada','orden':repo.crear_orden(proveedor_id,bodega_id,detalles,request.usuario_id)},201

@api
def compra(request, identificador):
    metodo(request, {'GET'})
    comprobar_rol(request, LECTORES)
    return repo.orden(identificador),200

@api
def compra_estado(request, identificador):
    metodo(request, {'PATCH'})
    comprobar_rol(request, ESCRITORES)
    if datos_json(request).get('estado') != 'CANCELADA':
        raise requerido('estado','Solo se permite CANCELADA')
    return {'mensaje':'Orden cancelada','orden':repo.cancelar_orden(identificador)},200

@api
def recepciones(request, identificador):
    metodo(request, {'GET','POST'})
    if request.method == 'GET':
        comprobar_rol(request, CONSULTA_RECEPCIONES)
        items = repo.listar_recepciones(identificador)
        return {'items':items,'total':len(items),'page':1,'limit':len(items)},200
    comprobar_rol(request, RECEPTORES)
    lineas = validar_recepcion(datos_json(request))
    recepcion = repo.crear_recepcion(identificador,lineas,request.usuario_id)
    # Guardar y confirmar la transacción antes de llamar a Inventario.
    recepcion = servicio.sincronizar_recepcion(recepcion['id'], request.cid)
    return {'mensaje':'Recepción registrada','recepcion':recepcion},201
