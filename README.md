# SportMarket S.A.S.

Sistema de Gestión de Inventarios basado en Arquitectura de Microservicios.

Proyecto desarrollado para la asignatura Ingeniería de Software II de la Universidad Nacional de Colombia.

## Integrantes

- Ana Maria Suarez Moncada
- Edwin Hernán Chenas Escobar

## Descripción

SportMarket S.A.S. es una empresa ficticia dedicada a la comercialización y distribución de productos deportivos.

El proyecto propone el desarrollo de un sistema que permita gestionar productos, categorías, proveedores, bodegas, existencias, movimientos de inventario, órdenes de compra, devoluciones, usuarios, alertas y reportes.

La solución será desarrollada utilizando una arquitectura basada en microservicios.

## Entrega 1

Durante la primera entrega se trabajó en:

- Investigación de sistemas de gestión de inventarios existentes.
- Definición de la empresa y problemática.
- Objetivos y alcance del sistema.
- Requerimientos funcionales y no funcionales.
- Dominios y Bounded Contexts.
- Comparación entre arquitectura monolítica y microservicios.
- Identificación preliminar de microservicios.
- Bitácora de uso de inteligencia artificial.

## Entrega 2

Diseño y arquitectura de la solución: diagrama de arquitectura, modelo de datos por microservicio y contratos OpenAPI. Los documentos están en `docs/entrega-2/`.

## Entrega 3: implementación e integración

### Arquitectura

Un API Gateway y siete microservicios, cada uno con su propia base de datos dentro de una única instancia de MySQL. El Gateway valida el JWT y es el único servicio con un puerto publicado (8080). Los servicios solo se comunican entre sí por REST y por la red interna de Docker, con un token interno.

| Servicio | Tecnología | Puerto | Responsable |
|---|---|---|---|
| API Gateway | Node.js | 8080 (único publicado) | Edwin |
| Catálogo | Node.js | 3003 | Edwin |
| Inventario | Node.js | 3004 | Edwin |
| Reportes y Alertas | Python (Flask) | 5007 | Edwin |
| Usuarios y Autenticación | Python (Flask) | 5001 | Ana |
| Bodegas | Python (Flask) | 5002 | Ana |
| Devoluciones | Python (Flask) | 5006 | Ana |
| Compras y Proveedores | Python (Django) | 8005 | Ana |

Seguridad: las rutas internas (`/api/interno/*`) no se exponen por el Gateway, los servicios exigen el token interno y los secretos viven en el archivo `.env`, que no se sube al repositorio.

### Cómo ejecutarlo

Requiere Docker con Docker Compose. Desde la raíz del repositorio:

1. Crear el archivo `.env` a partir de `.env.example` y completar los valores (`MYSQL_ROOT_PASSWORD`, `JWT_SECRET`, `INTERNAL_TOKEN` y `DJANGO_SECRET_KEY`).
2. Levantar todo: `docker compose up -d --build`
3. Crear las tablas de Usuarios, Bodegas, Devoluciones y Compras: `./scripts/aplicar-esquemas.sh`
4. Crear el administrador inicial (pide correo y contraseña por teclado): `./scripts/crear-admin.sh`
5. Iniciar sesión por el Gateway: `POST http://localhost:8080/api/auth/login` con `{"email": "...", "contrasena": "..."}`. El token devuelto se envía como `Authorization: Bearer <token>`.

Para detener sin perder los datos: `docker compose stop`. El comando `docker compose down -v` borra la base de datos.

### Pruebas y evidencias

- Pruebas unitarias en cada microservicio (carpeta `test/` de cada servicio).
- Prueba de humo del sistema integrado: `bash pruebas/edwin/humo_compose.sh`. Pasa por el Gateway, usa un inicio de sesión real y cubre roles, compra recibida, devoluciones, idempotencia, alertas y reportes (52 comprobaciones correctas en la corrida del 23/11/2026). Requiere datos base: un producto activo con id 2 y la bodega con id 1, que se crean por el Gateway con el usuario administrador.
- Pruebas de rendimiento con Locust: 15 pruebas de Edwin en `pruebas/edwin/` (1161 solicitudes, sin fallos, p95 de 45 ms) y 15 ejecuciones de Ana en `pruebas/ana/`. Cada carpeta incluye su README, los scripts y los resultados.
- Bitácora de uso de inteligencia artificial: `docs/entrega-3/Bitacora_IA_Entrega_3.pdf`.

### Alcance y limitaciones

- La recuperación de contraseña por correo está implementada, pero no tiene un servidor SMTP configurado en este entorno.
- Kubernetes: la carpeta `kubernetes/` es trabajo preliminar y queda pendiente de confirmar si la entrega lo exige.
- Las pruebas de carga se hicieron en un solo equipo y con carga moderada; no determinan la capacidad máxima del sistema.

## Estado del proyecto

Las entregas 1 y 2 están completas. En la Entrega 3 el sistema funciona de extremo a extremo: los ocho servicios arrancan con un solo comando, solo el Gateway es accesible desde afuera, la comunicación entre servicios es por REST y existe evidencia de pruebas funcionales, de integración y de rendimiento.
