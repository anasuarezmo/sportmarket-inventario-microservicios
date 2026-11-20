"""Acceso a reportes_db (PyMySQL). Solo existe la tabla alerta. Una conexion por operacion: el volumen es bajo."""
import logging
import os
import time

import pymysql
import pymysql.cursors

log = logging.getLogger("reportes")
DUPLICADO = 1062
COLUMNAS = ("id, producto_id, bodega_id, cantidad_disponible_al_generar, stock_minimo, estado_alerta, "
            "fecha_generacion_alerta, atendida_en, usuario_atencion_id")


def _alerta(fila):
    if fila is None:
        return None
    f = dict(fila)
    for c in ("fecha_generacion_alerta", "atendida_en"):
        if f.get(c) is not None:
            f[c] = f[c].strftime("%Y-%m-%dT%H:%M:%SZ")  # la sesion trabaja en UTC
    return f


def crear_repositorio(bd, conectar=None):
    def conexion():
        if conectar:
            return conectar()
        c = pymysql.connect(host=bd["host"], port=bd["port"], user=bd["user"], password=bd["password"], database=bd["database"],
                            cursorclass=pymysql.cursors.DictCursor, autocommit=True, connect_timeout=5, charset="utf8mb4")
        with c.cursor() as cur:
            cur.execute("SET time_zone = '+00:00'")
        return c

    def uno(sql, params=()):
        c = conexion()
        try:
            with c.cursor() as cur:
                cur.execute(sql, params)
                return cur.fetchone()
        finally:
            c.close()

    class Repo:
        def ping(self):
            uno("SELECT 1")

        def aplicar_esquema(self, ruta, intentos=30, espera=2):
            """CREATE TABLE IF NOT EXISTS al arrancar; reintenta mientras MySQL termina de levantar."""
            with open(ruta, encoding="utf-8") as f:
                texto = "\n".join(l for l in f.read().splitlines() if not l.strip().startswith("--"))
            sentencias = [x.strip() for x in texto.split(";") if x.strip()]
            ultimo = None
            for _ in range(intentos):
                try:
                    c = conexion()
                    try:
                        with c.cursor() as cur:
                            for sql in sentencias:
                                cur.execute(sql)
                        return
                    finally:
                        c.close()
                except Exception as e:  # MySQL aun no responde
                    ultimo = e
                    log.warning("Esperando a MySQL: %s", e)
                    time.sleep(espera)
            raise ultimo

        def crear_activa(self, producto_id, bodega_id, cantidad, minimo):
            """(alerta, creada). Si ya hay una ACTIVA para el par, la devuelve sin crear otra."""
            c = conexion()
            try:
                with c.cursor() as cur:
                    try:
                        cur.execute("INSERT INTO alerta (producto_id, bodega_id, cantidad_disponible_al_generar, stock_minimo, "
                                    "estado_alerta, fecha_generacion_alerta) VALUES (%s, %s, %s, %s, 'ACTIVA', UTC_TIMESTAMP())",
                                    (producto_id, bodega_id, cantidad, minimo))
                        nuevo = cur.lastrowid
                        creada = True
                    except pymysql.err.IntegrityError as e:
                        if e.args[0] != DUPLICADO:
                            raise
                        creada = False
                    if creada:
                        cur.execute(f"SELECT {COLUMNAS} FROM alerta WHERE id = %s", (nuevo,))
                    else:
                        cur.execute(f"SELECT {COLUMNAS} FROM alerta WHERE producto_id = %s AND bodega_id = %s AND estado_alerta = 'ACTIVA'",
                                    (producto_id, bodega_id))
                    return _alerta(cur.fetchone()), creada
            finally:
                c.close()

        def cerrar_activa(self, producto_id, bodega_id):
            """Marca ATENDIDA la alerta activa (usuario nulo). Devuelve la alerta o None si no habia."""
            c = conexion()
            try:
                with c.cursor() as cur:
                    cur.execute(f"SELECT {COLUMNAS} FROM alerta WHERE producto_id = %s AND bodega_id = %s AND estado_alerta = 'ACTIVA' FOR UPDATE",
                                (producto_id, bodega_id))
                    fila = cur.fetchone()
                    if fila is None:
                        return None
                    cur.execute("UPDATE alerta SET estado_alerta = 'ATENDIDA', atendida_en = UTC_TIMESTAMP(), usuario_atencion_id = NULL "
                                "WHERE id = %s AND estado_alerta = 'ACTIVA'", (fila["id"],))
                    cur.execute(f"SELECT {COLUMNAS} FROM alerta WHERE id = %s", (fila["id"],))
                    return _alerta(cur.fetchone())
            finally:
                c.close()

        def atender(self, id_, usuario_id):
            """('ok', alerta) | ('ya_atendida', alerta) | ('no_existe', None). Un solo UPDATE condicionado: sin carreras."""
            c = conexion()
            try:
                with c.cursor() as cur:
                    cur.execute("UPDATE alerta SET estado_alerta = 'ATENDIDA', atendida_en = UTC_TIMESTAMP(), usuario_atencion_id = %s "
                                "WHERE id = %s AND estado_alerta = 'ACTIVA'", (usuario_id, id_))
                    cambiada = cur.rowcount == 1
                    cur.execute(f"SELECT {COLUMNAS} FROM alerta WHERE id = %s", (id_,))
                    fila = _alerta(cur.fetchone())
                    if fila is None:
                        return "no_existe", None
                    return ("ok" if cambiada else "ya_atendida"), fila
            finally:
                c.close()

        def listar(self, f):
            donde, p = [], []
            for campo in ("estado_alerta", "producto_id", "bodega_id"):
                if f.get(campo) is not None:
                    donde.append(f"{campo} = %s")
                    p.append(f[campo])
            w = (" WHERE " + " AND ".join(donde)) if donde else ""
            c = conexion()
            try:
                with c.cursor() as cur:
                    cur.execute(f"SELECT COUNT(*) AS n FROM alerta{w}", p)
                    total = cur.fetchone()["n"]
                    cur.execute(f"SELECT {COLUMNAS} FROM alerta{w} ORDER BY id DESC LIMIT %s OFFSET %s",
                                p + [f["limit"], (f["page"] - 1) * f["limit"]])
                    return [_alerta(x) for x in cur.fetchall()], total
            finally:
                c.close()

        def contar_activas(self):
            return uno("SELECT COUNT(*) AS n FROM alerta WHERE estado_alerta = 'ACTIVA'")["n"]

    return Repo()


RUTA_ESQUEMA = os.path.join(os.path.dirname(__file__), "..", "sql", "schema.sql")
