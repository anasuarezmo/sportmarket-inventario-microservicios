"""Adaptador Flask: convierte la peticion HTTP al formato del manejador y viceversa. Incluye /docs (Swagger UI)."""
import os

from flask import Flask, Response, jsonify, request

from .manejador import crear_manejador

RAIZ = os.path.join(os.path.dirname(__file__), "..")
PAGINA_DOCS = """<!doctype html><html><head><meta charset="utf-8"><title>Reportes y Alertas - SportMarket</title>
<link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css"></head><body><div id="ui"></div>
<script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
<script>SwaggerUIBundle({url: '/openapi.yaml', dom_id: '#ui'});</script></body></html>"""


def crear_app(config, repo, clientes, log=None):
    app = Flask(__name__)
    app.json.sort_keys = False
    manejar = crear_manejador(config, repo, clientes, log)

    @app.get("/docs")
    def docs():
        return Response(PAGINA_DOCS, mimetype="text/html")

    @app.get("/openapi.yaml")
    def openapi():
        with open(os.path.join(RAIZ, "openapi.yaml"), encoding="utf-8") as f:
            return Response(f.read(), mimetype="application/yaml")

    @app.route("/", defaults={"ruta": ""}, methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
    @app.route("/<path:ruta>", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
    def todo(ruta):
        cuerpo, invalido = None, False
        if request.method in ("POST", "PUT", "PATCH") and request.get_data():
            cuerpo = request.get_json(silent=True)
            invalido = cuerpo is None
        r = manejar({
            "metodo": request.method, "ruta": request.path, "headers": dict(request.headers),
            "consulta": request.args.to_dict(), "cuerpo": cuerpo, "json_invalido": invalido,
        })
        resp = jsonify(r["cuerpo"])
        resp.status_code = r["status"]
        for k, v in r["headers"].items():
            resp.headers[k] = v
        return resp

    return app
