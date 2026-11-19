// Lee la configuracion desde variables de entorno (.env en local, environment en Docker).
function cargarConfig(env = process.env) {
  return {
    puerto: Number(env.PORT || 8080),
    jwtSecret: env.JWT_SECRET || '',
    tokenInterno: env.INTERNAL_TOKEN || '',
    timeoutMs: Number(env.TIMEOUT_MS || 10000),
    servicios: {
      usuarios: env.URL_USUARIOS || 'http://localhost:5001',
      bodegas: env.URL_BODEGAS || 'http://localhost:5002',
      catalogo: env.URL_CATALOGO || 'http://localhost:3003',
      inventario: env.URL_INVENTARIO || 'http://localhost:3004',
      compras: env.URL_COMPRAS || 'http://localhost:8005',
      devoluciones: env.URL_DEVOLUCIONES || 'http://localhost:5006',
      reportes: env.URL_REPORTES || 'http://localhost:5007',
    },
  };
}
module.exports = { cargarConfig };
