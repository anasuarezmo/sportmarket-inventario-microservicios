# Locust: pruebas individuales de Edwin (SportMarket, Entrega 3)

## Alcance
15 escenarios que se ejecutan juntos en una sola corrida y se reportan por separado (una fila por escenario). Todas las solicitudes entran **por el Gateway (8080)** con un JWT obtenido del login real del servicio de Usuarios. Cubren los servicios de Edwin: Catálogo, Inventario, Reportes y Alertas.

| # | Escenario | Tipo |
|---|---|---|
| 01 | Catálogo: listar productos | GET |
| 02 | Catálogo: buscar por nombre | GET |
| 03 | Catálogo: consultar un producto | GET |
| 04 | Catálogo: listar categorías | GET |
| 05 | Inventario: existencias | GET |
| 06 | Inventario: existencias de un producto | GET |
| 07 | Inventario: movimientos | GET |
| 08 | Inventario: registrar entrada | POST |
| 09 | Inventario: registrar salida | POST |
| 10 | Inventario: registrar traslado | POST |
| 11 | Reportes: dashboard | GET |
| 12 | Reportes: existencias | GET |
| 13 | Reportes: valorización | GET |
| 14 | Reportes: rotación | GET |
| 15 | Alertas: consultar | GET |

Las escrituras (08 a 10) usan un `operacion_id` UUID nuevo en cada solicitud (idempotencia) y solo cuentan como éxito la respuesta 201.

## Entorno de la corrida
- Stack completo en Docker Compose: MySQL y 8 servicios (Usuarios, Bodegas, Catálogo, Inventario, Compras, Devoluciones, Reportes y Gateway), todos reales, sin simulaciones.
- Máquina de desarrollo local (un solo equipo). Locust en contenedor (`locustio/locust`) con red del host.
- Parámetros: 10 usuarios, 2 usuarios nuevos por segundo, 2 minutos, modo sin interfaz.

## Resultados (corrida del 23/11/2026)
| # | Escenario | Solicitudes | Fallos | Mediana (ms) | p95 (ms) |
|---|---|---|---|---|---|
| 01 | Catálogo: listar productos | 131 | 0 | 8 | 9 |
| 02 | Catálogo: buscar por nombre | 116 | 0 | 8 | 11 |
| 03 | Catálogo: consultar un producto | 82 | 0 | 7 | 8 |
| 04 | Catálogo: listar categorías | 68 | 0 | 7 | 9 |
| 05 | Inventario: existencias | 117 | 0 | 8 | 10 |
| 06 | Inventario: existencias de un producto | 108 | 0 | 10 | 13 |
| 07 | Inventario: movimientos | 97 | 0 | 9 | 12 |
| 08 | Inventario: registrar entrada | 91 | 0 | 41 | 51 |
| 09 | Inventario: registrar salida | 23 | 0 | 44 | 48 |
| 10 | Inventario: registrar traslado | 34 | 0 | 44 | 57 |
| 11 | Reportes: dashboard | 58 | 0 | 24 | 31 |
| 12 | Reportes: existencias | 75 | 0 | 9 | 12 |
| 13 | Reportes: valorización | 65 | 0 | 8 | 11 |
| 14 | Reportes: rotación | 32 | 0 | 9 | 17 |
| 15 | Alertas: consultar | 64 | 0 | 27 | 32 |
| | **Total** | **1161** | **0 (0,00 %)** | **8** | **45** |

Rendimiento global: 9,7 solicitudes por segundo.

Criterios del proyecto: errores < 1 % y p95 < 2 s. Se cumplen con amplio margen.

## Lectura de los resultados
- Las lecturas simples responden en torno a 7 a 10 ms (mediana).
- Las escrituras cuestan más (41 a 44 ms): abren una transacción con bloqueo de fila y validan el producto y la bodega con otros servicios por la red.
- El dashboard y las alertas (24 a 27 ms) combinan datos de otros servicios.
- No hubo fallos ni excepciones (`real_failures.csv` y `real_exceptions.csv` solo traen el encabezado).

## Límites
Es una carga relativa en un solo equipo: 10 usuarios durante 2 minutos. No es una prueba de saturación y no determina la capacidad máxima del sistema. Las escrituras modifican el stock del producto 2, por lo que la base queda con movimientos de prueba.

## Cómo repetirla
Con el stack levantado, esquemas aplicados y administrador creado (`scripts/aplicar-esquemas.sh`, `scripts/crear-admin.sh`), desde la raíz del repositorio:

    read -rp 'Correo: ' E; read -rsp 'Contrasena: ' P; echo
    CUERPO=$(python3 -c 'import json,sys; print(json.dumps({"email":sys.argv[1],"contrasena":sys.argv[2]}))' "$E" "$P")
    export TOKEN=$(curl -s -X POST http://localhost:8080/api/auth/login -H 'Content-Type: application/json' -d "$CUERPO" | python3 -c 'import sys,json; print(json.load(sys.stdin)["token"])')
    unset P CUERPO
    docker run --rm --network host --user "$(id -u):$(id -g)" \
      -e TOKEN="$TOKEN" -e PRODUCTO_ID=2 \
      -v "$PWD/pruebas/edwin:/mnt/locust" locustio/locust \
      -f /mnt/locust/locustfile.py --host http://localhost:8080 \
      --headless -u 10 -r 2 -t 2m \
      --csv /mnt/locust/resultados_locust/real \
      --html /mnt/locust/resultados_locust/informe_real.html

El token no se guarda en ningún archivo. Dura 60 minutos.

## Archivos
- `locustfile.py`: los 15 escenarios.
- `resultados_locust/informe_real.html`: informe de Locust (gráficas y tablas).
- `resultados_locust/real_*.csv`: estadísticas, historial, fallos y excepciones.
