#!/usr/bin/env python3
"""Compara tres instancias Waxman existentes de la semilla 1010.

Por defecto lee los logs históricos. --repetir ejecuta E3 en las mismas
instancias y guarda logs nuevos; no genera redes ni modifica las baterías.
"""
import argparse
import csv
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import signal
import subprocess
import sys
import time
import webbrowser

CASOS = [
    ("Local", "local_extrema"),
    ("Backbone x1", "local_backbone"),
    ("Backbone x10", "local_backbone_x10"),
]


def extraer(texto):
    def ultimo(patron, tipo=float):
        valores = re.findall(patron, texto, re.M)
        return tipo(valores[-1]) if valores else None
    etapas = re.findall(r"maestro=([0-9.]+)s \| pricing=([0-9.]+)s", texto)
    total = ultimo(r"Tiempo total:\s*([0-9.]+)")
    maestro = sum(float(a) for a, _ in etapas)
    pricing = sum(float(b) for _, b in etapas)
    estado = ("optimo" if "Solución óptima certificada" in texto else
              "brecha_1pct" if "error relativo certificado" in texto else
              "sin_certificacion_o_incompleto")
    return dict(tiempo_total_s=total, maestro_s=round(maestro, 3),
                pricing_columnas_s=round(pricing, 3),
                maestro_pct=round(100*maestro/total, 2) if total else None,
                iteraciones=ultimo(r"Iteraciones:\s*(\d+)", int),
                columnas=ultimo(r"Columnas:\s*(\d+)", int),
                etapas_registradas=len(etapas), estado=estado)


def ejecutar(repo, instancia, log, limite):
    env = dict(os.environ, ARCHIVO_INSTANCIA=str(instancia),
               E2_LIMITE_TIEMPO=str(limite), E2_ETA="25", E2_TOLERANCIA="1e-7",
               PYTHONDONTWRITEBYTECODE="1", PYTHONUNBUFFERED="1")
    inicio = time.perf_counter()
    with log.open("w", encoding="utf-8") as salida:
        p = subprocess.Popen([sys.executable, str(repo/"compat/solver_columnas_e2_v2.py")],
                             cwd=repo, env=env, stdout=salida,
                             stderr=subprocess.STDOUT, start_new_session=True)
        def matar():
            try:
                os.killpg(p.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            p.wait()
        try:
            p.wait(timeout=limite+30)
        except subprocess.TimeoutExpired:
            matar()
            raise RuntimeError(f"Se alcanzó el límite externo. Log parcial: {log}")
        except BaseException:
            matar()
            raise
    if p.returncode:
        raise RuntimeError(f"E3 terminó con código {p.returncode}. Revisar {log}")
    return round(time.perf_counter()-inicio, 4)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo", type=Path, default=Path(__file__).resolve().parent)
    ap.add_argument("--repetir", action="store_true")
    ap.add_argument("--ver-redes", action="store_true")
    ap.add_argument("--limite", type=float, default=180)
    a = ap.parse_args()
    if a.limite <= 0:
        ap.error("El límite debe ser positivo.")
    repo = a.repo.expanduser().resolve()
    raiz = repo/"experimentos"/"waxman_formal"
    for _, caso in CASOS:
        for nombre in ["instancia.txt", "solver.log"]:
            if not (raiz/(caso+"_s1010")/nombre).is_file():
                raise RuntimeError(f"Falta {raiz/(caso+'_s1010')/nombre}")
    destino = None
    if a.repetir:
        destino = repo/"experimentos"/("perfil_waxman_"+datetime.now().strftime("%Y%m%d_%H%M%S_%f"))
        destino.mkdir()
        mapa = json.loads((repo/"docs/entradas_compatibles.json").read_text())
        fuente = repo/mapa.get("solver_columnas_e2_v2.py", "solver_columnas_e2_v2.py")
        (destino/"protocolo.json").write_text(json.dumps(dict(
            semilla=1010, solver="E3", archivo_solver="solver_columnas_e2_v2.py",
            python=sys.executable, plataforma=platform.platform(), limite_interno_s=a.limite,
            casos=[c for _, c in CASOS],
            fuente_sha256=hashlib.sha256(fuente.read_bytes()).hexdigest(),
            medicion="maestro y pricing+columnas: sumas de los tiempos redondeados del log"), indent=2))
        print(f"Nuevos registros: {destino}", flush=True)
    filas = []
    for etiqueta, caso in CASOS:
        carpeta = raiz/(caso+"_s1010")
        if a.ver_redes:
            imagen = carpeta/"red.png"
            if imagen.exists():
                webbrowser.open(imagen.as_uri())
        log = destino/(caso+".log") if destino else carpeta/"solver.log"
        pared = None
        if a.repetir:
            print(f"Resolviendo {etiqueta}, semilla 1010...", flush=True)
            pared = ejecutar(repo, carpeta/"instancia.txt", log, a.limite)
        datos = extraer(log.read_text(errors="replace"))
        datos.update(caso=etiqueta, semilla=1010, log=str(log), tiempo_proceso_s=pared,
                     instancia_sha256=hashlib.sha256((carpeta/"instancia.txt").read_bytes()).hexdigest())
        filas.append(datos)
        if destino:
            with (destino/"resumen.csv").open("w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=list(filas[0]))
                w.writeheader()
                w.writerows(filas)
    print("\nMisma semilla. N=400, A=1.600, K=10.000. Solver E3.")
    print(f"{'Red':<16} {'Total s':>9} {'Maestro s':>11} {'Maestro %':>11} {'Pricing+cols s':>16} {'Iter.':>7} {'Columnas':>11}")
    for r in filas:
        fmt = lambda v: f"{v:.2f}" if v is not None else "parcial"
        print(f"{r['caso']:<16} {fmt(r['tiempo_total_s']):>9} {r['maestro_s']:>11.2f} {fmt(r['maestro_pct']):>11} {r['pricing_columnas_s']:>16.2f} {str(r['iteraciones']):>7} {str(r['columnas']):>11}")
    print("\nPricing+cols incluye caminos mínimos, cálculo de cota y agregado de columnas.")
    print("Los tiempos por etapa son aproximados: el log redondea cada iteración a centésimas.")
    print("Son tres casos elegidos para diagnóstico; no representan el promedio de cada familia.")
    if destino:
        print(f"Resultado: {destino/'resumen.csv'}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrumpido; los registros ya escritos se conservan.", file=sys.stderr)
        raise SystemExit(130)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        raise SystemExit(1)
