# Bodegas — SportMarket, Entrega 3

Microservicio Flask con base de datos propia `bodegas_db`. Implementa los **10 endpoints** de
`docs/entrega-2/openapi/bodegas.yaml`. No consulta tablas de otros microservicios: la ruta de
existencias llama por HTTP a Inventario, por `URL_INVENTARIO`.

## Seguridad y contrato

- `/health` es público para el healthcheck de Docker.
- Las otras rutas requieren `X-Internal-Token`, validado con `INTERNAL_TOKEN`.
- `POST`, `PUT` y `PATCH` requieren `X-User-Role: ADM` o `INV`; GET permite todos los roles.
- `X-Correlation-ID` se conserva y se devuelve en la respuesta.
- Listas: `{items,total,page,limit}`; creación/actualización: `{mensaje,bodega}` o `{mensaje,ubicacion}`;
  errores: `{codigo,mensaje,detalles,correlation_id}`.
- El JWT se verifica **en el Gateway**, no aquí. El servicio no debe publicar su puerto fuera
  de la red interna en el Compose final de Edwin.

## Esquema MySQL

La base y usuario los crea el script de Edwin en `docker/mysql/init/`. Una sola vez, al preparar
la instalación, ejecutar el archivo `microservicios/bodegas/sql/schema.sql` con `bodegas_user`
sobre `bodegas_db`. No modifica otras bases de datos. Las contraseñas deben provenir del entorno.

## Variables del servicio

`PORT=5002`, `INTERNAL_TOKEN`, `DB_HOST=mysql`, `DB_PORT=3306`, `DB_NAME=bodegas_db`,
`DB_USER=bodegas_user`, `DB_PASSWORD` y `URL_INVENTARIO=http://inventario:3004`.
Solo configurar valores reales en archivos `.env` que nunca se suben a GitHub.

## Docker y pruebas

Desde raíz del repositorio:

```sh
docker build -f docker/bodegas/Dockerfile -t sportmarket-bodegas .
docker run --rm --entrypoint python sportmarket-bodegas -m unittest discover -s test -v
```

Estos tests usan mocks y **no** prueban MySQL real. Para prueba integrada, levantar el servicio
conectado a `sportmarket_mysql` e invocar `/health` y `/api/bodegas/1` con el token interno.
Confirmar posteriormente el acceso a través del Gateway con un JWT válido.
