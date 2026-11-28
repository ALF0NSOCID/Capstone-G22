"""Batería formal E3: cinco familias Waxman, acceso 60%/15%, 30 semillas nuevas.

python3 experimento_waxman.py plan
python3 experimento_waxman.py correr
python3 experimento_waxman.py correr --semillas 1001 1002
python3 experimento_waxman.py resumen
"""
import argparse
import csv
import hashlib
import json
import platform
import random
import statistics
import subprocess
import sys
from pathlib import Path
from compatibilidad import archivo_fuente

import explorar_waxman as explorador

RAIZ = Path(__file__).resolve().parent
CASOS = {nombre: dict(parametros) for nombre, parametros in explorador.CASOS.items()}
for nombre in ("local_backbone", "local_backbone_x10"):
    CASOS[nombre].update(prob_acceso_backbone=0.60, prob_segundo_hub=0.15)
# Reutilizar el worker sin alterar los casos exploratorios al importar este módulo.


def protocolo(limite, generacion):
    return dict(solver="E3", nodos=400, arcos=1600, productos=10000,
                limite_s=limite, preparacion_s=generacion, eta=25, tolerancia=1e-7,
                casos=CASOS, secuencias_independientes=True,
                sha256={n: hashlib.sha256(archivo_fuente(RAIZ / n).read_bytes()).hexdigest()
                        for n in ["generador_waxman.py", "solver_columnas_e2_v2.py",
                                  "explorar_waxman.py", "analisis_red.py"]})


def filas_guardadas(salida):
    filas = []
    for archivo in sorted(salida.glob("*/estado.json")):
        r = json.loads(archivo.read_text())
        caso, semilla = archivo.parent.name.rsplit("_s", 1)
        filas.append(dict(caso=caso, semilla=int(semilla), **r))
    return filas


def guardar_tablas(salida):
    filas = filas_guardadas(salida)
    if not filas:
        print("No hay resultados guardados.")
        return
    claves = ["caso", "semilla"] + sorted(set().union(*(r.keys() for r in filas)) - {"caso", "semilla"})
    with (salida / "corridas.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=claves); w.writeheader(); w.writerows(filas)
    resumen = []
    for caso in CASOS:
        rs = [r for r in filas if r['caso'] == caso]
        if not rs:
            continue
        ok = [r for r in rs if r['estado'] in ('optimo', 'brecha_1pct')]
        tiempos = [float(r['interno_s']) for r in ok if r.get('interno_s')]
        fila = dict(caso=caso, corridas=len(rs), certificadas=len(ok),
                    mediana_certificadas_s=statistics.median(tiempos) if tiempos else '',
                    max_certificadas_s=max(tiempos) if tiempos else '')
        resumen.append(fila)
        print(f"{caso}: {len(ok)}/{len(rs)} certificadas; mediana certificadas {fila['mediana_certificadas_s']} s")
    with (salida / "resumen.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(resumen[0])); w.writeheader(); w.writerows(resumen)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('modo', choices=['plan', 'correr', 'resumen'])
    ap.add_argument('--semillas', type=int, nargs='+', default=list(range(1001, 1031)))
    ap.add_argument('--casos', nargs='+', choices=CASOS, default=list(CASOS))
    ap.add_argument('--salida', type=Path, default=RAIZ/'experimentos/waxman_formal')
    ap.add_argument('--limite', type=float, default=120)
    ap.add_argument('--generacion-seg', type=float, default=60)
    a = ap.parse_args()
    if min(a.semillas) < 1 or len(set(a.semillas)) != len(a.semillas) or min(a.limite, a.generacion_seg) <= 0:
        ap.error('Semillas positivas sin duplicados y límites positivos.')
    salida = a.salida.expanduser().resolve()
    if a.modo == 'resumen':
        guardar_tablas(salida)
        return
    meta = protocolo(a.limite, a.generacion_seg)
    ficha = salida/'protocolo.json'
    if ficha.exists() and json.loads(ficha.read_text()) != meta:
        if a.modo != 'plan':
            ap.error('El protocolo de esa carpeta es distinto. Use una --salida nueva para no mezclar resultados.')
        print('Protocolo histórico: consulta de solo lectura; para repetir use --salida nueva.')
    plan = []
    for s in a.semillas:
        orden = list(a.casos)
        random.Random(f'{s}:orden_formal').shuffle(orden)
        plan.extend((s, c) for c in orden)
    pendientes = [(s, c) for s, c in plan if not (salida/f'{c}_s{s}'/'estado.json').exists()]
    print(f"Waxman formal: {len(plan)} corridas, {len(pendientes)} pendientes.")
    print(f"400 nodos, 1600 arcos, 10000 productos; acceso 60%/15%; límite {a.limite:g} s.")
    print(f"Semillas: {a.semillas}; salida: {salida}")
    if a.modo == 'plan':
        return
    salida.mkdir(parents=True, exist_ok=True)
    ficha.write_text(json.dumps(meta, indent=2), encoding='utf-8')
    entorno = dict(python=sys.version, plataforma=platform.platform(), semillas=a.semillas)
    (salida/'ultima_ejecucion.json').write_text(json.dumps(entorno, indent=2), encoding='utf-8')
    for i, (s, c) in enumerate(pendientes, 1):
        carpeta = salida/f'{c}_s{s}'; carpeta.mkdir(exist_ok=True)
        print(f"[{i}/{len(pendientes)}] {c}, semilla {s}", flush=True)
        with (carpeta/'generacion.log').open('w') as log:
            try:
                p = subprocess.run([sys.executable, str(Path(__entry_file__).resolve()), '_worker',
                                    str(RAIZ), str(carpeta), c, str(s)],
                                   stdout=log, stderr=subprocess.STDOUT, timeout=a.generacion_seg)
                estado = 'generada' if p.returncode == 0 else 'error_generacion'
            except subprocess.TimeoutExpired:
                estado = 'timeout_preparacion'
        resultado = dict(estado=estado)
        if estado == 'generada':
            resultado.update(explorador.resolver(RAIZ, carpeta, a.limite))
        (carpeta/'estado.json').write_text(json.dumps(resultado, indent=2), encoding='utf-8')
        print(resultado, flush=True)
        guardar_tablas(salida)
    print(f"Resultados: {salida}")


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '_worker':
        explorador.CASOS = CASOS
        explorador.worker(Path(sys.argv[2]), Path(sys.argv[3]), sys.argv[4], int(sys.argv[5]))
    else:
        main()
