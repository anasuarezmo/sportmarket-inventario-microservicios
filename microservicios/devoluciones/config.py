"""Configuración de Devoluciones obtenida de variables de entorno."""
import os


def configuracion():
    return {
        "db_host": os.getenv("DB_HOST", "mysql"),
        "db_port": int(os.getenv("DB_PORT", "3306")),
        "db_name": os.getenv("DB_NAME", "devoluciones_db"),
        "db_user": os.getenv("DB_USER", "devoluciones_user"),
        "db_password": os.getenv("DB_PASSWORD", ""),
        "internal_token": os.getenv("INTERNAL_TOKEN", ""),
        "url_inventario": os.getenv("URL_INVENTARIO", "http://inventario:3004").rstrip('/'),
        "port": int(os.getenv("PORT", "5006")),
        "timeout_seg": float(os.getenv("TIMEOUT_SEG", "3")),
        "reintentos": int(os.getenv("REINTENTOS", "3")),
    }
