# Reportes y Alertas (puerto 5007)

Microservicio Flask con base `reportes_db`. Guarda **solo las alertas de stock** (RF09); los informes (RF11) y el dashboard (RF14) se calculan al consultarlos, pidiendo los datos a Inventario y Catálogo, con un caché en memoria de pocos segundos (`CACHE_TTL_SEG`).

Se accede **solo a través del API Gateway** (exige `X-Internal-Token`).

| Método | Ruta | Roles | Descripción |
|---|---|---|---|
| GET | `/api/reportes/inventario` | ADM, INV, COM, CON | Existencias por producto y bodega (`categoria_id`, `bodega_id`) |
| GET | `/api/reportes/valorizacion` | ADM, INV, COM, CON | Valor a precio de venta (`categoria_id`) |
| GET | `/api/reportes/rotacion` | ADM, INV, COM, CON | Mayor y menor rotación (`desde`, `hasta`, `limite`) |
| GET | `/api/reportes/movimientos` | ADM, INV, COM, CON | Resumen por tipo en un periodo |
| GET | `/api/reportes/dashboard` | todos | Indicadores generales |
| GET | `/api/alertas` | todos | Alertas (`estado_alerta`, `producto_id`, `bodega_id`, `page`, `limit`) |
| PATCH | `/api/alertas/{id}/estado` | ADM, INV | Marcar ATENDIDA (guarda usuario y fecha) |
| POST | `/api/interno/alertas/stock` | solo Inventario | Crear o cerrar alerta (no pasa por el Gateway) |

Reglas principales: una sola alerta ACTIVA por producto y bodega (garantizado por un índice único en MySQL); `STOCK_RECUPERADO` la marca ATENDIDA con usuario nulo; los traslados no cuentan como demanda en la rotación; si Inventario o Catálogo no responden (3 s, 3 reintentos) los informes devuelven 503.

## Ejecutar
    cd microservicios/reportes-alertas
    python3 -m venv .venv && source .venv/bin/activate
    pip install -r requirements.txt
    cp .env.example .env      # poner el INTERNAL_TOKEN del Gateway
    python -m app.server      # puerto 5007; crea la tabla al arrancar

Documentación Swagger: `http://localhost:5007/docs` (carga Swagger UI desde internet).

## Pruebas
    python -m unittest discover -s test -t .

Las pruebas usan falsos (sin MySQL ni otros servicios).
