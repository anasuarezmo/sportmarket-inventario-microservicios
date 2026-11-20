# Inventario

Microservicio de existencias, kárdex y stock mínimo (RF04, RF09, RF10). Express + MySQL (`inventario_db`). Puerto **3004**.
Es el **único** servicio que modifica saldos. Solo se accede por el API Gateway (exige `X-Internal-Token`).

## Operaciones (10)
`existencias` (lista y por producto), `entradas`, `salidas`, `ajustes`, `traslados`, `movimientos` (kárdex, lista y por id), `minimos` (consultar y configurar).

## Reglas clave
- **Una transacción por operación:** bloquea el saldo (`SELECT ... FOR UPDATE`), modifica la cantidad y registra un solo movimiento; si algo falla, se revierte todo. En un traslado se bloquean los dos saldos en orden de bodega.
- **Idempotencia:** `operacion_id` (UUID) es único. Repetido con los mismos datos devuelve 200 sin tocar saldos; con datos distintos, 409.
- **Validación en otros servicios:** el producto se consulta en Catálogo y la bodega en Bodegas (espera de 3 s y hasta 3 reintentos; si no responden, 503).
- **Origen del movimiento:** los usuarios solo usan `MANUAL`; `COMPRA` y `DEVOLUCION` son para llamadas entre servicios (sin `X-User-Role`). Un usuario que los envía recibe 403.
- **Avisos de stock:** al cruzar el mínimo hacia abajo (`STOCK_BAJO`) o volver a alcanzarlo (`STOCK_RECUPERADO`) avisa a `POST /api/interno/alertas/stock` de Reportes. Si el aviso falla, el movimiento no se revierte.
- `usuario_id` sale del `X-User-Id` del Gateway, nunca del cuerpo.
- Listas `{items, total, page, limit}`; errores `{codigo, mensaje, detalles, correlation_id}`.

```
npm install
npm test
cp .env.example .env    # INTERNAL_TOKEN igual al del Gateway
npm start               # requiere MySQL (inventario_db) y, para operar, Catalogo y Bodegas
```
