function cargarConfig(env = process.env) {
  return {
    puerto: Number(env.PORT || 3003),
    tokenInterno: env.INTERNAL_TOKEN || '',
    bd: {
      host: env.DB_HOST || 'localhost',
      port: Number(env.DB_PORT || 3306),
      database: env.DB_NAME || 'catalogo_db',
      user: env.DB_USER || 'catalogo_user',
      password: env.DB_PASSWORD || '',
    },
  };
}
module.exports = { cargarConfig };
