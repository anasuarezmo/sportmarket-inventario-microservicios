"""Consolidar estadisticas de Locust por ejecucion; no inventa resultados."""
import csv
import sys
from pathlib import Path

ruta = Path(sys.argv[1] if len(sys.argv)>1 else "pruebas/ana/resultados")
archivos = sorted(ruta.glob("[0-9]*_*_stats.csv"), key=lambda p:int(p.name.split('_',1)[0]))
if not archivos:
    raise SystemExit("No se encontraron CSV de Locust. Ejecuta primero ejecutar_15.sh")
resumen = []
for archivo in archivos:
    with archivo.open(encoding='utf-8-sig', newline='') as f:
        filas = list(csv.DictReader(f))
    fila = next((r for r in filas if r.get('Name') == 'Aggregated'), None)
    if fila is None:
        fila = next((r for r in filas if r.get('Request Count') not in ('', None)), {})
    partes = archivo.name.removesuffix('_stats.csv').split('_',1)
    nombre = partes[1]
    req = int(fila.get('Request Count') or 0)
    fallos = int(fila.get('Failure Count') or 0)
    p95 = fila.get('95%', '')
    porcentaje = 100*fallos/req if req else None
    resumen.append({
        'ejecucion':partes[0], 'escenario_perfil':nombre,
        'solicitudes':req, 'fallos':fallos,
        'errores_pct':f'{porcentaje:.2f}' if porcentaje is not None else '',
        'p95_ms':p95,
        'meta_errores_menor_1pct':'SI' if porcentaje is not None and porcentaje < 1 else 'NO',
        'meta_p95_menor_2000ms': 'SI' if p95 and float(p95) < 2000 else 'NO',
    })
salida=ruta/'resumen_15_pruebas.csv'
with salida.open('w',encoding='utf-8',newline='') as f:
    w=csv.DictWriter(f,fieldnames=resumen[0].keys())
    w.writeheader();w.writerows(resumen)
print(f'Resumen consolidado: {salida} ({len(resumen)} ejecuciones encontradas)')
for r in resumen:
 print(f"{r['ejecucion']}. {r['escenario_perfil']}: {r['solicitudes']} solicitudes, {r['errores_pct']}% fallos, p95={r['p95_ms']} ms")
