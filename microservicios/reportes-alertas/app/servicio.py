"""Reglas de negocio: alertas (se guardan) e informes (se calculan al consultar, con cache corto)."""
from datetime import datetime, timezone

from . import validaciones as v
from .cache import Cache
from .errores import ErrorApi, no_encontrado

TIPOS = ("ENTRADA", "SALIDA", "AJUSTE", "TRASLADO")


def _ahora():
    return datetime.now(timezone.utc)


def _iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def crear_servicio(repo, clientes, config, ahora=_ahora, cache=None):
    cache = cache or Cache(config.get("cache_ttl", 30))

    # ---------- datos de otros servicios (con cache) ----------
    def existencias(cid, bodega_id=None):
        return cache.obtener(("existencias", bodega_id), lambda: clientes["existencias"](cid, bodega_id))

    def productos(cid, categoria_id=None):
        return cache.obtener(("productos", categoria_id), lambda: clientes["productos"](cid, categoria_id))

    def salidas(desde, hasta, cid):
        return cache.obtener(("salidas", desde, hasta), lambda: clientes["salidas"](desde.isoformat(), hasta.isoformat(), cid))

    def movimientos(desde, hasta, cid):
        return cache.obtener(("movs", desde, hasta), lambda: clientes["movimientos"](desde.isoformat(), hasta.isoformat(), cid))

    def respuesta(cuerpo):
        return {"status": 200, "cuerpo": {"generado_en": _iso(ahora()), **cuerpo}}

    # ---------- informes ----------
    def _inventario(f, cid):
        prods = {p["id"]: p for p in productos(cid, f["categoria_id"])}
        filas = []
        for s in existencias(cid, f["bodega_id"]):
            p = prods.get(s["producto_id"])
            if f["categoria_id"] is not None and p is None:
                continue  # producto de otra categoria
            filas.append({
                "producto_id": s["producto_id"],
                "codigo_producto": p and p.get("codigo_producto"),
                "nombre_producto": p and p.get("nombre_producto"),
                "bodega_id": s["bodega_id"],
                "cantidad_disponible": s["cantidad_disponible"],
            })
        filas.sort(key=lambda x: (x["producto_id"], x["bodega_id"]))
        return filas

    def inventario(q, ctx):
        f = v.filtros_inventario(q)
        filas = _inventario(f, ctx["cid"])
        return respuesta({"items": filas, "total": len(filas)})

    def _valorizacion(categoria_id, cid):
        prods = {p["id"]: p for p in productos(cid, categoria_id)}
        por_producto = {}
        for s in existencias(cid):
            if s["producto_id"] in prods:
                por_producto[s["producto_id"]] = por_producto.get(s["producto_id"], 0) + s["cantidad_disponible"]
        items = []
        for pid in sorted(por_producto):
            p = prods[pid]
            precio = p.get("precio_venta") or 0
            items.append({
                "producto_id": pid, "codigo_producto": p.get("codigo_producto"), "nombre_producto": p.get("nombre_producto"),
                "cantidad_disponible": por_producto[pid], "precio_venta": precio, "valor": round(por_producto[pid] * precio, 2),
            })
        return items, round(sum(i["valor"] for i in items), 2)

    def valorizacion(q, ctx):
        f = v.filtros_valorizacion(q)
        items, total = _valorizacion(f["categoria_id"], ctx["cid"])
        return respuesta({
            "descripcion": "Valor a precio de venta del inventario (no es costo contable)",
            "items": items, "valor_total": total,
        })

    def _rotacion(desde, hasta, limite, cid):
        """Solo cuentan las SALIDAS; los traslados no son demanda. Menor rotacion incluye productos activos sin salidas."""
        prods = {p["id"]: p for p in productos(cid)}
        unidades = {}
        for m in salidas(desde, hasta, cid):
            unidades[m["producto_id"]] = unidades.get(m["producto_id"], 0) + m["cantidad_movimiento"]

        def fila(pid, u):
            p = prods.get(pid) or {}
            return {"producto_id": pid, "codigo_producto": p.get("codigo_producto"),
                    "nombre_producto": p.get("nombre_producto"), "unidades_salida": u}

        mayor = sorted(unidades.items(), key=lambda kv: (-kv[1], kv[0]))[:limite]
        activos = [pid for pid, p in prods.items() if p.get("producto_activo", True)]
        menor = sorted(((pid, unidades.get(pid, 0)) for pid in activos), key=lambda kv: (kv[1], kv[0]))[:limite]
        return [fila(*x) for x in mayor], [fila(*x) for x in menor]

    def rotacion(q, ctx):
        f = v.filtros_rotacion(q, ahora().date())
        mayor, menor = _rotacion(f["desde"], f["hasta"], f["limite"], ctx["cid"])
        return respuesta({"desde": f["desde"].isoformat(), "hasta": f["hasta"].isoformat(), "limite": f["limite"],
                          "mayor_rotacion": mayor, "menor_rotacion": menor})

    def resumen_movimientos(q, ctx):
        desde, hasta = v.periodo(q, ahora().date())
        resumen = {t: {"movimientos": 0, "unidades": 0} for t in TIPOS}
        for m in movimientos(desde, hasta, ctx["cid"]):
            r = resumen.get(m["tipo_movimiento"])
            if r is not None:
                r["movimientos"] += 1
                r["unidades"] += m["cantidad_movimiento"]
        return respuesta({"desde": desde.isoformat(), "hasta": hasta.isoformat(), "resumen": resumen,
                          "nota": "Los traslados se muestran aparte y no cuentan como salidas del negocio"})

    def dashboard(q, ctx):
        cid = ctx["cid"]
        _, valor_total = _valorizacion(None, cid)
        total_por_producto = {}
        for s in existencias(cid):
            total_por_producto[s["producto_id"]] = total_por_producto.get(s["producto_id"], 0) + s["cantidad_disponible"]
        quiebre = sum(1 for p in productos(cid) if p.get("producto_activo", True) and total_por_producto.get(p["id"], 0) == 0)
        hasta = ahora().date()
        desde = hasta.fromordinal(hasta.toordinal() - v.DIAS_POR_DEFECTO)
        mayor, menor = _rotacion(desde, hasta, 3, cid)
        quitar = lambda xs: [{k: x[k] for k in ("producto_id", "nombre_producto", "unidades_salida")} for x in xs]
        return respuesta({
            "valor_total_inventario": valor_total, "productos_en_quiebre": quiebre,
            "alertas_activas": repo.contar_activas(),
            "mayor_rotacion": quitar(mayor), "menor_rotacion": quitar(menor),
        })

    # ---------- alertas ----------
    def listar_alertas(q):
        f = v.filtros_alertas(q)
        filas, total = repo.listar(f)
        return {"status": 200, "cuerpo": {"items": filas, "total": total, "page": f["page"], "limit": f["limit"]}}

    def atender(id_txt, body, ctx):
        id_ = v.parse_id(id_txt, "id")
        v.cambio_estado(body)
        res, alerta = repo.atender(id_, ctx.get("usuario_id"))
        if res == "no_existe":
            raise no_encontrado("Alerta")
        if res == "ya_atendida":
            raise ErrorApi(409, "ALERTA_YA_ATENDIDA", "La alerta ya estaba atendida", [{"campo": "estado_alerta", "error": "Ya es ATENDIDA"}])
        return {"status": 200, "cuerpo": {"mensaje": "Alerta atendida correctamente", "alerta": alerta}}

    def recibir_aviso(body):
        a = v.aviso_stock(body)
        if a["evento"] == "STOCK_BAJO":
            alerta, creada = repo.crear_activa(a["producto_id"], a["bodega_id"], a["cantidad_disponible"], a["stock_minimo"])
            if creada:
                return {"status": 201, "cuerpo": {"mensaje": "Alerta registrada correctamente", "alerta": alerta}}
            return {"status": 200, "cuerpo": {"mensaje": "Ya existe una alerta activa para el producto y la bodega", "alerta": alerta}}
        alerta = repo.cerrar_activa(a["producto_id"], a["bodega_id"])
        if alerta is None:
            return {"status": 200, "cuerpo": {"mensaje": "No habia alerta activa; sin cambios"}}
        return {"status": 200, "cuerpo": {"mensaje": "Alerta cerrada: el stock se recupero", "alerta": alerta}}

    return {
        "inventario": inventario, "valorizacion": valorizacion, "rotacion": rotacion, "movimientos": resumen_movimientos,
        "dashboard": dashboard, "listar_alertas": listar_alertas, "atender": atender, "recibir_aviso": recibir_aviso,
    }
