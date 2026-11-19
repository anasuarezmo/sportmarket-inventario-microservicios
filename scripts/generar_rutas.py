"""Regenera api-gateway/src/tablaRutas.js a partir de docs/entrega-2/openapi/*.yaml (x-roles).
Uso (desde la raiz del repo):  python scripts/generar_rutas.py
Requiere: pip install pyyaml"""
import yaml, glob, json, os
ROL = {'Administrador':'ADM','Responsable de inventario':'INV','Responsable de compras':'COM',
       'Operador de bodega':'BOD','Usuario de consulta':'CON','BOD y servicios internos':'BOD'}
SVC = [('/api/auth','usuarios'),('/api/usuarios','usuarios'),('/api/roles','usuarios'),
       ('/api/bodegas','bodegas'),('/api/productos','catalogo'),('/api/categorias','catalogo'),
       ('/api/inventario','inventario'),('/api/proveedores','compras'),('/api/compras','compras'),
       ('/api/devoluciones','devoluciones'),('/api/reportes','reportes'),('/api/alertas','reportes')]
out = []
for f in sorted(glob.glob('docs/entrega-2/openapi/*.yaml')):
    if f.endswith('gateway.yaml'): continue
    spec = yaml.safe_load(open(f, encoding='utf-8'))
    for p, ops in spec['paths'].items():
        if p.startswith('/api/interno'): continue   # los endpoints internos NO se exponen por el Gateway
        sv = [v for k, v in SVC if p == k or p.startswith(k + '/')][0]
        for m, o in ops.items():
            r = o['x-roles']
            if r == ['Pública']: acc, roles = 'publica', []
            elif r == ['Todos']: acc, roles = 'todos', []
            else: acc, roles = 'roles', [ROL[x] for x in r]
            out.append(dict(metodo=m.upper(), ruta=p, servicio=sv, acceso=acc, roles=roles))
with open('api-gateway/src/tablaRutas.js', 'w', encoding='utf-8', newline='\n') as fh:
    fh.write("// GENERADO desde docs/entrega-2/openapi/*.yaml con scripts/generar_rutas.py. No editar a mano.\n"
             "// acceso: 'publica' | 'todos' (cualquier autenticado) | 'roles'\n"
             "module.exports = " + json.dumps(out, indent=2, ensure_ascii=False) + ";\n")
print(len(out), 'rutas')
