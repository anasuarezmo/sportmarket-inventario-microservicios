// Verificacion de JWT HS256 sin librerias externas (solo modulo crypto de Node).
// Compatible con tokens generados por PyJWT (Flask) o cualquier libreria estandar.
const crypto = require('crypto');

const ROLES_VALIDOS = ['ADM', 'INV', 'COM', 'BOD', 'CON'];
const b64 = (s) => Buffer.from(s, 'base64url');

function verificarToken(token, secreto, ahora = Math.floor(Date.now() / 1000)) {
  if (!secreto) return { ok: false, motivo: 'Gateway sin JWT_SECRET configurado' };
  const partes = String(token || '').split('.');
  if (partes.length !== 3) return { ok: false, motivo: 'Token mal formado' };
  const [h, p, firma] = partes;
  let cabecera, payload;
  try {
    cabecera = JSON.parse(b64(h).toString('utf8'));
    payload = JSON.parse(b64(p).toString('utf8'));
  } catch {
    return { ok: false, motivo: 'Token mal formado' };
  }
  if (cabecera.alg !== 'HS256') return { ok: false, motivo: 'Algoritmo no permitido' };
  const esperada = crypto.createHmac('sha256', secreto).update(`${h}.${p}`).digest();
  const recibida = b64(firma);
  if (recibida.length !== esperada.length || !crypto.timingSafeEqual(recibida, esperada)) {
    return { ok: false, motivo: 'Firma invalida' };
  }
  if (typeof payload.exp !== 'number' || payload.exp <= ahora) return { ok: false, motivo: 'Token expirado' };
  if (payload.sub === undefined || payload.sub === null || payload.sub === '') return { ok: false, motivo: 'Token sin sub' };
  if (!ROLES_VALIDOS.includes(payload.rol)) return { ok: false, motivo: 'Rol invalido en el token' };
  return { ok: true, usuarioId: String(payload.sub), rol: payload.rol };
}

// Solo para pruebas y para generar un token de desarrollo (npm run token en el futuro).
function firmarToken(payload, secreto) {
  const h = Buffer.from(JSON.stringify({ alg: 'HS256', typ: 'JWT' })).toString('base64url');
  const p = Buffer.from(JSON.stringify(payload)).toString('base64url');
  const f = crypto.createHmac('sha256', secreto).update(`${h}.${p}`).digest('base64url');
  return `${h}.${p}.${f}`;
}
module.exports = { verificarToken, firmarToken, ROLES_VALIDOS };
