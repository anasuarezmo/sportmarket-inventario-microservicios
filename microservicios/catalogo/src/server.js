require('dotenv').config();
const { cargarConfig } = require('./config');
const { crearPool, migrar } = require('./db');
const { crearRepositorio } = require('./repositorio');
const { crearApp } = require('./app');

(async () => {
  const config = cargarConfig();
  if (!config.tokenInterno) { console.error('Falta INTERNAL_TOKEN en el .env'); process.exit(1); }
  const pool = crearPool(config.bd);
  await migrar(pool);
  crearApp(config, crearRepositorio(pool)).listen(config.puerto, () => console.log(`Catalogo escuchando en el puerto ${config.puerto}`));
})().catch((e) => { console.error('No se pudo iniciar Catalogo:', e.message); process.exit(1); });
