// Busca en la tabla (generada del OpenAPI) a que servicio va una peticion y quien puede hacerla.
const tabla = require('./tablaRutas');

function aRegex(ruta) {
  const exp = ruta.split('/').map((s) => (s.startsWith('{') ? '[^/]+' : s.replace(/[.*+?^$()|[\]\\]/g, '\\$&'))).join('/');
  return new RegExp(`^${exp}/?$`);
}
const reglas = tabla.map((r) => ({ ...r, regex: aRegex(r.ruta) }));

// Devuelve {regla} | {noPermitido:true} (la ruta existe pero con otro metodo) | null
function buscarRuta(metodo, ruta, reglasUsar = reglas) {
  const coinciden = reglasUsar.filter((r) => r.regex.test(ruta));
  if (coinciden.length === 0) return null;
  const regla = coinciden.find((r) => r.metodo === metodo.toUpperCase());
  return regla ? { regla } : { noPermitido: true };
}

function puedeAcceder(regla, rol) {
  if (regla.acceso === 'publica' || regla.acceso === 'todos') return true;
  return regla.roles.includes(rol);
}
module.exports = { buscarRuta, puedeAcceder, reglas, aRegex };
