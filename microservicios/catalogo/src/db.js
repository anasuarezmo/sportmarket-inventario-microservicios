const fs = require('fs');
const path = require('path');
const mysql = require('mysql2/promise');

function crearPool(bd) {
  return mysql.createPool({ ...bd, waitForConnections: true, connectionLimit: 10, dateStrings: false, timezone: 'Z' });
}

// Aplica sql/schema.sql (CREATE TABLE IF NOT EXISTS), con reintentos porque MySQL puede tardar en estar listo.
async function migrar(pool, intentos = 15) {
  const sql = fs.readFileSync(path.join(__dirname, '..', 'sql', 'schema.sql'), 'utf8');
  const sentencias = sql.split(';').map((x) => x.replace(/^\s*--.*$/gm, '').trim()).filter(Boolean);
  for (let i = 1; ; i++) {
    try {
      for (const st of sentencias) await pool.query(st);
      return;
    } catch (e) {
      if (i >= intentos) throw e;
      console.log(`Esperando a MySQL (${i}/${intentos}): ${e.code || e.message}`);
      await new Promise((r) => setTimeout(r, 2000));
    }
  }
}
module.exports = { crearPool, migrar };
