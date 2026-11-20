// Adaptador Express: convierte req/res al formato simple de manejador.js y publica la documentacion /docs
const fs = require('fs');
const path = require('path');
const express = require('express');
const swaggerUi = require('swagger-ui-express');
const YAML = require('yaml');
const { crearManejador } = require('./manejador');

function crearApp(config, repo) {
  const h = crearManejador(config, repo);
  const app = express();
  app.disable('x-powered-by');

  // Documentacion de la API (RNF08), generada desde openapi.yaml
  const ruta = path.join(__dirname, '..', 'openapi.yaml');
  const texto = fs.readFileSync(ruta, 'utf8');
  app.get('/openapi.yaml', (req, res) => res.type('text/yaml').send(texto));
  app.use('/docs', swaggerUi.serve, swaggerUi.setup(YAML.parse(texto)));

  app.use(express.json({ limit: '1mb' }));
  app.use((err, req, res, next) => {   // JSON mal formado
    if (!err) return next();
    return res.status(400).json({ codigo: 'PETICION_INVALIDA', mensaje: 'El cuerpo no es un JSON valido', detalles: [], correlation_id: 'sin-correlacion' });
  });
  app.use(async (req, res) => {
    const r = await h.manejar({ metodo: req.method, ruta: req.path, consulta: req.query, headers: req.headers, cuerpo: req.body });
    res.set(r.headers);
    res.status(r.status).json(r.cuerpo);
  });
  return app;
}
module.exports = { crearApp };
