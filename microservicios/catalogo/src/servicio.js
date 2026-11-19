// Reglas de negocio del Catalogo. Recibe el repositorio por parametro (asi se prueba sin base de datos).
const { ErrorApi, noEncontrado } = require('./errores');
const v = require('./validaciones');

function crearServicio(repo) {
  const pagina = (r, f) => ({ datos: r.filas, pagina: f.page, limite: f.limit, total: r.total });

  async function categoriaActivaOFalla(id, campo) {
    const c = await repo.categorias.obtener(id);
    if (!c || !c.categoria_activa) {
      throw new ErrorApi(422, 'CATEGORIA_INVALIDA', 'La categoria no existe o esta inactiva', [{ campo, error: `La categoria ${id} no existe o esta inactiva` }]);
    }
    return c;
  }
  async function codigoLibreOFalla(codigo, idActual) {
    const otro = await repo.productos.obtenerPorCodigo(codigo);
    if (otro && otro.id !== idActual) {
      throw new ErrorApi(409, 'CODIGO_DUPLICADO', 'Ya existe un producto con ese codigo', [{ campo: 'codigo_producto', error: `El codigo ${codigo} ya esta en uso` }]);
    }
  }

  const productos = {
    async listar(q) { const f = v.filtrosProductos(q); return { status: 200, cuerpo: pagina(await repo.productos.listar(f), f) }; },
    async obtener(idTxt) {
      const p = await repo.productos.obtener(v.parseId(idTxt));
      if (!p) throw noEncontrado('Producto');
      return { status: 200, cuerpo: p };
    },
    async crear(body) {
      const datos = v.validarProducto(body, true);
      await categoriaActivaOFalla(datos.categoria_id, 'categoria_id');
      await codigoLibreOFalla(datos.codigo_producto);
      const id = await repo.productos.insertar(datos);
      return { status: 201, cuerpo: { mensaje: 'Producto registrado correctamente', producto: await repo.productos.obtener(id) } };
    },
    async actualizar(idTxt, body) {
      const id = v.parseId(idTxt);
      if (!(await repo.productos.obtener(id))) throw noEncontrado('Producto');
      const datos = v.validarProducto(body, false);
      if (datos.categoria_id !== undefined) await categoriaActivaOFalla(datos.categoria_id, 'categoria_id');
      if (datos.codigo_producto !== undefined) await codigoLibreOFalla(datos.codigo_producto, id);
      await repo.productos.actualizar(id, datos);
      return { status: 200, cuerpo: { mensaje: 'Producto actualizado correctamente', producto: await repo.productos.obtener(id) } };
    },
    async cambiarEstado(idTxt, body) {
      const id = v.parseId(idTxt);
      const activo = v.validarEstado(body, 'producto_activo');
      if (!(await repo.productos.obtener(id))) throw noEncontrado('Producto');
      await repo.productos.actualizar(id, { producto_activo: activo });
      return { status: 200, cuerpo: { mensaje: activo ? 'Producto activado' : 'Producto desactivado', producto: await repo.productos.obtener(id) } };
    },
  };

  async function padreValidoOFalla(padreId, idPropio) {
    if (padreId === null || padreId === undefined) return;
    if (idPropio !== undefined && padreId === idPropio) {
      throw new ErrorApi(422, 'CATEGORIA_PADRE_INVALIDA', 'Una categoria no puede ser su propia categoria padre', [{ campo: 'categoria_padre_id', error: 'Igual al id de la categoria' }]);
    }
    const padre = await categoriaActivaOFalla(padreId, 'categoria_padre_id');
    // evita ciclos: ninguna ancestro de la categoria padre puede ser la categoria que se edita
    let actual = padre;
    while (idPropio !== undefined && actual && actual.categoria_padre_id) {
      if (actual.categoria_padre_id === idPropio) {
        throw new ErrorApi(422, 'CATEGORIA_PADRE_INVALIDA', 'La jerarquia de categorias no puede formar un ciclo', [{ campo: 'categoria_padre_id', error: 'Formaria un ciclo' }]);
      }
      actual = await repo.categorias.obtener(actual.categoria_padre_id);
    }
  }

  const categorias = {
    async listar(q) { const f = v.filtrosCategorias(q); return { status: 200, cuerpo: pagina(await repo.categorias.listar(f), f) }; },
    async obtener(idTxt) {
      const c = await repo.categorias.obtener(v.parseId(idTxt));
      if (!c) throw noEncontrado('Categoria');
      return { status: 200, cuerpo: c };
    },
    async crear(body) {
      const datos = v.validarCategoria(body, true);
      await padreValidoOFalla(datos.categoria_padre_id);
      const id = await repo.categorias.insertar(datos);
      return { status: 201, cuerpo: { mensaje: 'Categoria registrada correctamente', categoria: await repo.categorias.obtener(id) } };
    },
    async actualizar(idTxt, body) {
      const id = v.parseId(idTxt);
      if (!(await repo.categorias.obtener(id))) throw noEncontrado('Categoria');
      const datos = v.validarCategoria(body, false);
      await padreValidoOFalla(datos.categoria_padre_id, id);
      await repo.categorias.actualizar(id, datos);
      return { status: 200, cuerpo: { mensaje: 'Categoria actualizada correctamente', categoria: await repo.categorias.obtener(id) } };
    },
    async cambiarEstado(idTxt, body) {
      const id = v.parseId(idTxt);
      const activa = v.validarEstado(body, 'categoria_activa');
      if (!(await repo.categorias.obtener(id))) throw noEncontrado('Categoria');
      await repo.categorias.actualizar(id, { categoria_activa: activa });
      return { status: 200, cuerpo: { mensaje: activa ? 'Categoria activada' : 'Categoria desactivada', categoria: await repo.categorias.obtener(id) } };
    },
  };
  return { productos, categorias };
}
module.exports = { crearServicio };
