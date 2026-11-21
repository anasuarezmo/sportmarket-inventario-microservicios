"""Flask: contrato OpenAPI Entrega 2; validaciones y seguridad de cabeceras internas."""
import hashlib
import hmac
import logging
import re
import secrets
import smtplib
import uuid
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from pathlib import Path

import bcrypt
import jwt
import mysql.connector
from flask import Flask, Response, g, jsonify, request
from werkzeug.exceptions import HTTPException

from .config import cargar_config
from .repositorio import Repositorio

LOG = logging.getLogger(__name__)
CODIGOS_ROL = {1: "ADM", 2: "INV", 3: "COM", 4: "BOD", 5: "CON"}
EMAIL = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
CORRELACION = re.compile(r"^[\w-]{8,64}$")
OPENAPI = Path(__file__).resolve().parent.parent / "openapi.yaml"
DOCS_HTML = '''<!doctype html><html lang="es"><head><meta charset="utf-8"><title>Usuarios - SportMarket</title>
<link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css"></head>
<body><div id="ui"></div><script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
<script>SwaggerUIBundle({url:'/openapi.yaml',dom_id:'#ui'});</script></body></html>'''


def hash_password(contrasena):
    return bcrypt.hashpw(contrasena.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


def password_ok(contrasena, password_hash):
    try:
        return bcrypt.checkpw(contrasena.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def email_ok(value):
    return isinstance(value, str) and len(value) <= 120 and EMAIL.fullmatch(value) is not None


def usuario_publico(u):
    return {
        "id": u["id"], "nombre": u["nombre"], "email": u["email"],
        "rol_id": u["rol_id"], "rol": u["rol_nombre"], "usuario_activo": bool(u["usuario_activo"]),
        "fecha_registro": u["fecha_registro"].isoformat() if u.get("fecha_registro") else None,
        "fecha_ultimo_acceso": u["fecha_ultimo_acceso"].isoformat() if u.get("fecha_ultimo_acceso") else None,
    }


def enviar_correo_smtp(smtp_cfg, email_destino, token, minutos):
    """Devuelve True al entregar al servidor SMTP. Jamás registra el token en logs."""
    if not smtp_cfg["host"] or not smtp_cfg["sender"]:
        LOG.warning("Recuperación solicitada pero SMTP no está configurado: no se envió correo")
        return False
    mensaje = EmailMessage()
    mensaje["Subject"] = "Recuperación de contraseña - SportMarket"
    mensaje["From"] = smtp_cfg["sender"]
    mensaje["To"] = email_destino
    mensaje.set_content(
        "Has solicitado recuperar tu contraseña de SportMarket.\n"
        f"Token de un solo uso: {token}\n"
        f"Válido durante {minutos} minutos.\n"
        "Si no hiciste esta solicitud, ignora el mensaje.\n"
    )
    with smtplib.SMTP(smtp_cfg["host"], smtp_cfg["port"], timeout=5) as smtp:
        if smtp_cfg["use_tls"]:
            smtp.starttls()
        if smtp_cfg["username"]:
            smtp.login(smtp_cfg["username"], smtp_cfg["password"])
        smtp.send_message(mensaje)
    return True


def crear_app(config=None, repo=None, notificador=None):
    cfg = config if config is not None else cargar_config()
    repo = repo if repo is not None else Repositorio(cfg["mysql"])
    if notificador is None:
        notificador = lambda correo, token, mins: enviar_correo_smtp(cfg["smtp"], correo, token, mins)
    app = Flask(__name__)
    app.json.sort_keys = False

    def error(status, codigo, mensaje, detalles=None):
        return jsonify({
            "codigo": codigo, "mensaje": mensaje, "detalles": detalles or [],
            "correlation_id": g.get("cid", str(uuid.uuid4())),
        }), status

    def cuerpo_json():
        if not request.is_json:
            return None
        data = request.get_json(silent=True)
        return data if isinstance(data, dict) else None

    def obligatorio(data, campos):
        if data is None:
            return error(400, "PETICION_INVALIDA", "Se requiere un objeto JSON")
        faltan = [c for c in campos if c not in data or data[c] is None]
        if faltan:
            return error(400, "CAMPOS_OBLIGATORIOS", "Faltan campos obligatorios", [
                {"campo": campo, "error": "Obligatorio"} for campo in faltan
            ])
        return None

    def identificador():
        valor = request.headers.get("X-User-Id", "")
        if not valor.isdecimal() or int(valor) < 1:
            return None
        return int(valor)

    def admin():
        if request.headers.get("X-User-Role") != "ADM":
            return error(403, "PROHIBIDO", "Esta operación requiere rol ADM")
        if identificador() is None:
            return error(401, "NO_AUTENTICADO", "Falta identificar al usuario")
        return None

    def usuario_autenticado():
        if request.headers.get("X-User-Role") not in CODIGOS_ROL.values() or identificador() is None:
            return error(401, "NO_AUTENTICADO", "Falta identificar al usuario")
        return None

    def password_nueva_ok(value):
        return isinstance(value, str) and 8 <= len(value) and len(value.encode("utf-8")) <= 72

    @app.before_request
    def seguridad_interna():
        incoming = request.headers.get("X-Correlation-ID", "")
        g.cid = incoming if CORRELACION.fullmatch(incoming) else str(uuid.uuid4())
        if request.path == "/health":
            return None
        esperado = cfg["internal_token"]
        recibido = request.headers.get("X-Internal-Token", "")
        if not esperado or not recibido or not hmac.compare_digest(recibido, esperado):
            return error(401, "NO_AUTENTICADO", "Credencial interna ausente o incorrecta")
        return None

    @app.after_request
    def agregar_cid(response):
        response.headers["X-Correlation-ID"] = g.get("cid", str(uuid.uuid4()))
        return response

    @app.errorhandler(Exception)
    def errores_globales(exc):
        if isinstance(exc, HTTPException):
            if exc.code == 404:
                return error(404, "NO_ENCONTRADO", "Ruta no encontrada")
            if exc.code == 405:
                return error(405, "METODO_NO_PERMITIDO", "Método no permitido")
            return error(exc.code or 400, "PETICION_INVALIDA", exc.description)
        if isinstance(exc, mysql.connector.Error):
            LOG.exception("Error de MySQL (cid=%s)", g.get("cid"))
            return error(503, "BASE_DATOS_NO_DISPONIBLE", "No se pudo acceder a la base de datos")
        LOG.exception("Error inesperado (cid=%s)", g.get("cid"))
        return error(500, "ERROR_INTERNO", "No se pudo completar la operación")

    @app.get("/health")
    def health():
        return jsonify({"estado": "UP"})

    @app.get("/openapi.yaml")
    def openapi():
        return Response(OPENAPI.read_text(encoding="utf-8"), mimetype="application/yaml")

    @app.get("/docs")
    def docs():
        return Response(DOCS_HTML, mimetype="text/html")

    @app.post("/api/auth/login")
    def login():
        data = cuerpo_json()
        mal = obligatorio(data, ("email", "contrasena"))
        if mal:
            return mal
        correo, clave = data["email"], data["contrasena"]
        if not email_ok(correo) or not isinstance(clave, str) or not clave:
            return error(400, "DATOS_INVALIDOS", "Correo o contraseña inválidos")
        u = repo.usuario_email(correo.strip().lower())
        if not u or not password_ok(clave, u["password_hash"]):
            return error(401, "NO_AUTENTICADO", "Credenciales incorrectas")
        if not u["usuario_activo"]:
            return error(403, "PROHIBIDO", "Usuario desactivado")
        codigo = CODIGOS_ROL.get(u["rol_id"])
        if not codigo:
            return error(403, "PROHIBIDO", "Rol no válido")
        if not cfg["jwt_secret"] or cfg["jwt_secret"] == "cambiar_por_un_secreto_largo":
            return error(503, "SERVICIO_NO_CONFIGURADO", "JWT_SECRET no configurado")
        mins = cfg["jwt_exp_minutes"]
        if mins != 60:
            # El contrato acordó explícitamente 60 minutos.
            mins = 60
        expira = datetime.now(timezone.utc) + timedelta(minutes=mins)
        token = jwt.encode({"sub": str(u["id"]), "rol": codigo, "exp": expira}, cfg["jwt_secret"], algorithm="HS256")
        repo.guardar_ultimo_acceso(u["id"])
        return jsonify({
            "mensaje": "Inicio de sesión exitoso", "token": token, "tipo": "Bearer", "expira_en": mins * 60,
            "usuario": {"id": u["id"], "nombre": u["nombre"], "rol": u["rol_nombre"]},
        })

    @app.post("/api/auth/logout")
    def logout():
        mal = usuario_autenticado()
        if mal:
            return mal
        # Por contrato no hay blacklist; el cliente descarta el JWT.
        return Response(status=204)

    @app.post("/api/auth/forgot-password")
    def forgot_password():
        data = cuerpo_json()
        mal = obligatorio(data, ("email",))
        if mal:
            return mal
        if not email_ok(data["email"]):
            return error(400, "DATOS_INVALIDOS", "Correo no válido")
        u = repo.usuario_email(data["email"].strip().lower())
        if u and u["usuario_activo"]:
            token = secrets.token_urlsafe(32)
            token_hash = hashlib.sha256(token.encode()).hexdigest()
            vencimiento = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(minutes=cfg["recovery_minutes"])
            repo.guardar_token(u["id"], token_hash, vencimiento)
            try:
                notificador(u["email"], token, cfg["recovery_minutes"])
            except (OSError, smtplib.SMTPException):
                LOG.exception("Error de envío SMTP (cid=%s)", g.get("cid"))
        # Respuesta idéntica exista o no el correo; no revela el token.
        return jsonify({"mensaje": "Si el correo existe, recibirás instrucciones de recuperación"}), 202

    @app.post("/api/auth/reset-password")
    def reset_password():
        data = cuerpo_json()
        mal = obligatorio(data, ("token", "contrasena_nueva"))
        if mal:
            return mal
        if not isinstance(data["token"], str) or len(data["token"]) < 16:
            return error(422, "TOKEN_INVALIDO", "Token inválido, vencido o utilizado")
        if not password_nueva_ok(data["contrasena_nueva"]):
            return error(422, "CONTRASENA_INVALIDA", "La contraseña debe tener de 8 a 72 caracteres")
        token_hash = hashlib.sha256(data["token"].encode()).hexdigest()
        valido = repo.consumir_token(token_hash, hash_password(data["contrasena_nueva"]))
        if not valido:
            return error(422, "TOKEN_INVALIDO", "Token inválido, vencido o utilizado")
        return Response(status=204)

    @app.post("/api/auth/change-password")
    def change_password():
        mal = usuario_autenticado()
        if mal:
            return mal
        data = cuerpo_json()
        mal = obligatorio(data, ("contrasena_actual", "contrasena_nueva"))
        if mal:
            return mal
        if not isinstance(data["contrasena_actual"], str):
            return error(400, "DATOS_INVALIDOS", "La contraseña actual debe ser texto")
        if not password_nueva_ok(data["contrasena_nueva"]):
            return error(422, "CONTRASENA_INVALIDA", "La contraseña debe tener de 8 a 72 caracteres")
        u = repo.usuario_id(identificador())
        if not u or not u["usuario_activo"]:
            return error(401, "NO_AUTENTICADO", "Usuario no disponible")
        if not password_ok(data["contrasena_actual"], u["password_hash"]):
            return error(422, "CONTRASENA_INVALIDA", "Contraseña actual incorrecta")
        repo.actualizar_password(u["id"], hash_password(data["contrasena_nueva"]))
        return Response(status=204)

    @app.get("/api/usuarios")
    def listar_usuarios():
        mal = admin()
        if mal:
            return mal
        filtros = {"rol_id": None, "usuario_activo": None, "q": request.args.get("q", "")}
        try:
            page = int(request.args.get("page", "1"))
            limit = int(request.args.get("limit", "20"))
            if page < 1 or limit < 1 or limit > 100:
                raise ValueError()
            filtros.update(page=page, limit=limit)
            if request.args.get("rol_id") is not None:
                filtros["rol_id"] = int(request.args["rol_id"])
                if filtros["rol_id"] < 1:
                    raise ValueError()
            if request.args.get("usuario_activo") is not None:
                param = request.args["usuario_activo"].lower()
                if param not in ("true", "false", "1", "0"):
                    raise ValueError()
                filtros["usuario_activo"] = param in ("true", "1")
        except ValueError:
            return error(400, "FILTROS_INVALIDOS", "Parámetros de paginación o filtros inválidos")
        if len(filtros["q"]) > 120:
            return error(400, "FILTROS_INVALIDOS", "El filtro q es demasiado largo")
        filas, total = repo.usuarios(filtros)
        return jsonify({"items": [usuario_publico(u) for u in filas], "total": total, "page": page, "limit": limit})

    @app.post("/api/usuarios")
    def crear_usuario():
        mal = admin()
        if mal:
            return mal
        data = cuerpo_json()
        mal = obligatorio(data, ("nombre", "email", "contrasena", "rol_id"))
        if mal:
            return mal
        nombre, correo, clave, rol_id = data["nombre"], data["email"], data["contrasena"], data["rol_id"]
        if not isinstance(nombre, str) or not nombre.strip() or len(nombre.strip()) > 100 or not email_ok(correo):
            return error(400, "DATOS_INVALIDOS", "Nombre o correo inválidos")
        if not password_nueva_ok(clave):
            return error(422, "CONTRASENA_INVALIDA", "La contraseña debe tener de 8 a 72 caracteres")
        if type(rol_id) is not int or rol_id not in CODIGOS_ROL or not repo.rol_existe(rol_id):
            return error(422, "ROL_INVALIDO", "Rol inexistente")
        correo = correo.strip().lower()
        try:
            uid = repo.crear_usuario(nombre.strip(), correo, hash_password(clave), rol_id)
        except mysql.connector.IntegrityError:
            return error(409, "CONFLICTO", "El correo ya está registrado")
        return jsonify({"mensaje": "Usuario registrado", "usuario": usuario_publico(repo.usuario_id(uid))}), 201

    @app.get("/api/usuarios/<int:uid>")
    def consultar_usuario(uid):
        mal = admin()
        if mal:
            return mal
        u = repo.usuario_id(uid)
        if not u:
            return error(404, "NO_ENCONTRADO", "Usuario no encontrado")
        return jsonify(usuario_publico(u))

    @app.put("/api/usuarios/<int:uid>")
    def modificar_usuario(uid):
        mal = admin()
        if mal:
            return mal
        data = cuerpo_json()
        mal = obligatorio(data, ("nombre", "email"))
        if mal:
            return mal
        if not isinstance(data["nombre"], str) or not data["nombre"].strip() or len(data["nombre"].strip()) > 100 or not email_ok(data["email"]):
            return error(400, "DATOS_INVALIDOS", "Nombre o correo inválidos")
        if not repo.usuario_id(uid):
            return error(404, "NO_ENCONTRADO", "Usuario no encontrado")
        try:
            repo.actualizar_usuario(uid, data["nombre"].strip(), data["email"].strip().lower())
        except mysql.connector.IntegrityError:
            return error(409, "CONFLICTO", "El correo ya está registrado")
        return jsonify({"mensaje": "Usuario actualizado", "usuario": usuario_publico(repo.usuario_id(uid))})

    @app.patch("/api/usuarios/<int:uid>/rol")
    def cambiar_rol(uid):
        mal = admin()
        if mal:
            return mal
        data = cuerpo_json()
        mal = obligatorio(data, ("rol_id",))
        if mal:
            return mal
        if not repo.usuario_id(uid):
            return error(404, "NO_ENCONTRADO", "Usuario no encontrado")
        rol_id = data["rol_id"]
        if type(rol_id) is not int or rol_id not in CODIGOS_ROL or not repo.rol_existe(rol_id):
            return error(422, "ROL_INVALIDO", "Rol inexistente")
        repo.actualizar_rol(uid, rol_id)
        return jsonify({"mensaje": "Rol actualizado", "usuario": usuario_publico(repo.usuario_id(uid))})

    @app.patch("/api/usuarios/<int:uid>/estado")
    def cambiar_estado(uid):
        mal = admin()
        if mal:
            return mal
        data = cuerpo_json()
        mal = obligatorio(data, ("usuario_activo",))
        if mal:
            return mal
        if type(data["usuario_activo"]) is not bool:
            return error(400, "DATOS_INVALIDOS", "usuario_activo debe ser booleano")
        if not repo.usuario_id(uid):
            return error(404, "NO_ENCONTRADO", "Usuario no encontrado")
        repo.actualizar_estado(uid, data["usuario_activo"])
        return jsonify({"mensaje": "Estado actualizado", "usuario": usuario_publico(repo.usuario_id(uid))})

    @app.get("/api/roles")
    def consultar_roles():
        mal = admin()
        if mal:
            return mal
        roles = repo.roles()
        return jsonify({"items": [{**rol, "codigo": CODIGOS_ROL.get(rol["id"])} for rol in roles],
                        "total": len(roles), "page": 1, "limit": len(roles)})

    return app
