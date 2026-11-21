"""SportMarket: microservicio Bodegas (10 operaciones del contrato de Entrega 2).

La base de datos es exclusiva de Bodegas. Para consultar stock usa REST de Inventario.
El API Gateway valida el JWT. Este servicio exige el token interno y revalida roles de escritura.
"""
import hmac
import json
import logging
import os
import re
import time
import uuid
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import mysql.connector
from flask import Flask, Response, g, jsonify, request

app = Flask(__name__)
app.json.sort_keys = False
ROLES = {"ADM", "INV", "COM", "BOD", "CON"}
ESCRITURA = {"ADM", "INV"}


def error_http(estado, codigo, mensaje, detalles=None):
    return jsonify({"codigo": codigo, "mensaje": mensaje, "detalles": detalles or [],
                    "correlation_id": g.get("correlation_id", str(uuid.uuid4()))}), estado


@app.before_request
def autenticacion_interna():
    cid = request.headers.get("X-Correlation-ID", "")
    g.correlation_id = cid if re.fullmatch(r"[\w-]{8,64}", cid) else str(uuid.uuid4())
    # Healthchecks de Docker no dependen de la red interna ni de JWT.
    if request.path == "/health":
        return None
    esperado = os.environ.get("INTERNAL_TOKEN", "")
    recibido = request.headers.get("X-Internal-Token", "")
    if not esperado or not recibido or not hmac.compare_digest(recibido, esperado):
        return error_http(401, "NO_AUTENTICADO", "Credencial interna ausente o incorrecta")
    rol = request.headers.get("X-User-Role")
    if rol is not None and rol not in ROLES:
        return error_http(403, "PROHIBIDO", "Rol de usuario no valido")
    if request.method in {"POST", "PUT", "PATCH", "DELETE"} and rol not in ESCRITURA:
        return error_http(403, "PROHIBIDO", "Esta operacion requiere rol ADM o INV")
    return None


@app.after_request
def agregar_cid(respuesta):
    respuesta.headers["X-Correlation-ID"] = g.get("correlation_id", str(uuid.uuid4()))
    return respuesta


@app.get("/health")
def salud():
    return jsonify({"estado": "UP"})


@app.get("/openapi.yaml")
def contrato():
    return Response(Path(__file__).with_name("openapi.yaml").read_text(encoding="utf-8"),
                    mimetype="application/yaml")


@app.get("/docs")
def documentacion():
    return Response('''<!doctype html><html lang="es"><head><meta charset="utf-8">
<title>Bodegas - SportMarket</title><link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css"></head>
<body><div id="swagger"></div><script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
<script>SwaggerUIBundle({url:'/openapi.yaml',dom_id:'#swagger'});</script></body></html>''',
                    mimetype="text/html")


def conectar():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST", "localhost"), port=int(os.getenv("DB_PORT", "3306")),
        database=os.getenv("DB_NAME", "bodegas_db"), user=os.getenv("DB_USER", "bodegas_user"),
        password=os.getenv("DB_PASSWORD", ""), connection_timeout=3)


def db_uno(sql, parametros=()):
    con = conectar()
    try:
        cur = con.cursor(dictionary=True)
        try:
            cur.execute(sql, parametros)
            return cur.fetchone()
        finally:
            cur.close()
    finally:
        con.close()


def db_todos(sql, parametros=()):
    con = conectar()
    try:
        cur = con.cursor(dictionary=True)
        try:
            cur.execute(sql, parametros)
            return cur.fetchall()
        finally:
            cur.close()
    finally:
        con.close()


def db_escribir(sql, parametros=()):
    con = conectar()
    try:
        cur = con.cursor()
        try:
            cur.execute(sql, parametros)
            con.commit()
            return cur.lastrowid, cur.rowcount
        except Exception:
            con.rollback()
            raise
        finally:
            cur.close()
    finally:
        con.close()


def bodega_json(fila):
    if fila is not None:
        fila = dict(fila)
        fila["bodega_activa"] = bool(fila["bodega_activa"])
    return fila


def ubicacion_json(fila):
    if fila is not None:
        fila = dict(fila)
        fila["ubicacion_activa"] = bool(fila["ubicacion_activa"])
    return fila


def obtener_bodega(identificador):
    return bodega_json(db_uno("SELECT id,codigo,nombre,direccion,ciudad,bodega_activa "
                              "FROM bodega WHERE id=%s", (identificador,)))


def obtener_ubicacion(bodega_id, ubicacion_id):
    return ubicacion_json(db_uno("SELECT id,bodega_id,codigo,descripcion,ubicacion_activa "
                                "FROM ubicacion WHERE id=%s AND bodega_id=%s", (ubicacion_id, bodega_id)))


def entero_positivo(valor, campo):
    if not re.fullmatch(r"[0-9]+", str(valor)) or int(valor) < 1:
        raise ValueError((campo, "Debe ser un entero positivo"))
    return int(valor)


def paginacion():
    pagina = entero_positivo(request.args.get("page", "1"), "page")
    limite = entero_positivo(request.args.get("limit", "20"), "limit")
    if limite > 100:
        raise ValueError(("limit", "El maximo permitido es 100"))
    return pagina, limite


def validar_textos(cuerpo, limites, obligatorios):
    if not isinstance(cuerpo, dict):
        raise ValueError(("cuerpo", "Se requiere un objeto JSON"))
    for campo in obligatorios:
        if campo not in cuerpo:
            raise ValueError((campo, "Es obligatorio"))
    for campo, maximo in limites.items():
        if campo not in cuerpo:
            continue
        texto = cuerpo[campo]
        if texto is None and campo == "descripcion":
            continue
        if not isinstance(texto, str) or (campo != "descripcion" and not texto.strip()) or len(texto) > maximo:
            raise ValueError((campo, f"Debe ser texto valido de maximo {maximo} caracteres"))
    return {k: cuerpo[k].strip() if isinstance(cuerpo[k], str) else cuerpo[k]
            for k in limites if k in cuerpo}


def cuerpo_json():
    dato = request.get_json(silent=True)
    if not isinstance(dato, dict):
        raise ValueError(("cuerpo", "Se requiere un objeto JSON"))
    return dato


def valor_booleano(cuerpo, campo):
    if campo not in cuerpo or type(cuerpo[campo]) is not bool:
        raise ValueError((campo, "Debe ser true o false"))
    return cuerpo[campo]


def existe_bodega(id_bodega):
    bodega = obtener_bodega(id_bodega)
    if not bodega:
        return None, error_http(404, "RECURSO_NO_ENCONTRADO", "Bodega no encontrada")
    return bodega, None


def existe_ubicacion(id_bodega, id_ubicacion):
    ubicacion = obtener_ubicacion(id_bodega, id_ubicacion)
    if not ubicacion:
        return None, error_http(404, "RECURSO_NO_ENCONTRADO", "Ubicacion no encontrada")
    return ubicacion, None


@app.get("/api/bodegas")
def listar_bodegas():
    page, limit = paginacion()
    where, args = [], []
    ciudad = request.args.get("ciudad")
    if ciudad is not None:
        if not ciudad.strip() or len(ciudad) > 60:
            raise ValueError(("ciudad", "Ciudad no valida"))
        where.append("ciudad=%s")
        args.append(ciudad.strip())
    activa = request.args.get("bodega_activa")
    if activa is not None:
        if activa not in {"true", "false"}:
            raise ValueError(("bodega_activa", "Debe ser true o false"))
        where.append("bodega_activa=%s")
        args.append(activa == "true")
    filtro = " WHERE " + " AND ".join(where) if where else ""
    total = db_uno("SELECT COUNT(*) AS total FROM bodega" + filtro, tuple(args))["total"]
    filas = db_todos("SELECT id,codigo,nombre,direccion,ciudad,bodega_activa "
                     "FROM bodega" + filtro + " ORDER BY id LIMIT %s OFFSET %s",
                     tuple(args + [limit, (page - 1) * limit]))
    return jsonify({"items": [bodega_json(f) for f in filas], "total": total, "page": page, "limit": limit})


@app.post("/api/bodegas")
def crear_bodega():
    dato = validar_textos(cuerpo_json(),
                          {"codigo": 20, "nombre": 100, "direccion": 150, "ciudad": 60},
                          ("codigo", "nombre", "direccion", "ciudad"))
    nuevo, _ = db_escribir("INSERT INTO bodega (codigo,nombre,direccion,ciudad) VALUES (%s,%s,%s,%s)",
                          (dato["codigo"], dato["nombre"], dato["direccion"], dato["ciudad"]))
    return jsonify({"mensaje": "Bodega registrada", "bodega": obtener_bodega(nuevo)}), 201


@app.get("/api/bodegas/<int:bodega_id>")
def consultar_bodega(bodega_id):
    bodega_id = entero_positivo(bodega_id, "id")
    bodega, err = existe_bodega(bodega_id)
    if err:
        return err
    return jsonify(bodega)


@app.put("/api/bodegas/<int:bodega_id>")
def actualizar_bodega(bodega_id):
    bodega_id = entero_positivo(bodega_id, "id")
    _, err = existe_bodega(bodega_id)
    if err:
        return err
    datos = validar_textos(cuerpo_json(),
                           {"codigo": 20, "nombre": 100, "direccion": 150, "ciudad": 60},
                           ("codigo", "nombre", "direccion", "ciudad"))
    db_escribir("UPDATE bodega SET codigo=%s,nombre=%s,direccion=%s,ciudad=%s WHERE id=%s",
                (datos["codigo"], datos["nombre"], datos["direccion"], datos["ciudad"], bodega_id))
    return jsonify({"mensaje": "Bodega actualizada", "bodega": obtener_bodega(bodega_id)})


@app.patch("/api/bodegas/<int:bodega_id>/estado")
def cambiar_estado_bodega(bodega_id):
    bodega_id = entero_positivo(bodega_id, "id")
    _, err = existe_bodega(bodega_id)
    if err:
        return err
    activa = valor_booleano(cuerpo_json(), "bodega_activa")
    db_escribir("UPDATE bodega SET bodega_activa=%s WHERE id=%s", (activa, bodega_id))
    return jsonify({"mensaje": "Estado de bodega actualizado", "bodega": obtener_bodega(bodega_id)})


@app.get("/api/bodegas/<int:bodega_id>/ubicaciones")
def listar_ubicaciones(bodega_id):
    bodega_id = entero_positivo(bodega_id, "id")
    _, err = existe_bodega(bodega_id)
    if err:
        return err
    page, limit = paginacion()
    total = db_uno("SELECT COUNT(*) AS total FROM ubicacion WHERE bodega_id=%s", (bodega_id,))["total"]
    filas = db_todos("SELECT id,bodega_id,codigo,descripcion,ubicacion_activa FROM ubicacion "
                     "WHERE bodega_id=%s ORDER BY id LIMIT %s OFFSET %s",
                     (bodega_id, limit, (page - 1) * limit))
    return jsonify({"items": [ubicacion_json(f) for f in filas], "total": total, "page": page, "limit": limit})


@app.post("/api/bodegas/<int:bodega_id>/ubicaciones")
def crear_ubicacion(bodega_id):
    bodega_id = entero_positivo(bodega_id, "id")
    bodega, err = existe_bodega(bodega_id)
    if err:
        return err
    if not bodega["bodega_activa"]:
        return error_http(409, "BODEGA_INACTIVA", "No se crean ubicaciones en una bodega inactiva")
    datos = validar_textos(cuerpo_json(), {"codigo": 30, "descripcion": 255}, ("codigo",))
    nuevo, _ = db_escribir("INSERT INTO ubicacion (bodega_id,codigo,descripcion) VALUES (%s,%s,%s)",
                          (bodega_id, datos["codigo"], datos.get("descripcion")))
    return jsonify({"mensaje": "Ubicacion registrada", "ubicacion": obtener_ubicacion(bodega_id, nuevo)}), 201


@app.put("/api/bodegas/<int:bodega_id>/ubicaciones/<int:ubicacion_id>")
def actualizar_ubicacion(bodega_id, ubicacion_id):
    bodega_id = entero_positivo(bodega_id, "id")
    ubicacion_id = entero_positivo(ubicacion_id, "ubicacion_id")
    _, err = existe_ubicacion(bodega_id, ubicacion_id)
    if err:
        return err
    datos = validar_textos(cuerpo_json(), {"codigo": 30, "descripcion": 255}, ("codigo",))
    db_escribir("UPDATE ubicacion SET codigo=%s,descripcion=%s WHERE id=%s AND bodega_id=%s",
                (datos["codigo"], datos.get("descripcion"), ubicacion_id, bodega_id))
    return jsonify({"mensaje": "Ubicacion actualizada", "ubicacion": obtener_ubicacion(bodega_id, ubicacion_id)})


@app.patch("/api/bodegas/<int:bodega_id>/ubicaciones/<int:ubicacion_id>/estado")
def cambiar_estado_ubicacion(bodega_id, ubicacion_id):
    bodega_id = entero_positivo(bodega_id, "id")
    ubicacion_id = entero_positivo(ubicacion_id, "ubicacion_id")
    _, err = existe_ubicacion(bodega_id, ubicacion_id)
    if err:
        return err
    activa = valor_booleano(cuerpo_json(), "ubicacion_activa")
    db_escribir("UPDATE ubicacion SET ubicacion_activa=%s WHERE id=%s AND bodega_id=%s",
                (activa, ubicacion_id, bodega_id))
    return jsonify({"mensaje": "Estado de ubicacion actualizado",
                    "ubicacion": obtener_ubicacion(bodega_id, ubicacion_id)})


def pedir_existencias(bodega_id, producto_id=None):
    """REST sobre Inventario, nunca SQL sobre inventario_db (hasta 3 reintentos)."""
    params = {"bodega_id": bodega_id}
    if producto_id is not None:
        params["producto_id"] = producto_id
    base = os.environ.get("URL_INVENTARIO", "http://inventario:3004").rstrip("/")
    destino = f"{base}/api/inventario/existencias?{urlencode(params)}"
    encabezados = {"X-Internal-Token": os.environ.get("INTERNAL_TOKEN", ""),
                   "X-Correlation-ID": g.correlation_id, "Accept": "application/json"}
    for intentos in range(4):  # 1 intento inicial + 3 reintentos por fallos transitorios
        if intentos:
            time.sleep(0.2 * 2 ** (intentos - 1))
        try:
            with urlopen(Request(destino, headers=encabezados), timeout=3) as respuesta:
                return json.load(respuesta)
        except HTTPError as exc:
            # Fallos 4xx indican un problema de contrato; no reintentar.
            if exc.code < 500:
                app.logger.warning("Inventario rechazo consulta de existencias: HTTP %s", exc.code)
                break
        except (URLError, TimeoutError, OSError, ValueError) as exc:
            app.logger.warning("Inventario no disponible (intento %s): %s", intentos + 1, exc)
    return None


@app.get("/api/bodegas/<int:bodega_id>/existencias")
def consultar_existencias(bodega_id):
    bodega_id = entero_positivo(bodega_id, "id")
    _, err = existe_bodega(bodega_id)
    if err:
        return err
    producto_txt = request.args.get("producto_id")
    producto_id = entero_positivo(producto_txt, "producto_id") if producto_txt is not None else None
    existencias = pedir_existencias(bodega_id, producto_id)
    if existencias is None:
        return error_http(503, "SERVICIO_NO_DISPONIBLE", "Inventario no esta disponible")
    return jsonify(existencias)


@app.errorhandler(ValueError)
def datos_invalidos(exc):
    info = exc.args[0] if exc.args else ("cuerpo", "Dato invalido")
    campo, mensaje = info if isinstance(info, tuple) and len(info) == 2 else ("cuerpo", "Dato invalido")
    return error_http(400, "PETICION_INVALIDA", "Datos de entrada invalidos",
                      [{"campo": campo, "error": mensaje}])


@app.errorhandler(mysql.connector.IntegrityError)
def conflicto(exc):
    app.logger.warning("Restriccion de integridad en Bodegas: %s", exc.errno)
    return error_http(409, "CONFLICTO", "Codigo duplicado o referencia invalida")


@app.errorhandler(mysql.connector.Error)
def error_base(exc):
    app.logger.error("Bodegas/MySQL: %s", type(exc).__name__)
    return error_http(503, "SERVICIO_NO_DISPONIBLE", "No se pudo acceder a bodegas_db")


@app.errorhandler(404)
def ruta_desconocida(_):
    return error_http(404, "RECURSO_NO_ENCONTRADO", "Ruta no encontrada")


@app.errorhandler(405)
def metodo_desconocido(_):
    return error_http(405, "METODO_NO_PERMITIDO", "Metodo no permitido")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5002")))
