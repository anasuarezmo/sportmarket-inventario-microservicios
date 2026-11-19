require('dotenv').config();
const { cargarConfig } = require('./config');
const { crearApp } = require('./app');

const config = cargarConfig();
if (!config.jwtSecret || !config.tokenInterno) {
  console.error('Faltan JWT_SECRET o INTERNAL_TOKEN en el .env');
  process.exit(1);
}
crearApp(config).listen(config.puerto, () => console.log(`API Gateway escuchando en el puerto ${config.puerto}`));
