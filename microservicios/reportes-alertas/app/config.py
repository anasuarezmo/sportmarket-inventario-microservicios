import os


def cargar_env(ruta=".env"):
    """Lee un archivo .env sencillo (CLAVE=valor) sin pisar variables que ya existan."""
    if not os.path.exists(ruta):
        return
    with open(ruta, encoding="utf-8") as f:
        for linea in f:
            linea = linea.strip()
            if not linea or linea.startswith("#") or "=" not in linea:
                continue
            clave, valor = linea.split("=", 1)
            os.environ.setdefault(clave.strip(), valor.strip())


def cargar_config(env=None):
    env = os.environ if env is None else env
    return {
        "puerto": int(env.get("PORT", 5007)),
        "token_interno": env.get("INTERNAL_TOKEN", ""),
        "timeout": float(env.get("TIMEOUT_SEG", 3)),
        "reintentos": int(env.get("REINTENTOS", 3)),
        "cache_ttl": float(env.get("CACHE_TTL_SEG", 30)),
        "urls": {
            "inventario": env.get("URL_INVENTARIO", "http://localhost:3004"),
            "catalogo": env.get("URL_CATALOGO", "http://localhost:3003"),
        },
        "bd": {
            "host": env.get("DB_HOST", "localhost"),
            "port": int(env.get("DB_PORT", 3306)),
            "database": env.get("DB_NAME", "reportes_db"),
            "user": env.get("DB_USER", "reportes_user"),
            "password": env.get("DB_PASSWORD", ""),
        },
    }
