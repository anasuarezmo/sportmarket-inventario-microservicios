// Solo para DESARROLLO: genera un JWT de prueba con el JWT_SECRET del .env
// Uso: node src/generarToken.js ADM        (roles: ADM INV COM BOD CON)
require('dotenv').config();
const { firmarToken, ROLES_VALIDOS } = require('./jwt');
const rol = (process.argv[2] || 'ADM').toUpperCase();
if (!ROLES_VALIDOS.includes(rol)) { console.error('Rol invalido. Usa:', ROLES_VALIDOS.join(' ')); process.exit(1); }
if (!process.env.JWT_SECRET) { console.error('Falta JWT_SECRET en .env'); process.exit(1); }
console.log(firmarToken({ sub: '1', rol, exp: Math.floor(Date.now() / 1000) + 3600 }, process.env.JWT_SECRET));
