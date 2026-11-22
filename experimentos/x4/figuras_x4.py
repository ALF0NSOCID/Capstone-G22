#!/usr/bin/env python3
"""Figura del X4: tiempo contra tamaño (log-log) para E2 v2 y el caso base, con β y la aceleración por tamaño."""
import os, math, numpy as np, pandas as pd, matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
AQUI = os.path.dirname(os.path.abspath(__file__)); FIG = os.path.join(AQUI, 'figuras'); os.makedirs(FIG, exist_ok=True)
TXT, TXT2, GRID, SURF = '#0b0b0b', '#52514e', '#e4e3df', '#fcfcfb'
COL = {'e2_v2': '#2a78d6', 'base': '#eb6834'}; NOM = {'e2_v2': 'E2 v2 (solver final)', 'base': 'Caso base (pricing con Gurobi)'}
plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10, 'axes.edgecolor': GRID, 'axes.labelcolor': TXT2,
                     'xtick.color': TXT2, 'ytick.color': TXT2, 'axes.spines.top': False, 'axes.spines.right': False,
                     'figure.facecolor': SURF, 'axes.facecolor': SURF, 'savefig.facecolor': SURF})
d = pd.read_csv(os.path.join(AQUI, 'corridas.csv'))
d = d[d.certificacion.isin(['óptimo', 'brecha <= 1%', 'óptimo (sin cota)'])]
fmt = FuncFormatter(lambda v, _: f'{v:g}'.replace('.', ','))
fig, (ax, ax2) = plt.subplots(1, 2, figsize=(12, 5.2), gridspec_kw=dict(width_ratios=[1.6, 1]))
betas = {}
for m in ('base', 'e2_v2'):
    s = d[d.metodo == m]; x, y = s.k_por_arcos.astype(float), s.tiempo_interno_s.astype(float)
    b, a = np.polyfit(np.log10(x), np.log10(y), 1); betas[m] = b
    ax.scatter(x, y, s=40, color=COL[m], edgecolor=SURF, lw=1, zorder=3, alpha=0.9)
    xs = np.logspace(np.log10(x.min()), np.log10(x.max()), 50); ax.plot(xs, 10 ** a * xs ** b, color=COL[m], lw=2)
    ax.annotate(f'{NOM[m]}\nβ = {b:.2f}'.replace('.', ','), (xs[-1], 10 ** a * xs[-1] ** b), xytext=(8, 0), textcoords='offset points',
                fontsize=9, color=COL[m], va='center', fontweight='bold')
ax.set_xscale('log'); ax.set_yscale('log'); ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: (f'{v/1e6:,.0f} mill.'.replace(',', '.'))))
ax.yaxis.set_major_formatter(fmt); ax.set_xlim(right=ax.get_xlim()[1] * 25)
ax.set_xlabel('Tamaño del problema K · |A| (productos × arcos, escala log)'); ax.set_ylabel('Tiempo interno (s, escala log)')
ax.grid(color=GRID, lw=0.8); ax.set_axisbelow(True)
import matplotlib.transforms as mt
tr = mt.blended_transform_factory(ax.transData, ax.transAxes)
for n in sorted(d.nodos.unique()):
    s = d[(d.metodo == 'e2_v2') & (d.nodos == n)]
    ax.text(s.k_por_arcos.median(), 0.02, f'N={n:,}'.replace(',', '.'), transform=tr, ha='center', fontsize=8, color=TXT2)
ax.set_title('E2 v2 escala casi lineal; el caso base, más que lineal', loc='left', fontsize=13, fontweight='bold', color=TXT, pad=34)
ax.text(0, 1.02, 'Grado 4, 25 productos por nodo, 5 semillas por tamaño. Rectas: ajuste log-log; β = pendiente.\nCaso base corrido hasta 800 nodos.',
        transform=ax.transAxes, fontsize=9, color=TXT2)
# aceleración pareada por tamaño
p = d.pivot_table(index=['nodos', 'semilla'], columns='metodo', values='tiempo_interno_s').dropna()
p['razon'] = p.base / p.e2_v2; g = p.groupby('nodos').razon
med, lo, hi = g.median(), g.min(), g.max(); xs = range(len(med))
ax2.bar(xs, med.values, color=COL['e2_v2'], width=0.55)
ax2.errorbar(xs, med.values, yerr=[med.values - lo.values, hi.values - med.values], fmt='none', ecolor=TXT2, capsize=4, lw=1)
for i, v in zip(xs, med.values):
    ax2.text(i + 0.31, v, f'{v:.0f}×', ha='left', va='center', fontsize=11, fontweight='bold', color=TXT)
ax2.set_xlim(-0.5, len(med) - 0.1); ax2.set_xticks(list(xs)); ax2.set_xticklabels([f'{n:,}'.replace(',', '.') for n in med.index]); ax2.set_xlabel('Nodos')
ax2.set_ylabel('Caso base / E2 v2 (veces más rápido)'); ax2.grid(axis='y', color=GRID, lw=0.8); ax2.set_axisbelow(True)
ax2.set_title('La ventaja crece con el tamaño', loc='left', fontsize=13, fontweight='bold', color=TXT, pad=34)
ax2.text(0, 1.02, 'Mediana de la razón por semilla (barras: mín. y máx.)', transform=ax2.transAxes, fontsize=9, color=TXT2)
fig.tight_layout(); fig.savefig(os.path.join(FIG, 'escalabilidad.png'), dpi=200)
print({k: round(v, 3) for k, v in betas.items()}, med.round(1).to_dict(), lo.round(1).to_dict(), hi.round(1).to_dict())
