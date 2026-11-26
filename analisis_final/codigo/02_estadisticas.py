#!/usr/bin/env python3
"""Paso 2: estadísticas descriptivas, razones pareadas y remuestreo por semilla.

Lee las tablas consolidadas de analisis_final/tablas/ (paso 1) y escribe
resúmenes en la misma carpeta, más cifras_clave.json para el informe.

Convenciones:
- Tiempos = tiempo interno informado por el solver (s), salvo que se diga pared.
- Corridas censuradas (límite interno / timeout externo) se tratan como
  "≥ límite": entran en las medianas de "todas las corridas" solo como valores
  superiores; si un cuantil cae sobre ellas se informa como inf (≥ límite).
- "mediana_solo_certificadas" se rotula explícitamente.
- Aceleración = T_base / T_E3 por semilla coincidente (misma instancia).
- IC 95 %: percentil de remuestreo de semillas (B = 10 000; 2 000 en ajustes).
"""
from __future__ import annotations

import json
import sys
import warnings
import zlib
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from comun import (B_BOOTSTRAP, FAMILIAS_WAXMAN, SEMILLA_BOOTSTRAP, TABLAS, cuantil_censurado,  # noqa: E402
                   ic_mediana_censurada, ols_loglog, resumen_diferencias, resumen_razones)


warnings.filterwarnings("ignore", message="Mean of empty slice")  # familias sin hubs


def spearman(a, b):
    """Correlación de rangos (Pearson sobre rangos promedio), sin scipy."""
    return float(pd.Series(a).rank().corr(pd.Series(b).rank()))


def rng_para(nombre):
    return np.random.default_rng([SEMILLA_BOOTSTRAP, zlib.crc32(nombre.encode())])


def resumen_tiempos(g, nombre):
    v = g.tiempo_interno_s.to_numpy(float)
    c = g.censurada.to_numpy(bool)
    cert = g.certificada.to_numpy(bool)
    lo, hi = ic_mediana_censurada(v, c, rng_para(nombre))
    return dict(
        n=len(g), certificadas=int(cert.sum()), tasa_certificacion=cert.mean(),
        n_optimo=int((g.estado == "optimo").sum()), n_brecha_1pct=int((g.estado == "brecha_1pct").sum()),
        n_limite_interno=int((g.estado == "limite_interno").sum()),
        n_timeout_externo=int((g.estado == "timeout_externo").sum()),
        n_error=int((~g.estado.isin(["optimo", "brecha_1pct", "limite_interno", "timeout_externo"])).sum()),
        mediana_todas_s=cuantil_censurado(v, c, 0.5), q1_todas_s=cuantil_censurado(v, c, 0.25),
        q3_todas_s=cuantil_censurado(v, c, 0.75), ic95_mediana_inf_s=lo, ic95_mediana_sup_s=hi,
        maximo_todas_s=(np.inf if c.any() else v.max()),
        mediana_solo_certificadas_s=float(np.median(v[cert])) if cert.any() else np.nan,
        maximo_certificadas_s=float(v[cert].max()) if cert.any() else np.nan,
        minimo_s=float(v.min()),
        mediana_pared_s=cuantil_censurado(g.tiempo_pared_s.to_numpy(float), c, 0.5),
        iteraciones_mediana=float(g.iteraciones.median()), iteraciones_max=int(g.iteraciones.max()),
        columnas_mediana=float(g.columnas.median()), columnas_max=int(g.columnas.max()),
        columnas_por_producto_mediana=float(g.columnas_por_producto.median()),
        frac_maestro_mediana=float(g.frac_maestro.median()),
    )


# ----------------------------------------------------------------------- X3

def x3(cifras):
    df = pd.read_csv(TABLAS / "x3_corridas_consolidadas.csv")
    filas = []
    for grado, g in df.groupby("grado"):
        r = dict(grado=grado, arcos=int(g.arcos_generados.iloc[0]))
        r.update(productos_efectivos_mediana=g.productos_efectivos.median(),
                 productos_efectivos_min=g.productos_efectivos.min(),
                 productos_efectivos_max=g.productos_efectivos.max())
        r.update(resumen_tiempos(g, f"x3_{grado}"))
        zc = g.z.where(g.z.notna(), g.cota_superior)
        r.update(z_mediana=float(g.z.median()), z_min=float(g.z.min()), z_max=float(g.z.max()),
                 z_mediana_incluye_cota_sup_en_limites=float(zc.median()),
                 spearman_z_vs_tiempo=spearman(zc.values, g.tiempo_interno_s.values))
        filas.append(r)
    res = pd.DataFrame(filas)
    res.to_csv(TABLAS / "x3_resumen_por_grado.csv", index=False)
    lim = df[df.censurada][["grado", "semilla", "tiempo_interno_s", "iteraciones", "columnas", "cota_superior",
                            "cota_inferior", "gap_pct", "tipo_limite", "frac_maestro"]]
    lim.to_csv(TABLAS / "x3_corridas_en_limite.csv", index=False)
    # Correlación de rangos agrupada (dentro de grado): exploratoria.
    zc = df.z.where(df.z.notna(), df.cota_superior)
    rz = zc.groupby(df.grado).rank()
    ri = df.tiempo_interno_s.groupby(df.grado).rank()
    cifras["x3"] = dict(
        corridas=len(df), certificadas=int(df.certificada.sum()), limites=int(df.censurada.sum()),
        por_grado=res.set_index("grado")[["certificadas", "n", "mediana_todas_s", "mediana_solo_certificadas_s",
                                          "q1_todas_s", "q3_todas_s", "ic95_mediana_inf_s", "ic95_mediana_sup_s",
                                          "iteraciones_mediana", "columnas_mediana", "z_mediana",
                                          "frac_maestro_mediana"]].to_dict("index"),
        spearman_rangos_dentro_de_grado_z_tiempo=float(rz.corr(ri)),
        gap_final_limites_pct=lim.gap_pct.tolist(),
        frac_maestro_limites=lim.frac_maestro.tolist(),
        frac_maestro_mediana_grados_12_16=float(df[df.grado >= 12].frac_maestro.median()),
    )
    return res


# ----------------------------------------------------------------------- X4

def x4(cifras):
    df = pd.read_csv(TABLAS / "x4_corridas_consolidadas.csv")
    filas = []
    for (metodo, n), g in df.groupby(["metodo", "nodos"]):
        r = dict(metodo=metodo, nodos=n, arcos=int(g.arcos_generados.iloc[0]),
                 productos_efectivos_mediana=g.productos_efectivos.median(),
                 k_por_arcos_mediana=g.k_por_arcos.median())
        r.update(resumen_tiempos(g, f"x4_{metodo}_{n}"))
        r.update(caminos_iniciales_mediana_s=g.t_caminos_iniciales_s.median(),
                 maestro_mediana_s=g.suma_maestro_s.median(), pricing_mediana_s=g.suma_pricing_s.median(),
                 resto_mediana_s=(g.tiempo_interno_s - g.t_caminos_iniciales_s - g.suma_maestro_s -
                                  g.suma_pricing_s).median(),
                 sobrecosto_pared_mediana_s=(g.tiempo_pared_s - g.tiempo_interno_s).median())
        filas.append(r)
    res = pd.DataFrame(filas).sort_values(["metodo", "nodos"])
    res.to_csv(TABLAS / "x4_resumen_por_tamano.csv", index=False)

    e3 = df[df.metodo == "E3"].set_index(["nodos", "semilla"])
    ba = df[df.metodo == "GC base"].set_index(["nodos", "semilla"])
    par = ba.join(e3, lsuffix="_base", rsuffix="_e3", how="inner").reset_index()
    par["aceleracion_interna"] = par.tiempo_interno_s_base / par.tiempo_interno_s_e3
    par["aceleracion_pared"] = par.tiempo_pared_s_base / par.tiempo_pared_s_e3
    cols = ["nodos", "semilla", "tiempo_interno_s_base", "tiempo_interno_s_e3", "aceleracion_interna",
            "tiempo_pared_s_base", "tiempo_pared_s_e3", "aceleracion_pared", "estado_e3", "z_base", "z_e3",
            "cota_inferior_e3", "iteraciones_base", "iteraciones_e3", "columnas_base", "columnas_e3",
            "t_caminos_iniciales_s_base", "t_caminos_iniciales_s_e3"]
    par[cols].to_csv(TABLAS / "x4_aceleracion_por_semilla.csv", index=False)
    filas = []
    for n, g in par.groupby("nodos"):
        for medida in ("aceleracion_interna", "aceleracion_pared"):
            for sub, gg in (("todas", g), ("E3 óptimo exacto", g[g.estado_e3 == "optimo"]),
                            ("E3 brecha ≤1 %", g[g.estado_e3 == "brecha_1pct"])):
                if len(gg) < 3:
                    continue
                r = dict(nodos=n, medida=medida, subconjunto=sub)
                r.update(resumen_razones(gg[medida], rng_para(f"x4_acel_{n}_{medida}_{sub}")))
                filas.append(r)
    acel = pd.DataFrame(filas)
    acel.to_csv(TABLAS / "x4_aceleracion_resumen.csv", index=False)

    # Crecimiento empírico: ajuste log-log por corridas y exponentes locales.
    crec = []
    for metodo, g in df.groupby("metodo"):
        g = g[g.certificada]
        b, a, r2 = ols_loglog(g.k_por_arcos.to_numpy(float), g.tiempo_interno_s.to_numpy(float))
        bn, _, r2n = ols_loglog(g.nodos.to_numpy(float), g.tiempo_interno_s.to_numpy(float))
        rng = rng_para(f"x4_beta_{metodo}")
        grupos = [gg for _, gg in g.groupby("nodos")]
        bs, bsn = [], []
        for _ in range(2000):
            m = pd.concat([gg.iloc[rng.integers(0, len(gg), len(gg))] for gg in grupos])
            bs.append(ols_loglog(m.k_por_arcos.to_numpy(float), m.tiempo_interno_s.to_numpy(float))[0])
            bsn.append(ols_loglog(m.nodos.to_numpy(float), m.tiempo_interno_s.to_numpy(float))[0])
        med = g.groupby("nodos").agg(t=("tiempo_interno_s", "median"), ka=("k_por_arcos", "median"))
        bm, _, r2m = ols_loglog(med.ka.to_numpy(float), med.t.to_numpy(float))
        crec.append(dict(metodo=metodo, tramo="global (corridas)", n_corridas=len(g),
                         beta_vs_KA=b, ic95_inf=np.percentile(bs, 2.5), ic95_sup=np.percentile(bs, 97.5), r2=r2,
                         beta_vs_N=bn, ic95_N_inf=np.percentile(bsn, 2.5), ic95_N_sup=np.percentile(bsn, 97.5),
                         r2_N=r2n, beta_medianas_vs_KA=bm, r2_medianas=r2m))
        ns = sorted(g.nodos.unique())
        for n0, n1 in zip(ns, ns[1:]):
            g0, g1 = g[g.nodos == n0], g[g.nodos == n1]
            def expo(t0, t1, k0, k1):
                return np.log(np.median(t1) / np.median(t0)) / np.log(np.median(k1) / np.median(k0))
            e = expo(g0.tiempo_interno_s, g1.tiempo_interno_s, g0.k_por_arcos, g1.k_por_arcos)
            boot = []
            for _ in range(2000):
                i0 = rng.integers(0, len(g0), len(g0)); i1 = rng.integers(0, len(g1), len(g1))
                boot.append(expo(g0.tiempo_interno_s.values[i0], g1.tiempo_interno_s.values[i1],
                                 g0.k_por_arcos.values[i0], g1.k_por_arcos.values[i1]))
            crec.append(dict(metodo=metodo, tramo=f"{n0}→{n1}", n_corridas=len(g0) + len(g1), beta_vs_KA=e,
                             ic95_inf=np.percentile(boot, 2.5), ic95_sup=np.percentile(boot, 97.5),
                             factor_tiempo_mediano=float(g1.tiempo_interno_s.median() / g0.tiempo_interno_s.median()),
                             factor_KA_mediano=float(g1.k_por_arcos.median() / g0.k_por_arcos.median())))
    crec = pd.DataFrame(crec)
    crec.to_csv(TABLAS / "x4_crecimiento_empirico.csv", index=False)

    a = acel[(acel.medida == "aceleracion_interna") & (acel.subconjunto == "todas")].set_index("nodos")
    ap = acel[(acel.medida == "aceleracion_pared") & (acel.subconjunto == "todas")].set_index("nodos")
    ao = acel[(acel.medida == "aceleracion_interna") & (acel.subconjunto == "E3 óptimo exacto")].set_index("nodos")
    cifras["x4"] = dict(
        corridas=len(df), certificadas=int(df.certificada.sum()),
        resumen=res.set_index(["metodo", "nodos"])[["mediana_todas_s", "q1_todas_s", "q3_todas_s", "maximo_todas_s",
                                                     "iteraciones_mediana", "columnas_por_producto_mediana",
                                                     "k_por_arcos_mediana", "n_optimo", "n_brecha_1pct",
                                                     "caminos_iniciales_mediana_s", "maestro_mediana_s",
                                                     "pricing_mediana_s"]].reset_index().to_dict("records"),
        aceleracion_interna=a[["mediana", "q1", "q3", "minimo", "maximo", "media_geometrica",
                               "ic95_mediana_inf", "ic95_mediana_sup"]].to_dict("index"),
        aceleracion_pared=ap[["mediana", "minimo", "maximo", "ic95_mediana_inf", "ic95_mediana_sup"]].to_dict("index"),
        aceleracion_interna_E3_optimo=ao[["n_pares", "mediana", "minimo"]].to_dict("index"),
        crecimiento=crec.to_dict("records"),
    )
    return res, acel, crec


# ------------------------------------------------------------------- Waxman

COMPARACIONES = [
    ("C1", "local_extrema", "intermedia", "W1 local vs W2 intermedia (cambian α y β)"),
    ("C2", "local_extrema", "larga", "W1 local vs W3 larga (cambian α y β)"),
    ("C3", "larga", "intermedia", "W3 larga vs W2 intermedia (solo cambia α; β=0,40)"),
    ("C4", "local_backbone", "local_extrema", "W4 backbone ×1 vs W1 local (cambia topología y presupuesto)"),
    ("C5", "local_backbone_x10", "local_backbone", "W5 ×10 vs W4 ×1 (misma topología y demandas)"),
]


def clasificar_z(ub_b, lb_b, ub_a, lb_a):
    if ub_b < lb_a * (1 - 1e-9):
        return "disminución certificada"
    if lb_b > ub_a * (1 + 1e-9):
        return "aumento certificado"
    return "no distinguible (brechas)"


def waxman(cifras):
    df = pd.read_csv(TABLAS / "waxman_corridas_consolidadas.csv")
    filas = []
    for caso in FAMILIAS_WAXMAN:
        g = df[df.caso == caso]
        r = dict(caso=caso)
        r.update(resumen_tiempos(g, f"wax_{caso}"))
        r.update(z_mediana=g.z.median(), z_q1=g.z.quantile(.25), z_q3=g.z.quantile(.75), z_min=g.z.min(),
                 z_max=g.z.max(), gap_mediana_pct=g.gap_pct.median(), gap_max_pct=g.gap_pct.max())
        filas.append(r)
    res = pd.DataFrame(filas)
    res.to_csv(TABLAS / "waxman_resumen_por_familia.csv", index=False)

    est = []
    for caso in FAMILIAS_WAXMAN:
        g = df[df.caso == caso]
        fila = dict(caso=caso)
        for col in ["puentes", "cobertura_backbone_pct", "acceso_obligatorio_pct", "doble_acceso_obligatorio_pct",
                    "normales_con_dos_hubs", "grado_medio_hubs", "grado_medio_normales", "grado_max", "grado_cv",
                    "longitud_media", "clustering", "capacidad_media_enlace", "capacidad_total_arcos",
                    "demanda_total", "intentos_generacion"]:
            fila[f"{col}_mediana"] = g[col].median()
            fila[f"{col}_min"] = g[col].min()
            fila[f"{col}_max"] = g[col].max()
        fila["puente_coincide_con_z"] = int((g.puente_explica_optimo == "coincide").sum())
        fila["puente_no_coincide"] = int((g.puente_explica_optimo == "no coincide").sum())
        fila["puente_indeterminado"] = int(g.puente_explica_optimo.str.startswith("indeterminado").sum())
        fila["cota_puentes_sobre_z_mediana"] = g.cota_puentes_sobre_z.median()
        fila["cota_puentes_sobre_z_min"] = g.cota_puentes_sobre_z.min()
        est.append(fila)
    est = pd.DataFrame(est)
    est.to_csv(TABLAS / "waxman_estructura_y_puentes_por_familia.csv", index=False)

    # Tiempo según si un puente explica el óptimo (descriptivo, no causal).
    tp = (df.groupby(["caso", "puente_explica_optimo"]).tiempo_interno_s
          .agg(["count", "median", "min", "max"]).reset_index())
    tp.to_csv(TABLAS / "waxman_tiempo_segun_puente.csv", index=False)

    piv = {c: df[df.caso == c].set_index("semilla") for c in FAMILIAS_WAXMAN}
    comp, detalles = [], {}
    for cid, b, a, desc in COMPARACIONES:
        B, A = piv[b], piv[a]
        semillas = sorted(set(A.index) & set(B.index))
        B, A = B.loc[semillas], A.loc[semillas]
        razon_t = B.tiempo_interno_s / A.tiempo_interno_s
        razon_p = B.tiempo_pared_s / A.tiempo_pared_s
        dz = 100 * (B.z / A.z - 1)
        clas = [clasificar_z(B.z[s], B.cota_inferior[s], A.z[s], A.cota_inferior[s]) for s in semillas]
        det = pd.DataFrame(dict(semilla=semillas, t_A=A.tiempo_interno_s.values, t_B=B.tiempo_interno_s.values,
                                razon_tiempo_B_sobre_A=razon_t.values, razon_pared=razon_p.values,
                                z_A=A.z.values, lb_A=A.cota_inferior.values, estado_A=A.estado.values,
                                z_B=B.z.values, lb_B=B.cota_inferior.values, estado_B=B.estado.values,
                                cambio_z_pct=dz.values, clasificacion_cambio_z=clas,
                                iter_A=A.iteraciones.values, iter_B=B.iteraciones.values,
                                col_A=A.columnas.values, col_B=B.columnas.values,
                                puentes_A=A.puentes.values, puentes_B=B.puentes.values,
                                puente_explica_A=A.puente_explica_optimo.values,
                                puente_explica_B=B.puente_explica_optimo.values))
        detalles[cid] = det
        rt = resumen_razones(razon_t, rng_para(f"wax_{cid}_t"))
        rp = resumen_razones(razon_p, rng_para(f"wax_{cid}_p"))
        rz = resumen_diferencias(dz, rng_para(f"wax_{cid}_z"))
        fila = dict(id=cid, comparacion=desc, A=a, B=b, n_pares=len(semillas))
        fila.update({f"tiempo_{k}": v for k, v in rt.items() if k != "n_pares"})
        fila.update({f"pared_{k}": v for k, v in rp.items() if k in ("mediana", "ic95_mediana_inf",
                                                                      "ic95_mediana_sup", "frac_mayor_que_1")})
        fila.update({f"cambio_z_pct_{k}": v for k, v in rz.items() if k != "n_pares"})
        for etiqueta in ("disminución certificada", "aumento certificado", "no distinguible (brechas)"):
            fila[f"z_{etiqueta}"] = clas.count(etiqueta)
        fila["razon_iteraciones_mediana"] = float(np.median(B.iteraciones / A.iteraciones))
        fila["razon_columnas_mediana"] = float(np.median(B.columnas / A.columnas))
        comp.append(fila)
    comp = pd.DataFrame(comp)
    comp.to_csv(TABLAS / "waxman_comparaciones_pareadas.csv", index=False)
    detalles["C5"].to_csv(TABLAS / "waxman_backbone_x1_vs_x10_por_semilla.csv", index=False)
    detalles["C4"].to_csv(TABLAS / "waxman_local_vs_backbone_por_semilla.csv", index=False)
    pd.concat([d.assign(id=k) for k, d in detalles.items()]).to_csv(
        TABLAS / "waxman_comparaciones_por_semilla.csv", index=False)

    c5 = detalles["C5"]
    cifras["waxman"] = dict(
        corridas=len(df), certificadas=int(df.certificada.sum()),
        resumen=res.set_index("caso")[["n_optimo", "n_brecha_1pct", "mediana_todas_s", "q1_todas_s", "q3_todas_s",
                                       "maximo_todas_s", "ic95_mediana_inf_s", "ic95_mediana_sup_s",
                                       "iteraciones_mediana", "columnas_mediana", "z_mediana",
                                       "frac_maestro_mediana"]].to_dict("index"),
        comparaciones=comp.set_index("id")[["comparacion", "tiempo_mediana", "tiempo_ic95_mediana_inf",
                                             "tiempo_ic95_mediana_sup", "tiempo_media_geometrica",
                                             "tiempo_ic95_mgeom_inf", "tiempo_ic95_mgeom_sup",
                                             "tiempo_frac_mayor_que_1", "cambio_z_pct_mediana",
                                             "cambio_z_pct_minimo", "cambio_z_pct_maximo",
                                             "z_disminución certificada", "z_aumento certificado",
                                             "z_no distinguible (brechas)", "razon_iteraciones_mediana",
                                             "razon_columnas_mediana"]].to_dict("index"),
        estructura=est.set_index("caso")[["puentes_mediana", "cobertura_backbone_pct_mediana",
                                          "acceso_obligatorio_pct_mediana", "doble_acceso_obligatorio_pct_mediana",
                                          "grado_medio_hubs_mediana", "grado_medio_normales_mediana",
                                          "longitud_media_mediana", "capacidad_media_enlace_mediana",
                                          "puente_coincide_con_z", "puente_no_coincide",
                                          "puente_indeterminado"]].to_dict("index"),
        c5_semillas_x10_mas_rapido=int((c5.razon_tiempo_B_sobre_A < 1).sum()),
        c5_semillas_z_igual=int((c5.cambio_z_pct.abs() < 1e-6).sum()),
    )
    return res, comp, est


def a_json(o):
    if isinstance(o, dict):
        return {str(k): a_json(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [a_json(v) for v in o]
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating, float)):
        o = float(o)
        return None if np.isnan(o) else ("inf" if np.isinf(o) else o)
    if isinstance(o, np.bool_):
        return bool(o)
    return o


def main():
    cifras = dict(convenciones=__doc__, bootstrap=dict(B=B_BOOTSTRAP, semilla=SEMILLA_BOOTSTRAP))
    r3 = x3(cifras)
    r4, acel, crec = x4(cifras)
    rw, comp, est = waxman(cifras)
    (TABLAS / "cifras_clave.json").write_text(json.dumps(a_json(cifras), indent=2, ensure_ascii=False),
                                              encoding="utf-8")
    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 40)
    print(r3[["grado", "n", "certificadas", "n_limite_interno", "mediana_todas_s", "q1_todas_s", "q3_todas_s",
              "ic95_mediana_inf_s", "ic95_mediana_sup_s", "mediana_solo_certificadas_s", "maximo_certificadas_s",
              "iteraciones_mediana", "columnas_mediana", "frac_maestro_mediana", "z_mediana",
              "spearman_z_vs_tiempo", "productos_efectivos_mediana"]].round(3).to_string())
    print(r4[["metodo", "nodos", "n", "certificadas", "n_optimo", "mediana_todas_s", "q1_todas_s", "q3_todas_s",
              "maximo_todas_s", "mediana_pared_s", "iteraciones_mediana", "columnas_por_producto_mediana",
              "k_por_arcos_mediana", "caminos_iniciales_mediana_s", "maestro_mediana_s", "pricing_mediana_s",
              "resto_mediana_s", "frac_maestro_mediana"]].round(3).to_string())
    print(acel.round(2).to_string())
    print(crec.round(3).to_string())
    print(rw[["caso", "n", "n_optimo", "n_brecha_1pct", "mediana_todas_s", "q1_todas_s", "q3_todas_s",
              "maximo_todas_s", "ic95_mediana_inf_s", "ic95_mediana_sup_s", "iteraciones_mediana",
              "columnas_mediana", "frac_maestro_mediana", "z_mediana", "z_min", "z_max", "gap_max_pct"]].round(3).to_string())
    print(comp.round(3).T.to_string())
    print(est.round(3).T.to_string())


if __name__ == "__main__":
    main()
