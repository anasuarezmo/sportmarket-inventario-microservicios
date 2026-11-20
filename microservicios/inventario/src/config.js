function cargarConfig(env = process.env) {
  return {
    puerto: Number(env.PORT || 3004),
    tokenInterno: env.INTERNAL_TOKEN || '',
    timeoutMs: Number(env.TIMEOUT_MS || 3000),
    reintentos: Number(env.REINTENTOS || 3),
    urls: {
      catalogo: env.URL_CATALOGO || 'http://localhost:3003',
      bodegas: env.URL_BODEGAS || 'http://localhost:5002',
      reportes: env.URL_REPORTES || 'http://localhost:5007',
    },
    bd: {
      host: env.DB_HOST || 'localhost',
      port: Number(env.DB_PORT || 3306),
      database: env.DB_NAME || 'inventario_db',
      user: env.DB_USER || 'inventario_user',
      password: env.DB_PASSWORD || '',
    },
  };
}
module.exports = { cargarConfig };
