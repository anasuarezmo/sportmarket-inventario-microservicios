"""Crear primer administrador usando variables de entorno, nunca contraseñas hardcodeadas.

Uso dentro del contenedor: ADMIN_EMAIL=... ADMIN_PASSWORD=... python -m app.bootstrap
"""
import os
import sys

from .config import cargar_config
from .repositorio import Repositorio
from .web import email_ok, hash_password


def main():
    email = os.getenv("ADMIN_EMAIL", "").strip().lower()
    password = os.getenv("ADMIN_PASSWORD", "")
    nombre = os.getenv("ADMIN_NOMBRE", "Administrador")
    if not email_ok(email) or not (8 <= len(password) and len(password.encode("utf-8")) <= 72) or not 0 < len(nombre.strip()) <= 100:
        print("Error: configura ADMIN_EMAIL, ADMIN_PASSWORD (8-72 caracteres) y ADMIN_NOMBRE opcional.", file=sys.stderr)
        return 1
    repo = Repositorio(cargar_config()["mysql"])
    existente = repo.usuario_email(email)
    if existente:
        if existente["rol_id"] != 1:
            print("Ya existe ese correo pero no pertenece a un administrador.", file=sys.stderr)
            return 1
        print("El administrador ya existe. No se modificó su contraseña.")
        return 0
    if not repo.rol_existe(1):
        print("No existe el rol Administrador. Ejecuta antes sql/schema.sql.", file=sys.stderr)
        return 1
    pk = repo.crear_usuario(nombre.strip(), email, hash_password(password), 1)
    print(f"Administrador creado con id={pk}, correo={email}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
