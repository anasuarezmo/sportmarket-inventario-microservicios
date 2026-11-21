"""Acceso exclusivo a usuarios_db. Sentencias parametrizadas y transacciones."""
from contextlib import contextmanager

import mysql.connector


class Repositorio:
    def __init__(self, config_mysql):
        self.cfg = config_mysql

    @contextmanager
    def conexion(self):
        cn = mysql.connector.connect(**self.cfg)
        try:
            yield cn
        finally:
            cn.close()

    @staticmethod
    def _consulta_uno(cn, sql, params=()):
        cursor = cn.cursor(dictionary=True)
        try:
            cursor.execute(sql, params)
            return cursor.fetchone()
        finally:
            cursor.close()

    @staticmethod
    def _consulta_todos(cn, sql, params=()):
        cursor = cn.cursor(dictionary=True)
        try:
            cursor.execute(sql, params)
            return cursor.fetchall()
        finally:
            cursor.close()

    @staticmethod
    def _ejecutar(cn, sql, params=()):
        cursor = cn.cursor()
        try:
            cursor.execute(sql, params)
            return cursor.lastrowid, cursor.rowcount
        finally:
            cursor.close()

    _SELECT_USER = ("SELECT u.id, u.nombre, u.email, u.password_hash, u.rol_id, "
                    "u.usuario_activo, u.fecha_registro, u.fecha_ultimo_acceso, r.nombre AS rol_nombre "
                    "FROM usuario u JOIN rol r ON r.id = u.rol_id ")

    def usuario_email(self, email):
        with self.conexion() as cn:
            return self._consulta_uno(cn, self._SELECT_USER + "WHERE u.email = %s", (email,))

    def usuario_id(self, id_usuario):
        with self.conexion() as cn:
            return self._consulta_uno(cn, self._SELECT_USER + "WHERE u.id = %s", (id_usuario,))

    def guardar_ultimo_acceso(self, id_usuario):
        with self.conexion() as cn:
            self._ejecutar(cn, "UPDATE usuario SET fecha_ultimo_acceso=UTC_TIMESTAMP() WHERE id=%s", (id_usuario,))
            cn.commit()

    def roles(self):
        with self.conexion() as cn:
            return self._consulta_todos(cn, "SELECT id,nombre,descripcion FROM rol ORDER BY id")

    def rol_existe(self, rol_id):
        with self.conexion() as cn:
            return self._consulta_uno(cn, "SELECT id FROM rol WHERE id=%s", (rol_id,)) is not None

    def usuarios(self, filtros):
        clausulas, parametros = [], []
        if filtros.get("rol_id") is not None:
            clausulas.append("u.rol_id=%s")
            parametros.append(filtros["rol_id"])
        if filtros.get("usuario_activo") is not None:
            clausulas.append("u.usuario_activo=%s")
            parametros.append(filtros["usuario_activo"])
        if filtros.get("q"):
            clausulas.append("(u.nombre LIKE %s OR u.email LIKE %s)")
            parametros += ["%" + filtros["q"] + "%"] * 2
        where = (" WHERE " + " AND ".join(clausulas)) if clausulas else ""
        with self.conexion() as cn:
            cant = self._consulta_uno(cn, "SELECT COUNT(*) AS total FROM usuario u" + where, tuple(parametros))["total"]
            filas = self._consulta_todos(
                cn, self._SELECT_USER + where + " ORDER BY u.id LIMIT %s OFFSET %s",
                (*parametros, filtros["limit"], (filtros["page"] - 1) * filtros["limit"]),
            )
            return filas, cant

    def crear_usuario(self, nombre, email, password_hash, rol_id):
        with self.conexion() as cn:
            pk, _ = self._ejecutar(
                cn, "INSERT INTO usuario (nombre,email,password_hash,rol_id) VALUES (%s,%s,%s,%s)",
                (nombre, email, password_hash, rol_id),
            )
            cn.commit()
            return pk

    def actualizar_usuario(self, usuario_id, nombre, email):
        with self.conexion() as cn:
            self._ejecutar(cn, "UPDATE usuario SET nombre=%s,email=%s WHERE id=%s", (nombre, email, usuario_id))
            cn.commit()

    def actualizar_rol(self, usuario_id, rol_id):
        with self.conexion() as cn:
            self._ejecutar(cn, "UPDATE usuario SET rol_id=%s WHERE id=%s", (rol_id, usuario_id))
            cn.commit()

    def actualizar_estado(self, usuario_id, activo):
        with self.conexion() as cn:
            self._ejecutar(cn, "UPDATE usuario SET usuario_activo=%s WHERE id=%s", (activo, usuario_id))
            cn.commit()

    def actualizar_password(self, usuario_id, password_hash):
        with self.conexion() as cn:
            self._ejecutar(cn, "UPDATE usuario SET password_hash=%s WHERE id=%s", (password_hash, usuario_id))
            self._ejecutar(cn, "UPDATE token_recuperacion SET token_utilizado=1 WHERE usuario_id=%s AND token_utilizado=0", (usuario_id,))
            cn.commit()

    def guardar_token(self, usuario_id, token_hash, expiracion_utc):
        with self.conexion() as cn:
            self._ejecutar(cn, "UPDATE token_recuperacion SET token_utilizado=1 WHERE usuario_id=%s AND token_utilizado=0", (usuario_id,))
            self._ejecutar(
                cn, "INSERT INTO token_recuperacion (usuario_id,token_hash,fecha_expiracion) VALUES (%s,%s,%s)",
                (usuario_id, token_hash, expiracion_utc),
            )
            cn.commit()

    def consumir_token(self, token_hash, password_hash):
        """Bloquea el token hasta actualizar la contraseña: evita reutilización concurrente."""
        with self.conexion() as cn:
            cursor = cn.cursor(dictionary=True)
            try:
                cursor.execute(
                    "SELECT id,usuario_id FROM token_recuperacion "
                    "WHERE token_hash=%s AND token_utilizado=0 AND fecha_expiracion>UTC_TIMESTAMP() FOR UPDATE",
                    (token_hash,),
                )
                fila = cursor.fetchone()
            finally:
                cursor.close()
            if not fila:
                cn.rollback()
                return False
            self._ejecutar(cn, "UPDATE usuario SET password_hash=%s WHERE id=%s", (password_hash, fila["usuario_id"]))
            self._ejecutar(cn, "UPDATE token_recuperacion SET token_utilizado=1 WHERE usuario_id=%s", (fila["usuario_id"],))
            cn.commit()
            return True
