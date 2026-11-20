// GENERADO desde docs/entrega-2/openapi/*.yaml con scripts/generar_rutas.py. No editar a mano.
// acceso: 'publica' (sin JWT) | 'todos' (cualquier usuario autenticado) | 'roles' (solo los listados)
module.exports = [
  {
    "metodo": "GET",
    "ruta": "/api/bodegas",
    "servicio": "bodegas",
    "acceso": "todos",
    "roles": []
  },
  {
    "metodo": "POST",
    "ruta": "/api/bodegas",
    "servicio": "bodegas",
    "acceso": "roles",
    "roles": [
      "ADM",
      "INV"
    ]
  },
  {
    "metodo": "GET",
    "ruta": "/api/bodegas/{id}",
    "servicio": "bodegas",
    "acceso": "todos",
    "roles": []
  },
  {
    "metodo": "PUT",
    "ruta": "/api/bodegas/{id}",
    "servicio": "bodegas",
    "acceso": "roles",
    "roles": [
      "ADM",
      "INV"
    ]
  },
  {
    "metodo": "PATCH",
    "ruta": "/api/bodegas/{id}/estado",
    "servicio": "bodegas",
    "acceso": "roles",
    "roles": [
      "ADM",
      "INV"
    ]
  },
  {
    "metodo": "GET",
    "ruta": "/api/bodegas/{id}/ubicaciones",
    "servicio": "bodegas",
    "acceso": "todos",
    "roles": []
  },
  {
    "metodo": "POST",
    "ruta": "/api/bodegas/{id}/ubicaciones",
    "servicio": "bodegas",
    "acceso": "roles",
    "roles": [
      "ADM",
      "INV"
    ]
  },
  {
    "metodo": "PUT",
    "ruta": "/api/bodegas/{id}/ubicaciones/{ubicacion_id}",
    "servicio": "bodegas",
    "acceso": "roles",
    "roles": [
      "ADM",
      "INV"
    ]
  },
  {
    "metodo": "PATCH",
    "ruta": "/api/bodegas/{id}/ubicaciones/{ubicacion_id}/estado",
    "servicio": "bodegas",
    "acceso": "roles",
    "roles": [
      "ADM",
      "INV"
    ]
  },
  {
    "metodo": "GET",
    "ruta": "/api/bodegas/{id}/existencias",
    "servicio": "bodegas",
    "acceso": "todos",
    "roles": []
  },
  {
    "metodo": "GET",
    "ruta": "/api/productos",
    "servicio": "catalogo",
    "acceso": "todos",
    "roles": []
  },
  {
    "metodo": "POST",
    "ruta": "/api/productos",
    "servicio": "catalogo",
    "acceso": "roles",
    "roles": [
      "ADM",
      "INV"
    ]
  },
  {
    "metodo": "GET",
    "ruta": "/api/productos/{id}",
    "servicio": "catalogo",
    "acceso": "todos",
    "roles": []
  },
  {
    "metodo": "PUT",
    "ruta": "/api/productos/{id}",
    "servicio": "catalogo",
    "acceso": "roles",
    "roles": [
      "ADM",
      "INV"
    ]
  },
  {
    "metodo": "PATCH",
    "ruta": "/api/productos/{id}/estado",
    "servicio": "catalogo",
    "acceso": "roles",
    "roles": [
      "ADM",
      "INV"
    ]
  },
  {
    "metodo": "GET",
    "ruta": "/api/categorias",
    "servicio": "catalogo",
    "acceso": "todos",
    "roles": []
  },
  {
    "metodo": "POST",
    "ruta": "/api/categorias",
    "servicio": "catalogo",
    "acceso": "roles",
    "roles": [
      "ADM",
      "INV"
    ]
  },
  {
    "metodo": "GET",
    "ruta": "/api/categorias/{id}",
    "servicio": "catalogo",
    "acceso": "todos",
    "roles": []
  },
  {
    "metodo": "PUT",
    "ruta": "/api/categorias/{id}",
    "servicio": "catalogo",
    "acceso": "roles",
    "roles": [
      "ADM",
      "INV"
    ]
  },
  {
    "metodo": "PATCH",
    "ruta": "/api/categorias/{id}/estado",
    "servicio": "catalogo",
    "acceso": "roles",
    "roles": [
      "ADM",
      "INV"
    ]
  },
  {
    "metodo": "GET",
    "ruta": "/api/proveedores",
    "servicio": "compras",
    "acceso": "roles",
    "roles": [
      "ADM",
      "INV",
      "COM",
      "CON"
    ]
  },
  {
    "metodo": "POST",
    "ruta": "/api/proveedores",
    "servicio": "compras",
    "acceso": "roles",
    "roles": [
      "ADM",
      "COM"
    ]
  },
  {
    "metodo": "GET",
    "ruta": "/api/proveedores/{id}",
    "servicio": "compras",
    "acceso": "roles",
    "roles": [
      "ADM",
      "INV",
      "COM",
      "CON"
    ]
  },
  {
    "metodo": "PUT",
    "ruta": "/api/proveedores/{id}",
    "servicio": "compras",
    "acceso": "roles",
    "roles": [
      "ADM",
      "COM"
    ]
  },
  {
    "metodo": "PATCH",
    "ruta": "/api/proveedores/{id}/estado",
    "servicio": "compras",
    "acceso": "roles",
    "roles": [
      "ADM",
      "COM"
    ]
  },
  {
    "metodo": "POST",
    "ruta": "/api/proveedores/{id}/productos",
    "servicio": "compras",
    "acceso": "roles",
    "roles": [
      "ADM",
      "COM"
    ]
  },
  {
    "metodo": "GET",
    "ruta": "/api/proveedores/{id}/productos",
    "servicio": "compras",
    "acceso": "roles",
    "roles": [
      "ADM",
      "INV",
      "COM",
      "CON"
    ]
  },
  {
    "metodo": "GET",
    "ruta": "/api/compras",
    "servicio": "compras",
    "acceso": "roles",
    "roles": [
      "ADM",
      "INV",
      "COM",
      "CON"
    ]
  },
  {
    "metodo": "POST",
    "ruta": "/api/compras",
    "servicio": "compras",
    "acceso": "roles",
    "roles": [
      "ADM",
      "COM"
    ]
  },
  {
    "metodo": "GET",
    "ruta": "/api/compras/{id}",
    "servicio": "compras",
    "acceso": "roles",
    "roles": [
      "ADM",
      "INV",
      "COM",
      "CON"
    ]
  },
  {
    "metodo": "PATCH",
    "ruta": "/api/compras/{id}/estado",
    "servicio": "compras",
    "acceso": "roles",
    "roles": [
      "ADM",
      "COM"
    ]
  },
  {
    "metodo": "POST",
    "ruta": "/api/compras/{id}/recepciones",
    "servicio": "compras",
    "acceso": "roles",
    "roles": [
      "ADM",
      "COM",
      "BOD"
    ]
  },
  {
    "metodo": "GET",
    "ruta": "/api/compras/{id}/recepciones",
    "servicio": "compras",
    "acceso": "roles",
    "roles": [
      "ADM",
      "COM",
      "INV",
      "BOD"
    ]
  },
  {
    "metodo": "GET",
    "ruta": "/api/devoluciones",
    "servicio": "devoluciones",
    "acceso": "todos",
    "roles": []
  },
  {
    "metodo": "POST",
    "ruta": "/api/devoluciones",
    "servicio": "devoluciones",
    "acceso": "roles",
    "roles": [
      "ADM",
      "INV",
      "COM",
      "BOD"
    ]
  },
  {
    "metodo": "GET",
    "ruta": "/api/devoluciones/{id}",
    "servicio": "devoluciones",
    "acceso": "todos",
    "roles": []
  },
  {
    "metodo": "POST",
    "ruta": "/api/devoluciones/{id}/procesar",
    "servicio": "devoluciones",
    "acceso": "roles",
    "roles": [
      "ADM",
      "INV"
    ]
  },
  {
    "metodo": "GET",
    "ruta": "/api/inventario/existencias",
    "servicio": "inventario",
    "acceso": "todos",
    "roles": []
  },
  {
    "metodo": "GET",
    "ruta": "/api/inventario/existencias/{producto_id}",
    "servicio": "inventario",
    "acceso": "todos",
    "roles": []
  },
  {
    "metodo": "POST",
    "ruta": "/api/inventario/entradas",
    "servicio": "inventario",
    "acceso": "roles",
    "roles": [
      "ADM",
      "INV",
      "BOD"
    ]
  },
  {
    "metodo": "POST",
    "ruta": "/api/inventario/salidas",
    "servicio": "inventario",
    "acceso": "roles",
    "roles": [
      "ADM",
      "INV",
      "BOD"
    ]
  },
  {
    "metodo": "POST",
    "ruta": "/api/inventario/ajustes",
    "servicio": "inventario",
    "acceso": "roles",
    "roles": [
      "ADM",
      "INV"
    ]
  },
  {
    "metodo": "POST",
    "ruta": "/api/inventario/traslados",
    "servicio": "inventario",
    "acceso": "roles",
    "roles": [
      "ADM",
      "INV",
      "BOD"
    ]
  },
  {
    "metodo": "GET",
    "ruta": "/api/inventario/movimientos",
    "servicio": "inventario",
    "acceso": "todos",
    "roles": []
  },
  {
    "metodo": "GET",
    "ruta": "/api/inventario/movimientos/{id}",
    "servicio": "inventario",
    "acceso": "todos",
    "roles": []
  },
  {
    "metodo": "GET",
    "ruta": "/api/inventario/minimos/{producto_id}/{bodega_id}",
    "servicio": "inventario",
    "acceso": "todos",
    "roles": []
  },
  {
    "metodo": "PUT",
    "ruta": "/api/inventario/minimos/{producto_id}/{bodega_id}",
    "servicio": "inventario",
    "acceso": "roles",
    "roles": [
      "ADM",
      "INV"
    ]
  },
  {
    "metodo": "GET",
    "ruta": "/api/reportes/inventario",
    "servicio": "reportes",
    "acceso": "roles",
    "roles": [
      "ADM",
      "INV",
      "COM",
      "CON"
    ]
  },
  {
    "metodo": "GET",
    "ruta": "/api/reportes/valorizacion",
    "servicio": "reportes",
    "acceso": "roles",
    "roles": [
      "ADM",
      "INV",
      "COM",
      "CON"
    ]
  },
  {
    "metodo": "GET",
    "ruta": "/api/reportes/rotacion",
    "servicio": "reportes",
    "acceso": "roles",
    "roles": [
      "ADM",
      "INV",
      "COM",
      "CON"
    ]
  },
  {
    "metodo": "GET",
    "ruta": "/api/reportes/movimientos",
    "servicio": "reportes",
    "acceso": "roles",
    "roles": [
      "ADM",
      "INV",
      "COM",
      "CON"
    ]
  },
  {
    "metodo": "GET",
    "ruta": "/api/reportes/dashboard",
    "servicio": "reportes",
    "acceso": "todos",
    "roles": []
  },
  {
    "metodo": "GET",
    "ruta": "/api/alertas",
    "servicio": "reportes",
    "acceso": "todos",
    "roles": []
  },
  {
    "metodo": "PATCH",
    "ruta": "/api/alertas/{id}/estado",
    "servicio": "reportes",
    "acceso": "roles",
    "roles": [
      "ADM",
      "INV"
    ]
  },
  {
    "metodo": "POST",
    "ruta": "/api/auth/login",
    "servicio": "usuarios",
    "acceso": "publica",
    "roles": []
  },
  {
    "metodo": "POST",
    "ruta": "/api/auth/logout",
    "servicio": "usuarios",
    "acceso": "todos",
    "roles": []
  },
  {
    "metodo": "POST",
    "ruta": "/api/auth/forgot-password",
    "servicio": "usuarios",
    "acceso": "publica",
    "roles": []
  },
  {
    "metodo": "POST",
    "ruta": "/api/auth/reset-password",
    "servicio": "usuarios",
    "acceso": "publica",
    "roles": []
  },
  {
    "metodo": "POST",
    "ruta": "/api/auth/change-password",
    "servicio": "usuarios",
    "acceso": "todos",
    "roles": []
  },
  {
    "metodo": "GET",
    "ruta": "/api/usuarios",
    "servicio": "usuarios",
    "acceso": "roles",
    "roles": [
      "ADM"
    ]
  },
  {
    "metodo": "POST",
    "ruta": "/api/usuarios",
    "servicio": "usuarios",
    "acceso": "roles",
    "roles": [
      "ADM"
    ]
  },
  {
    "metodo": "GET",
    "ruta": "/api/usuarios/{id}",
    "servicio": "usuarios",
    "acceso": "roles",
    "roles": [
      "ADM"
    ]
  },
  {
    "metodo": "PUT",
    "ruta": "/api/usuarios/{id}",
    "servicio": "usuarios",
    "acceso": "roles",
    "roles": [
      "ADM"
    ]
  },
  {
    "metodo": "PATCH",
    "ruta": "/api/usuarios/{id}/rol",
    "servicio": "usuarios",
    "acceso": "roles",
    "roles": [
      "ADM"
    ]
  },
  {
    "metodo": "PATCH",
    "ruta": "/api/usuarios/{id}/estado",
    "servicio": "usuarios",
    "acceso": "roles",
    "roles": [
      "ADM"
    ]
  },
  {
    "metodo": "GET",
    "ruta": "/api/roles",
    "servicio": "usuarios",
    "acceso": "roles",
    "roles": [
      "ADM"
    ]
  }
];
