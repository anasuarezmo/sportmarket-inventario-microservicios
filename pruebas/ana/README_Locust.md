# Locust: pruebas individuales de Ana (SportMarket, Entrega 3)

## Alcance y fundamento

Se realizan **15 ejecuciones independientes**: cinco escenarios de lectura de endpoints de los cuatro microservicios asignados a Ana, en tres perfiles de carga (normal, pico y carga alta relativa). Las solicitudes entran **siempre por el Gateway 8080**, con un JWT obtenido al inicio de la sesión. Las pruebas solo leen datos: no crean, editan ni eliminan registros durante la carga.

| Escenario | Método / ruta | Servicio |
|---|---|---|
| bodegas_lista | GET /api/bodegas | Bodegas |
| bodegas_detalle | GET /api/bodegas/1 | Bodegas |
| usuarios_lista | GET /api/usuarios | Usuarios (ADM) |
| devoluciones_lista | GET /api/devoluciones | Devoluciones |
| compras_lista | GET /api/compras | Compras (ADM) |

Perfiles de **20 segundos por ejecución**: normal (3 usuarios), pico (8 usuarios), carga alta relativa (15 usuarios). Con `constant_pacing(1)` cada usuario virtual emite aproximadamente 1 solicitud por segundo. El perfil alto no implica haber encontrado la capacidad máxima; para eso se necesitaría una prueba de saturación controlada.

## Antes de empezar

1. Tener MySQL, Gateway y los cuatro servicios ejecutándose y conectados en la misma red Docker.
2. Confirmar que `GET /api/bodegas/1` responde 200; el registro existe en la base de desarrollo según las pruebas anteriores.
3. El Gateway debe apuntar a las direcciones **internas** de los contenedores para los cuatro servicios, no a `localhost`. La validación previa del script detiene las pruebas si alguna ruta falla.
4. Utilizar el administrador creado previamente. No escribir credenciales ni JWT en archivos de la entrega.
5. Instalar Locust en un entorno virtual, por ejemplo:

   ```bash
   python3 -m venv ~/.venvs/locust-sportmarket
   source ~/.venvs/locust-sportmarket/bin/activate
   python -m pip install locust
   ```

## Ejecución

Desde la **raíz del repositorio** (rama de trabajo personal o nueva rama para pruebas):

```bash
bash pruebas/ana/ejecutar_15.sh
```

El script solicita correo y contraseña sin mostrarlos en la terminal; obtiene un JWT de desarrollo de forma temporal y ejecuta los 15 ensayos. Dura aproximadamente 5 minutos más arranques. No envía tokens ni contraseñas a archivos CSV.

## Evidencias y criterios

Se generan archivos CSV de Locust por ejecución y `pruebas/ana/resultados/resumen_15_pruebas.csv`. Registrar en la bitácora el entorno, los parámetros de carga, hora, máquinas y servicios activos, además de los errores reales que se observen. La guía del proyecto menciona p95 < 2 s y errores < 1 % como criterios; documentar los valores medidos, incluso si no se cumplen. **No afirmar resultados antes de ejecutar los ensayos**.

Las 15 ejecuciones no sustituyen pruebas funcionales de escritura ni pruebas generales de integración; únicamente miden escenarios concretos de lectura a través del Gateway. Para subir a GitHub, guardar los scripts y resultados apropiados en `pruebas/ana/` y coordinar con Edwin la carpeta final de evidencias `docs/entrega-3/`.
