"""Arranque: python -m app.server  (desde la carpeta del servicio)."""
import logging

from .app import crear_app
from .clientes import crear_clientes
from .config import cargar_config, cargar_env
from .repositorio import RUTA_ESQUEMA, crear_repositorio


def main():
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    cargar_env()
    config = cargar_config()
    repo = crear_repositorio(config["bd"])
    repo.aplicar_esquema(RUTA_ESQUEMA)
    app = crear_app(config, repo, crear_clientes(config), logging.getLogger("reportes"))
    print(f"Reportes y Alertas escuchando en el puerto {config['puerto']}", flush=True)
    app.run(host="0.0.0.0", port=config["puerto"])


if __name__ == "__main__":
    main()
