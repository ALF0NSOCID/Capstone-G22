#!/usr/bin/env python3
"""Figura de S6: tiempo e iteraciones del solver E2 v2 en función de eta (partida congestion-aware).
Uso: python experimentos/s6/figuras_s6.py   (lee experimentos/s6/corridas.csv, escribe experimentos/s6/figuras/s6_eta.png)
Un punto por semilla en las familias Mulgen; la red chilena se muestra como la mediana de sus 3 instancias."""
import csv, statistics, sys
from pathlib import Path
import matplotlib, matplotlib.ticker
matplotlib.use("Agg")
import matplotlib.pyplot as plt

AQUI = Path(__file__).resolve().parent
CSV = Path(sys.argv[1]) if len(sys.argv) > 1 else AQUI / "corridas.csv"
SAL = Path(sys.argv[2]) if len(sys.argv) > 2 else AQUI / "figuras"
SAL.mkdir(exist_ok=True)
ETAS = (0, 1, 5, 10, 25, 50, 100)
POS = {e: i for i, e in enumerate(ETAS)}
FAM = [("mulgen_g4_p25", "Grado 4, 25 prod./nodo", "#0B3D5C", "o", "-"),
       ("mulgen_g8_p10", "Grado 8, 10 prod./nodo", "#F2A541", "s", "-"),
       ("mulgen_g8_p25", "Grado 8, 25 prod./nodo", "#1C7293", "^", "--"),
       ("chile", "Red chilena (mediana de 3)", "#8A9AA4", "D", ":")]
INK, MUTED, GRID = "#37474F", "#8A9AA4", "#D5DEE3"

filas = list(csv.DictReader(open(CSV, newline="", encoding="utf-8")))
datos = {}
for r in filas:
    datos.setdefault((r["familia"], int(r["eta"])), []).append((float(r["tiempo_interno_s"]), int(r["iteraciones"])))

plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.edgecolor": GRID,
                     "axes.labelcolor": INK, "xtick.color": INK, "ytick.color": INK})
fig, axs = plt.subplots(1, 2, figsize=(11.2, 4.4))
for ax, k, titulo, ylab in ((axs[0], 0, "Tiempo interno", "Tiempo mediano (s)"),
                            (axs[1], 1, "Iteraciones", "Iteraciones medianas")):
    ax.axvspan(POS[25] - 0.35, POS[25] + 0.35, color="#F2A541", alpha=0.13, lw=0)
    for fam, nombre, col, mk, ls in FAM:
        med = [statistics.median(v[k] for v in datos[(fam, e)]) for e in ETAS]
        ax.plot([POS[e] for e in ETAS], med, color=col, marker=mk, ls=ls, lw=2, ms=6, label=nombre, zorder=3)
        if fam != "chile":
            for e in ETAS:
                ax.scatter([POS[e]] * len(datos[(fam, e)]), [v[k] for v in datos[(fam, e)]], s=14, color=col,
                           alpha=0.35, lw=0, zorder=2)
    ax.set_xticks(range(len(ETAS))); ax.set_xticklabels([str(e) for e in ETAS])
    ax.set_xlabel("η (penalización de la partida congestion-aware)"); ax.set_ylabel(ylab + " (escala log)")
    ax.set_title(titulo, loc="left", fontsize=11, fontweight="bold", color="#0B3D5C")
    ax.grid(axis="y", color=GRID, lw=0.8); ax.set_axisbelow(True)
    for s in ("top", "right"): ax.spines[s].set_visible(False)
    ax.set_yscale('log')
    ax.set_ylim(*( (0.4, 90) if k == 0 else (0.8, 130) ))
    from matplotlib.ticker import ScalarFormatter
    ax.yaxis.set_major_formatter(ScalarFormatter()); ax.yaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())
axs[0].text(POS[25], 0.46, "η = 25 (valor usado)", ha="center", va="bottom", fontsize=8.5, color="#B9770E")
h, l = axs[0].get_legend_handles_labels()
fig.legend(h, l, frameon=False, fontsize=9, loc="lower center", ncol=4, bbox_to_anchor=(0.5, 0.045))
fig.text(0.01, 0.005, "Solver E2 v2, límite 300 s. Mulgen: 400 nodos, 3 semillas (línea = mediana, puntos = semillas). "
         "Chile: base, extendida_200 y base + 20 candidatos. Las 84 corridas certifican (error ≤ 1 %).",
         fontsize=7.8, color=MUTED, ha="left", va="bottom")
fig.tight_layout(rect=(0, 0.11, 1, 1))
fig.savefig(SAL / "s6_eta.png", dpi=200)
print("listo", SAL / "s6_eta.png")
