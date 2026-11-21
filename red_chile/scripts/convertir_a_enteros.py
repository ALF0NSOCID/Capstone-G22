#!/usr/bin/env python3
"""Convierte las instancias chilenas (demandas decimales) al formato entero que lee lector.py.

Escala capacidades y demandas por la misma potencia de diez (z* no cambia), exacta con Decimal;
si algún valor no es exacto con 1e6, sube la potencia. Además arma variantes con enlaces candidatos.
Salida: red_chile/instancias_enteras/*.txt  y  referencias_instancias_enteras.csv (z* de referencia, HiGHS).
Uso: python3 red_chile/scripts/convertir_a_enteros.py
Luego, desde la raíz:  python ejecutar_instancia.py red_chile/instancias_enteras/<archivo>.txt solver_columnas
"""
import os, sys, csv
from decimal import Decimal
import pandas as pd

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
from resolver_referencia import leer, resolver

ROOT = os.path.dirname(AQUI)
OUT = os.path.join(ROOT, 'instancias_enteras'); os.makedirs(OUT, exist_ok=True)
enl = pd.read_csv(os.path.join(ROOT, 'enlaces.csv'))
CAND = enl[enl.capa == 'CANDIDATO']
ID_GREEDY4 = [292, 305, 291, 293]   # mejores 4 candidatos según experimentos/candidatos_greedy.csv


def leer_texto(ruta):
    with open(ruta) as fh:
        n, m, K = map(int, fh.readline().split())
        arcos = [fh.readline().split() for _ in range(m)]
        bal = [fh.readline().split() for _ in range(2 * K)]
    return n, arcos, bal


def a_entero(valor, escala):
    x = Decimal(valor) * escala
    if x != x.to_integral_value():
        raise ValueError(f'{valor} no es exacto con escala {escala}')
    return int(x)


def escribir(nombre, n, arcos, bal, K):
    escala = Decimal(10) ** 6
    while True:
        try:
            filas_arcos = [(o, d, a_entero(c, escala)) for o, d, _, c, _ in arcos]
            filas_bal = [(k, nodo, a_entero(v, escala)) for k, nodo, v in bal]
            break
        except ValueError:
            escala *= 10
    ruta = os.path.join(OUT, nombre + '.txt')
    with open(ruta, 'w') as fh:
        fh.write(f'{n} {len(filas_arcos)} {K}\n')
        for o, d, c in filas_arcos:
            fh.write(f'{o} {d} 0 {c} 0\n')
        for k, nodo, v in filas_bal:
            fh.write(f'{k} {nodo} {v}\n')
    return ruta, int(escala)


def arcos_candidatos(ids):
    a = []
    for r in CAND[CAND.id.isin(ids)].itertuples():
        c = str(int(r.capacidad_gbps_por_sentido))
        a += [[str(r.origen), str(r.destino), '1', c, '0'], [str(r.destino), str(r.origen), '1', c, '0']]
    return a


casos = []   # (nombre, archivo_origen, ids_candidatos)
esc = os.path.join(ROOT, 'escenarios')
casos.append(('base', os.path.join(ROOT, 'instancia_base.txt'), []))
for e in ['uniforme_+25', 'uniforme_+50', 'uniforme_+100', 'hotspot_antofagasta_+200', 'hotspot_aysen_+200']:
    casos.append((e.replace('+', 'mas'), os.path.join(esc, f'instancia_{e}.txt'), []))
todos = list(CAND.id)
casos.append(('base_mas_4_candidatos', os.path.join(ROOT, 'instancia_base.txt'), ID_GREEDY4))
casos.append(('base_mas_20_candidatos', os.path.join(ROOT, 'instancia_base.txt'), todos))
casos.append(('hotspot_aysen_mas200_mas_20_candidatos', os.path.join(esc, 'instancia_hotspot_aysen_+200.txt'), todos))
casos.append(('uniforme_mas100_mas_20_candidatos', os.path.join(esc, 'instancia_uniforme_+100.txt'), todos))

filas = []
for nombre, origen, ids in casos:
    n, arcos, bal = leer_texto(origen)
    arcos = arcos + arcos_candidatos(ids)
    K = len(bal) // 2
    ruta, escala = escribir(nombre, n, arcos, bal, K)
    # La referencia se calcula con los valores reescalados a Gbps: con capacidades enteras de 1e8-1e10 HiGHS
    # pierde precisión (daba 0,437 en vez de 0,3958 con los 20 candidatos).
    N, a, p = leer(ruta)
    a = [(o, d, c / escala) for o, d, c in a]; p = [(o, d, v / escala) for o, d, v in p]
    z, u, a2 = resolver(N, a, p)
    filas.append(dict(instancia=nombre, archivo=os.path.relpath(ruta, ROOT), arcos=len(arcos), escala=escala, z_ref_highs=round(z, 6)))
    print(filas[-1], flush=True)
pd.DataFrame(filas).to_csv(os.path.join(ROOT, 'referencias_instancias_enteras.csv'), index=False)
