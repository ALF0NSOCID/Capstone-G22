#!/usr/bin/env python3
"""W1: sensibilidad a la topología con redes Waxman (solver_columnas_e2_v2.py).

Waxman ubica los nodos en el plano y enlaza con probabilidad decreciente en la distancia (red bidireccional conexa,
con agrupaciones locales y caminos largos). Se usa para ver si lo observado en Mulgen se mantiene.
Plan (30 corridas, 10 productos por nodo, alpha=0.2, beta=0.4, límite 300 s):
  - Tamaño: N en {200, 400, 800} x grado {4, 8} x semillas 1-3, con eta=25 (escalamiento y certificación).
  - Efecto de eta: N=400, grado {4, 8}, semillas 1-3, con eta en {0, 50} (junto con el eta=25 anterior).
Como la red es bidireccional y conexa, el filtro de productos sin camino (S2) elimina 0 productos por construcción.
Cada corrida agrega una fila a experimentos/waxman/corridas.csv; si se interrumpe, al relanzar salta las hechas.

Uso (desde la raíz del repo):
  python experimento_waxman.py prueba    # 1 corrida corta (N=200, grado 4, semilla 1, eta=25)
  python experimento_waxman.py correr    # las 30 corridas
  python experimento_waxman.py resumen   # tabla por celda y resumen.csv
"""
import argparse, statistics

import experimento_s6 as s6
from generador_waxman import generar_instancia, escribir_instancia

RAIZ = s6.RAIZ
SALIDA = RAIZ / "experimentos" / "waxman"; SALIDA.mkdir(parents=True, exist_ok=True)
INST = SALIDA / "instancias"; INST.mkdir(exist_ok=True)
LOGS = SALIDA / "logs"; LOGS.mkdir(exist_ok=True)
# Reutiliza correr_una / hechas / anexar de S6 apuntando a las carpetas de Waxman.
s6.CSV, s6.LOGS = SALIDA / "corridas.csv", LOGS
PPN, ALPHA, BETA = 10, 0.2, 0.4
TAMANOS, GRADOS, SEMILLAS = (200, 400, 800), (4, 8), (1, 2, 3)


def preparar(n, grado, semilla):
    nombre = f"w_n{n:04d}_g{grado:02d}_s{semilla:02d}"
    destino = INST / f"{nombre}.txt"
    if not destino.exists():
        grafo, arcos, comm = generar_instancia(nodos=n, productos=PPN * n, arcos_objetivo=grado * n,
                                               alpha=ALPHA, beta=BETA, semilla=semilla)
        escribir_instancia(destino, grafo, arcos, comm)
    return f"waxman_g{grado}_n{n}", nombre, destino


def plan():
    p = [(preparar(n, g, s), 25) for n in TAMANOS for g in GRADOS for s in SEMILLAS]
    p += [(preparar(400, g, s), e) for g in GRADOS for s in SEMILLAS for e in (0, 50)]
    return p


def correr(args):
    todo = plan(); ya = s6.hechas()
    pend = [(i, e) for (i, e) in todo if (i[1], e) not in ya]
    print(f"Waxman: {len(todo)} corridas en el plan, {len(pend)} pendientes. Límite {args.limite} s.", flush=True)
    for k, ((f, n, a), e) in enumerate(pend, 1):
        print(f"\n[{k}/{len(pend)}] {n}, eta={e}", flush=True)
        fila = s6.correr_una(f, n, a, e, args.limite); s6.anexar(fila)
        print(f"  -> {fila['certificacion']} | z={fila['z']} | gap={fila['gap_pct']} % | "
              f"iter={fila['iteraciones']} | cols={fila['columnas']} | {fila['tiempo_interno_s']} s", flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("modo", choices=["prueba", "correr", "resumen"])
    ap.add_argument("--limite", type=float, default=300)
    a = ap.parse_args()
    if a.modo == "prueba":
        f, n, arch = preparar(200, 4, 1)
        print(s6.correr_una(f, n, arch, 25, 120))
    elif a.modo == "correr":
        correr(a)
    else:
        s6.SALIDA = SALIDA
        s6.resumen(a)
