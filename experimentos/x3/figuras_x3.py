#!/usr/bin/env python3
"""Figuras del X3 a partir de experimentos/x3/corridas.csv y experimentos/sndlib_validacion_v2.csv."""
import os, re, numpy as np, pandas as pd, matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm, LinearSegmentedColormap
from matplotlib.lines import Line2D
AQUI = os.path.dirname(os.path.abspath(__file__)); RAIZ = os.path.dirname(os.path.dirname(AQUI))
FIG = os.path.join(AQUI, 'figuras'); os.makedirs(FIG, exist_ok=True)
TXT, TXT2, GRID, SURF = '#0b0b0b', '#52514e', '#e4e3df', '#fcfcfb'
plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10, 'axes.edgecolor': GRID, 'axes.labelcolor': TXT2,
                     'xtick.color': TXT2, 'ytick.color': TXT2, 'axes.spines.top': False, 'axes.spines.right': False,
                     'figure.facecolor': SURF, 'axes.facecolor': SURF, 'savefig.facecolor': SURF})
d = pd.read_csv(os.path.join(AQUI, 'corridas.csv'))
ok = d.certificacion.isin(['óptimo', 'brecha <= 1%'])
# z de corridas no certificadas: la cota superior del log (solo para ubicarlas en el gráfico).
for i in d.index[~ok]:
    t = open(os.path.join(AQUI, 'logs', d.instancia[i] + '.txt'), encoding='utf-8').read()
    m = re.findall(r'Cota superior:\s*([0-9.eE+\-]+)', t); d.loc[i, 'z'] = float(m[-1]) if m else np.nan

# 1. Mapa de regímenes
azules = LinearSegmentedColormap.from_list('az', ['#cde2fb', '#86b6ef', '#3987e5', '#256abf', '#104281'])
grados, ppns = sorted(d.grado.unique()), sorted(d.productos_por_nodo.unique())
fig, (ax, ax2) = plt.subplots(2, 1, figsize=(9, 5.6), gridspec_kw=dict(height_ratios=[len(ppns), 1.1], hspace=0.08), sharex=True)
norm = LogNorm(0.1, 1000)
for g in grados:
    for j, p in enumerate(ppns):
        c = d[(d.grado == g) & (d.productos_por_nodo == p)]; cert = ok[c.index]
        med = c[cert].tiempo_interno_s.median() if 2 * cert.sum() > len(c) else None
        val = med if med is not None else 900
        col = azules(norm(val))
        ax.add_patch(plt.Rectangle((g - 1.9, j - 0.47), 3.8, 0.94, color=col, lw=0))
        tinta = 'white' if norm(val) > 0.55 else TXT
        tiempo = ((f'{med:.2f} s' if med < 10 else f'{med:.0f} s').replace('.', ',')) if med is not None else '> 900 s'
        ax.text(g, j + 0.12, tiempo, ha='center', va='center', fontsize=12, fontweight='bold', color=tinta)
        ax.text(g, j - 0.2, f'certifican {cert.sum()}/{len(c)}', ha='center', va='center', fontsize=8.5, color=tinta)
ax.set_yticks(range(len(ppns))); ax.set_yticklabels([f'{p} prod./nodo\n(K = {p * 400:,})'.replace(',', '.') for p in ppns])
ax.set_ylim(-0.55, len(ppns) - 0.45); ax.tick_params(length=0)
ax.set_title('El método certifica en todo el rango; en redes densas se vuelve lento', loc='left', fontsize=13, fontweight='bold', color=TXT, pad=24)
ax.text(0, 1.02, 'Mediana del tiempo interno de E2 v2 (400 nodos, 3 semillas por celda, límite 900 s). Abajo: grado de las redes reales.',
        transform=ax.transAxes, fontsize=9, color=TXT2)
s = pd.read_csv(os.path.join(RAIZ, 'experimentos', 'sndlib_validacion_v2.csv')); s['grado'] = s.arcos / s.nodos
sn = s[s.red != 'fon-raw']
ax2.scatter(sn.grado, np.zeros(len(sn)), s=40, marker='|', color=TXT2, lw=1.5)
ch = s[s.red == 'fon-raw'].grado.iloc[0]
ax2.scatter([ch], [0], s=80, marker='v', color='#e34948', zorder=3)
ax2.text(ch, 0.35, 'Chile', ha='center', fontsize=8.5, color='#e34948')
ax2.text(float(sn.grado.median()), -0.55, f'26 redes SNDlib: grado {sn.grado.min():.1f} a {sn.grado.max():.1f} (mediana {sn.grado.median():.1f})'.replace('.', ','),
         ha='left', fontsize=8.5, color=TXT2)
ax2.set_ylim(-0.8, 0.8); ax2.set_yticks([]); ax2.spines['left'].set_visible(False)
ax2.set_xlim(1.5, 18.1); ax2.set_xticks(grados + [2]); ax2.set_xlabel('Grado medio (arcos dirigidos por nodo)')
fig.subplots_adjust(left=0.17, right=0.98, top=0.86, bottom=0.11)
fig.savefig(os.path.join(FIG, 'mapa_regimenes.png'), dpi=200); plt.close(fig)

# 2. Tiempo contra carga (z)
colores = {4: '#2a78d6', 8: '#1baf7a', 12: '#eda100', 16: '#e34948'}
marc = {10: 'o', 25: 's'}
fig, ax = plt.subplots(figsize=(9, 5.4))
for _, r in d.iterrows():
    cert = r.certificacion in ('óptimo', 'brecha <= 1%')
    ax.scatter(r.z, r.tiempo_interno_s, s=70, marker=marc[r.productos_por_nodo], zorder=3,
               color=colores[r.grado] if cert else SURF, edgecolor=colores[r.grado], lw=1.8)
cens = d[~ok]
for _, r in cens.iterrows():
    ax.annotate('no certificó en 900 s', (r.z, r.tiempo_interno_s), xytext=(10, -16), textcoords='offset points', fontsize=8.5, color=TXT2)
ax.set_xscale('log'); ax.set_yscale('log'); ax.set_ylim(0.08, 2000)
ax.axhline(900, color=TXT2, lw=0.8, ls='--'); ax.text(0.95, 900 * 1.12, 'límite 900 s', fontsize=8.5, color=TXT2, ha='right')
from matplotlib.ticker import FuncFormatter
fmt = FuncFormatter(lambda v, _: (f'{v:g}').replace('.', ','))
ax.xaxis.set_major_formatter(fmt); ax.yaxis.set_major_formatter(fmt)
ax.set_xlabel('Congestión óptima z (carga de la red, escala log)'); ax.set_ylabel('Tiempo interno E2 v2 (s, escala log)')
ax.grid(color=GRID, lw=0.8); ax.set_axisbelow(True)
h = [Line2D([], [], marker='o', ls='', color=colores[g], ms=8, label=f'grado {g}') for g in sorted(colores)]
h += [Line2D([], [], marker=marc[p], ls='', color=TXT2, mfc='none', ms=8, label=f'{p} prod./nodo') for p in marc]
ax.legend(handles=h, frameon=False, fontsize=8.5, loc='lower left', ncol=2)
rho = d[ok][['z', 'tiempo_interno_s']].corr(method='spearman').iloc[0, 1]
ax.set_title('Lo lento son las redes densas y poco cargadas', loc='left', fontsize=13, fontweight='bold', color=TXT, pad=34)
ax.text(0, 1.015, f'Cada punto es una corrida del X3. A menor z hay más rutas casi equivalentes y el maestro trabaja más\n(correlación de Spearman entre z y tiempo = {rho:.2f}).'.replace('-0.', '−0,'),
        transform=ax.transAxes, fontsize=9, color=TXT2)
fig.tight_layout(); fig.savefig(os.path.join(FIG, 'tiempo_vs_carga.png'), dpi=200); plt.close(fig)
print('ok', round(rho, 2))
