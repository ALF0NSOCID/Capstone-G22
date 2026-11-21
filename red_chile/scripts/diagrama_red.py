#!/usr/bin/env python3
"""Diagrama de la red chilena: (a) base + 20 candidatos, (b) red extendida con 200 enlaces extra.
Uso: python red_chile/scripts/diagrama_red.py -> red_chile/experimentos/figuras/diagrama_red_chilena.png
Requiere haber corrido antes red_extendida.py."""
import os
import pandas as pd, matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIG = os.path.join(ROOT, 'experimentos', 'figuras'); os.makedirs(FIG, exist_ok=True)
nod = pd.read_csv(os.path.join(ROOT, 'nodos.csv')).set_index('id'); enl = pd.read_csv(os.path.join(ROOT, 'enlaces.csv'))
extra = pd.read_csv(os.path.join(ROOT, 'experimentos', 'red_extendida', 'enlaces_extra_200.csv'))
TXT, TXT2, SURF = '#0b0b0b', '#52514e', '#fcfcfb'
COL = {'TRONCAL': TXT, 'FON': '#a9a8a3', 'FOA': '#6250d6', 'CANDIDATO': '#2a78d6', 'EXTRA': '#eb6834'}
plt.rcParams.update({'font.family': 'DejaVu Sans', 'figure.facecolor': SURF, 'savefig.facecolor': SURF})

def dibujar(ax, capas, titulo, sub, lim=None, etiquetas=None):
    for capa, df, lw, ls, z in capas:
        for r in df.itertuples():
            a, b = nod.loc[r.origen], nod.loc[r.destino]
            ax.plot([a.lon, b.lon], [a.lat, b.lat], color=COL[capa], lw=lw, ls=ls, zorder=z, solid_capstyle='round')
    ax.scatter(nod.lon, nod.lat, s=3, color=TXT2, zorder=5)
    for nom in etiquetas or ['Arica', 'Antofagasta', 'La Serena', 'Santiago', 'Concepción', 'Puerto Montt', 'Coyhaique', 'Punta Arenas']:
        r = nod[nod.nombre == nom].iloc[0]; ax.text(r.lon + (0.12 if lim else 0.5), r.lat, nom, fontsize=7.5, va='center', color=TXT,
                bbox=dict(boxstyle='round,pad=0.15', fc=SURF, ec='none', alpha=0.8) if lim else None, zorder=6)
    (x0, x1), (y0, y1) = lim or ((-77, -66), (-56, -17))
    ax.set_aspect(1.25); ax.set_xlim(x0, x1); ax.set_ylim(y0, y1); ax.axis('off')
    ax.set_title(titulo, fontsize=11, fontweight='bold', loc='left', color=TXT)
    ax.text(0, 1.0, sub, transform=ax.transAxes, fontsize=8.5, color=TXT2, va='top')

base = [('FON', enl[enl.capa == 'FON'], 0.8, '-', 1), ('FOA', enl[enl.capa == 'FOA'], 1.2, '-', 2), ('TRONCAL', enl[enl.capa == 'TRONCAL'], 2.4, '-', 3)]
fig, (a1, a2, a3) = plt.subplots(1, 3, figsize=(13, 11), gridspec_kw=dict(width_ratios=[1, 1, 1.25]))
dibujar(a1, base + [('CANDIDATO', enl[enl.capa == 'CANDIDATO'], 1.8, (0, (2, 1.2)), 4)],
        '(a) Base + 20 candidatos', '305 enlaces · 33 % son puentes')
dibujar(a2, base + [('CANDIDATO', enl[enl.capa == 'CANDIDATO'], 1.4, '-', 4), ('EXTRA', extra, 1.0, '-', 4)],
        '(b) Extendida: + 200 enlaces', '505 enlaces · 7 % son puentes')
dibujar(a3, [('FON', enl[enl.capa == 'FON'], 1.0, '-', 1), ('TRONCAL', enl[enl.capa == 'TRONCAL'], 3, '-', 3),
             ('CANDIDATO', enl[enl.capa == 'CANDIDATO'], 2, '-', 4), ('EXTRA', extra, 1.6, '-', 4)],
        '(c) Zoom centro-sur de (b)', 'Santiago a Puerto Montt', lim=((-74.3, -70.2), (-41.8, -32.6)),
        etiquetas=['Santiago', 'Rancagua', 'Talca', 'Chillán', 'Concepción', 'Temuco', 'Valdivia', 'Puerto Montt'])
fig.legend(handles=[Line2D([], [], color=COL['TRONCAL'], lw=2.4, label='Troncal (supuesta)'),
                    Line2D([], [], color=COL['FON'], lw=1, label='Ramales FON'),
                    Line2D([], [], color=COL['FOA'], lw=1.2, label='FOA (Austral)'),
                    Line2D([], [], color=COL['CANDIDATO'], lw=1.8, ls=(0, (2, 1.2)), label='20 enlaces candidatos'),
                    Line2D([], [], color=COL['EXTRA'], lw=1.2, label='200 enlaces extra (prueba de esfuerzo)')],
           loc='lower center', ncol=3, frameon=False, fontsize=8.5)
fig.suptitle('Red inspirada en la fibra óptica chilena: base 94 % puentes, casi un árbol', fontsize=12.5, fontweight='bold', x=0.02, ha='left', color=TXT)
fig.tight_layout(rect=(0, 0.06, 1, 0.97)); fig.savefig(os.path.join(FIG, 'diagrama_red_chilena.png'), dpi=200)
print('ok')
