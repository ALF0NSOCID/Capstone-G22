#!/usr/bin/env python3
"""Experimentos de realismo sobre la red chilena (referencia LP agregado por origen, HiGHS).
NO usa el solver del proyecto: sirve para decidir qué experimentos correr con E2 y como referencia.

Salidas en red_chile/experimentos/:
  estructura.csv        puentes y grado con red base, con cada candidato y con los 20
  candidatos_greedy.csv  agregado secuencial de candidatos (mejor z en cada paso)
  fallas_con_sin.csv     cada falla N-1 con y sin los 20 candidatos: demanda servida y z restante
Uso: python3 experimentos_chile.py [greedy|fallas|estructura|todo]
"""
import os, sys, json
from multiprocessing import Pool
import numpy as np, pandas as pd, networkx as nx
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from resolver_referencia import leer, resolver

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'experimentos'); os.makedirs(OUT, exist_ok=True)
nodos = pd.read_csv(os.path.join(ROOT, 'nodos.csv'), dtype={'cut': str})
enl = pd.read_csv(os.path.join(ROOT, 'enlaces.csv'))
N, _, PRODS = leer(os.path.join(ROOT, 'instancia_base.txt'))
BASE = enl[enl.capa != 'CANDIDATO']
CAND = enl[enl.capa == 'CANDIDATO']
DEM_TOTAL = sum(v for _, _, v in PRODS)


def arcos(df):
    a = []
    for r in df.itertuples():
        c = float(r.capacidad_gbps_por_sentido)
        a += [(r.origen, r.destino, c), (r.destino, r.origen, c)]
    return a


def grafo(df):
    G = nx.MultiGraph(); G.add_nodes_from(nodos.id); G.add_edges_from(zip(df.origen, df.destino)); return G


def pct_puentes(df):
    G = nx.Graph(); G.add_nodes_from(nodos.id); G.add_edges_from(zip(df.origen, df.destino))
    return 100 * len(list(nx.bridges(G))) / G.number_of_edges()


def z_de(df, prods=None):
    z, u, a2 = resolver(N, arcos(df), prods or PRODS)
    return z, u, a2


def _cand_z(args):
    ids_actuales, cid = args
    df = pd.concat([BASE, enl[enl.id.isin(list(ids_actuales) + [cid])]])
    return cid, z_de(df)[0]


def greedy(pasos=20):
    actuales, filas = [], []
    z0 = z_de(BASE)[0]
    filas.append(dict(paso=0, candidato_agregado='(base)', id_enlace=None, km_acum=0.0, z=round(z0, 4), mejora_acum_pct=0.0,
                      puentes_pct=round(pct_puentes(BASE), 1)))
    zprev = z0
    with Pool(2) as p:
        for k in range(1, pasos + 1):
            resto = [c for c in CAND.id if c not in actuales]
            res = p.map(_cand_z, [(tuple(actuales), c) for c in resto])
            # mejor z; en empate (meseta) se prefiere el candidato más corto
            km = dict(zip(CAND.id, CAND.km))
            cid, zk = min(res, key=lambda t: (round(t[1], 6), km[t[0]]))
            actuales.append(cid)
            df = pd.concat([BASE, enl[enl.id.isin(actuales)]])
            r = CAND[CAND.id == cid].iloc[0]
            filas.append(dict(paso=k, candidato_agregado=f'{r.origen_nombre} – {r.destino_nombre}', id_enlace=cid,
                              km_acum=round(sum(km[a] for a in actuales), 1), z=round(zk, 4),
                              mejora_acum_pct=round(100 * (z0 - zk) / z0, 2), puentes_pct=round(pct_puentes(df), 1)))
            print(filas[-1], flush=True)
            pd.DataFrame(filas).to_csv(os.path.join(OUT, 'candidatos_greedy.csv'), index=False)
    return filas


def _falla(args):
    eid, con_cand = args
    df = pd.concat([BASE, CAND]) if con_cand else BASE
    df = df[df.id != eid]
    G = nx.Graph(); G.add_nodes_from(nodos.id); G.add_edges_from(zip(df.origen, df.destino))
    comp = {v: i for i, cc in enumerate(nx.connected_components(G)) for v in cc}
    p2 = [(o, d, v) for o, d, v in PRODS if comp[o] == comp[d]]
    servida = sum(v for _, _, v in p2)
    z, u, a2 = z_de(df, p2)
    return eid, con_cand, 100 * servida / DEM_TOTAL, z


def fallas(parte=None, total=None):
    """Sin argumentos corre todo. Con parte/total (1..total) corre un trozo y guarda un CSV parcial;
    'unir' junta los parciales en fallas_con_sin.csv."""
    fl = pd.read_csv(os.path.join(ROOT, 'fallas.csv'))
    if parte is not None:
        ids = list(fl.id_enlace)
        ids = ids[parte - 1::total]
        fl = fl[fl.id_enlace.isin(ids)]
    tareas = [(e, c) for e in fl.id_enlace for c in (False, True)]
    with Pool(2) as p:
        res = p.map(_falla, tareas)
    d = {(e, c): (s, z) for e, c, s, z in res}
    filas = []
    for r in fl.itertuples():
        s0, z0 = d[(r.id_enlace, False)]; s1, z1 = d[(r.id_enlace, True)]
        filas.append(dict(id_enlace=r.id_enlace, capa=r.capa, origen=r.origen, destino=r.destino,
                          servida_sin_cand_pct=round(s0, 2), z_sin_cand=round(z0, 4),
                          servida_con_cand_pct=round(s1, 2), z_con_cand=round(z1, 4),
                          mejora_servida_pp=round(s1 - s0, 2)))
    out = pd.DataFrame(filas)
    nombre = 'fallas_con_sin.csv' if parte is None else f'_parcial_fallas_{parte}.csv'
    out.to_csv(os.path.join(OUT, nombre), index=False)


def unir_fallas():
    import glob
    df = pd.concat([pd.read_csv(f) for f in sorted(glob.glob(os.path.join(OUT, '_parcial_fallas_*.csv')))])
    df = df.sort_values('id_enlace'); df.to_csv(os.path.join(OUT, 'fallas_con_sin.csv'), index=False)
    os.makedirs(os.path.join(OUT, '_parciales'), exist_ok=True)
    for f in glob.glob(os.path.join(OUT, '_parcial_fallas_*.csv')):
        os.replace(f, os.path.join(OUT, '_parciales', os.path.basename(f)))
    print(len(df), 'fallas')


def estructura():
    filas = [dict(config='base', puentes_pct=round(pct_puentes(BASE), 1), enlaces=len(BASE))]
    todo = pd.concat([BASE, CAND]); filas.append(dict(config='base + 20 candidatos', puentes_pct=round(pct_puentes(todo), 1), enlaces=len(todo)))
    pd.DataFrame(filas).to_csv(os.path.join(OUT, 'estructura.csv'), index=False); print(pd.DataFrame(filas))


if __name__ == '__main__':
    modo = sys.argv[1] if len(sys.argv) > 1 else 'todo'
    if modo in ('estructura', 'todo'): estructura()
    if modo in ('greedy', 'todo'): greedy(int(sys.argv[2]) if len(sys.argv) > 2 else 20)
    if modo in ('fallas', 'todo'): fallas()
    if modo == 'fallas_parte': fallas(int(sys.argv[2]), int(sys.argv[3]))
    if modo == 'unir': unir_fallas()
