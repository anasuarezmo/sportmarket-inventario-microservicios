# Catálogo

Microservicio de productos y categorías (RF01, RF02, RF12). Express + MySQL (`catalogo_db`). Puerto **3003**.
Solo se accede a través del API Gateway: exige la cabecera `X-Internal-Token`.

- Tablas: `categoria` (con `categoria_padre_id` para subcategorías) y `producto`. El esquema está en `sql/schema.sql` y se aplica solo al arrancar.
- Contrato: `openapi.yaml` (documentación en `http://localhost:3003/docs`).
- Capas: `manejador.js` (HTTP, credencial y rol) → `servicio.js` (reglas de negocio) → `repositorio.js` (SQL). Las pruebas usan un repositorio en memoria.
- Respuestas: crear/actualizar `{mensaje, producto|categoria}`; consultar uno, el objeto; listas `{items, total, page, limit}` (convención de la Entrega 2); errores `{codigo, mensaje, detalles, correlation_id}`.

```
npm install
npm test
cp .env.example .env    # cambiar INTERNAL_TOKEN (el mismo del Gateway)
npm start               # requiere MySQL con catalogo_db (docker compose up -d)
```
