# Usuarios y Autenticación · SportMarket · Entrega 3

Microservicio Flask + MySQL 8 (usuarios_db), puerto 5001. Implementa las **12 operaciones** de `docs/entrega-2/openapi/usuarios.yaml` sin modificar el Gateway ni el contrato.

## Contrato y seguridad

- El Gateway es la entrada pública (`http://localhost:8080`). La API interna exige `X-Internal-Token` en todas las rutas salvo `/health`.
- El Gateway envía `X-User-Id`, `X-User-Role` y `X-Correlation-ID`. El microservicio exige además rol `ADM` en todas las operaciones de administración de usuarios/roles.
- JWT HS256: `sub` es `str(id)`, `rol` en `ADM|INV|COM|BOD|CON`, caducidad 60 min. `JWT_SECRET` tiene que coincidir con el del Gateway.
- `logout` responde 204: el cliente descarta el JWT; **no hay revocación inmediata** (contrato de Entrega 2). Los cambios de rol, estado o contraseña tampoco invalidan JWT ya emitidos hasta que expiren.
- Errores: `{codigo,mensaje,detalles,correlation_id}`. Listados: `{items,total,page,limit}`. Nunca se devuelve `password_hash`.
- `/docs` y `/openapi.yaml` requieren `X-Internal-Token` al acceder directamente al contenedor. El Gateway no tiene rutas de documentación para este microservicio.

## Inicializar con MySQL ya creado por Edwin

Desde la **raíz** del repositorio y en `feat/usuarios`:

```bash
docker compose up -d --wait mysql
docker exec -i sportmarket_mysql mysql -u usuarios_user -pdev_password usuarios_db < microservicios/usuarios-autenticacion/sql/schema.sql
# Comprobar las tablas:
docker exec sportmarket_mysql mysql -u usuarios_user -pdev_password usuarios_db -e 'SHOW TABLES;'
```

El esquema crea `rol`, `usuario` y `token_recuperacion` y siembra 5 roles. La contraseña `dev_password` es la del SQL de inicialización actual de Edwin y solo sirve para entorno de desarrollo. Para instalaciones nuevas se debe migrar a secretos seguros y variables concordantes.

## Construcción, pruebas y ejecución

```bash
docker build -f docker/usuarios/Dockerfile -t sportmarket-usuarios .
docker run --rm --entrypoint python sportmarket-usuarios -m unittest discover -s test -v
```

Pruebas unitarias con repositorio simulado. Para probar contra MySQL real:

```bash
docker rm -f sportmarket_usuarios_dev 2>/dev/null || true
docker run -d --name sportmarket_usuarios_dev \
  --network sportmarket-inventario-microservicios_default --network-alias usuarios \
  --env-file .env \
  -e DB_HOST=mysql -e DB_PORT=3306 -e DB_NAME=usuarios_db \
  -e DB_USER=usuarios_user -e DB_PASSWORD=dev_password -e PORT=5001 \
  -p 127.0.0.1:5001:5001 sportmarket-usuarios
curl -sS http://127.0.0.1:5001/health
```

**Configuración**: `.env` de la raíz debe tener `JWT_SECRET` e `INTERNAL_TOKEN` válidos y coincidentes con el Gateway. Generar el JWT secret con `openssl rand -hex 32` si todavía no existe; comunicarlo en privado a Edwin. No subir `.env` ni secretos al repositorio.

El contenedor de desarrollo se enlaza a la red de Compose con alias `usuarios`; Edwin incorporará el servicio al Compose definitivo. En producción solo Gateway debe ser accesible externamente.

## Crear el primer administrador

El modelo no trae usuarios precargados. Este paso es necesario para probar `login`; la contraseña se captura sin mostrarla y **nunca** se sube en código ni en el SQL:

```bash
read -rp 'Correo del administrador: ' ADMIN_EMAIL
read -rsp 'Contraseña del administrador (8-72 caracteres): ' ADMIN_PASSWORD; echo
docker exec -e ADMIN_EMAIL="$ADMIN_EMAIL" -e ADMIN_PASSWORD="$ADMIN_PASSWORD" \
  sportmarket_usuarios_dev python -m app.bootstrap
unset ADMIN_PASSWORD
```

Si el correo ya existe no se sobrescribe la clave. El script crea una sola cuenta con rol `ADM` (id=1).

## Probar login desde el Gateway

Después de tener el gateway funcionando en puerto 8080 y el alias `usuarios` en la misma red, enviar `POST /api/auth/login` con JSON `{"email":"<correo>","contrasena":"<clave>"}` al `http://localhost:8080`. El JWT obtenido permite probar `GET /api/roles` y demás rutas de administrador por el Gateway usando `Authorization: Bearer <token>`. Evitar pegar contraseñas o tokens en capturas o historiales de comandos.

## Recuperación de contraseña

El servidor guarda **solo SHA-256 del token aleatorio** y obliga a usarlo antes de 30 minutos y una única vez. `forgot-password` siempre responde 202 con el mismo texto, independientemente de la existencia del correo. **Para enviar correos se necesita SMTP**, con variables opcionales (configurar localmente, sin subir secretos): `SMTP_HOST`, `SMTP_PORT` (587), `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` y `SMTP_USE_TLS=true`. Sin SMTP configurado, no se envían los tokens y no puede probarse el ciclo por correo de extremo a extremo (sí hay pruebas unitarias con notificador falso). El correo lleva el token para llamar a `POST /api/auth/reset-password`; **nunca se muestra en respuestas API**.

## Evidencias y límites conocidos

- Pruebas unitarias: `test/test_usuarios.py` (31 escenarios; deben ejecutarse en Docker antes de reportarlas como aprobadas).
- Se requieren pruebas adicionales **con MySQL y a través del Gateway** para confirmar integración.
- Las 15 pruebas de carga con Locust por integrante y la bitácora IA son entregables **separados**, no cubiertos por este paquete.
- El JWT no se revoca en logout ni al cambiar contraseña/rol, según contrato original: para invalidación inmediata habría que acordar un cambio de arquitectura con Edwin.
- El servidor Flask incluido es para práctica/demostración académica; no se considera endurecido para producción.
