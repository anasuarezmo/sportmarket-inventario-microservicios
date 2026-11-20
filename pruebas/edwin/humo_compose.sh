#!/usr/bin/env bash
# Prueba de humo del stack en Docker Compose, siempre a traves del Gateway (8080).
# Uso (desde la raiz del repo): bash pruebas/edwin/humo_compose.sh
G=${GATEWAY:-http://localhost:8080}
GEN=${GENERADOR_TOKEN:-$HOME/Escritorio/SportMarket-gateway/api-gateway}
ADM=$(cd "$GEN" && node src/generarToken.js ADM) || exit 1
CON=$(cd "$GEN" && node src/generarToken.js CON) || exit 1
A="Authorization: Bearer $ADM"
J="Content-Type: application/json"
ok=0; mal=0
verifica() {
  if [ "$2" = "$3" ]; then echo "OK     $1 ($3)"; ok=$((ok+1)); else echo "FALLO  $1 (esperado $2, obtenido $3)"; mal=$((mal+1)); fi
}
codigo() { curl -s -o /dev/null -w "%{http_code}" "$@"; }
total() { python3 -c "import sys,json;print(json.load(sys.stdin)['total'])"; }
mov() { # ruta cuerpo
  codigo -X POST "$G/api/inventario/$1" -H "$A" -H "$J" -d "$2"
}
minimo() { codigo -X PUT "$G/api/inventario/minimos/2/1" -H "$A" -H "$J" -d "{\"stock_minimo\":$1}"; }
activas() { curl -s "$G/api/alertas?estado_alerta=ACTIVA&producto_id=2&bodega_id=1" -H "$A" | total; }

echo "== Gateway =="
verifica "Gateway responde" 200 "$(codigo $G/health)"
verifica "Sin token se rechaza" 401 "$(codigo $G/api/productos)"
verifica "Rol CON no puede registrar entradas" 403 "$(codigo -X POST $G/api/inventario/entradas -H "Authorization: Bearer $CON" -H "$J" -d '{}')"
verifica "Ruta interna no expuesta" 404 "$(codigo -X POST $G/api/interno/alertas/stock -H "$A" -H "$J" -d '{}')"
verifica "Servicio aun no desplegado (usuarios) responde 503" 503 "$(codigo $G/api/usuarios -H "$A")"

echo "== Catalogo =="
verifica "Lista de productos" 200 "$(codigo "$G/api/productos?limit=1" -H "$A")"

echo "== Inventario =="
U=$(uuidgen)
CUERPO="{\"operacion_id\":\"$U\",\"producto_id\":2,\"bodega_destino_id\":1,\"cantidad_movimiento\":10,\"origen_movimiento\":\"MANUAL\"}"
verifica "Entrada de 10 unidades" 201 "$(mov entradas "$CUERPO")"
verifica "Misma operacion repetida (idempotencia)" 200 "$(mov entradas "$CUERPO")"
verifica "Misma operacion con otra cantidad" 409 "$(mov entradas "${CUERPO/10,/99,}")"
verifica "Salida mayor a las existencias" 409 "$(mov salidas "{\"operacion_id\":\"$(uuidgen)\",\"producto_id\":2,\"bodega_origen_id\":1,\"cantidad_movimiento\":999999,\"origen_movimiento\":\"MANUAL\"}")"
verifica "Bodega inexistente" 422 "$(mov entradas "{\"operacion_id\":\"$(uuidgen)\",\"producto_id\":2,\"bodega_destino_id\":99,\"cantidad_movimiento\":1,\"origen_movimiento\":\"MANUAL\"}")"
verifica "Origen COMPRA no permitido a un usuario" 403 "$(mov entradas "{\"operacion_id\":\"$(uuidgen)\",\"producto_id\":2,\"bodega_destino_id\":1,\"cantidad_movimiento\":1,\"origen_movimiento\":\"COMPRA\"}")"

echo "== Alertas (Inventario avisa a Reportes por la red de Docker) =="
cant=$(curl -s "$G/api/inventario/existencias/2" -H "$A" | python3 -c "import sys,json;print([b['cantidad_disponible'] for b in json.load(sys.stdin)['bodegas'] if b['bodega_id']==1][0])")
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

echo
echo "Resultado: $ok correctas, $mal con fallo"
[ "$mal" -eq 0 ]
