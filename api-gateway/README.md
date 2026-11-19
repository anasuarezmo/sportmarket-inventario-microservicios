# API Gateway

Unico punto de entrada del sistema (puerto 8080). No tiene base de datos.

Hace, en orden: valida JWT (HS256) -> revisa el rol contra la tabla de permisos -> agrega `X-User-Id`, `X-User-Role`, `X-Internal-Token`, `X-Correlation-ID` -> reenvia al microservicio -> devuelve su respuesta (o un error 401/403/404/405/503/504 con el formato estandar).

- `src/tablaRutas.js` se genera desde `docs/entrega-2/openapi/*.yaml` con `python scripts/generar_rutas.py`.
- `/api/interno/*` nunca se expone.
- Pruebas: `npm test`. Ejecucion: `npm install` y `npm start` (requiere `.env`, ver `.env.example`).
- Token de prueba: `node src/generarToken.js ADM`.
