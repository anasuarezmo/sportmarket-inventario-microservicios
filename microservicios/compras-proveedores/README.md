# Compras y Proveedores — Entrega 3

**Framework:** Django (según diseño Entrega 2; confirmar con el profesor si está permitido). **Puerto:** 8005. **BD:** `compras_db` (MySQL 8).

Este paquete contiene las 13 operaciones de `docs/entrega-2/openapi/compras.yaml` y se integra internamente con Catálogo e Inventario. No modifica código ni archivos de Edwin. La ruta `/health` es pública, y los endpoints de negocio requieren `X-Internal-Token` y `X-User-Role` (cabeceras que agrega el Gateway).

## Instalar las tablas

Con MySQL ya iniciado en Compose:

```bash
docker exec -i sportmarket_mysql mysql -u compras_user -pdev_password compras_db < microservicios/compras-proveedores/sql/schema.sql
```

**Solo para el entorno local proporcionado por el repositorio**: `dev_password` es la credencial de desarrollo utilizada por el script de Edwin; no usarla en producción.

## Construir y probar

```bash
docker build -f docker/compras/Dockerfile -t sportmarket-compras .
docker run --rm --entrypoint python sportmarket-compras -m unittest discover -s test -v
```

## Ejecutar en la red de Docker del repositorio

```bash
docker run -d --name sportmarket_compras_dev \
  --network sportmarket-inventario-microservicios_default \
  --network-alias compras \
  --env-file .env \
  -e DB_HOST=mysql -e DB_PORT=3306 -e DB_NAME=compras_db \
  -e DB_USER=compras_user -e DB_PASSWORD=dev_password \
  -e URL_CATALOGO=http://catalogo:3003 \
  -e URL_INVENTARIO=http://inventario:3004 \
  -p 127.0.0.1:8005:8005 sportmarket-compras
curl http://127.0.0.1:8005/health
```

La llamada externa a Compras **debe pasar por el Gateway (8080)**; la publicación en `127.0.0.1` es solo para pruebas locales. Edwin agregará el servicio a su `docker-compose.yml` al integrar.

## Recepciones e idempotencia

Una recepción se guarda en MySQL *antes* de enviar movimientos a Inventario. Cada línea conserva un UUID `operacion_id` y una bandera `aplicada`, agregada al diseño para evitar incrementos repetidos de `cantidad_recibida` si Inventario contesta 200 a un reintento. La llamada de Inventario **no** envía `X-User-Role`, tal como exige su middleware para aceptar origen `COMPRA` interno. El servicio reintenta errores transitorios sin cambiar el UUID. Si falta Inventario, la recepción queda `PENDIENTE_DE_SINCRONIZAR`; si Inventario rechaza una operación de negocio con 4xx, queda `RECHAZADA`.

Para recuperar recepciones pendientes cuando el servicio vuelve a estar disponible, sin crear operaciones nuevas:

```bash
docker exec sportmarket_compras_dev python manage.py sincronizar_pendientes
```

El script no altera recepciones sincronizadas o rechazadas.

## Variables de entorno

`PORT=8005`, `INTERNAL_TOKEN`, `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `URL_CATALOGO`, `URL_INVENTARIO`. `JWT_SECRET` no se utiliza directamente: es Usuarios quien genera el JWT y el Gateway quien lo valida. **Nunca subir `.env` al repositorio.**

## Contrato y pendientes de verificación

- 13 rutas método + path de OpenAPI; GET `/openapi.yaml` entrega documentación solo con credencial interna y rol válido.
- Errores: `{codigo, mensaje, detalles, correlation_id}`. Listas: `{items,total,page,limit}`; respuestas de escritura: `{mensaje, recurso}`.
- Pendiente **probar**: ejecución de tests en Docker; DDL con MySQL real; validación con Catálogo; recepción contra Inventario real; integración de Gateway 8080; rendimiento con Locust.
- Antes de la demostración, se requiere verificar con el docente si Django está permitido. Si la respuesta es negativa, se tendrá que adaptar a Flask sin cambiar la API ni el esquema de datos.
