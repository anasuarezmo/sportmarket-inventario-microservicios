# Devoluciones — SportMarket (Entrega 3)

Flask + MySQL 8. Puerto interno `5006`. Solo accesible mediante API Gateway.

## Endpoints
- `GET /api/devoluciones` (filtros: `tipo`, `estado_inventario`, `producto_id`, `desde`, `hasta`, `page`, `limit`).
- `POST /api/devoluciones` (roles ADM, INV, COM, BOD).
- `GET /api/devoluciones/{id}`.
- `POST /api/devoluciones/{id}/procesar` (roles ADM, INV).
- `GET /health`, `GET /openapi.yaml`, `GET /docs`.

Todas las rutas salvo `/health` requieren `X-Internal-Token`. El Gateway entrega los headers confiables `X-User-Id`, `X-User-Role` y `X-Correlation-ID`.

## Reglas de negocio
1. Registrar guarda en MySQL una devolución `PENDIENTE`, sus líneas y un UUID estable por línea que afectará Inventario. No altera el stock.
2. CLIENTE/BUEN_ESTADO llama a `POST /api/inventario/entradas`; CLIENTE/DEFECTUOSO no mueve existencias; PROVEEDOR llama a `POST /api/inventario/salidas`.
3. Cada petición a Inventario envía `X-Internal-Token`, `X-Correlation-ID` y `origen_movimiento=DEVOLUCION`. No envía `X-User-Role` porque Inventario reserva ese origen a llamadas de servicio.
4. Fallas de Inventario (409, 422, 503) mantienen `PENDIENTE`. Al reintentar se reutiliza `operacion_id` por línea; Inventario debe responder 200 para operaciones idénticas repetidas. Solo al finalizar todas se cambia a `APLICADA`.
5. `APLICADA` no se procesa nuevamente (409). Todas las líneas defectuosas pasan a `APLICADA` sin movimientos.

### Variables de entorno
`INTERNAL_TOKEN`, `DB_HOST=mysql`, `DB_PORT=3306`, `DB_NAME=devoluciones_db`, `DB_USER=devoluciones_user`, `DB_PASSWORD`, `PORT=5006`, `URL_INVENTARIO=http://inventario:3004`, `TIMEOUT_SEG=3`, `REINTENTOS=3`.

`JWT_SECRET` no es necesario para Devoluciones: autentica el Gateway, no este servicio. **No guardar secretos en Git.**

## Pruebas locales
Desde la raíz del repositorio:

```bash
docker build -f docker/devoluciones/Dockerfile -t sportmarket-devoluciones .
docker run --rm --entrypoint python sportmarket-devoluciones -m unittest discover -s test -v
```

Con MySQL iniciado y ya preparada `devoluciones_db` por el script de Edwin:

```bash
docker exec -i sportmarket_mysql mysql -u devoluciones_user -pdev_password devoluciones_db < microservicios/devoluciones/sql/schema.sql
```

Docker local **sin modificar `docker-compose.yml`**:

```bash
docker run -d --name sportmarket_devoluciones_dev \
  --network sportmarket-inventario-microservicios_default \
  --network-alias devoluciones \
  --env-file .env \
  -e DB_HOST=mysql -e DB_PORT=3306 -e DB_NAME=devoluciones_db \
  -e DB_USER=devoluciones_user -e DB_PASSWORD=dev_password \
  -e URL_INVENTARIO=http://inventario:3004 -e PORT=5006 \
  -p 127.0.0.1:5006:5006 sportmarket-devoluciones
```

La integración final necesita que Edwin agregue el contenedor de Devoluciones a Compose y sustituya el mock de Bodegas. Pruebas de Inventario requieren que estén levantados Catalogo, Inventario y Bodegas reales.

### Discrepancia documental que hay que validar
`docs/entrega-2/openapi/devoluciones.yaml` marca `proveedor_id` y `detalles[].condicion` como obligatorios en todos los casos. Sin embargo, la sección 2.8.2 del documento *Diseño y Arquitectura*, páginas 29–30, establece que `proveedor_id` solo es obligatorio si `tipo=PROVEEDOR`, y que `condicion` debe omitirse en devoluciones a proveedor. La implementación sigue **la regla detallada del diseño**, conservando sin modificar el YAML original; ambos contratos deberían reconciliarse con Edwin antes de la demo.
