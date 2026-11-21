# Evidencia de Bodegas

1. Ejecutar los tests con `docker run ... -m unittest discover -s test -v` y guardar captura.
2. Ejecutar una consulta real a MySQL mediante `GET /api/bodegas/{id}` con `X-Internal-Token`.
3. Verificar 401 sin token y 403 con rol `CON` en POST.
4. Probar POST/PUT/PATCH contra MySQL con datos de prueba y registrar los HTTP status.
5. Pedir a Edwin integrar el Compose real de Bodegas, sin modificar su `docker-compose.yml`.
6. Probar rutas mediante puerto 8080 y JWT emitido por Usuarios.
7. Crear `feat/bodegas` en GitHub con PR a `main`; registrar bitácora de IA.

**Importante:** pruebas unitarias y carga Locust son actividades diferentes. Las 15 pruebas
individuales de Locust aún deben diseñarse/ejecutarse y guardar resultados reales.
