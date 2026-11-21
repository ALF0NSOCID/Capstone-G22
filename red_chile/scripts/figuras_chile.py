#!/usr/bin/env python3
"""Figuras del caso chileno a partir de red_chile/experimentos/e2_*.csv (resultados de E2 v2).
Uso: python red_chile/scripts/figuras_chile.py   -> red_chile/experimentos/figuras/*.png
"""
import os
import pandas as pd, matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXP = os.path.join(ROOT, 'experimentos'); FIG = os.path.join(EXP, 'figuras'); os.makedirs(FIG, exist_ok=True)
AZUL, NARANJA, AQUA, CRIT = '#2a78d6', '#eb6834', '#1baf7a', '#d03b3b'
TXT, TXT2, GRID, SURF = '#0b0b0b', '#52514e', '#e4e3df', '#fcfcfb'
plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10, 'axes.edgecolor': GRID, 'axes.labelcolor': TXT2,
                     'xtick.color': TXT2, 'ytick.color': TXT2, 'axes.spines.top': False, 'axes.spines.right': False,
                     'figure.facecolor': SURF, 'axes.facecolor': SURF, 'savefig.facecolor': SURF})

def titulo(ax, t, sub):
    ax.set_title(t, loc='left', fontsize=13, fontweight='bold', color=TXT, pad=34 if '\n' in sub else 22)
    ax.text(0, 1.015, sub, transform=ax.transAxes, fontsize=9.5, color=TXT2, va='bottom')

# 1. Fallas troncales: congestión tras la falla según la variante de red
t = pd.read_csv(os.path.join(EXP, 'e2_troncal.csv'))
p = t.pivot_table(index=['id_enlace', 'origen', 'destino'], columns='variante', values='z_e2').reset_index().sort_values('id_enlace')
p['tramo'] = p.origen + ' – ' + p.destino
fig, ax = plt.subplots(figsize=(9, 7.2)); y = range(len(p))[::-1]
ax.axvline(1, color=CRIT, lw=1.2, ls='--'); ax.text(1.03, len(p) - 0.4, '100 % de capacidad', color=CRIT, fontsize=9, va='top')
for yi, a, b in zip(y, p['candidatos 800 Gbps'], p['troncal doble, sin candidatos']):
    ax.plot([b, a], [yi, yi], color=GRID, lw=2, zorder=1)
ax.scatter(p['candidatos 800 Gbps'], y, s=60, color=AZUL, edgecolor=SURF, lw=1.5, zorder=3, label='Con los 20 candidatos (800 Gbps)')
ax.scatter(p['troncal doble, sin candidatos'], y, s=60, color=AQUA, edgecolor=SURF, lw=1.5, zorder=3, marker='D', label='Troncal doble, sin candidatos')
ax.set_yticks(list(y)); ax.set_yticklabels(p.tramo, fontsize=9); ax.set_xlabel('Congestión máxima z tras la falla (1 = 100 % de capacidad)')
ax.grid(axis='x', color=GRID, lw=0.8); ax.set_axisbelow(True); ax.set_xlim(0, 3.9)
ax.legend(loc='lower right', frameon=False, fontsize=9)
titulo(ax, 'Con candidatos, 11 de 21 fallas troncales saturan la red',
       'Tramo que falla (norte a sur). Con candidatos de 8.000 Gbps el resultado es igual:\nel cuello son los ramales de 800 Gbps. Solo una troncal doble lo evita.')
fig.tight_layout(); fig.savefig(os.path.join(FIG, 'fallas_troncales.png'), dpi=200); plt.close(fig)

# 2. Curva de candidatos agregados
c = pd.read_csv(os.path.join(EXP, 'e2_candidatos.csv'))
g = c[c.candidato_agregado.notna()].sort_values('paso').copy(); g['km_acum'] = g.km_acum.fillna(0)
fig, ax = plt.subplots(figsize=(9, 5))
ax.step(g.km_acum, g.z_e2, where='post', color=AZUL, lw=2); ax.scatter(g.km_acum, g.z_e2, s=50, color=AZUL, edgecolor=SURF, lw=1.5, zorder=3)
desplaz = {1: (8, 6), 2: (8, 6), 3: (-12, 10), 4: (-12, -16)}
for _, r in g[g.paso.between(1, 4)].iterrows():
    dx, dy = desplaz[int(r.paso)]
    ax.annotate(f'+ {r.candidato_agregado}', (r.km_acum, r.z_e2), xytext=(dx, dy), textcoords='offset points', fontsize=9,
                color=TXT, ha='right' if dx < 0 else 'left')
ax.annotate('desde aquí, más enlaces\nno bajan la congestión', (g.km_acum.max(), g.z_e2.iloc[-1]), xytext=(-40, 45), textcoords='offset points',
            fontsize=9, color=TXT2, ha='center', arrowprops=dict(arrowstyle='-', color=TXT2, lw=0.8))
ax.set_xlabel('Kilómetros de fibra agregados (acumulado)'); ax.set_ylabel('Congestión máxima z')
ax.grid(axis='y', color=GRID, lw=0.8); ax.set_axisbelow(True); ax.set_ylim(0.38, 0.5)
titulo(ax, f'Cuatro enlaces (452 km) logran toda la mejora: −{g.mejora_acum_pct.max():.1f} % de congestión',
       'Agregado secuencial: en cada paso se suma el candidato que más baja z (resuelto con E2 v2).')
fig.tight_layout(); fig.savefig(os.path.join(FIG, 'candidatos_greedy.png'), dpi=200); plt.close(fig)

# 3. Demanda servida tras cada falla troncal, sin y con candidatos
f = pd.read_csv(os.path.join(EXP, 'e2_fallas.csv')); tr = f[f.capa == 'TRONCAL']
q = tr.pivot_table(index=['id_enlace', 'origen', 'destino'], columns='candidatos', values='demanda_servida_pct').reset_index().sort_values('id_enlace')
nombres = pd.read_csv(os.path.join(ROOT, 'nodos.csv')).set_index('id').nombre
q['tramo'] = q.origen + ' – ' + q.destino
fig, ax = plt.subplots(figsize=(9, 7.2)); y = range(len(q))[::-1]
for yi, a, b in zip(y, q[False], q[True]):
    ax.plot([a, b], [yi, yi], color=GRID, lw=2, zorder=1)
ax.scatter(q[False], y, s=60, color=NARANJA, edgecolor=SURF, lw=1.5, zorder=3, label='Red base (sin candidatos)')
ax.scatter(q[True], y, s=60, color=AZUL, edgecolor=SURF, lw=1.5, zorder=3, label='Con los 20 candidatos')
ax.set_yticks(list(y)); ax.set_yticklabels(q.tramo, fontsize=9); ax.set_xlabel('Demanda que sigue conectada tras la falla (%)')
ax.grid(axis='x', color=GRID, lw=0.8); ax.set_axisbelow(True); ax.set_xlim(25, 103)
ax.legend(loc='lower left', frameon=False, fontsize=9)
titulo(ax, 'Sin candidatos, una falla troncal desconecta hasta 66 %',
       'Demanda que sigue conectada tras cada falla troncal (norte a sur).\nCon los 20 candidatos, el 100 % sigue conectado en las 21 fallas.')
fig.tight_layout(); fig.savefig(os.path.join(FIG, 'fallas_demanda_servida.png'), dpi=200); plt.close(fig)

# 4. Mapa: tramos troncales coloreados según si su falla satura la red (con candidatos)
nod = pd.read_csv(os.path.join(ROOT, 'nodos.csv')).set_index('id'); enl = pd.read_csv(os.path.join(ROOT, 'enlaces.csv'))
zt = p.set_index('id_enlace')['candidatos 800 Gbps']
fig, ax = plt.subplots(figsize=(4.6, 11))
def linea(r, **kw):
    a, b = nod.loc[r.origen], nod.loc[r.destino]; ax.plot([a.lon, b.lon], [a.lat, b.lat], **kw)
for r in enl[enl.capa.isin(['FON', 'FOA'])].itertuples(): linea(r, color='#c9c8c3', lw=0.7, zorder=1)
for r in enl[enl.capa == 'CANDIDATO'].itertuples(): linea(r, color=AZUL, lw=1.2, ls=(0, (2, 1.5)), zorder=2)
for r in enl[enl.capa == 'TRONCAL'].itertuples():
    sat = zt.get(r.id, 0) > 1; linea(r, color=CRIT if sat else TXT2, lw=3 if sat else 2, zorder=3, solid_capstyle='round')
for nom in ['Arica', 'Antofagasta', 'La Serena', 'Santiago', 'Talca', 'Concepción', 'Temuco', 'Puerto Montt', 'Coyhaique', 'Punta Arenas']:
    r = nod[nod.nombre == nom].iloc[0]; ax.scatter(r.lon, r.lat, s=14, color=TXT, zorder=4); ax.text(r.lon + 0.35, r.lat, nom, fontsize=8, va='center', color=TXT)
ax.set_aspect(1.25); ax.set_xlim(-76.5, -66); ax.set_ylim(-56, -17); ax.axis('off')
ax.legend(handles=[Line2D([], [], color=CRIT, lw=3, label='Su falla satura la red (z > 1)'),
                   Line2D([], [], color=TXT2, lw=2, label='Su falla no satura'),
                   Line2D([], [], color=AZUL, lw=1.2, ls=(0, (2, 1.5)), label='Enlace candidato'),
                   Line2D([], [], color='#c9c8c3', lw=0.7, label='Ramales FON / FOA')],
          loc='upper left', bbox_to_anchor=(0.0, -0.01), frameon=False, fontsize=8)
ax.set_title('Tramos troncales críticos\n(red con los 20 candidatos)', fontsize=11, fontweight='bold', color=TXT, loc='left')
fig.tight_layout(); fig.savefig(os.path.join(FIG, 'mapa_tramos_criticos.png'), dpi=200); plt.close(fig)
print('Figuras en', FIG)
