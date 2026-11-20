require('dotenv').config();
const { cargarConfig } = require('./config');
const { crearPool, migrar } = require('./db');
const { crearRepositorio } = require('./repositorio');
const { crearClientes } = require('./clientes');
const { crearApp } = require('./app');

(async () => {
  const config = cargarConfig();
  if (!config.tokenInterno) { console.error('Falta INTERNAL_TOKEN en el .env'); process.exit(1); }
  const pool = crearPool(config.bd);
  await migrar(pool);
  crearApp(config, crearRepositorio(pool), crearClientes(config)).listen(config.puerto, () => console.log(`Inventario escuchando en el puerto ${config.puerto}`));
})().catch((e) => { console.error('No se pudo iniciar Inventario:', e.message); process.exit(1); });
