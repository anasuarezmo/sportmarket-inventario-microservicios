#!/usr/bin/env bash
# Crea el administrador inicial en Usuarios. La contrasena se pide por teclado y no se guarda.
# Requiere el stack levantado y los esquemas aplicados (scripts/aplicar-esquemas.sh).
set -euo pipefail
cd "$(dirname "$0")/.."

read -rp 'Correo del administrador: ' ADMIN_EMAIL
read -rsp 'Contrasena del administrador (8-72 caracteres): ' ADMIN_PASSWORD; echo
docker compose exec -T -e ADMIN_EMAIL="$ADMIN_EMAIL" -e ADMIN_PASSWORD="$ADMIN_PASSWORD" usuarios python -m app.bootstrap
unset ADMIN_PASSWORD
