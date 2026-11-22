#!/usr/bin/env bash
set -Eeuo pipefail

# Ejecutar desde la raiz del repositorio: bash pruebas/ana/ejecutar_15.sh
GATEWAY="${GATEWAY:-http://127.0.0.1:8080}"
DESTINO="${DESTINO:-pruebas/ana/resultados}"
mkdir -p "$DESTINO"
if ! command -v locust >/dev/null 2>&1; then
  echo "Falta Locust. Instala en un venv y activalo antes de ejecutar el script."
  exit 2
fi

read -r -p "Correo del administrador de pruebas: " LOGIN_EMAIL
read -r -s -p "Contrasena (no se mostrara): " LOGIN_PASSWORD
printf '\n'
export LOGIN_EMAIL LOGIN_PASSWORD GATEWAY

# Solicita el JWT una sola vez y no imprime ni guarda el token.
LOCUST_TOKEN="$(python3 - <<'PYLOGIN'
import json, os, sys, urllib.request, urllib.error
url = os.environ["GATEWAY"].rstrip("/") + "/api/auth/login"
body = json.dumps({"email": os.environ["LOGIN_EMAIL"], "contrasena": os.environ["LOGIN_PASSWORD"]}).encode()
req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
try:
    with urllib.request.urlopen(req, timeout=15) as response:
        result = json.load(response)
except urllib.error.HTTPError as err:
    print(f"Login fallido, HTTP {err.code}", file=sys.stderr)
    sys.exit(1)
except Exception as exc:
    print(f"Error de conexion en login: {exc}", file=sys.stderr)
    sys.exit(1)
token = result.get("token")
if not isinstance(token, str) or not token:
    print("Login sin token JWT en la respuesta", file=sys.stderr)
    sys.exit(1)
print(token)
PYLOGIN
)"
unset LOGIN_EMAIL LOGIN_PASSWORD
export LOCUST_TOKEN

echo "Validando cinco rutas de lectura mediante Gateway..."
python3 - <<'PYPRE'
import json, os, sys, urllib.request, urllib.error
base = os.environ['GATEWAY'].rstrip('/')
paths = ['/api/bodegas', '/api/bodegas/1', '/api/usuarios', '/api/devoluciones', '/api/compras']
for path in paths:
    req = urllib.request.Request(base+path, headers={'Authorization': 'Bearer '+os.environ['LOCUST_TOKEN']})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            body = json.load(r)
            if r.status != 200:
                raise RuntimeError(f'HTTP {r.status}')
            print(f'  OK {path} (200)')
    except urllib.error.HTTPError as e:
        print(f'  ERROR {path}: HTTP {e.code}', file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f'  ERROR {path}: {e}', file=sys.stderr)
        sys.exit(1)
PYPRE

# Tres perfiles, con concurrencia limitada para no agotar un equipo de desarrollo.
# Son cargas relativas: no prueban por si solas el punto real de saturacion.
ESCENARIOS=(bodegas_lista bodegas_detalle usuarios_lista devoluciones_lista compras_lista)
PERFILES=(normal pico alta)
USUARIOS=(3 8 15)
DURACIONES=(20s 20s 20s)
NUM=0
for idx in 0 1 2; do
  for escenario in "${ESCENARIOS[@]}"; do
    NUM=$((NUM+1))
    export ESCENARIO="$escenario"
    prefijo="${DESTINO}/${NUM}_${escenario}_${PERFILES[$idx]}"
    echo ""
    echo "[$NUM/15] $escenario | ${PERFILES[$idx]} | ${USUARIOS[$idx]} usuarios | ${DURACIONES[$idx]}"
    locust       -f pruebas/ana/locustfile.py       --host "$GATEWAY"       --headless       --users "${USUARIOS[$idx]}"       --spawn-rate "${USUARIOS[$idx]}"       --run-time "${DURACIONES[$idx]}"       --stop-timeout 5       --only-summary       --csv "$prefijo"       --loglevel ERROR
  done
done
unset LOCUST_TOKEN ESCENARIO

python3 pruebas/ana/resumir_resultados.py "$DESTINO"
echo "15 ejecuciones completadas. Resultados en: $DESTINO"
