#!/usr/bin/env python3
"""Mapa de control: HTML autocontenido (sin teselas externas) y PNG, coloreados por capa."""
import json, os
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def regiones():
    out = {}
    for line in open(os.path.join(ROOT, 'datos_crudos', 'regiones_ine_simplificadas.txt')):
        cut, rings = line.strip().split(':', 1)
        out[cut] = [[(-float(p.split(',')[0]), -float(p.split(',')[1])) for p in r.split(' ')] for r in rings.split('|')]
    return out


PANELES = [  # (titulo, lat_max, lat_min, lon_min, lon_max)
    ('Norte · Arica a La Serena', -17.3, -30.4, -71.9, -66.8),
    ('Centro y Sur · Coquimbo a Chiloé', -29.6, -43.0, -74.3, -69.9),
    ('Austral · Chaitén a Puerto Williams', -42.4, -55.4, -75.8, -66.9),
]
COL = {'TRONCAL': '#22302b', 'FON': '#0f7b6c', 'FOA_SUB': '#3b4fb8', 'FOA_TER': '#7a3fb0', 'CANDIDATO': '#c9780a'}


def capa_key(r):
    if r.capa == 'FOA':
        return 'FOA_SUB' if r.subtipo == 'submarino' else 'FOA_TER'
    return r.capa


def png(nodos, enl, regs, path):
    import math
    fig, axes = plt.subplots(1, 3, figsize=(15, 9.5), gridspec_kw=dict(width_ratios=[
        (p[4] - p[3]) * math.cos(math.radians((p[1] + p[2]) / 2)) for p in PANELES]))
    pos = {r.id: (r.lon, r.lat) for r in nodos.itertuples()}
    for ax, (tit, la1, la2, lo1, lo2) in zip(axes, PANELES):
        for rings in regs.values():
            for ring in rings:
                xs, ys = zip(*ring)
                ax.fill(xs, ys, color='#e6ebe6', lw=0.4, ec='#b9c3bb', zorder=0)
        for r in enl.itertuples():
            k = capa_key(r)
            (x1, y1), (x2, y2) = pos[r.origen], pos[r.destino]
            ls = {'FOA_SUB': (0, (4, 2)), 'CANDIDATO': (0, (1, 1.5))}.get(k, '-')
            lw = {'TRONCAL': 2.2, 'FON': 1.0, 'FOA_SUB': 1.6, 'FOA_TER': 1.1, 'CANDIDATO': 1.2}[k]
            ax.plot([x1, x2], [y1, y2], color=COL[k], lw=lw, ls=ls, zorder=2 if k != 'TRONCAL' else 3)
            if r.es_puente == 1 and k == 'TRONCAL':
                pass
        for r in nodos.itertuples():
            s = 4 + (r.poblacion_comuna ** 0.5) / 18
            c = {'CAPITAL_PIX': '#22302b', 'NODO_TRONCAL': '#22302b', 'POIIT': '#0f7b6c', 'FOA': '#7a3fb0'}[r.tipo]
            mk = 's' if r.tipo in ('CAPITAL_PIX', 'NODO_TRONCAL') else 'o'
            ax.scatter(r.lon, r.lat, s=s, c=c, marker=mk, zorder=4, edgecolors='white', linewidths=0.3)
            if r.tipo in ('CAPITAL_PIX', 'NODO_TRONCAL') or r.nombre in ('Coyhaique', 'Punta Arenas', 'Puerto Williams', 'Caleta Tortel'):
                ax.annotate(r.nombre, (r.lon, r.lat), xytext=(4, 0), textcoords='offset points', fontsize=6.5, zorder=5)
        ax.set_xlim(lo1, lo2); ax.set_ylim(la2, la1)
        ax.set_aspect(1 / math.cos(math.radians((la1 + la2) / 2)))
        ax.set_title(tit, fontsize=9); ax.tick_params(labelsize=6)
    from matplotlib.lines import Line2D
    h = [Line2D([], [], color=COL['TRONCAL'], lw=2.2, label='Troncal (supuesta)'),
         Line2D([], [], color=COL['FON'], lw=1, label='FON'),
         Line2D([], [], color=COL['FOA_SUB'], lw=1.6, ls=(0, (4, 2)), label='FOA submarina'),
         Line2D([], [], color=COL['FOA_TER'], lw=1.1, label='FOA terrestre'),
         Line2D([], [], color=COL['CANDIDATO'], lw=1.2, ls=(0, (1, 1.5)), label='Candidato (no en red base)')]
    fig.legend(handles=h, loc='lower center', ncol=5, fontsize=8, frameon=False)
    fig.suptitle('Red inspirada en la infraestructura chilena de fibra óptica — mapa de control', fontsize=11)
    fig.tight_layout(rect=(0, 0.04, 1, 0.97))
    fig.savefig(path, dpi=170)


def html(nodos, enl, regs, stats, path):
    data = dict(
        nodes=[[r.id, r.nombre, r.tipo, r.lat, r.lon, int(r.poblacion_comuna), r.region, r.comuna, r.capas] for r in nodos.itertuples()],
        edges=[[r.id, r.origen, r.destino, capa_key(r), round(r.km, 1), int(r.capacidad_gbps_por_sentido), int(r.es_puente),
                r.clasificacion, r.subtipo, round(float(r.demanda_desconectada_si_falla_gbps), 1)] for r in enl.itertuples()],
        regs={k: [[[round(x, 2), round(y, 2)] for x, y in ring] for ring in v] for k, v in regs.items()},
        panels=PANELES, stats=stats)
    tpl = open(os.path.join(ROOT, 'scripts', 'mapa_template.html'), encoding='utf-8').read()
    open(path, 'w', encoding='utf-8').write(tpl.replace('/*__DATA__*/null', json.dumps(data, ensure_ascii=False)))


if __name__ == '__main__':
    nodos = pd.read_csv(os.path.join(ROOT, 'nodos.csv'), dtype={'cut': str})
    enl = pd.read_csv(os.path.join(ROOT, 'enlaces.csv'))
    regs = regiones()
    stats = json.load(open(os.path.join(ROOT, 'datos_crudos', '_stats.json')))
    png(nodos, enl, regs, os.path.join(ROOT, 'mapa_control.png'))
    html(nodos, enl, regs, stats, os.path.join(ROOT, 'mapa_control.html'))
    print('ok')
