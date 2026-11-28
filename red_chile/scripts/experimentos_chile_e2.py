#!/usr/bin/env python3
"""Experimentos de la red chilena resueltos con el solver del proyecto (solver_columnas_e2_v2.py).

Cada caso se resuelve con E2 v2 y con la referencia HiGHS (LP agregado por origen) para comparar.
Modos (correr desde la raíz del repositorio):
  python red_chile/scripts/experimentos_chile_e2.py candidatos   # greedy de candidatos (~130 corridas)
  python red_chile/scripts/experimentos_chile_e2.py fallas       # 95 fallas, con y sin candidatos (190)
  python red_chile/scripts/experimentos_chile_e2.py troncal      # 21 fallas troncales: candidatos 800,
                                                                 # candidatos 8000 y troncal doble (63)
  python red_chile/scripts/experimentos_chile_e2.py prueba       # 3 casos, para comprobar que todo funciona
Opciones: --sin-referencia (no corre HiGHS), --solver otro_solver
Salida: red_chile/experimentos/e2_<modo>.csv
Capacidades y demandas se escriben en kbps enteros (Gbps × 1e6), igual que red_chile/instancias_enteras.
"""
import argparse, os, re, subprocess, sys, time, tempfile
from decimal import Decimal
import numpy as np, pandas as pd, networkx as nx

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
from resolver_referencia import leer, resolver

ROOT = os.path.dirname(AQUI)
REPO = os.path.dirname(ROOT)
OUT = os.path.join(ROOT, 'experimentos'); os.makedirs(OUT, exist_ok=True)
TMP = tempfile.mkdtemp(prefix='chile_e2_')
ESCALA = Decimal(10) ** 6

nodos = pd.read_csv(os.path.join(ROOT, 'nodos.csv'), dtype={'cut': str})
NOMBRE = dict(zip(nodos.id, nodos.nombre))
enl = pd.read_csv(os.path.join(ROOT, 'enlaces.csv'))
BASE = enl[enl.capa != 'CANDIDATO']
CAND = enl[enl.capa == 'CANDIDATO']
TRONCAL = enl[enl.capa == 'TRONCAL']

# Demandas con su texto decimal original (exacto al multiplicar por 1e6).
with open(os.path.join(ROOT, 'instancia_base.txt')) as fh:
    n_nodos, m0, K0 = map(int, fh.readline().split())
    for _ in range(m0):
        fh.readline()
    PRODS = []
    for _ in range(K0):
        _, o, v = fh.readline().split(); _, d, _ = fh.readline().split()
        PRODS.append((int(o), int(d), v))
DEM_TOTAL = sum(float(v) for _, _, v in PRODS)


def enlaces_a_arcos(df, cap_override=None):
    """Lista (o, d, cap_gbps) con dos arcos por enlace."""
    arcos = []
    for r in df.itertuples():
        c = cap_override.get(r.id, r.capacidad_gbps_por_sentido) if cap_override else r.capacidad_gbps_por_sentido
        arcos += [(r.origen, r.destino, int(c)), (r.destino, r.origen, int(c))]
    return arcos


def productos_conectados(arcos):
    G = nx.Graph(); G.add_nodes_from(nodos.id); G.add_edges_from((o, d) for o, d, _ in arcos)
    comp = {v: i for i, cc in enumerate(nx.connected_components(G)) for v in cc}
    return [p for p in PRODS if comp[p[0]] == comp[p[1]]]


def escribir(nombre, arcos, prods):
    ruta = os.path.join(TMP, nombre + '.txt')
    with open(ruta, 'w') as fh:
        fh.write(f'{n_nodos} {len(arcos)} {len(prods)}\n')
        for o, d, c in arcos:
            fh.write(f'{o} {d} 0 {int(Decimal(c) * ESCALA)} 0\n')
        for k, (o, d, v) in enumerate(prods, 1):
            x = int(Decimal(v) * ESCALA)
            fh.write(f'{k} {o} {x}\n{k} {d} {-x}\n')
    return ruta


def num(patron, texto, conv=float):
    m = re.findall(patron, texto)
    if not m:
        return None
    return float('inf') if m[-1] == 'inf' else conv(m[-1])


def correr_e2(ruta, solver):
    env = dict(os.environ, ARCHIVO_INSTANCIA=ruta)
    t0 = time.perf_counter()
    p = subprocess.run([sys.executable, solver], cwd=REPO, env=env, capture_output=True, text=True)
    pared = time.perf_counter() - t0
    s = p.stdout + p.stderr
    if 'SIN CERTIFICAR' in s:
        cert = 'sin certificar'
    elif 'ptima certificada' in s:
        cert = 'óptimo'
    elif 'error relativo certificado' in s:
        cert = 'brecha <= 1%'
    else:
        cert = f'error ({p.returncode})'
    return dict(z_e2=num(r'Congesti[oó]n m[aá]xima:\s*([0-9.eE+\-]+)', s),
                cota_inf_e2=num(r'Cota inferior:\s*([0-9.eE+\-]+)', s),
                gap_pct_e2=num(r'(?m)^Gap certificado:\s*([0-9.eE+\-]+|inf)%', s),
                iter_e2=num(r'Iteraciones:\s*(\d+)', s, int), columnas_e2=num(r'Columnas:\s*(\d+)', s, int),
                tiempo_e2_s=num(r'Tiempo total:\s*([0-9.]+)', s), pared_s=round(pared, 2), certificacion_e2=cert)


def correr_ref(arcos, prods):
    m = max(c for _, _, c in arcos)
    z, _, _ = resolver(n_nodos, [(o, d, c / m) for o, d, c in arcos], [(o, d, float(v) / m) for o, d, v in prods])
    return z


def caso(nombre, arcos, args, extra):
    prods = productos_conectados(arcos)
    fila = dict(caso=nombre, **extra, demanda_servida_pct=round(100 * sum(float(v) for _, _, v in prods) / DEM_TOTAL, 2))
    fila.update(correr_e2(escribir(nombre, arcos, prods), args.solver))
    if not args.sin_referencia:
        fila['z_ref_highs'] = correr_ref(arcos, prods)
        fila['dif_rel'] = abs(fila['z_e2'] - fila['z_ref_highs']) / fila['z_ref_highs'] if fila['z_e2'] else None
    fila = {k: (float(v) if isinstance(v, np.floating) else v) for k, v in fila.items()}
    print({k: (round(v, 6) if isinstance(v, float) else v) for k, v in fila.items()}, flush=True)
    return fila


def guardar(filas, modo):
    ruta = os.path.join(OUT, f'e2_{modo}.csv'); pd.DataFrame(filas).to_csv(ruta, index=False)
    return ruta


def modo_prueba(args):
    filas = [caso('base', enlaces_a_arcos(BASE), args, {}),
             caso('base_mas_20_candidatos', enlaces_a_arcos(pd.concat([BASE, CAND])), args, {}),
             caso('falla_238_con_candidatos', enlaces_a_arcos(pd.concat([BASE, CAND])[lambda d: d.id != 238]), args, {})]
    return guardar(filas, 'prueba')


def modo_candidatos(args):
    km = dict(zip(CAND.id, CAND.km)); elegidos, filas = [], []
    base = caso('greedy_paso0', enlaces_a_arcos(BASE), args, dict(paso=0, candidato_agregado='(base)', evaluado=None))
    filas.append(base); z0 = base['z_e2']
    for paso in range(1, 9):
        evaluaciones = []
        for cid in [c for c in CAND.id if c not in elegidos]:
            df = pd.concat([BASE, CAND[CAND.id.isin(elegidos + [cid])]])
            f = caso(f'greedy_paso{paso}_cand{cid}', enlaces_a_arcos(df), args,
                     dict(paso=paso, candidato_agregado=None, evaluado=cid))
            filas.append(f); evaluaciones.append((round(f['z_e2'], 6), km[cid], cid))
        _, _, mejor = min(evaluaciones); elegidos.append(mejor)
        r = CAND[CAND.id == mejor].iloc[0]
        for f in filas:
            if f['paso'] == paso and f['evaluado'] == mejor:
                f['candidato_agregado'] = f'{r.origen_nombre} – {r.destino_nombre}'
                f['km_acum'] = round(sum(km[c] for c in elegidos), 1)
                f['mejora_acum_pct'] = round(100 * (z0 - f['z_e2']) / z0, 2)
        guardar(filas, 'candidatos')
    return guardar(filas, 'candidatos')


def modo_fallas(args):
    fl = pd.read_csv(os.path.join(ROOT, 'fallas.csv')); filas = []
    for r in fl.itertuples():
        for con in (False, True):
            df = (pd.concat([BASE, CAND]) if con else BASE)
            filas.append(caso(f'falla{r.id_enlace}_{"con" if con else "sin"}_cand',
                              enlaces_a_arcos(df[df.id != r.id_enlace]), args,
                              dict(id_enlace=r.id_enlace, capa=r.capa, origen=r.origen, destino=r.destino, candidatos=con)))
        guardar(filas, 'fallas')
    return guardar(filas, 'fallas')


def modo_troncal(args):
    filas = []
    cap8000 = {cid: 8000 for cid in CAND.id}
    for r in TRONCAL.itertuples():
        extra = dict(id_enlace=r.id, origen=r.origen_nombre, destino=r.destino_nombre)
        sin_t = lambda df: df[df.id != r.id]
        filas.append(caso(f'troncal{r.id}_cand800', enlaces_a_arcos(sin_t(pd.concat([BASE, CAND]))), args,
                          dict(variante='candidatos 800 Gbps', **extra)))
        filas.append(caso(f'troncal{r.id}_cand8000', enlaces_a_arcos(sin_t(pd.concat([BASE, CAND])), cap8000), args,
                          dict(variante='candidatos 8000 Gbps', **extra)))
        # Troncal doble: cada tramo troncal tiene un segundo cable independiente de igual capacidad;
        # la falla corta solo uno de los dos.
        arcos = enlaces_a_arcos(BASE) + enlaces_a_arcos(TRONCAL)
        quitar = [(r.origen, r.destino, int(r.capacidad_gbps_por_sentido)), (r.destino, r.origen, int(r.capacidad_gbps_por_sentido))]
        for q in quitar:
            arcos.remove(q)
        filas.append(caso(f'troncal{r.id}_doble', arcos, args, dict(variante='troncal doble, sin candidatos', **extra)))
        guardar(filas, 'troncal')
    return guardar(filas, 'troncal')


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('modo', choices=['prueba', 'candidatos', 'fallas', 'troncal'])
    ap.add_argument('--solver', default=os.path.join(REPO, 'compat', 'solver_columnas_e2_v2.py'))
    ap.add_argument('--sin-referencia', action='store_true')
    args = ap.parse_args()
    ruta = {'prueba': modo_prueba, 'candidatos': modo_candidatos, 'fallas': modo_fallas, 'troncal': modo_troncal}[args.modo](args)
    print('\nResultados en', ruta)
