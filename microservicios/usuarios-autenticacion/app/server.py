"""Inicio del servicio dentro de Docker (puerto 5001)."""
from .config import cargar_config
from .web import crear_app

if __name__ == "__main__":
    configuracion = cargar_config()
    app = crear_app(configuracion)
    app.run(host="0.0.0.0", port=configuracion["port"], debug=False)
