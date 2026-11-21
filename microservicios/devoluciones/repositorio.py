"""Persistencia MySQL. No accede a bases de otros microservicios."""
import uuid
from contextlib import contextmanager
import mysql.connector


class Repositorio:
    def __init__(self, config):
        self.config = config

    @contextmanager
    def conexion(self):
        conn = mysql.connector.connect(
            host=self.config['db_host'], port=self.config['db_port'],
            database=self.config['db_name'], user=self.config['db_user'],
            password=self.config['db_password'], connection_timeout=5)
        try:
            yield conn
        finally:
            conn.close()

    def ping(self):
        with self.conexion() as conn:
            conn.ping(reconnect=False, attempts=1)

    @staticmethod
    def serializar(cabecera, lineas=None):
        if cabecera is None:
            return None
        d = dict(cabecera)
        if d.get('fecha') is not None:
            d['fecha'] = d['fecha'].isoformat(timespec='seconds')
        if lineas is not None:
            d['detalles'] = [dict(x) for x in lineas]
        return d

    def crear(self, datos, usuario_id):
        with self.conexion() as conn:
            try:
                cur = conn.cursor(dictionary=True)
                cur.execute('''INSERT INTO devolucion
                    (tipo, motivo, bodega_id, proveedor_id, documento_ref, estado_inventario, usuario_id)
                    VALUES (%s,%s,%s,%s,%s,'PENDIENTE',%s)''',
                    (datos['tipo'], datos['motivo'], datos['bodega_id'], datos['proveedor_id'], datos['documento_ref'], usuario_id))
                dev_id = cur.lastrowid
                for item in datos['detalles']:
                    operacion = None if datos['tipo'] == 'CLIENTE' and item['condicion'] == 'DEFECTUOSO' else str(uuid.uuid4())
                    cur.execute('''INSERT INTO devolucion_detalle
                        (devolucion_id, producto_id, cantidad, condicion, operacion_id)
                        VALUES (%s,%s,%s,%s,%s)''',
                        (dev_id, item['producto_id'], item['cantidad'], item['condicion'], operacion))
                conn.commit()
            except Exception:
                conn.rollback()
                raise
        return self.obtener(dev_id)

    def obtener(self, dev_id):
        with self.conexion() as conn:
            cur = conn.cursor(dictionary=True)
            cur.execute('''SELECT id, tipo, fecha, motivo, bodega_id, proveedor_id,
                documento_ref, estado_inventario, usuario_id FROM devolucion WHERE id=%s''', (dev_id,))
            cab = cur.fetchone()
            if cab is None:
                return None
            cur.execute('''SELECT id, producto_id, cantidad, condicion, operacion_id
                FROM devolucion_detalle WHERE devolucion_id=%s ORDER BY id''', (dev_id,))
            return self.serializar(cab, cur.fetchall())

    def listar(self, f):
        where, vals = [], []
        for campo in ['tipo', 'estado_inventario']:
            if f[campo] is not None:
                where.append(f'd.{campo} = %s'); vals.append(f[campo])
        if f['producto_id'] is not None:
            where.append('EXISTS (SELECT 1 FROM devolucion_detalle l WHERE l.devolucion_id=d.id AND l.producto_id=%s)')
            vals.append(f['producto_id'])
        if f['desde'] is not None:
            where.append('d.fecha >= %s'); vals.append(f['desde'])
        if f['hasta'] is not None:
            where.append('d.fecha <= %s'); vals.append(f['hasta'])
        clausula = ' WHERE ' + ' AND '.join(where) if where else ''
        with self.conexion() as conn:
            cur = conn.cursor(dictionary=True)
            cur.execute('SELECT COUNT(*) AS total FROM devolucion d' + clausula, tuple(vals))
            total = cur.fetchone()['total']
            cur.execute('''SELECT d.id, d.tipo, d.fecha, d.motivo, d.bodega_id,
                d.proveedor_id, d.documento_ref, d.estado_inventario, d.usuario_id
                FROM devolucion d''' + clausula + ' ORDER BY d.id DESC LIMIT %s OFFSET %s',
                tuple(vals + [f['limit'], (f['page'] - 1) * f['limit']]))
            rows = [self.serializar(x) for x in cur.fetchall()]
        return {"items": rows, "total": total, "page": f['page'], "limit": f['limit']}

    def marcar_aplicada(self, dev_id):
        # La marca se escribe tras confirmar TODOS los movimientos externos.
        with self.conexion() as conn:
            cur = conn.cursor()
            cur.execute("UPDATE devolucion SET estado_inventario='APLICADA' WHERE id=%s AND estado_inventario='PENDIENTE'", (dev_id,))
            conn.commit()
            return cur.rowcount > 0
