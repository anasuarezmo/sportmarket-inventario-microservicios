from decimal import Decimal
from django.db import connection, transaction, IntegrityError
from .errores import ErrorApi, no_existe

def filas(sql, args=()):
    with connection.cursor() as cursor:
        cursor.execute(sql, args)
        columnas = [d[0] for d in cursor.description]
        return [dict(zip(columnas, row)) for row in cursor.fetchall()]

def uno(sql, args=()):
    r = filas(sql, args)
    return r[0] if r else None

def ejecutar(sql, args=()):
    with connection.cursor() as cursor:
        cursor.execute(sql, args)
        return cursor.lastrowid or cursor.rowcount

def proveedor(identificador, bloqueo=False):
    p = uno('SELECT * FROM proveedor WHERE id=%s' + (' FOR UPDATE' if bloqueo else ''), [identificador])
    if not p: raise no_existe('Proveedor')
    return p

def listar_proveedores(params, page, limit):
    where, valores = [], []
    q = params.get('q')
    if q:
        where.append('(razon_social LIKE %s OR nit LIKE %s)')
        valores.extend([f'%{q}%', f'%{q}%'])
    if 'proveedor_activo' in params:
        s = params['proveedor_activo'].lower()
        if s not in ('true','false','1','0'):
            raise ErrorApi(400, 'DATOS_INVALIDOS', 'proveedor_activo debe ser booleano')
        where.append('proveedor_activo = %s')
        valores.append(1 if s in ('true', '1') else 0)
    clausula = (' WHERE ' + ' AND '.join(where)) if where else ''
    total = uno('SELECT COUNT(*) AS total FROM proveedor' + clausula, valores)['total']
    items = filas('SELECT * FROM proveedor' + clausula + ' ORDER BY id LIMIT %s OFFSET %s', valores + [limit, (page-1)*limit])
    return {'items': items, 'total': total, 'page': page, 'limit': limit}

def crear_proveedor(datos):
    try:
        pid = ejecutar('INSERT INTO proveedor (nit, razon_social, contacto, email, telefono, direccion) VALUES (%s,%s,%s,%s,%s,%s)', [datos['nit'], datos['razon_social'], datos.get('contacto'), datos.get('email'), datos.get('telefono'), datos.get('direccion')])
    except IntegrityError:
        raise ErrorApi(409, 'DUPLICADO', 'El NIT ya existe')
    return proveedor(pid)

def actualizar_proveedor(identificador, datos):
    proveedor(identificador)
    if datos:
        updates = ','.join(f'{k}=%s' for k in datos)
        try:
            ejecutar(f'UPDATE proveedor SET {updates} WHERE id=%s', [*datos.values(), identificador])
        except IntegrityError:
            raise ErrorApi(409, 'DUPLICADO', 'El NIT ya existe')
    return proveedor(identificador)

def productos_proveedor(identificador):
    proveedor(identificador)
    return filas('SELECT id, proveedor_id, producto_id, costo_referencia FROM producto_proveedor WHERE proveedor_id=%s ORDER BY id', [identificador])

def asociar_producto(identificador, producto_id, costo_referencia):
    with transaction.atomic():
        p = proveedor(identificador, bloqueo=True)
        if not p['proveedor_activo']:
            raise ErrorApi(422, 'PROVEEDOR_INACTIVO', 'No se pueden asociar productos a un proveedor inactivo')
        try:
            ident = ejecutar('INSERT INTO producto_proveedor (proveedor_id, producto_id, costo_referencia) VALUES (%s,%s,%s)', [identificador, producto_id, costo_referencia])
        except IntegrityError:
            raise ErrorApi(409, 'DUPLICADO', 'Producto ya asociado a este proveedor')
    return uno('SELECT * FROM producto_proveedor WHERE id=%s', [ident])

def orden(identificador, bloqueo=False):
    o = uno('SELECT * FROM orden_compra WHERE id=%s' + (' FOR UPDATE' if bloqueo else ''), [identificador])
    if not o: raise no_existe('Orden de compra')
    o['detalles'] = filas('SELECT * FROM orden_detalle WHERE orden_id=%s ORDER BY id', [identificador])
    return o

def listar_ordenes(params, page, limit, fecha_iso):
    where, args = [], []
    if params.get('estado'):
        if params['estado'] not in ('CREADA','PARCIALMENTE_RECIBIDA','RECIBIDA','CANCELADA'):
            raise ErrorApi(400, 'DATOS_INVALIDOS', 'Estado de orden inválido')
        where.append('estado=%s'); args.append(params['estado'])
    if params.get('proveedor_id'):
        from .validaciones import entero
        where.append('proveedor_id=%s'); args.append(entero(params['proveedor_id'],'proveedor_id'))
    desde = fecha_iso(params.get('desde'), 'desde')
    hasta = fecha_iso(params.get('hasta'), 'hasta')
    if desde and hasta and desde > hasta: raise ErrorApi(400, 'DATOS_INVALIDOS', 'desde debe ser anterior a hasta')
    if desde: where.append('fecha_creacion_orden >= %s'); args.append(desde)
    if hasta: where.append('fecha_creacion_orden <= %s'); args.append(hasta)
    w = (' WHERE ' + ' AND '.join(where)) if where else ''
    total = uno('SELECT COUNT(*) AS total FROM orden_compra'+w, args)['total']
    items = filas('SELECT * FROM orden_compra'+w+' ORDER BY id DESC LIMIT %s OFFSET %s', args+[limit,(page-1)*limit])
    return {'items':items,'total':total,'page':page,'limit':limit}

def crear_orden(proveedor_id, bodega_id, detalles, usuario_id):
    with transaction.atomic():
        p = proveedor(proveedor_id, bloqueo=True)
        if not p['proveedor_activo']:
            raise ErrorApi(422,'PROVEEDOR_INACTIVO','El proveedor debe estar activo')
        total = sum((Decimal(d['cantidad_solicitada']) * d['costo_unitario'] for d in detalles), Decimal('0'))
        if total > Decimal('999999999999.99'):
            raise ErrorApi(422, 'TOTAL_EXCEDIDO', 'El total excede el máximo permitido')
        ident = ejecutar('INSERT INTO orden_compra (proveedor_id,bodega_destino_id,estado,total,usuario_registrador_id) VALUES (%s,%s,%s,%s,%s)', [proveedor_id,bodega_id,'CREADA',total,usuario_id])
        # Numero estable y unico, derivado del ID. No usar MAX(id) + 1 por carreras.
        ejecutar('UPDATE orden_compra SET numero=%s WHERE id=%s', [f'OC-{ident:04d}', ident])
        for d in detalles:
            ejecutar('INSERT INTO orden_detalle (orden_id,producto_id,cantidad_solicitada,cantidad_recibida,costo_unitario) VALUES (%s,%s,%s,%s,%s)', [ident,d['producto_id'],d['cantidad_solicitada'],0,d['costo_unitario']])
    return orden(ident)

def cancelar_orden(identificador):
    with transaction.atomic():
        o = orden(identificador, bloqueo=True)
        if o['estado'] != 'CREADA' or uno('SELECT id FROM recepcion WHERE orden_id=%s LIMIT 1',[identificador]):
            raise ErrorApi(409,'ESTADO_INVALIDO','Solo se puede cancelar una orden CREADA sin recepciones')
        ejecutar('UPDATE orden_compra SET estado=%s WHERE id=%s',['CANCELADA',identificador])
    return orden(identificador)

def listar_recepciones(identificador):
    orden(identificador)
    return [dict(r, detalles=filas('SELECT * FROM recepcion_detalle WHERE recepcion_id=%s ORDER BY id',[r['id']])) for r in filas('SELECT * FROM recepcion WHERE orden_id=%s ORDER BY id',[identificador])]

def recepcion(identificador):
    r = uno('SELECT * FROM recepcion WHERE id=%s',[identificador])
    if not r: raise no_existe('Recepción')
    r['detalles'] = filas('SELECT * FROM recepcion_detalle WHERE recepcion_id=%s ORDER BY id',[identificador])
    return r

def crear_recepcion(orden_id, detalles, usuario_id):
    from uuid import uuid4
    with transaction.atomic():
        o = orden(orden_id, bloqueo=True)
        if o['estado'] not in ('CREADA','PARCIALMENTE_RECIBIDA'):
            raise ErrorApi(409,'ESTADO_INVALIDO','La orden no admite nuevas recepciones')
        por_id = {d['id']: d for d in o['detalles']}
        for d in detalles:
            linea = por_id.get(d['orden_detalle_id'])
            if not linea:
                raise ErrorApi(422,'LINEA_INVALIDA','El detalle no pertenece a la orden')
            # Reservas pendientes evitan que dos recepciones en paralelo excedan lo solicitado.
            pendiente = uno('SELECT COALESCE(SUM(rd.cantidad_recibida),0) AS cantidad FROM recepcion_detalle rd JOIN recepcion r ON r.id=rd.recepcion_id WHERE rd.orden_detalle_id=%s AND rd.aplicada=0 AND r.estado=%s', [linea['id'],'PENDIENTE_DE_SINCRONIZAR'])['cantidad']
            if linea['cantidad_recibida'] + pendiente + d['cantidad_recibida'] > linea['cantidad_solicitada']:
                raise ErrorApi(422,'CANTIDAD_EXCEDIDA','Cantidad recibida supera la cantidad pendiente')
        rid = ejecutar('INSERT INTO recepcion (orden_id, usuario_receptor_id, estado) VALUES (%s,%s,%s)', [orden_id,usuario_id,'PENDIENTE_DE_SINCRONIZAR'])
        for d in detalles:
            ejecutar('INSERT INTO recepcion_detalle (recepcion_id,orden_detalle_id,cantidad_recibida,operacion_id) VALUES (%s,%s,%s,%s)', [rid,d['orden_detalle_id'],d['cantidad_recibida'],str(uuid4())])
    return recepcion(rid)

def aplicar_linea(identificador):
    # No acumula dos veces aunque Inventario responda 200 (reintento de la misma operacion).
    with transaction.atomic():
        r = uno('SELECT * FROM recepcion_detalle WHERE id=%s FOR UPDATE',[identificador])
        if not r: raise no_existe('Detalle de recepción')
        if r['aplicada']: return
        ejecutar('UPDATE recepcion_detalle SET aplicada=1 WHERE id=%s',[identificador])
        ejecutar('UPDATE orden_detalle SET cantidad_recibida=cantidad_recibida+%s WHERE id=%s', [r['cantidad_recibida'], r['orden_detalle_id']])
        oid = uno('SELECT orden_id FROM orden_detalle WHERE id=%s',[r['orden_detalle_id']])['orden_id']
        _recalcular_estado_orden(oid)

def _recalcular_estado_orden(orden_id):
    linea = uno('SELECT COALESCE(SUM(cantidad_recibida),0) AS recibidas, COALESCE(SUM(cantidad_solicitada),0) AS solicitadas FROM orden_detalle WHERE orden_id=%s',[orden_id])
    if linea['recibidas'] == linea['solicitadas']: estado = 'RECIBIDA'
    elif linea['recibidas'] > 0: estado = 'PARCIALMENTE_RECIBIDA'
    else: estado = 'CREADA'
    ejecutar('UPDATE orden_compra SET estado=%s WHERE id=%s',[estado, orden_id])

def fijar_estado_recepcion(identificador, estado):
    ejecutar('UPDATE recepcion SET estado=%s WHERE id=%s',[estado, identificador])
    return recepcion(identificador)
