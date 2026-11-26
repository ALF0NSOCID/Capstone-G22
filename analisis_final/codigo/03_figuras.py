#!/usr/bin/env python3
"""Paso 3: figuras para informe y presentación (PNG 300 ppp + SVG + PDF).

Los SVG llevan el texto convertido a trazos para verse igual en cualquier
programa (PowerPoint, Keynote, Illustrator) aunque no tenga la fuente.

Lee analisis_final/tablas/ (pasos 1 y 2) y, para las imágenes topológicas,
las instancias Waxman originales. Escribe en analisis_final/figuras/.

Uso, desde la raíz del repositorio:
    python3 analisis_final/codigo/03_figuras.py
"""
from __future__ import annotations

import math
import random
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.collections import LineCollection  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Patch, Rectangle  # noqa: E402
from matplotlib.ticker import FixedLocator, FuncFormatter, NullLocator  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from comun import ETIQUETAS_WAXMAN, EXP, FAMILIAS_WAXMAN, FIGURAS, TABLAS, cuantil_censurado  # noqa: E402

# Paleta (validada con el validador de la guía de visualización: azul/naranjo/aqua).
AZUL, NARANJO, AQUA, VIOLETA, AMARILLO = "#2a78d6", "#eb6834", "#1baf7a", "#6250d6", "#eda100"
CRITICO = "#d03b3b"
TINTA, TINTA2, TENUE = "#0b0b0b", "#52514e", "#898781"
GRILLA, EJE, BANDA = "#e1e0d9", "#c3c2b7", "#efeee9"
RAMPA_GRADO = {4: "#86b6ef", 8: "#3987e5", 12: "#1c5cab", 16: "#0d366b"}

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 9, "axes.titlesize": 10, "axes.labelsize": 9,
    "axes.edgecolor": EJE, "axes.linewidth": 0.8, "xtick.color": TINTA2, "ytick.color": TINTA2,
    "axes.labelcolor": TINTA2, "text.color": TINTA, "axes.grid": False, "grid.color": GRILLA,
    "grid.linewidth": 0.6, "axes.spines.top": False, "axes.spines.right": False,
    "svg.fonttype": "path", "pdf.fonttype": 42, "figure.facecolor": "white", "axes.facecolor": "white",
    "legend.frameon": False, "xtick.major.size": 3, "ytick.major.size": 3, "ytick.minor.size": 0,
})


def num(x, d=1):
    """Número con coma decimal y punto de miles."""
    x = x + (1e-9 if x >= 0 else -1e-9)
    s = f"{x:,.{d}f}"
    return s.replace(",", "_").replace(".", ",").replace("_", ".")


def fmt_log(v, _pos=None):
    if v >= 1:
        return num(v, 0)
    return num(v, 2 if v < 0.1 else 1)


def eje_log_y(ax, lo, hi, ticks=None):
    ax.set_yscale("log")
    ax.set_ylim(lo, hi)
    ticks = ticks or [t for t in (0.01, 0.1, 1, 10, 100, 1000) if lo <= t <= hi]
    ax.yaxis.set_major_locator(FixedLocator(ticks))
    ax.yaxis.set_minor_locator(NullLocator())
    ax.yaxis.set_major_formatter(FuncFormatter(fmt_log))
    ax.grid(axis="y", which="major")
    ax.set_axisbelow(True)


def encabezado(fig, titulo, subtitulo, pie=None, y=0.975):
    fig.text(0.015, y, titulo, fontsize=11.5, fontweight="bold", color=TINTA, va="top")
    fig.text(0.015, y - 0.058, subtitulo, fontsize=8.6, color=TINTA2, va="top", linespacing=1.35)
    if pie:
        fig.text(0.015, 0.012, pie, fontsize=7.6, color=TENUE, va="bottom", linespacing=1.35)


def guardar(fig, nombre):
    FIGURAS.mkdir(parents=True, exist_ok=True)
    for ext in ("png", "svg", "pdf"):
        fig.savefig(FIGURAS / f"{nombre}.{ext}", dpi=300 if ext == "png" else None)
    plt.close(fig)
    print("figura:", nombre)


def enjambre(y, ancho=0.34, paso=0.055, dy=0.075):
    """Desplazamientos horizontales tipo beeswarm sobre log10(y)."""
    ly = np.log10(np.asarray(y, float))
    orden = np.argsort(ly)
    pos = np.zeros(len(ly))
    colocados = []
    candidatos = [0.0] + [s * k * paso for k in range(1, 40) for s in (1, -1)]
    for i in orden:
        for c in candidatos:
            if abs(c) > ancho:
                c = (random.Random(int(i)).random() - 0.5) * 2 * ancho
                break
            if all(abs(c - pc) >= paso * 0.95 or abs(ly[i] - pl) >= dy for pc, pl in colocados):
                break
        pos[i] = c
        colocados.append((c, ly[i]))
    return pos


def marcar(ax, x, y, estado, color, s=24, z=3):
    """Relleno = óptimo; hueco = brecha ≤ 1 %; × rojo = límite sin certificar."""
    x, y, estado = np.asarray(x), np.asarray(y), np.asarray(estado)
    m = estado == "optimo"
    ax.scatter(x[m], y[m], s=s, facecolor=color, edgecolor="white", linewidth=0.6, zorder=z)
    m = estado == "brecha_1pct"
    ax.scatter(x[m], y[m], s=s, facecolor="white", edgecolor=color, linewidth=1.2, zorder=z + 0.1)
    m = np.isin(estado, ["limite_interno", "timeout_externo"])
    ax.scatter(x[m], y[m], s=s * 1.5, marker="X", facecolor=CRITICO, edgecolor="white", linewidth=0.5, zorder=z + 0.2)


def leyenda_estados(color, con_limite=True, extra=()):
    h = [Line2D([], [], ls="", marker="o", ms=5.5, mfc=color, mec="white", label="óptimo certificado"),
         Line2D([], [], ls="", marker="o", ms=5.5, mfc="white", mec=color, mew=1.2, label="brecha ≤ 1 % certificada")]
    if con_limite:
        h.append(Line2D([], [], ls="", marker="X", ms=7, mfc=CRITICO, mec="white", label="límite interno, sin certificar"))
    h.append(Line2D([], [], color=TINTA, lw=2, label="mediana (todas las corridas)"))
    h.append(Patch(facecolor=BANDA, edgecolor="none", label="rango intercuartílico"))
    return h + list(extra)


def banda_mediana(ax, x, v, c, medio_ancho=0.36, lim=None):
    q1, med, q3 = (cuantil_censurado(v, c, q) for q in (0.25, 0.5, 0.75))
    top = q3 if np.isfinite(q3) else lim
    ax.add_patch(Rectangle((x - medio_ancho, q1), 2 * medio_ancho, top - q1, facecolor=BANDA, edgecolor="none", zorder=1))
    if np.isfinite(med):
        ax.hlines(med, x - medio_ancho, x + medio_ancho, color=TINTA, lw=2, zorder=4)
    return q1, med, q3


# ------------------------------------------------------------------------ X3

def fig_x3(df):
    fig = plt.figure(figsize=(7.6, 4.9))
    ax = fig.add_axes([0.085, 0.2, 0.62, 0.6])
    grados = [4, 8, 12, 16]
    for i, g in enumerate(grados):
        d = df[df.grado == g]
        y = np.where(d.censurada, 300.0, d.tiempo_interno_s)
        q1, med, q3 = banda_mediana(ax, i, d.tiempo_interno_s.values, d.censurada.values, lim=300)
        marcar(ax, i + enjambre(y), y, d.estado.values, AZUL)
        ncert = int(d.certificada.sum())
        ax.text(i, 900, f"{ncert}/{len(d)}\ncertificadas", ha="center", va="center", fontsize=7.8,
                color=TINTA if ncert == len(d) else CRITICO)
        ax.text(i + 0.4, med, f"{num(med, 2 if med < 1 else 1)} s", va="center", ha="left", fontsize=7.6, color=TINTA)
    ax.axhline(300, color=CRITICO, lw=1.0, ls=(0, (4, 3)), zorder=0.5)
    ax.text(3.55, 300, "límite\n300 s", color=CRITICO, fontsize=7.2, va="center", ha="left")
    eje_log_y(ax, 0.1, 1600, [0.1, 1, 10, 100, 300, 1000])
    ax.set_xlim(-0.6, 3.75)
    ax.set_xticks(range(4), [f"grado {g}\n{g * 400:,} arcos".replace(",", ".") for g in grados])
    ax.set_ylabel("tiempo interno de E3 (s, escala log)")
    ax.legend(handles=leyenda_estados(AZUL), loc="upper left", bbox_to_anchor=(1.04, 1.0), fontsize=7.8,
              handlelength=1.6)
    r = pd.read_csv(TABLAS / "x3_resumen_por_grado.csv").set_index("grado")
    nota = ("Mediana calculada solo con\ncertificadas (sesgada a la baja):\n"
            f"grado 12: {num(r.loc[12, 'mediana_solo_certificadas_s'])} s\n"
            f"grado 16: {num(r.loc[16, 'mediana_solo_certificadas_s'])} s")
    ax.text(1.04, 0.22, nota, transform=ax.transAxes, fontsize=7.6, color=TINTA2, va="top")
    encabezado(fig, "X3 · Densidad: con grado 12–16 el tiempo de E3 se dispersa y aparecen límites",
               "Mulgen, 400 nodos, 10.000 productos solicitados (grado 4: 9.478–9.795 efectivos), semillas 1–10 por grado;\n"
               "n = 40 corridas, límite interno 300 s. Cada punto es una semilla.",
               "Mediana y RIC de las 10 corridas; las corridas en el límite cuentan como ≥ 300 s (se dibujan en 300 s;\n"
               "no son tiempos de solución). Escala log: tiempos de 0,17 s a ≥ 300 s. Fuente: analisis_final/tablas/x3_corridas_consolidadas.csv.")
    guardar(fig, "fig01_x3_tiempo_por_grado")


def fig_x3_esfuerzo(df):
    fig = plt.figure(figsize=(7.6, 4.3))
    a1 = fig.add_axes([0.08, 0.19, 0.4, 0.6])
    a2 = fig.add_axes([0.58, 0.19, 0.4, 0.6])
    for g in [4, 8, 12, 16]:
        d = df[df.grado == g]
        y = np.where(d.censurada, 300.0, d.tiempo_interno_s)
        for est, mk, fc in (("optimo", "o", RAMPA_GRADO[g]), ("brecha_1pct", "o", "white")):
            m = d.estado == est
            a1.scatter(d.columnas[m], y[m], s=22, marker=mk, facecolor=fc, edgecolor=RAMPA_GRADO[g] if fc == "white" else "white",
                       linewidth=1.1 if fc == "white" else 0.5, zorder=3)
        m = d.censurada
        a1.scatter(d.columnas[m], y[m], s=34, marker="X", facecolor=RAMPA_GRADO[g], edgecolor=CRITICO, linewidth=0.9, zorder=4)
    a1.set_xscale("log")
    a1.xaxis.set_major_locator(FixedLocator([1e4, 2e4, 5e4]))
    a1.xaxis.set_minor_locator(NullLocator())
    a1.xaxis.set_major_formatter(FuncFormatter(lambda v, _: num(v, 0)))
    eje_log_y(a1, 0.1, 400, [0.1, 1, 10, 100, 300])
    a1.grid(axis="x")
    a1.set_xlabel("columnas generadas (escala log)")
    a1.set_ylabel("tiempo interno (s, escala log)")
    a1.set_title("a) Tiempo frente a columnas", loc="left", fontsize=9, color=TINTA)
    h = [Line2D([], [], ls="", marker="o", ms=5.5, mfc=RAMPA_GRADO[g], mec="white", label=f"grado {g}") for g in RAMPA_GRADO]
    h.append(Line2D([], [], ls="", marker="X", ms=6.5, mfc=TENUE, mec=CRITICO, label="límite 300 s"))
    a1.legend(handles=h, loc="upper left", fontsize=7.4, handletextpad=0.2)
    for i, g in enumerate([4, 8, 12, 16]):
        d = df[df.grado == g]
        v = 100 * d.frac_maestro.values
        a2.add_patch(Rectangle((i - 0.33, np.quantile(v, .25)), 0.66, np.quantile(v, .75) - np.quantile(v, .25),
                               facecolor=BANDA, edgecolor="none", zorder=1))
        a2.hlines(np.median(v), i - 0.33, i + 0.33, color=TINTA, lw=2, zorder=4)
        off = np.linspace(-0.22, 0.22, len(v))[np.argsort(np.argsort(v))]
        a2.scatter(i + off, v, s=18, facecolor=np.where(d.censurada, CRITICO, RAMPA_GRADO[g]), edgecolor="white",
                   linewidth=0.5, zorder=3)
        a2.text(i + 0.36, np.median(v), f"{num(np.median(v), 0)} %", ha="left", va="center", fontsize=7.4)
    a2.set_ylim(0, 105)
    a2.set_xlim(-0.5, 3.75)
    a2.set_xticks(range(4), [f"grado {g}" for g in [4, 8, 12, 16]])
    a2.set_ylabel("tiempo en el problema maestro (% del interno)")
    a2.grid(axis="y")
    a2.set_axisbelow(True)
    a2.set_title("b) Peso del maestro (rojo: corrida en límite)", loc="left", fontsize=9, color=TINTA)
    encabezado(fig, "X3 · En redes densas crecen las columnas y el maestro concentra el tiempo",
               "Mismas 40 corridas de la figura 1. Columnas y tiempo de maestro extraídos de los logs; son medidas explicativas,\n"
               "no memoria. Asociación descriptiva: no establece causalidad.",
               "Fuente: experimentos/x3_formal/logs/*.txt (líneas «maestro=…s | pricing=…s»).", y=0.975)
    guardar(fig, "fig02_x3_esfuerzo_maestro_columnas")


# ------------------------------------------------------------------------ X4

def fig_x4_tiempo(df):
    fig = plt.figure(figsize=(7.6, 4.9))
    ax = fig.add_axes([0.09, 0.2, 0.74, 0.6])
    ns = [200, 400, 800, 1600, 3200]
    for metodo, color, despl in (("E3", AZUL, 0.0), ("GC base", NARANJO, 0.0)):
        d = df[df.metodo == metodo]
        meds, xs = [], []
        for n in ns:
            dd = d[d.nodos == n]
            if dd.empty:
                continue
            off = enjambre(dd.tiempo_interno_s, ancho=0.2, paso=0.04, dy=0.06)
            x = n * 2 ** (off + despl)
            marcar(ax, x, dd.tiempo_interno_s, dd.estado.values, color, s=16)
            meds.append(dd.tiempo_interno_s.median())
            xs.append(n)
        ax.plot(xs, meds, color=color, lw=2, zorder=5, solid_capstyle="round")
        ax.scatter(xs, meds, s=34, color=color, edgecolor="white", linewidth=1, zorder=6)
        for x, m in zip(xs, meds):
            ax.text(x * 1.12, m * (0.58 if metodo == "E3" else 1.45), f"{num(m, 2 if m < 1 else 1)} s", fontsize=7.4,
                    color=TINTA, ha="left", va="center", zorder=7)
        ax.text(xs[-1] * 1.32, meds[-1], metodo, color=color, fontsize=9.5, fontweight="bold", va="center")
    ax.set_xscale("log", base=2)
    ax.set_xlim(150, 5800)
    ka = df[df.metodo == "E3"].groupby("nodos").k_por_arcos.median()
    ax.xaxis.set_major_locator(FixedLocator(ns))
    ax.xaxis.set_minor_locator(NullLocator())
    ax.set_xticklabels([f"{num(n, 0)}\nK·|A| ≈ {num(ka[n] / 1e6, 0 if ka[n] > 1e7 else 1)} M" for n in ns])
    ax.set_xlabel("nodos N (escala log₂); K·|A| = variables equivalentes del LP por arcos con K efectivo")
    eje_log_y(ax, 0.04, 400, [0.1, 1, 10, 100])
    ax.set_ylabel("tiempo interno (s, escala log)")
    ax.legend(handles=leyenda_estados(TENUE, con_limite=False)[:2] +
              [Line2D([], [], color=TENUE, lw=2, marker="o", ms=5, mec="white", label="mediana por tamaño")],
              loc="upper left", fontsize=7.6)
    encabezado(fig, "X4 · Redes dispersas: E3 resuelve 3.200 nodos en 7,5 s (mediana)",
               "Mulgen grado 4, 25 productos solicitados por nodo, semillas 1–30. E3: 150 corridas (200–3.200 nodos);\n"
               "GC base: 90 corridas, solo hasta 800 nodos (no se extrapola). Todas certificadas; ninguna tocó el límite de 900 s.",
               "E3 certifica brecha ≤ 1 % (117/150 con óptimo exacto); GC base certifica por costo reducido. K·|A| no significa\n"
               "que E3 construya esas variables. Fuente: experimentos/x4_formal/ → analisis_final/tablas/x4_corridas_consolidadas.csv.")
    guardar(fig, "fig03_x4_tiempo_vs_tamano")


def fig_x4_aceleracion(df):
    par = pd.read_csv(TABLAS / "x4_aceleracion_por_semilla.csv")
    acel = pd.read_csv(TABLAS / "x4_aceleracion_resumen.csv")
    fig = plt.figure(figsize=(7.6, 4.7))
    ax = fig.add_axes([0.09, 0.17, 0.62, 0.62])
    for i, n in zip([0, 1.45, 2.9], [200, 400, 800]):
        d = par[par.nodos == n]
        off = enjambre(d.aceleracion_interna, ancho=0.3, paso=0.05, dy=0.04)
        marcar(ax, i + off, d.aceleracion_interna, d.estado_e3.values, AZUL, s=22)
        r = acel[(acel.nodos == n) & (acel.medida == "aceleracion_interna") & (acel.subconjunto == "todas")].iloc[0]
        ax.hlines(r.mediana, i - 0.36, i + 0.36, color=TINTA, lw=2, zorder=4)
        ax.vlines(i + 0.42, r.ic95_mediana_inf, r.ic95_mediana_sup, color=TINTA, lw=1.2, zorder=4)
        ax.hlines([r.ic95_mediana_inf, r.ic95_mediana_sup], i + 0.39, i + 0.45, color=TINTA, lw=1.2, zorder=4)
        ax.text(i + 0.5, r.mediana, f"{num(r.mediana, 0)}×\n[{num(r.ic95_mediana_inf, 0)}–{num(r.ic95_mediana_sup, 0)}]",
                fontsize=7.6, va="center", ha="left")
        rp = acel[(acel.nodos == n) & (acel.medida == "aceleracion_pared") & (acel.subconjunto == "todas")].iloc[0]
        ax.scatter([i - 0.45], [rp.mediana], marker="D", s=26, facecolor=TENUE, edgecolor="white", zorder=5)
    ax.axhline(1, color=EJE, lw=0.8)
    eje_log_y(ax, 1, 400, [1, 3, 10, 30, 100, 300])
    ax.set_xlim(-0.7, 3.75)
    ax.set_xticks([0, 1.45, 2.9], ["200 nodos", "400 nodos", "800 nodos"])
    ax.set_ylabel("aceleración T_GC base / T_E3 (×, escala log)")
    h = [Line2D([], [], ls="", marker="o", ms=5.5, mfc=AZUL, mec="white", label="semilla: E3 con óptimo exacto"),
         Line2D([], [], ls="", marker="o", ms=5.5, mfc="white", mec=AZUL, mew=1.2, label="semilla: E3 con brecha ≤ 1 %"),
         Line2D([], [], color=TINTA, lw=2, label="mediana de las razones"),
         Line2D([], [], color=TINTA, lw=1.2, marker="_", ms=6, label="IC 95 % de la mediana\n(remuestreo de semillas)"),
         Line2D([], [], ls="", marker="D", ms=5, mfc=TENUE, mec="white", label="mediana con tiempo de pared")]
    ax.legend(handles=h, loc="upper left", bbox_to_anchor=(1.02, 1.0), fontsize=7.6)
    ao = acel[(acel.medida == "aceleracion_interna") & (acel.subconjunto == "E3 óptimo exacto")].set_index("nodos")
    ax.text(1.03, 0.36, "Solo semillas con óptimo\nexacto en E3:\n" +
            "\n".join(f"{n} nodos: {num(ao.loc[n, 'mediana'], 0)}× (n = {int(ao.loc[n, 'n_pares'])})" for n in (200, 400, 800)) +
            "\nLa ventaja no proviene de\ndetenerse al 1 %.", transform=ax.transAxes, fontsize=7.4, color=TINTA2, va="top")
    encabezado(fig, "X4 · La aceleración pareada de E3 frente a GC base crece con el tamaño",
               "Razón por semilla sobre la misma instancia (n = 30 pares por tamaño), con tiempo interno de cada solver.\n"
               "Ninguna semilla fue más lenta con E3 (mínimos: 3,6×; 18×; 41×).",
               "El tiempo de pared incluye arranque de Python, lectura de la instancia y licencia; por eso su razón es menor.\n"
               "Fuente: analisis_final/tablas/x4_aceleracion_por_semilla.csv y x4_aceleracion_resumen.csv.")
    guardar(fig, "fig04_x4_aceleracion_pareada")


def fig_x4_explicacion(df):
    fig = plt.figure(figsize=(7.6, 4.9))
    a1 = fig.add_axes([0.2, 0.27, 0.42, 0.51])
    a2 = fig.add_axes([0.73, 0.27, 0.25, 0.51])
    comps = [("t_caminos_iniciales_s", "caminos iniciales", AQUA), ("suma_maestro_s", "maestro", VIOLETA),
             ("suma_pricing_s", "pricing y columnas", AMARILLO), ("resto", "resto", EJE)]
    filas = []
    for metodo in ("GC base", "E3"):
        for n in (200, 400, 800, 1600, 3200):
            d = df[(df.metodo == metodo) & (df.nodos == n)]
            if d.empty:
                continue
            tot = d.tiempo_interno_s.sum()
            v = {c: d[c].sum() / tot for c, _, _ in comps[:3]}
            v["resto"] = max(0.0, 1 - sum(v.values()))
            filas.append((f"{metodo} · {num(n, 0)}", v, d.tiempo_interno_s.median()))
    for j, (et, v, med) in enumerate(filas):
        izq = 0
        for c, nombre, color in comps:
            a1.barh(j, v[c], left=izq, height=0.72, color=color, edgecolor="white", linewidth=1)
            if v[c] > 0.09:
                a1.text(izq + v[c] / 2, j, f"{num(100 * v[c], 0)}", ha="center", va="center", fontsize=7,
                        color="white" if color in (VIOLETA,) else TINTA)
            izq += v[c]
        a1.text(1.02, j, f"{num(med, 2 if med < 1 else 1)} s", va="center", fontsize=7.2, color=TINTA2)
    a1.set_yticks(range(len(filas)), [f[0] for f in filas], fontsize=7.6)
    a1.invert_yaxis()
    a1.set_xlim(0, 1)
    a1.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{num(100 * v, 0)} %"))
    a1.set_xlabel("participación en el tiempo interno total del grupo")
    a1.set_title("a) Composición del tiempo (mediana total a la derecha)", loc="left", fontsize=8.6, color=TINTA)
    a1.legend(handles=[Patch(color=c, label=nm) for _, nm, c in comps], loc="upper center", ncol=4, fontsize=7.2,
              bbox_to_anchor=(0.45, -0.2), handlelength=1, columnspacing=0.8)
    for k, (metodo, color) in enumerate((("GC base", NARANJO), ("E3", AZUL))):
        d = df[df.metodo == metodo]
        med = d.groupby("nodos").iteraciones.median()
        a2.plot(med.index, med.values, color=color, lw=2, marker="o", ms=4.5, mec="white")
        a2.text(med.index[-1] * 1.15, med.values[-1], metodo, color=color, fontsize=8, fontweight="bold", va="center")
    a2.set_xscale("log", base=2)
    a2.xaxis.set_major_locator(FixedLocator([200, 800, 3200]))
    a2.xaxis.set_minor_locator(NullLocator())
    a2.xaxis.set_major_formatter(FuncFormatter(lambda v, _: num(v, 0)))
    a2.set_xlim(150, 6500)
    a2.set_ylim(0, 25)
    a2.grid(axis="y")
    a2.set_xlabel("nodos")
    a2.set_title("b) Iteraciones (mediana)", loc="left", fontsize=8.6, color=TINTA)
    encabezado(fig, "X4 · Composición del tiempo: E3 itera 3–5 veces; GC base, 11–22",
               "Suma de componentes medidos en los logs dividida por el tiempo interno total de las 30 semillas de cada grupo.\n"
               "E3 genera 1,01–1,04 columnas por producto; GC base, 1,12–1,22. Descriptivo: no aísla el aporte de cada mejora.",
               "«pricing y columnas» incluye costos reducidos y alta de columnas en Python; «resto» es construcción del maestro y otros.\n"
               "Fuente: analisis_final/tablas/x4_corridas_consolidadas.csv.")
    guardar(fig, "fig05_x4_descomposicion_iteraciones")


# --------------------------------------------------------------------- Waxman

def fig_waxman_familias(df):
    fig = plt.figure(figsize=(7.8, 5.3))
    ax = fig.add_axes([0.085, 0.27, 0.78, 0.52])
    xs = [0, 1, 2, 3.5, 4.5]
    res = pd.read_csv(TABLAS / "waxman_resumen_por_familia.csv").set_index("caso")
    for x, caso in zip(xs, FAMILIAS_WAXMAN):
        d = df[df.caso == caso]
        banda_mediana(ax, x, d.tiempo_interno_s.values, d.censurada.values, medio_ancho=0.38)
        marcar(ax, x + enjambre(d.tiempo_interno_s, ancho=0.36, paso=0.05, dy=0.05), d.tiempo_interno_s,
               d.estado.values, AZUL, s=18)
        ax.text(x, 330, f"{int(res.loc[caso, 'certificadas'])}/30 cert.", ha="center", fontsize=7.6, color=TINTA2)
    ax.axhline(120, color=CRITICO, lw=0.8, ls=(0, (4, 3)), zorder=0.5)
    ax.text(5.05, 120, "límite\n120 s", color=CRITICO, fontsize=7.2, va="center")
    ax.axvline(2.75, color=GRILLA, lw=0.8)
    ax.text(1, 0.065, "organización espacial (sin hubs)", ha="center", fontsize=7.8, color=TINTA2)
    ax.text(4, 0.065, "local + backbone (20 hubs, 60 % / 15 %)", ha="center", fontsize=7.8, color=TINTA2)
    eje_log_y(ax, 0.05, 500, [0.1, 1, 10, 100])
    ax.set_xlim(-0.55, 5.45)
    ax.set_xticks(xs, [ETIQUETAS_WAXMAN[c] + f"\nmediana {num(res.loc[c, 'mediana_todas_s'], 2 if res.loc[c, 'mediana_todas_s'] < 1 else 1)} s"
                       for c in FAMILIAS_WAXMAN], fontsize=7.8)
    ax.set_ylabel("tiempo interno de E3 (s, escala log)")
    ax.legend(handles=leyenda_estados(AZUL, con_limite=False), loc="upper left", bbox_to_anchor=(0.0, -0.25),
              ncol=4, fontsize=7.4, handletextpad=0.3, columnspacing=1.0)
    encabezado(fig, "Waxman · La topología cambia el tiempo de E3 en dos órdenes de magnitud",
               "400 nodos, 800 enlaces físicos (1.600 arcos), 10.000 productos; semillas 1001–1030 con posiciones y demandas comunes;\n"
               "n = 30 por familia (150 corridas, todas certificadas). Límite interno 120 s; protección externa 180 s.",
               "W1→W2 y W1→W3 cambian α y β a la vez. W4 y W5 comparten topología y demandas; W5 solo multiplica ×10 la capacidad hub–hub.\n"
               "Fuente: experimentos/waxman_formal/*/estado.json → analisis_final/tablas/waxman_corridas_consolidadas.csv.")
    guardar(fig, "fig06_waxman_tiempo_por_familia")


def fig_pareada(det, nombre, titulo, sub, etiq_a, etiq_b, texto_razon):
    fig = plt.figure(figsize=(7.8, 5.0))
    a1 = fig.add_axes([0.085, 0.25, 0.38, 0.53])
    a2 = fig.add_axes([0.6, 0.25, 0.36, 0.53])
    dism = det.clasificacion_cambio_z == "disminución certificada"
    aum = det.clasificacion_cambio_z == "aumento certificado"
    nd = ~(dism | aum)
    for m, fc, ec, lab in ((dism, AZUL, "white", "z baja (certificado)"), (aum, NARANJO, "white", "z sube (certificado)"),
                           (nd, "white", TENUE, "cambio de z no distinguible")):
        if m.sum():
            a1.scatter(det.t_A[m], det.t_B[m], s=26, facecolor=fc, edgecolor=ec, linewidth=1.1 if fc == "white" else 0.6,
                       zorder=3, label=f"{lab} ({int(m.sum())})")
    lo, hi = 0.1, 200
    a1.plot([lo, hi], [lo, hi], color=EJE, lw=1, zorder=1)
    for ax_ in (a1,):
        ax_.set_xscale("log")
        ax_.set_xlim(lo, hi)
        ax_.xaxis.set_major_locator(FixedLocator([0.1, 1, 10, 100]))
        ax_.xaxis.set_minor_locator(NullLocator())
        ax_.xaxis.set_major_formatter(FuncFormatter(fmt_log))
    eje_log_y(a1, lo, hi, [0.1, 1, 10, 100])
    a1.grid(axis="x")
    debajo = int((det.t_B < det.t_A).sum())
    a1.set_xlabel(f"tiempo {etiq_a} (s, log)")
    a1.set_ylabel(f"tiempo {etiq_b} (s, log)")
    a1.set_title(f"a) Tiempo por semilla: {debajo}/30 bajo la diagonal\n    ({etiq_b} más rápido); {texto_razon}",
                 loc="left", fontsize=8.4, color=TINTA)
    fig.legend(*a1.get_legend_handles_labels(), loc="lower left", bbox_to_anchor=(0.08, 0.085), fontsize=7.4, ncol=3,
               handletextpad=0.2, columnspacing=1.2)
    d = det.sort_values("cambio_z_pct").reset_index(drop=True)
    dism = d.clasificacion_cambio_z == "disminución certificada"
    aum = d.clasificacion_cambio_z == "aumento certificado"
    nd = ~(dism | aum)
    a2.hlines(d.index, 0, d.cambio_z_pct, color=GRILLA, lw=1, zorder=1)
    for m, fc, ec in ((dism, AZUL, "white"), (aum, NARANJO, "white"), (nd, "white", TENUE)):
        a2.scatter(d.cambio_z_pct[m], d.index[m], s=22, facecolor=fc, edgecolor=ec, linewidth=1.1 if fc == "white" else 0.5, zorder=3)
    a2.axvline(0, color=EJE, lw=0.9)
    med = float(np.median(det.cambio_z_pct))
    a2.axvline(med, color=TINTA, lw=1.4, zorder=2)
    a2.text(med + 0.8, -1.4, f"mediana {num(med, 1)} %", ha="left", va="center", fontsize=7.4)
    a2.set_ylim(-2.4, 30.6)
    a2.set_yticks([])
    a2.spines["left"].set_visible(False)
    a2.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{num(v, 0)} %"))
    a2.set_xlabel(f"cambio de z, {etiq_b} vs {etiq_a} (%)")
    a2.set_title("b) Cambio de congestión z por semilla\n    (ordenado)", loc="left", fontsize=8.4, color=TINTA)
    encabezado(fig, titulo, sub, "Cambio de z «certificado» cuando los intervalos [cota inferior, z] de ambas corridas no se traslapan; "
               "si se traslapan, la diferencia\nno se distingue de la aproximación ≤ 1 %. Fuente: analisis_final/tablas/waxman_comparaciones_por_semilla.csv.")
    guardar(fig, nombre)


# ------------------------------------------------------------ topología Waxman

def leer_enlaces(ruta):
    with open(ruta, encoding="utf-8") as fh:
        n, m, _ = map(int, fh.readline().split())
        enl = {}
        for _ in range(m):
            o, d, _, cap = (int(float(x)) for x in fh.readline().split()[:4])
            enl[(min(o, d), max(o, d))] = cap
    return enl


def puentes(enlaces, nodos):
    ady = {u: [] for u in nodos}
    for a, b in enlaces:
        ady[a].append(b)
        ady[b].append(a)
    disc, low, t, res = {}, {}, 0, []
    for s in nodos:
        if s in disc:
            continue
        disc[s] = low[s] = t
        t += 1
        pila = [(s, -1, iter(sorted(ady[s])))]
        while pila:
            u, p, it = pila[-1]
            for v in it:
                if v == p:
                    continue
                if v not in disc:
                    disc[v] = low[v] = t
                    t += 1
                    pila.append((v, u, iter(sorted(ady[v]))))
                    break
                low[u] = min(low[u], disc[v])
            else:
                pila.pop()
                if pila:
                    pu = pila[-1][0]
                    low[pu] = min(low[pu], low[u])
                    if low[u] > disc[pu]:
                        res.append((min(pu, u), max(pu, u)))
    return res


def fig_topologia(df, semilla=1001):
    rng = random.Random(f"{semilla}:posiciones")
    pos = {u + 1: (rng.random(), rng.random()) for u in range(400)}
    base = EXP / "waxman_formal"
    e1 = leer_enlaces(base / f"local_extrema_s{semilla}" / "instancia.txt")
    e4 = leer_enlaces(base / f"local_backbone_s{semilla}" / "instancia.txt")
    e5 = leer_enlaces(base / f"local_backbone_x10_s{semilla}" / "instancia.txt")
    backbone = {e for e in e4 if e5[e] != e4[e]}
    hubs = {u for e in backbone for u in e}
    fig = plt.figure(figsize=(8.6, 5.4))
    paneles = [("local_extrema", e1, set()), ("local_backbone", e4, hubs)]
    for k, (caso, enl, hb) in enumerate(paneles):
        ax = fig.add_axes([0.01 + k * 0.5, 0.2, 0.47, 0.6])
        pts = puentes(enl, list(pos))
        fila = df[(df.caso == caso) & (df.semilla == semilla)].iloc[0]
        assert len(pts) == fila.puentes, (caso, len(pts), fila.puentes)
        crit = tuple(sorted(eval(fila.puente_critico)))
        acceso = [e for e in enl if (e[0] in hb) != (e[1] in hb)]
        normal = [e for e in enl if e not in backbone and e not in acceso and e not in pts]
        seg = lambda es: [(pos[a], pos[b]) for a, b in es]
        ax.add_collection(LineCollection(seg(normal), colors="#b9b8b1", linewidths=0.55, zorder=1))
        if hb:
            ax.add_collection(LineCollection(seg([e for e in acceso if e not in pts]), colors=AQUA, linewidths=0.7, zorder=2))
            ax.add_collection(LineCollection(seg(backbone), colors=AZUL, linewidths=2.0, zorder=3))
        ax.add_collection(LineCollection(seg(pts), colors=CRITICO, linewidths=1.3, zorder=4))
        ax.add_collection(LineCollection(seg([crit]), colors=CRITICO, linewidths=3.2, zorder=5))
        xs = np.array([pos[u] for u in pos if u not in hb])
        ax.scatter(xs[:, 0], xs[:, 1], s=4, color="#6b6a65", zorder=6, linewidths=0)
        if hb:
            xh = np.array([pos[u] for u in hb])
            ax.scatter(xh[:, 0], xh[:, 1], s=34, marker="s", facecolor=NARANJO, edgecolor="white", linewidth=0.7, zorder=7)
        mx, my = (np.array(pos[crit[0]]) + np.array(pos[crit[1]])) / 2
        ax.annotate("puente crítico", (mx, my), xytext=(mx + (0.12 if mx < 0.7 else -0.3), my + (0.08 if my < 0.8 else -0.1)),
                    fontsize=7.4, color=CRITICO, arrowprops=dict(arrowstyle="-", color=CRITICO, lw=0.8), zorder=8)
        ax.set_xlim(-0.02, 1.02)
        ax.set_ylim(-0.02, 1.02)
        ax.set_aspect("equal")
        ax.axis("off")
        nombre = "W1 local (α=0,04, β=1)" if caso == "local_extrema" else "W4 local + backbone ×1 (20 hubs)"
        ax.set_title(nombre, loc="left", fontsize=9.2, color=TINTA, fontweight="bold")
        info = (f"800 enlaces · {int(fila.puentes)} puentes · z = {num(fila.z, 1)} · {num(fila.tiempo_interno_s, 2)} s\n"
                f"cota de puentes / z = {num(fila.cota_puentes_sobre_z, 2)}")
        if hb:
            info += (f" · {len(backbone)} enlaces hub–hub\nacceso obligatorio: {num(fila.acceso_obligatorio_pct, 0)} % de los normales; "
                     f"con algún hub vecino: {num(fila.cobertura_backbone_pct, 0)} %")
        ax.text(0.0, -0.035, info, transform=ax.transAxes, fontsize=7.2, color=TINTA2, va="top")
    h = [Line2D([], [], color="#b9b8b1", lw=1, label="enlace"), Line2D([], [], color=CRITICO, lw=1.4, label="puente"),
         Line2D([], [], color=AZUL, lw=2, label="enlace hub–hub (backbone)"), Line2D([], [], color=AQUA, lw=1, label="enlace hub–normal"),
         Line2D([], [], ls="", marker="s", ms=6, mfc=NARANJO, mec="white", label="hub")]
    fig.legend(handles=h, loc="lower center", ncol=5, fontsize=7.6, bbox_to_anchor=(0.5, 0.0))
    encabezado(fig, f"Waxman · Semilla {semilla}: local frente a local + backbone, mismas posiciones",
               "Semilla elegida por ser la primera de la muestra, no por su resultado. Posiciones reconstruidas con la secuencia del generador y\n"
               "verificadas contra la longitud media del diagnóstico; puentes recalculados y verificados contra diagnostico.json.", y=0.985)
    guardar(fig, f"fig09_waxman_topologia_s{semilla}")


# ---------------------------------------------------------- resumen visual

def fig_resumen(x3, x4, wx):
    fig = plt.figure(figsize=(13.33, 7.5))
    fig.text(0.02, 0.955, "E3 en tres sensibilidades: qué se sostiene con los datos", fontsize=19, fontweight="bold")
    fig.text(0.02, 0.905, "Tiempo interno por corrida (escala log). 430 corridas formales en una sola sesión secuencial; memoria no registrada en estas baterías.",
             fontsize=11, color=TINTA2)
    cajas = [[0.05, 0.14, 0.27, 0.56], [0.39, 0.14, 0.27, 0.56], [0.72, 0.14, 0.27, 0.56]]
    titulares = [("Densidad (X3)", "Más arcos, más dispersión: con grado\n12–16, 2 de 10 sin certificar en 300 s"),
                 ("Escalabilidad (X4)", "3.200 nodos en 7,5 s (mediana);\n26×–124× más rápido que GC base"),
                 ("Topología (Waxman)", "Local ≈ 19× más lenta que intermedia;\nhubs ×10: 0,29× el tiempo (pareado)")]
    axs = [fig.add_axes(c) for c in cajas]
    for ax, (eti, tit), c in zip(axs, titulares, cajas):
        fig.text(c[0] - 0.02, 0.83, eti.upper(), fontsize=10, color=TENUE, fontweight="bold")
        fig.text(c[0] - 0.02, 0.765, tit, fontsize=12.5, color=TINTA, va="center", linespacing=1.3)
    ax = axs[0]
    for i, g in enumerate([4, 8, 12, 16]):
        d = x3[x3.grado == g]
        y = np.where(d.censurada, 300.0, d.tiempo_interno_s)
        banda_mediana(ax, i, d.tiempo_interno_s.values, d.censurada.values, lim=300)
        marcar(ax, i + enjambre(y), y, d.estado.values, AZUL, s=30)
    ax.axhline(300, color=CRITICO, lw=1, ls=(0, (4, 3)))
    ax.text(3.45, 420, "límite 300 s", color=CRITICO, fontsize=9, ha="right")
    eje_log_y(ax, 0.1, 700, [0.1, 1, 10, 100])
    ax.set_xticks(range(4), ["grado 4", "8", "12", "16"], fontsize=10)
    ax.set_ylabel("segundos", fontsize=10)
    ax = axs[1]
    for metodo, color in (("E3", AZUL), ("GC base", NARANJO)):
        d = x4[x4.metodo == metodo]
        for n, dd in d.groupby("nodos"):
            ax.scatter(n * 2 ** enjambre(dd.tiempo_interno_s, ancho=0.18, paso=0.04, dy=0.06), dd.tiempo_interno_s, s=12,
                       color=color, alpha=0.55, linewidths=0)
        med = d.groupby("nodos").tiempo_interno_s.median()
        ax.plot(med.index, med.values, color=color, lw=2.6, marker="o", ms=6, mec="white")
        ax.text(med.index[-1] * 1.25, med.values[-1], metodo, color=color, fontsize=11, fontweight="bold", va="center")
    ax.set_xscale("log", base=2)
    ax.xaxis.set_major_locator(FixedLocator([200, 400, 800, 1600, 3200]))
    ax.xaxis.set_minor_locator(NullLocator())
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: num(v, 0)))
    ax.set_xlim(150, 6000)
    ax.set_xlabel("nodos (grado 4)", fontsize=10)
    eje_log_y(ax, 0.05, 300, [0.1, 1, 10, 100])
    ax = axs[2]
    xs = [0, 1, 2, 3.4, 4.4]
    for x, caso in zip(xs, FAMILIAS_WAXMAN):
        d = wx[wx.caso == caso]
        banda_mediana(ax, x, d.tiempo_interno_s.values, d.censurada.values, medio_ancho=0.38)
        marcar(ax, x + enjambre(d.tiempo_interno_s, ancho=0.34, paso=0.06, dy=0.06), d.tiempo_interno_s, d.estado.values, AZUL, s=16)
    eje_log_y(ax, 0.1, 300, [0.1, 1, 10, 100])
    ax.set_xticks(xs, ["local", "interm.", "larga", "backb.\n×1", "backb.\n×10"], fontsize=9.5)
    for ax in axs:
        ax.tick_params(labelsize=9.5)
    fig.text(0.02, 0.025, "Relleno = óptimo certificado · hueco = brecha ≤ 1 % · × rojo = límite interno sin certificar · barra = mediana de todas las corridas "
             "(límites como ≥ 300 s) · banda = RIC.\nRazones pareadas por semilla (medianas). Backbone ×10 vs ×1: 0,29× el tiempo y −25 % de congestión (n = 30). "
             "X4 base solo hasta 800 nodos.", fontsize=9.2, color=TINTA2, linespacing=1.4)
    guardar(fig, "fig00_resumen_visual_presentacion")


def main():
    x3 = pd.read_csv(TABLAS / "x3_corridas_consolidadas.csv")
    x4 = pd.read_csv(TABLAS / "x4_corridas_consolidadas.csv")
    wx = pd.read_csv(TABLAS / "waxman_corridas_consolidadas.csv")
    comp = pd.read_csv(TABLAS / "waxman_comparaciones_pareadas.csv").set_index("id")
    det = pd.read_csv(TABLAS / "waxman_comparaciones_por_semilla.csv")
    fig_x3(x3)
    fig_x3_esfuerzo(x3)
    fig_x4_tiempo(x4)
    fig_x4_aceleracion(x4)
    fig_x4_explicacion(x4)
    fig_waxman_familias(wx)
    c5, c4 = comp.loc["C5"], comp.loc["C4"]
    fig_pareada(det[det.id == "C5"], "fig07_waxman_backbone_x1_vs_x10",
                f"W4→W5 · Hubs ×10: z nunca sube y el tiempo baja en {30 - round(30 * c5.tiempo_frac_mayor_que_1)} de 30 semillas",
                "Misma topología y mismas demandas por semilla (n = 30 pares); solo cambia la capacidad de 24–29 enlaces hub–hub.\n"
                f"Razón de tiempos ×10/×1: mediana {num(c5.tiempo_mediana, 2)} [IC 95 % {num(c5.tiempo_ic95_mediana_inf, 2)}–"
                f"{num(c5.tiempo_ic95_mediana_sup, 2)}]; {round(30 * c5.tiempo_frac_mayor_que_1)} de 30 semillas fueron más lentas con ×10.",
                "×1", "×10", f"mediana T×10/T×1 = {num(c5.tiempo_mediana, 2)}")
    fig_pareada(det[det.id == "C4"], "fig08_waxman_local_vs_backbone",
                f"W1→W4 · Backbone ×1: z baja en {int(c4['z_disminución certificada'])} de 30 semillas, pero el tiempo suele subir",
                "Mismas posiciones y demandas; cambia la topología: los enlaces obligatorios consumen el presupuesto fijo de 800 enlaces.\n"
                f"Razón de tiempos W4/W1: mediana {num(c4.tiempo_mediana, 2)} [IC 95 % {num(c4.tiempo_ic95_mediana_inf, 2)}–"
                f"{num(c4.tiempo_ic95_mediana_sup, 2)}]; {30 - round(30 * c4.tiempo_frac_mayor_que_1)} de 30 semillas fueron más rápidas con backbone.",
                "W1 local", "W4 backbone", f"mediana T_W4/T_W1 = {num(c4.tiempo_mediana, 2)}")
    fig_topologia(wx, 1001)
    fig_resumen(x3, x4, wx)


if __name__ == "__main__":
    main()
