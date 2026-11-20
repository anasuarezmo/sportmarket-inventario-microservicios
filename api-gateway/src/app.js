// Adaptador Express: convierte req/res de Express al formato simple que usa gateway.js
const express = require('express');
const { crearGateway } = require('./gateway');
const { error } = require('./errores');

function crearApp(config, fetchFn) {
  const gw = crearGateway(config, fetchFn);
  const app = express();
  app.disable('x-powered-by');
  app.use(express.json({ limit: '1mb' }));
  // JSON mal formado -> error en nuestro formato
  app.use((err, req, res, next) => {
    if (err) {
      const e = error(400, 'PETICION_INVALIDA', 'El cuerpo no es un JSON valido', 'sin-correlacion');
      return res.status(e.status).json(e.cuerpo);
    }
    next();
  });
  app.use(async (req, res) => {
    const consulta = req.originalUrl.includes('?') ? req.originalUrl.slice(req.originalUrl.indexOf('?')) : '';
    const r = await gw.manejar({ metodo: req.method, ruta: req.path, consulta, headers: req.headers, cuerpo: req.body });
    if (r.headers) res.set(r.headers);
    if (r.cuerpo === null || r.cuerpo === undefined) return res.status(r.status).end();
    return res.status(r.status).json(r.cuerpo);
  });
  return app;
}
module.exports = { crearApp };
