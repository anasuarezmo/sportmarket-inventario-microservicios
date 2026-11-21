"""Variables de entorno: mismo JWT_SECRET e INTERNAL_TOKEN que el Gateway."""
import os


def cargar_config(env=None):
    e = env or os.environ
    return {
        "port": int(e.get("PORT", "5001")),
        "jwt_secret": e.get("JWT_SECRET", ""),
        "internal_token": e.get("INTERNAL_TOKEN", ""),
        "jwt_exp_minutes": int(e.get("JWT_EXPIRES_MINUTES", "60")),
        "recovery_minutes": int(e.get("RECOVERY_TOKEN_MINUTES", "30")),
        "mysql": {
            "host": e.get("DB_HOST", "localhost"),
            "port": int(e.get("DB_PORT", "3306")),
            "database": e.get("DB_NAME", "usuarios_db"),
            "user": e.get("DB_USER", "usuarios_user"),
            "password": e.get("DB_PASSWORD", ""),
            "connection_timeout": 5,
        },
        "smtp": {
            "host": e.get("SMTP_HOST", ""),
            "port": int(e.get("SMTP_PORT", "587")),
            "username": e.get("SMTP_USER", ""),
            "password": e.get("SMTP_PASSWORD", ""),
            "sender": e.get("SMTP_FROM", ""),
            "use_tls": e.get("SMTP_USE_TLS", "true").lower() == "true",
        },
    }
