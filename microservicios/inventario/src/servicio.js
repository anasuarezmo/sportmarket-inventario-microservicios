// Reglas de negocio de Inventario. Recibe el repositorio y los clientes por parametro (se prueba sin MySQL ni red).
const { ErrorApi, noEncontrado } = require('./errores');
const v = require('./validaciones');

const MENSAJES = { ENTRADA: 'Movimiento registrado correctamente', SALIDA: 'Movimiento registrado correctamente', AJUSTE: 'Ajuste registrado correctamente', TRASLADO: 'Traslado registrado correctamente' };
const pagina = (r, f) => ({ items: r.filas, total: r.total, page: f.page, limit: f.limit });
const norm = (x) => (x === undefined ? null : x);

// Aviso solo cuando el saldo CRUZA el minimo: baja de "no bajo" a "bajo" o vuelve a alcanzarlo.
function evaluarCruce(antes, despues, minimoAntes, minimoDespues) {
  const estabaBajo = antes < minimoAntes; const estaBajo = despues < minimoDespues;
  if (!estabaBajo && estaBajo) return 'STOCK_BAJO';
  if (estabaBajo && !estaBajo) return 'STOCK_RECUPERADO';
  return null;
}

function crearServicio(repo, clientes, log = console) {
  const pendientes = new Set();

  // El aviso se envia despues de confirmar la transaccion y sin esperar: si falla, el movimiento NO se revierte.
  function avisar(cambios, productoId, cid) {
    for (const c of cambios) {
      const evento = evaluarCruce(c.antes, c.despues, c.minimoAntes, c.minimoDespues);
      if (!evento) continue;
      const p = clientes.avisarStock({ evento, producto_id: productoId, bodega_id: c.bodega_id, cantidad_disponible: c.despues, stock_minimo: c.minimoDespues }, cid)
        .catch((e) => log.error(`No se pudo avisar ${evento} (producto ${productoId}, bodega ${c.bodega_id}):`, e.message))
        .finally(() => pendientes.delete(p));
      pendientes.add(p);
    }
  }
  const esperarAvisos = () => Promise.allSettled([...pendientes]);

  async function validarProductoBodegas(productoId, bodegas, cid) {
    const [okProducto, ...okBodegas] = await Promise.all([clientes.productoExiste(productoId, cid), ...bodegas.map((b) => clientes.bodegaExiste(b, cid))]);
    if (!okProducto) throw new ErrorApi(422, 'PRODUCTO_INEXISTENTE', 'El producto no existe en el catalogo', [{ campo: 'producto_id', error: `El producto ${productoId} no existe` }]);
    okBodegas.forEach((ok, i) => {
      if (!ok) throw new ErrorApi(422, 'BODEGA_INEXISTENTE', 'La bodega no existe', [{ campo: 'bodega_id', error: `La bodega ${bodegas[i]} no existe` }]);
    });
  }

  async function respuesta(datos, mov, status) {
    const cuerpo = { mensaje: MENSAJES[mov.tipo_movimiento], movimiento: mov };
    if (mov.tipo_movimiento === 'TRASLADO') {
      const [o, d] = await Promise.all([repo.obtenerSaldo(mov.producto_id, mov.bodega_origen_id), repo.obtenerSaldo(mov.producto_id, mov.bodega_destino_id)]);
      cuerpo.saldos = { origen: { bodega_id: mov.bodega_origen_id, cantidad_disponible: o ? o.cantidad_disponible : 0 }, destino: { bodega_id: mov.bodega_destino_id, cantidad_disponible: d ? d.cantidad_disponible : 0 } };
    }
    return { status, cuerpo };
  }

  // Misma operacion_id: con los mismos datos -> 200 con el resultado ya confirmado; con datos distintos -> 409.
  async function repeticion(datos, prev) {
    const igual = prev.tipo_movimiento === datos.tipo_movimiento && prev.producto_id === datos.producto_id
      && norm(prev.bodega_origen_id) === norm(datos.bodega_origen_id) && norm(prev.bodega_destino_id) === norm(datos.bodega_destino_id)
      && prev.cantidad_movimiento === datos.cantidad_movimiento && prev.origen_movimiento === datos.origen_movimiento;
    if (!igual) throw new ErrorApi(409, 'OPERACION_DUPLICADA', 'El operacion_id ya se uso con datos diferentes', [{ campo: 'operacion_id', error: 'Reutilizado con otros datos' }]);
    return respuesta(datos, prev, 200);
  }

  // Todo dentro de UNA transaccion: bloquea saldos, modifica cantidades y registra el movimiento (o revierte todo).
  async function ejecutar(datos, ctx) {
    return repo.transaccion(async (tx) => {
      const previo = await tx.movimientoPorOperacion(datos.operacion_id);
      if (previo) return { previo };
      const { tipo_movimiento: tipo, producto_id: p, cantidad_movimiento: cant } = datos;
      const cambios = []; let saldoResultante;

      const sumar = async (bodega) => {
        const s = await tx.saldoBloqueado(p, bodega);
        const nueva = s.cantidad_disponible + cant;
        await tx.fijarCantidad(p, bodega, nueva);
        cambios.push({ bodega_id: bodega, antes: s.cantidad_disponible, despues: nueva, minimoAntes: s.stock_minimo, minimoDespues: s.stock_minimo });
        return nueva;
      };
      const restar = async (bodega, s) => {
        if (s.cantidad_disponible < cant) {
          throw new ErrorApi(409, 'STOCK_INSUFICIENTE', 'No hay existencias suficientes', [{ campo: 'cantidad_movimiento', error: `Solicitadas ${cant}, disponibles ${s.cantidad_disponible}` }]);
        }
        const nueva = s.cantidad_disponible - cant;
        await tx.fijarCantidad(p, bodega, nueva);
        cambios.push({ bodega_id: bodega, antes: s.cantidad_disponible, despues: nueva, minimoAntes: s.stock_minimo, minimoDespues: s.stock_minimo });
        return nueva;
      };

      if (tipo === 'TRASLADO') {
        // se bloquean siempre en orden de bodega para evitar interbloqueos entre traslados cruzados
        const orden = [datos.bodega_origen_id, datos.bodega_destino_id].sort((a, b) => a - b);
        const saldos = {};
        for (const b of orden) saldos[b] = await tx.saldoBloqueado(p, b);
        saldoResultante = await restar(datos.bodega_origen_id, saldos[datos.bodega_origen_id]);
        const s2 = saldos[datos.bodega_destino_id];
        const nuevaDestino = s2.cantidad_disponible + cant;
        await tx.fijarCantidad(p, datos.bodega_destino_id, nuevaDestino);
        cambios.push({ bodega_id: datos.bodega_destino_id, antes: s2.cantidad_disponible, despues: nuevaDestino, minimoAntes: s2.stock_minimo, minimoDespues: s2.stock_minimo });
      } else if (datos.bodega_destino_id !== undefined) {           // ENTRADA o AJUSTE positivo
        saldoResultante = await sumar(datos.bodega_destino_id);
      } else {                                                        // SALIDA o AJUSTE negativo
        saldoResultante = await restar(datos.bodega_origen_id, await tx.saldoBloqueado(p, datos.bodega_origen_id));
      }

      const id = await tx.insertarMovimiento({
        operacion_id: datos.operacion_id, tipo_movimiento: tipo, producto_id: p,
        bodega_origen_id: norm(datos.bodega_origen_id), bodega_destino_id: norm(datos.bodega_destino_id),
        cantidad_movimiento: cant, saldo_resultante: saldoResultante, motivo_movimiento: norm(datos.motivo_movimiento),
        origen_movimiento: datos.origen_movimiento, documento_ref: norm(datos.documento_ref), usuario_id: ctx.usuarioId,
      });
      return { id, cambios };
    });
  }

  async function registrar(datos, ctx) {
    // 1) repeticion: se responde aunque Catalogo o Bodegas esten caidos
    const prev = await repo.movimientoPorOperacion(datos.operacion_id);
    if (prev) return repeticion(datos, prev);
    // 2) el producto y las bodegas deben existir (se valida antes de abrir la transaccion para no mantener bloqueos mientras se espera la red)
    await validarProductoBodegas(datos.producto_id, [datos.bodega_origen_id, datos.bodega_destino_id].filter((x) => x !== undefined), ctx.cid);
    // 3) escritura transaccional
    let r;
    try { r = await ejecutar(datos, ctx); } catch (e) {
      if (e && e.code === 'ER_DUP_ENTRY') { const otra = await repo.movimientoPorOperacion(datos.operacion_id); if (otra) return repeticion(datos, otra); }
      throw e;
    }
    if (r.previo) return repeticion(datos, r.previo);
    avisar(r.cambios, datos.producto_id, ctx.cid);
    return respuesta(datos, await repo.movimientoPorId(r.id), 201);
  }

  // El origen COMPRA/DEVOLUCION solo lo pueden usar los servicios internos (llamadas sin rol de usuario).
  const origenPermitido = (datos, ctx) => {
    if (datos.origen_movimiento !== 'MANUAL' && !ctx.interno) {
      throw new ErrorApi(403, 'ORIGEN_NO_PERMITIDO', 'Un usuario solo puede registrar movimientos con origen MANUAL', [{ campo: 'origen_movimiento', error: `${datos.origen_movimiento} esta reservado para servicios internos` }]);
    }
  };

  const existencias = {
    async listar(q) { const f = v.filtrosExistencias(q); return { status: 200, cuerpo: pagina(await repo.listarExistencias(f), f) }; },
    async porProducto(idTxt, ctx) {
      const id = v.parseId(idTxt, 'producto_id');
      if (!(await clientes.productoExiste(id, ctx.cid))) throw noEncontrado('Producto');
      const filas = await repo.saldosDeProducto(id);
      return { status: 200, cuerpo: { producto_id: id, total: filas.reduce((t, s) => t + s.cantidad_disponible, 0), bodegas: filas.map((s) => ({ bodega_id: s.bodega_id, cantidad_disponible: s.cantidad_disponible, stock_minimo: s.stock_minimo })) } };
    },
  };

  const movimientos = {
    entrada: async (body, ctx) => { const d = v.validarEntradaSalida(body, 'ENTRADA'); origenPermitido(d, ctx); return registrar(d, ctx); },
    salida: async (body, ctx) => { const d = v.validarEntradaSalida(body, 'SALIDA'); origenPermitido(d, ctx); return registrar(d, ctx); },
    ajuste: async (body, ctx) => registrar(v.validarAjuste(body), ctx),
    traslado: async (body, ctx) => registrar(v.validarTraslado(body), ctx),
    async listar(q) { const f = v.filtrosMovimientos(q); return { status: 200, cuerpo: pagina(await repo.listarMovimientos(f), f) }; },
    async obtener(idTxt) { const m = await repo.movimientoPorId(v.parseId(idTxt)); if (!m) throw noEncontrado('Movimiento'); return { status: 200, cuerpo: m }; },
  };

  async function existeEnRuta(p, b, cid) {
    const [okP, okB] = await Promise.all([clientes.productoExiste(p, cid), clientes.bodegaExiste(b, cid)]);
    if (!okP) throw noEncontrado('Producto');
    if (!okB) throw noEncontrado('Bodega');
  }
  const minimos = {
    async obtener(pTxt, bTxt, ctx) {
      const p = v.parseId(pTxt, 'producto_id'); const b = v.parseId(bTxt, 'bodega_id');
      await existeEnRuta(p, b, ctx.cid);
      const s = await repo.obtenerSaldo(p, b);
      return { status: 200, cuerpo: { producto_id: p, bodega_id: b, stock_minimo: s ? s.stock_minimo : 0, cantidad_disponible: s ? s.cantidad_disponible : 0 } };
    },
    async fijar(pTxt, bTxt, body, ctx) {
      const p = v.parseId(pTxt, 'producto_id'); const b = v.parseId(bTxt, 'bodega_id');
      const minimo = v.validarMinimo(body);
      await existeEnRuta(p, b, ctx.cid);
      const cambio = await repo.transaccion(async (tx) => {
        const s = await tx.saldoBloqueado(p, b);     // si la pareja no tiene saldo, se crea con cantidad 0
        await tx.fijarMinimo(p, b, minimo);
        return { bodega_id: b, antes: s.cantidad_disponible, despues: s.cantidad_disponible, minimoAntes: s.stock_minimo, minimoDespues: minimo };
      });
      avisar([cambio], p, ctx.cid);
      return { status: 200, cuerpo: { mensaje: 'Stock minimo actualizado correctamente', minimo: { producto_id: p, bodega_id: b, stock_minimo: minimo, cantidad_disponible: cambio.despues } } };
    },
  };
  return { existencias, movimientos, minimos, esperarAvisos };
}
module.exports = { crearServicio, evaluarCruce };
