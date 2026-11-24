#!/usr/bin/env bash
# Prueba de humo del stack integrado (9 servicios), siempre a traves del Gateway (8080).
# Uso (desde la raiz del repo): bash pruebas/edwin/humo_compose.sh
# Pide el correo y la contrasena del administrador (no se muestran ni se guardan);
# tambien se pueden pasar con LOGIN_EMAIL y LOGIN_PASSWORD. Requiere: stack levantado,
# esquemas aplicados (scripts/aplicar-esquemas.sh) y administrador creado (scripts/crear-admin.sh).
G=${GATEWAY:-http://localhost:8080}
J="Content-Type: application/json"

if [ -z "${LOGIN_EMAIL:-}" ]; then read -rp 'Correo del administrador: ' LOGIN_EMAIL; fi
if [ -z "${LOGIN_PASSWORD:-}" ]; then read -rsp 'Contrasena: ' LOGIN_PASSWORD; echo; fi

login() { # correo contrasena -> imprime el token (vacio si falla)
  EMAIL="$1" CLAVE="$2" python3 - "$G" <<'PY'
import json, os, sys, urllib.request
req = urllib.request.Request(sys.argv[1] + "/api/auth/login",
    data=json.dumps({"email": os.environ["EMAIL"], "contrasena": os.environ["CLAVE"]}).encode(),
    headers={"Content-Type": "application/json"})
try:
    print(json.load(urllib.request.urlopen(req, timeout=10))["token"])
except Exception:
    sys.exit(1)
PY
}

ADM=$(login "$LOGIN_EMAIL" "$LOGIN_PASSWORD") || { echo "No se pudo iniciar sesion como administrador"; exit 1; }
unset LOGIN_PASSWORD
A="Authorization: Bearer $ADM"

ok=0; mal=0
verifica() {
  if [ "$2" = "$3" ]; then echo "OK     $1 ($3)"; ok=$((ok+1)); else echo "FALLO  $1 (esperado $2, obtenido $3)"; mal=$((mal+1)); fi
}
codigo() { curl -s -o /dev/null -w "%{http_code}" "$@"; }
total() { python3 -c "import sys,json;print(json.load(sys.stdin)['total'])"; }
campo() { python3 -c 'import sys,json
d=json.load(sys.stdin)
for k in sys.argv[1].split("."):
    d = d[int(k)] if isinstance(d,list) else (d.get(k) if isinstance(d,dict) else None)
print(d if d is not None else "")' "$1"; }
api() { # metodo ruta [cuerpo] [token]  -> deja CODE y RESP
  local t=${4:-$ADM}
  if [ -n "${3:-}" ]; then R=$(curl -s -w '\n%{http_code}' -X "$1" "$G$2" -H "Authorization: Bearer $t" -H "$J" -d "$3")
  else R=$(curl -s -w '\n%{http_code}' -X "$1" "$G$2" -H "Authorization: Bearer $t"); fi
  RESP=${R%$'\n'*}; CODE=${R##*$'\n'}
}
mov() { codigo -X POST "$G/api/inventario/$1" -H "$A" -H "$J" -d "$2"; }
minimo() { codigo -X PUT "$G/api/inventario/minimos/2/1" -H "$A" -H "$J" -d "{\"stock_minimo\":$1}"; }
activas() { curl -s "$G/api/alertas?estado_alerta=ACTIVA&producto_id=2&bodega_id=1" -H "$A" | total; }
stock() { curl -s "$G/api/inventario/existencias/2" -H "$A" | python3 -c "import sys,json;print([b['cantidad_disponible'] for b in json.load(sys.stdin)['bodegas'] if b['bodega_id']==1][0])"; }

echo "== Usuarios: login real y usuario CON desechable =="
verifica "Login con clave incorrecta" 401 "$(codigo -X POST $G/api/auth/login -H "$J" -d "{\"email\":\"$LOGIN_EMAIL\",\"contrasena\":\"clave-incorrecta-123\"}")"
SUF=$(date +%s)
CON_EMAIL="humo.$SUF@sportmarket.test"
CON_CLAVE=$(openssl rand -hex 12)
api POST /api/usuarios "{\"nombre\":\"Usuario de humo\",\"email\":\"$CON_EMAIL\",\"contrasena\":\"$CON_CLAVE\",\"rol_id\":5}"
verifica "Crear usuario CON (solo ADM)" 201 "$CODE"
CON_ID=$(printf '%s' "$RESP" | campo usuario.id)
CON=$(login "$CON_EMAIL" "$CON_CLAVE") || CON=""
unset CON_CLAVE
verifica "Login del usuario CON" 1 "$([ -n "$CON" ] && echo 1 || echo 0)"

echo "== Gateway =="
verifica "Gateway responde" 200 "$(codigo $G/health)"
verifica "Sin token se rechaza" 401 "$(codigo $G/api/productos)"
verifica "Rol CON no puede registrar entradas" 403 "$(codigo -X POST $G/api/inventario/entradas -H "Authorization: Bearer $CON" -H "$J" -d '{}')"
verifica "Rol CON no puede ver usuarios" 403 "$(codigo $G/api/usuarios -H "Authorization: Bearer $CON")"
verifica "Rol CON no puede crear bodegas" 403 "$(codigo -X POST $G/api/bodegas -H "Authorization: Bearer $CON" -H "$J" -d '{}')"
verifica "Rol CON no puede crear devoluciones" 403 "$(codigo -X POST $G/api/devoluciones -H "Authorization: Bearer $CON" -H "$J" -d '{}')"
verifica "Ruta interna no expuesta" 404 "$(codigo -X POST $G/api/interno/alertas/stock -H "$A" -H "$J" -d '{}')"

echo "== Los 7 servicios responden por el Gateway con el token real =="
for r in usuarios roles bodegas productos devoluciones compras proveedores; do
  verifica "GET /api/$r" 200 "$(codigo "$G/api/$r" -H "$A")"
done
verifica "Bodega 1 existe" 200 "$(codigo $G/api/bodegas/1 -H "$A")"
verifica "Bodega inexistente (99)" 404 "$(codigo $G/api/bodegas/99 -H "$A")"

echo "== Inventario =="
U=$(uuidgen)
CUERPO="{\"operacion_id\":\"$U\",\"producto_id\":2,\"bodega_destino_id\":1,\"cantidad_movimiento\":10,\"origen_movimiento\":\"MANUAL\"}"
verifica "Entrada de 10 unidades" 201 "$(mov entradas "$CUERPO")"
verifica "Misma operacion repetida (idempotencia)" 200 "$(mov entradas "$CUERPO")"
verifica "Misma operacion con otra cantidad" 409 "$(mov entradas "${CUERPO/10,/99,}")"
verifica "Salida mayor a las existencias" 409 "$(mov salidas "{\"operacion_id\":\"$(uuidgen)\",\"producto_id\":2,\"bodega_origen_id\":1,\"cantidad_movimiento\":999999,\"origen_movimiento\":\"MANUAL\"}")"
verifica "Bodega inexistente en un movimiento" 422 "$(mov entradas "{\"operacion_id\":\"$(uuidgen)\",\"producto_id\":2,\"bodega_destino_id\":99,\"cantidad_movimiento\":1,\"origen_movimiento\":\"MANUAL\"}")"
verifica "Origen COMPRA no permitido a un usuario" 403 "$(mov entradas "{\"operacion_id\":\"$(uuidgen)\",\"producto_id\":2,\"bodega_destino_id\":1,\"cantidad_movimiento\":1,\"origen_movimiento\":\"COMPRA\"}")"

echo "== Compras -> Inventario (origen COMPRA) =="
antes=$(stock)
api POST /api/proveedores "{\"nit\":\"9$SUF-1\",\"razon_social\":\"Proveedor de humo $SUF\"}"
verifica "Crear proveedor" 201 "$CODE"
PROV=$(printf '%s' "$RESP" | campo proveedor.id)
api POST /api/compras "{\"proveedor_id\":$PROV,\"bodega_destino_id\":1,\"detalles\":[{\"producto_id\":2,\"cantidad_solicitada\":4,\"costo_unitario\":15000}]}"
verifica "Crear orden de compra" 201 "$CODE"
ORD=$(printf '%s' "$RESP" | campo orden.id)
DET=$(printf '%s' "$RESP" | campo orden.detalles.0.id)
api POST /api/compras/$ORD/recepciones "{\"detalles\":[{\"orden_detalle_id\":$DET,\"cantidad_recibida\":4}]}"
verifica "Registrar recepcion" 201 "$CODE"
verifica "Recepcion sincronizada con Inventario" SINCRONIZADA "$(printf '%s' "$RESP" | campo recepcion.estado)"
verifica "El stock sube en 4" $((antes + 4)) "$(stock)"
api GET /api/compras/$ORD
verifica "La orden queda RECIBIDA" RECIBIDA "$(printf '%s' "$RESP" | campo estado)"

echo "== Devoluciones -> Inventario (origen DEVOLUCION) =="
antes=$(stock)
api POST /api/devoluciones '{"tipo":"CLIENTE","motivo":"Humo: devolucion de cliente","bodega_id":1,"detalles":[{"producto_id":2,"cantidad":2,"condicion":"BUEN_ESTADO"}]}'
verifica "Crear devolucion de cliente" 201 "$CODE"
D1=$(printf '%s' "$RESP" | campo devolucion.id)
api POST /api/devoluciones/$D1/procesar
verifica "Procesar devolucion de cliente" 200 "$CODE"
verifica "El stock sube en 2" $((antes + 2)) "$(stock)"
api POST /api/devoluciones/$D1/procesar
verifica "Reprocesar la misma devolucion" 409 "$CODE"
verifica "El stock no se duplica" $((antes + 2)) "$(stock)"
api POST /api/devoluciones "{\"tipo\":\"PROVEEDOR\",\"motivo\":\"Humo: stock insuficiente\",\"bodega_id\":1,\"proveedor_id\":$PROV,\"detalles\":[{\"producto_id\":2,\"cantidad\":999999}]}"
verifica "Crear devolucion a proveedor excesiva" 201 "$CODE"
D2=$(printf '%s' "$RESP" | campo devolucion.id)
api POST /api/devoluciones/$D2/procesar
verifica "Procesarla: stock insuficiente" 409 "$CODE"
verifica "El stock no cambia" $((antes + 2)) "$(stock)"
api GET /api/devoluciones/$D2
verifica "Queda PENDIENTE" PENDIENTE "$(printf '%s' "$RESP" | campo estado_inventario)"

echo "== Alertas (Inventario avisa a Reportes por la red de Docker) =="
cant=$(stock)
minimo 0 >/dev/null; sleep 1
verifica "Minimo en 0: sin alerta activa" 0 "$(activas)"
verifica "Minimo sobre el stock actual ($cant): cruza hacia abajo" 200 "$(minimo $((cant + 5)))"; sleep 1
verifica "Nace una alerta ACTIVA" 1 "$(activas)"
verifica "Minimo de nuevo en 0: stock recuperado" 200 "$(minimo 0)"; sleep 1
verifica "La alerta se cierra sola" 0 "$(activas)"

echo "== Reportes (piden datos a Inventario y Catalogo) =="
for r in dashboard inventario valorizacion rotacion movimientos; do
  verifica "Informe $r" 200 "$(codigo "$G/api/reportes/$r" -H "$A")"
done
verifica "Periodo invalido" 400 "$(codigo "$G/api/reportes/rotacion?desde=2026-11-20&hasta=2026-11-01" -H "$A")"

echo "== Limpieza =="
api PATCH /api/usuarios/$CON_ID/estado '{"usuario_activo":false}'
verifica "Usuario de prueba desactivado" 200 "$CODE"

echo
echo "Resultado: $ok correctas, $mal con fallo"
[ "$mal" -eq 0 ]
