// Bodegas "de mentira" SOLO para probar Inventario mientras no exista el servicio real (Ana).
// Responde 200 para las bodegas 1 a 3 en GET /api/bodegas/{id}; 404 para las demas. Puerto 5002.
const http = require('http');
http.createServer((req, res) => {
  const m = /^\/api\/bodegas\/(\d+)$/.exec(req.url.split('?')[0]);
  res.setHeader('Content-Type', 'application/json');
  if (req.url === '/health') { res.end('{"estado":"UP","servicio":"mock-bodegas"}'); return; }
  if (m && Number(m[1]) >= 1 && Number(m[1]) <= 3) { res.end(JSON.stringify({ id: Number(m[1]), nombre_bodega: `Bodega ${m[1]} (mock)`, bodega_activa: true })); return; }
  res.statusCode = 404; res.end('{"codigo":"RECURSO_NO_ENCONTRADO","mensaje":"Bodega no encontrada","detalles":[]}');
}).listen(5002, () => console.log('Mock de Bodegas escuchando en el puerto 5002 (bodegas 1 a 3)'));
