#!/usr/bin/env python3
"""Red chilena extendida: base + 20 candidatos + N enlaces sintéticos adicionales (N = 50, 100, 200).

Regla (SUPUESTO, solo para probar el solver en una red con mucho ruteo): se recorren los pares de nodos
del más cercano al más lejano (distancia geodésica) y se agrega el enlace si el par no está conectado,
si ambos nodos tienen menos de 3 enlaces extra y si la distancia es <= 250 km. Capacidad 800 Gbps
(como un ramal FON), km = geodésica × 1,319. No son enlaces propuestos: es una prueba de esfuerzo.

Salidas:
  red_chile/experimentos/red_extendida/enlaces_extra_<N>.csv
  red_chile/instancias_enteras/extendida_<N>.txt   (kbps enteros, listo para ejecutar_instancia.py)
  red_chile/experimentos/red_extendida/resumen.csv (puentes, arcos y z de referencia HiGHS)
"""
import math, os, sys
import pandas as pd, networkx as nx
AQUI = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, AQUI)
import experimentos_chile_e2 as X   # reutiliza lectura de datos, escritura de instancias y referencia

ROOT = X.ROOT
SAL = os.path.join(ROOT, 'experimentos', 'red_extendida'); os.makedirs(SAL, exist_ok=True)
INST = os.path.join(ROOT, 'instancias_enteras')
LL = {r.id: (r.lat, r.lon) for r in X.nodos.itertuples()}
NOM = X.NOMBRE

def km(a, b):
    (la1, lo1), (la2, lo2) = LL[a], LL[b]
    p1, p2, dl = math.radians(la1), math.radians(la2), math.radians(lo2 - lo1)
    h = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6371 * math.asin(math.sqrt(h))

def generar_extra(n_extra, max_por_nodo=3, max_km=250):
    existentes = {frozenset((r.origen, r.destino)) for r in pd.concat([X.BASE, X.CAND]).itertuples()}
    ids = sorted(LL); pares = sorted((km(a, b), a, b) for i, a in enumerate(ids) for b in ids[i + 1:])
    grado, filas = {v: 0 for v in ids}, []
    for d, a, b in pares:
        if len(filas) == n_extra or d > max_km:
            break
        if frozenset((a, b)) in existentes or grado[a] >= max_por_nodo or grado[b] >= max_por_nodo:
            continue
        grado[a] += 1; grado[b] += 1
        filas.append(dict(id=10000 + len(filas), origen=a, destino=b, origen_nombre=NOM[a], destino_nombre=NOM[b],
                          capa='EXTRA', km=round(d * 1.319, 1), capacidad_gbps_por_sentido=800))
    return pd.DataFrame(filas)

def pct_puentes(df):
    G = nx.Graph(); G.add_nodes_from(LL); G.add_edges_from(zip(df.origen, df.destino))
    return 100 * len(list(nx.bridges(G))) / G.number_of_edges()

if __name__ == '__main__':
    resumen = []
    for n in (0, 50, 100, 200):
        extra = generar_extra(n) if n else None
        if n:
            extra.to_csv(os.path.join(SAL, f'enlaces_extra_{n}.csv'), index=False)
        red = pd.concat([X.BASE, X.CAND] + ([extra] if n else []))
        arcos = X.enlaces_a_arcos(red); prods = X.productos_conectados(arcos)
        ruta = X.escribir(f'extendida_{n}', arcos, prods)
        destino = os.path.join(INST, f"extendida_{n}.txt"); import shutil; shutil.copyfile(ruta, destino)
        z = X.correr_ref(arcos, prods)
        resumen.append(dict(enlaces_extra=n, enlaces_totales=len(red), arcos_dirigidos=len(arcos),
                            puentes_pct=round(pct_puentes(red), 1), km_extra=round(extra.km.sum(), 0) if n else 0,
                            z_ref_highs=round(z, 6), instancia=os.path.relpath(destino, ROOT)))
        print(resumen[-1], flush=True)
    pd.DataFrame(resumen).to_csv(os.path.join(SAL, 'resumen.csv'), index=False)
