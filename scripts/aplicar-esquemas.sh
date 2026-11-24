#!/usr/bin/env bash
# Aplica los schema.sql de Usuarios, Bodegas, Devoluciones y Compras a su propia base.
# Es repetible: todas las tablas usan IF NOT EXISTS. Requiere el stack levantado (docker compose up -d).
set -euo pipefail
cd "$(dirname "$0")/.."

aplicar() {
  local base="$1" archivo="$2"
  [ -f "$archivo" ] || { echo "No existe $archivo" >&2; exit 1; }
  docker compose exec -T mysql sh -c 'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" exec mysql -uroot "$0"' "$base" < "$archivo"
  echo "OK  $base  <-  $archivo"
}

aplicar usuarios_db      microservicios/usuarios-autenticacion/sql/schema.sql
aplicar bodegas_db       microservicios/bodegas/sql/schema.sql
aplicar devoluciones_db  microservicios/devoluciones/sql/schema.sql
aplicar compras_db       microservicios/compras-proveedores/sql/schema.sql
echo "Esquemas aplicados."
