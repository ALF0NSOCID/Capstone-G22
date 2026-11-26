#!/usr/bin/env python3
"""Paso 1: inventario, verificación de integridad y tablas consolidadas.

Lee únicamente los resultados originales de experimentos/x3_formal,
experimentos/x4_formal y experimentos/waxman_formal (CSV, logs, JSON e
instancias Waxman) y escribe en analisis_final/tablas/. No modifica nada fuera
de analisis_final/.

Uso, desde la raíz del repositorio:
    python3 analisis_final/codigo/01_consolidar.py
"""
from __future__ import annotations

import csv
import json
import math
import os
import random
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from comun import (EXP, FAMILIAS_WAXMAN, RAIZ, TABLAS, analizar_log_solver,  # noqa: E402
                   normalizar_estado_waxman, normalizar_estado_x, rel, sha256)

VERIF: list[dict] = []


def verif(bateria, chequeo, esperado, observado, ok, detalle=""):
    VERIF.append(dict(bateria=bateria, chequeo=chequeo, esperado=str(esperado), observado=str(observado),
                      resultado=ok if isinstance(ok, str) else ("OK" if ok else "ALERTA"), detalle=detalle))


def utc(ts):
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def casi(a, b, rel_tol=1e-6, abs_tol=1e-9):
    if a is None or b is None:
        return a is None and b is None
    if math.isinf(a) or math.isinf(b):
        return a == b
    return math.isclose(a, b, rel_tol=rel_tol, abs_tol=abs_tol)


def f(x):
    try:
        return math.inf if x == "inf" else float(x)
    except (TypeError, ValueError):
        return None


def tipo_limite(d, limite):
    if d["iteraciones_log"] == 1000:
        return "iteraciones (1000)"
    if d["tiempo_total_log_s"] is not None and limite and d["tiempo_total_log_s"] >= limite - 1:
        return "tiempo"
    return "maestro no óptimo u otra causa"


# ------------------------------------------------------------------- X3 / X4

def consolidar_x(bateria: str):
    carpeta = EXP / f"{bateria}_formal"
    ruta_csv = carpeta / "corridas.csv"
    with open(ruta_csv, newline="", encoding="utf-8") as fh:
        lector = csv.DictReader(fh)
        cabecera = lector.fieldnames
        filas = list(lector)
    with open(ruta_csv, encoding="utf-8") as fh:
        n_lineas = sum(1 for _ in fh)
    verif(bateria, "filas de datos en corridas.csv", "1 por corrida", len(filas), "INFO",
          f"{n_lineas} líneas con cabecera")
    incompletas = [r["instancia"] for r in filas if any(v is None for v in r.values()) or None in r]
    verif(bateria, "filas truncadas o con columnas de más", 0, len(incompletas), not incompletas,
          ",".join(incompletas))
    salida = []
    for linea, r in enumerate(filas, start=2):
        metodo = r.get("metodo", "e2_v2")
        nombre_log = f"{r['instancia']}.txt" if bateria == "x3" else f"{r['instancia']}_{metodo}.txt"
        ruta_log = carpeta / "logs" / nombre_log
        existe = ruta_log.exists()
        texto = ruta_log.read_text(encoding="utf-8", errors="replace") if existe else ""
        d = analizar_log_solver(texto)
        estado = normalizar_estado_x(r["certificacion"])
        limite = f(r["limite_s"])
        z_csv = f(r["z"])
        t_csv = f(r["tiempo_interno_s"])
        problemas = []
        if not existe:
            problemas.append("falta log")
        esperado_log = {"optimo": ("optimo",), "brecha_1pct": ("brecha_1pct",),
                        "limite_interno": ("limite_interno", "limite_interno_base"),
                        "sin_certificar": ("sin_certificar",)}.get(estado, ())
        if esperado_log and d["estado_log"] not in esperado_log:
            problemas.append(f"estado CSV {estado} vs log {d['estado_log']}")
        if z_csv is not None and not casi(z_csv, d["z_log"]):
            problemas.append(f"z CSV {z_csv} vs log {d['z_log']}")
        if t_csv is not None and not casi(t_csv, d["tiempo_total_log_s"], abs_tol=0.006):
            problemas.append("tiempo CSV vs log")
        for campo, clave in (("iteraciones", "iteraciones_log"), ("columnas", "columnas_log")):
            if r[campo] and int(float(r[campo])) != d[clave]:
                problemas.append(f"{campo} CSV vs log")
        if r["productos_efectivos"] and int(r["productos_efectivos"]) != d["productos_log"]:
            problemas.append("productos efectivos CSV vs log")
        if int(r["arcos"]) != d["arcos_log"]:
            problemas.append(f"arcos solicitados {r['arcos']} vs generados {d['arcos_log']}")
        if int(r["nodos"]) != d["nodos_log"]:
            problemas.append("nodos CSV vs log")
        if metodo == "e2_v2" and (d["limite_log_s"] is None or not casi(d["limite_log_s"], limite)):
            problemas.append(f"límite CSV {limite} vs log {d['limite_log_s']}")
        if bateria == "x3" and r.get("tiempo_maestro_s") and abs(float(r["tiempo_maestro_s"]) - d["suma_maestro_s"]) > 0.05:
            problemas.append("tiempo_maestro CSV vs suma log")
        if str(r["codigo_salida"]) != "0":
            problemas.append(f"código de salida {r['codigo_salida']}")
        if d["traceback"]:
            problemas.append("traceback en log")
        if not d["log_completo"]:
            problemas.append("log sin línea final de tiempo")
        cert = estado in ("optimo", "brecha_1pct")
        censura = estado in ("limite_interno", "timeout_externo")
        if metodo == "base":
            criterio = "costo reducido ≥ −1e-7 (sin cota inferior)" if cert else ""
        else:
            criterio = ("cota inferior: brecha ≤ 1e-6" if estado == "optimo" else
                        "cota inferior: brecha ≤ 1%" if estado == "brecha_1pct" else "")
        fila = dict(
            serie=f"{bateria}_formal", instancia=r["instancia"],
            metodo=("E3" if metodo == "e2_v2" else "GC base"), etiqueta_csv=metodo,
            semilla=int(r["semilla"]), nodos=int(r["nodos"]),
            grado=int(r["grado"]) if bateria == "x3" else int(r["arcos"]) // int(r["nodos"]),
            arcos_solicitados=int(r["arcos"]), arcos_generados=d["arcos_log"],
            productos_solicitados=int(r["productos_generados"]), productos_efectivos=d["productos_log"],
            eliminados_filtro=d["eliminados_filtro"],
            k_por_arcos=(d["productos_log"] * d["arcos_log"]) if d["productos_log"] and d["arcos_log"] else None,
            k_por_arcos_csv=f(r.get("k_por_arcos")) if bateria == "x4" else None,
            estado=estado, certificada=cert, criterio_certificacion=criterio, censurada=censura,
            tipo_limite=tipo_limite(d, limite) if censura else "",
            limite_s=limite, limite_en_log_s=d["limite_log_s"],
            tiempo_interno_s=t_csv, tiempo_pared_s=f(r["tiempo_pared_s"]),
            z=z_csv, cota_superior=d["cota_superior_log"] if metodo == "e2_v2" else z_csv,
            cota_inferior=d["cota_inferior_log"], gap_pct=d["gap_log_pct"],
            iteraciones=d["iteraciones_log"], columnas=d["columnas_log"],
            columnas_por_producto=(d["columnas_log"] / d["productos_log"]) if d["columnas_log"] and d["productos_log"] else None,
            t_caminos_iniciales_s=d["t_caminos_iniciales_s"], suma_maestro_s=d["suma_maestro_s"],
            suma_pricing_s=d["suma_pricing_s"], max_maestro_s=d["max_maestro_s"],
            frac_maestro=(d["suma_maestro_s"] / t_csv) if t_csv else None,
            frac_pricing=(d["suma_pricing_s"] / t_csv) if t_csv else None,
            frac_caminos_iniciales=(d["t_caminos_iniciales_s"] / t_csv) if t_csv and d["t_caminos_iniciales_s"] is not None else None,
            licencia_gurobi=d["licencia_log"], eta=d["eta_log"], escala_capacidad=d["escala_capacidad_log"],
            codigo_salida=r["codigo_salida"], memoria_registrada=False,
            consistencia_csv_log="OK" if not problemas else "; ".join(problemas),
            log_fin_utc=utc(ruta_log.stat().st_mtime) if existe else "",
            _log_mtime=ruta_log.stat().st_mtime if existe else None,
            origen_csv=rel(ruta_csv), origen_linea_csv=linea, origen_log=rel(ruta_log) if existe else "",
        )
        salida.append(fila)
    df = pd.DataFrame(salida)

    # Combinaciones esperadas, duplicados y logs huérfanos.
    if bateria == "x3":
        esperadas = {(g, s) for g in (4, 8, 12, 16) for s in range(1, 11)}
        obs = list(zip(df.grado, df.semilla))
        semillas_extra = sorted(set(df.semilla) - set(range(1, 11)))
        verif("x3", "semillas presentes", "1–10 (diseño predeterminado)", f"{df.semilla.min()}–{df.semilla.max()}",
              not semillas_extra, f"semillas fuera del diseño: {semillas_extra}" if semillas_extra else "no se amplió la muestra")
    else:
        esperadas = ({("E3", n, s) for n in (200, 400, 800, 1600, 3200) for s in range(1, 31)} |
                     {("GC base", n, s) for n in (200, 400, 800) for s in range(1, 31)})
        obs = list(zip(df.metodo, df.nodos, df.semilla))
        verif("x4", "GC base solo hasta 800 nodos", "máx. 800", df[df.metodo == "GC base"].nodos.max(),
              df[df.metodo == "GC base"].nodos.max() <= 800)
    faltan = sorted(esperadas - set(obs))
    sobran = sorted(set(obs) - esperadas)
    dups = sorted({o for o in obs if obs.count(o) > 1})
    verif(bateria, "corridas esperadas presentes", len(esperadas), len(esperadas) - len(faltan), not faltan,
          f"faltan: {faltan}" if faltan else "")
    verif(bateria, "corridas fuera del diseño", 0, len(sobran), not sobran, str(sobran) if sobran else "")
    verif(bateria, "duplicados (combinación repetida)", 0, len(dups), not dups, str(dups) if dups else "")
    logs = {p.name for p in (EXP / f"{bateria}_formal" / "logs").glob("*.txt")}
    usados = {Path(p).name for p in df.origen_log if p}
    verif(bateria, "logs huérfanos (sin fila en CSV)", 0, len(logs - usados), not (logs - usados),
          ",".join(sorted(logs - usados)))
    malas = df[df.consistencia_csv_log != "OK"]
    verif(bateria, "consistencia CSV ↔ log por corrida", 0, len(malas), len(malas) == 0,
          " | ".join(f"{a}/{b}: {c}" for a, b, c in zip(malas.instancia, malas.metodo, malas.consistencia_csv_log)))
    verif(bateria, "códigos de salida", "todos 0", sorted(df.codigo_salida.unique()), set(df.codigo_salida) == {"0"})
    verif(bateria, "licencia Gurobi (huella de entorno)", "una sola", sorted(df.licencia_gurobi.dropna().unique()),
          df.licencia_gurobi.nunique() == 1)
    verif(bateria, "estados", "", df.groupby(["metodo", "estado"]).size().to_dict(), "INFO")
    if bateria == "x4":
        dif = df[(df.k_por_arcos_csv.notna()) & (df.k_por_arcos != df.k_por_arcos_csv)]
        verif("x4", "k_por_arcos del CSV = K efectivo × arcos generados", 0, len(dif), len(dif) == 0,
              "el CSV usa arcos solicitados; coincide si Mulgen genera exactamente 4N")
        e3 = df[df.metodo == "E3"]
        verif("x4", "límite E3 leído en log", "900 s", sorted(e3.limite_en_log_s.unique()),
              set(e3.limite_en_log_s) == {900.0})
        src = (RAIZ / "src/solvers/solver_columnas_pricing_gurobi.py").read_text(encoding="utf-8")
        lim_base = re.search(r"^LIMITE_TIEMPO = ([0-9.]+)", src, re.M).group(1)
        verif("x4", "límite GC base (constante en código, ignora E2_LIMITE_TIEMPO)", "900 s", f"{lim_base} s",
              float(lim_base) == 900.0, "src/solvers/solver_columnas_pricing_gurobi.py:30; coincide con el protocolo")
    else:
        verif("x3", "límite E3 leído en log", "300 s", sorted(df.limite_en_log_s.unique()),
              set(df.limite_en_log_s) == {300.0})
    return df


def validar_z_x4(df):
    """GC base certifica el óptimo exacto; E3 entrega [cota inferior, z]."""
    filas = []
    e3 = df[df.metodo == "E3"].set_index(["nodos", "semilla"])
    for _, b in df[df.metodo == "GC base"].iterrows():
        e = e3.loc[(b.nodos, b.semilla)]
        dentro = (e.cota_inferior <= b.z * (1 + 1e-6)) and (b.z <= e.z * (1 + 1e-6))
        filas.append(dict(nodos=b.nodos, semilla=b.semilla, z_base=b.z, z_e3=e.z, cota_inferior_e3=e.cota_inferior,
                          estado_e3=e.estado, exceso_rel_e3_pct=100 * (e.z / b.z - 1),
                          base_dentro_de_intervalo_e3=dentro,
                          mismos_productos=b.productos_efectivos == e.productos_efectivos,
                          mismos_arcos=b.arcos_generados == e.arcos_generados))
    v = pd.DataFrame(filas)
    v.to_csv(TABLAS / "x4_validacion_cruzada_z.csv", index=False)
    malos = v[~v.base_dentro_de_intervalo_e3]
    verif("x4", "z de GC base dentro de [cota inferior E3, z E3]", len(v), len(v) - len(malos), len(malos) == 0,
          f"máx. exceso de E3 sobre el óptimo: {v.exceso_rel_e3_pct.max():.4f} %; "
          f"en corridas E3 'óptimo': {v[v.estado_e3 == 'optimo'].exceso_rel_e3_pct.abs().max():.2e} %")
    verif("x4", "mismas instancias para E3 y GC base", len(v), int((v.mismos_productos & v.mismos_arcos).sum()),
          bool((v.mismos_productos & v.mismos_arcos).all()))
    return v


# -------------------------------------------------------------------- Waxman

def leer_instancia(ruta):
    with open(ruta, encoding="utf-8") as fh:
        lineas = fh.read().splitlines()
    n, m, k = map(int, lineas[0].split())
    arcos = [tuple(int(float(x)) for x in l.split()[:4]) for l in lineas[1:1 + m]]
    bloque_dem = "\n".join(lineas[1 + m:1 + m + 2 * k])
    return n, m, k, arcos, bloque_dem, len(lineas) == 1 + m + 2 * k


def posiciones(semilla, nodos=400):
    rng = random.Random(f"{semilla}:posiciones")
    return {u + 1: (rng.random(), rng.random()) for u in range(nodos)}


def consolidar_waxman():
    carpeta = EXP / "waxman_formal"
    proto = json.loads((carpeta / "protocolo.json").read_text())
    entorno = json.loads((carpeta / "ultima_ejecucion.json").read_text())
    mapa = {"generador_waxman.py": "src/generadores/generador_waxman.py",
            "solver_columnas_e2_v2.py": "src/solvers/solver_columnas_e2_v2.py",
            "explorar_waxman.py": "experimentos/scripts/explorar_waxman.py",
            "analisis_red.py": "src/diagnosticos/analisis_red.py"}
    for nombre, ruta in mapa.items():
        actual = sha256(RAIZ / ruta)
        verif("waxman", f"sha256 actual de {ruta} = protocolo.json", proto["sha256"][nombre][:12], actual[:12],
              actual == proto["sha256"][nombre])
    verif("waxman", "protocolo: límites y tamaños", "120 s solver, 60 s preparación, 400/1600/10000",
          f"{proto['limite_s']} s, {proto['preparacion_s']} s, {proto['nodos']}/{proto['arcos']}/{proto['productos']}",
          proto["limite_s"] == 120 and proto["preparacion_s"] == 60 and proto["arcos"] == 1600)
    verif("waxman", "entorno registrado", "", f"{entorno['plataforma']}; Python {entorno['python'].split()[0]}", "INFO")
    with open(carpeta / "corridas.csv", newline="", encoding="utf-8") as fh:
        csv_filas = {(r["caso"], int(r["semilla"])): r for r in csv.DictReader(fh)}
    carpetas = sorted(p.name for p in carpeta.iterdir() if p.is_dir())
    esperadas = [f"{c}_s{s}" for c in FAMILIAS_WAXMAN for s in range(1001, 1031)]
    verif("waxman", "carpetas de corrida esperadas", 150, len(set(esperadas) & set(carpetas)),
          set(esperadas) <= set(carpetas), f"faltan: {sorted(set(esperadas) - set(carpetas))}")
    otras = sorted(set(carpetas) - set(esperadas))
    verif("waxman", "carpetas ajenas al diseño (p. ej. piloto s42/s43)", 0, len(otras), not otras, ",".join(otras))
    sin_estado = [c for c in esperadas if not (carpeta / c / "estado.json").exists()]
    verif("waxman", "estado.json por corrida", 150, 150 - len(sin_estado), not sin_estado, ",".join(sin_estado))

    salida, instancias = [], {}
    for caso in FAMILIAS_WAXMAN:
        for s in range(1001, 1031):
            c = carpeta / f"{caso}_s{s}"
            est = json.loads((c / "estado.json").read_text())
            par = json.loads((c / "parametros.json").read_text())
            dia = json.loads((c / "diagnostico.json").read_text())
            meta = json.loads((c / "generacion_metadata.json").read_text())["generacion"]
            texto = (c / "solver.log").read_text(encoding="utf-8", errors="replace")
            d = analizar_log_solver(texto)
            gen_log = (c / "generacion.log").read_text(encoding="utf-8", errors="replace")
            n, m, k, arcos, dem, completo = leer_instancia(c / "instancia.txt")
            enlaces = {}
            reciproco = True
            por_par = {(o, dd): cap for o, dd, _, cap in arcos}
            for (o, dd), cap in por_par.items():
                if por_par.get((dd, o)) != cap:
                    reciproco = False
                enlaces[(min(o, dd), max(o, dd))] = cap
            pos = posiciones(s)
            long_media = sum(math.dist(pos[a], pos[b]) for a, b in enlaces) / len(enlaces)
            instancias[(caso, s)] = dict(enlaces=enlaces, dem=dem)
            csv_r = csv_filas.get((caso, s), {})
            problemas = []
            for clave in ("estado", "interno_s", "z", "iteraciones", "columnas", "gap_pct"):
                if str(csv_r.get(clave, "")) != str(est.get(clave, "")):
                    problemas.append(f"{clave} CSV≠estado.json")
            esperado_par = dict(proto["casos"][caso])
            for clave, valor in esperado_par.items():
                if par.get(clave) != valor:
                    problemas.append(f"parametro {clave}={par.get(clave)} (esperado {valor})")
            if caso != "local_backbone_x10" and par.get("multiplicador_capacidad_hubs") != 1:
                problemas.append("multiplicador distinto de 1")
            if meta.get("prob_acceso_backbone", 0) != par.get("prob_acceso_backbone", 0):
                problemas.append("metadata de generación ≠ parámetros")
            if est["estado"] in ("optimo", "brecha_1pct") and d["estado_log"] != est["estado"]:
                problemas.append(f"estado log {d['estado_log']}")
            if not casi(f(est.get("z")), d["z_log"]):
                problemas.append("z estado vs log")
            if d["limite_log_s"] != 120.0:
                problemas.append(f"límite log {d['limite_log_s']}")
            if (n, m, k) != (400, 1600, 10000) or not completo:
                problemas.append(f"instancia {n}/{m}/{k} completa={completo}")
            if d["arcos_log"] != 1600 or d["productos_log"] != 10000:
                problemas.append("arcos/productos en log")
            if not reciproco:
                problemas.append("arcos no recíprocos o capacidades asimétricas")
            if abs(long_media - dia["longitud_media"]) > 1e-9:
                problemas.append("posiciones reconstruidas no reproducen longitud_media")
            if "Traceback" in gen_log or d["traceback"]:
                problemas.append("traceback")
            z = f(est.get("z"))
            lb = d["cota_inferior_log"]
            cota = dia["cota_puentes"]
            ub = z
            if cota >= ub * (1 - 1e-6):
                explica = "coincide"
            elif lb is not None and cota < lb * (1 - 1e-6):
                explica = "no coincide"
            else:
                explica = "indeterminado (dentro de la brecha)"
            if cota > ub * (1 + 1e-6):
                problemas.append("cota de puentes > z (inconsistente)")
            normales = 400 - dia.get("hubs", 0)
            fila = dict(
                serie="waxman_formal", caso=caso, semilla=s,
                alpha=par["alpha"], beta=par["beta"], porcentaje_hubs=par.get("porcentaje_hubs", 0),
                prob_acceso=par.get("prob_acceso_backbone", 0), prob_segundo=par.get("prob_segundo_hub", 0),
                multiplicador_hubs=par.get("multiplicador_capacidad_hubs", 1),
                estado=normalizar_estado_waxman(est["estado"]), estado_original=est["estado"],
                certificada=est["estado"] in ("optimo", "brecha_1pct"), censurada=est["estado"] in ("timeout_externo",),
                codigo=est.get("codigo"), tiempo_interno_s=f(est.get("interno_s")), tiempo_pared_s=f(est.get("pared_s")),
                limite_s=120.0, z=z, cota_inferior=lb, gap_pct=d["gap_log_pct"],
                iteraciones=d["iteraciones_log"], columnas=d["columnas_log"],
                columnas_por_producto=d["columnas_log"] / 10000 if d["columnas_log"] else None,
                t_caminos_iniciales_s=d["t_caminos_iniciales_s"], suma_maestro_s=d["suma_maestro_s"],
                suma_pricing_s=d["suma_pricing_s"],
                frac_maestro=d["suma_maestro_s"] / f(est["interno_s"]) if f(est.get("interno_s")) else None,
                escala_capacidad=d["escala_capacidad_log"], licencia_gurobi=d["licencia_log"],
                cota_puentes=cota, cota_puentes_sobre_z=cota / z if z else None, puente_explica_optimo=explica,
                puente_critico=str(dia.get("puente_critico")),
                enlaces=dia["enlaces"], puentes=dia["puentes"], hubs=dia.get("hubs", 0),
                enlaces_hub_normal=dia.get("enlaces_hub_normal", 0),
                normales_con_hub=dia.get("normales_con_hub", 0),
                normales_con_dos_hubs=dia.get("normales_con_dos_hubs", 0),
                normales_acceso_obligatorio=dia.get("normales_acceso_obligatorio", 0),
                normales_doble_acceso_obligatorio=dia.get("normales_doble_acceso_obligatorio", 0),
                cobertura_backbone_pct=dia.get("cobertura_backbone_pct", 0),
                acceso_obligatorio_pct=100 * dia.get("normales_acceso_obligatorio", 0) / normales,
                doble_acceso_obligatorio_pct=100 * dia.get("normales_doble_acceso_obligatorio", 0) / normales,
                grado_medio_hubs=dia.get("grado_medio_hubs"), grado_medio_normales=dia.get("grado_medio_normales"),
                grado_max=dia["grado_max"], grado_cv=dia["grado_cv"], longitud_media=dia["longitud_media"],
                clustering=dia["clustering"], demanda_total=dia["demanda_total"],
                capacidad_total_arcos=dia["capacidad_total_arcos"],
                capacidad_media_enlace=sum(enlaces.values()) / len(enlaces),
                generacion_s=dia.get("generacion_s"), intentos_generacion=meta.get("intentos"),
                memoria_registrada=False,
                consistencia="OK" if not problemas else "; ".join(problemas),
                estado_fin_utc=utc((c / "estado.json").stat().st_mtime),
                _fin_mtime=(c / "estado.json").stat().st_mtime,
                origen_estado=rel(c / "estado.json"), origen_log=rel(c / "solver.log"),
                origen_diagnostico=rel(c / "diagnostico.json"), origen_instancia=rel(c / "instancia.txt"),
            )
            salida.append(fila)
    df = pd.DataFrame(salida)
    malas = df[df.consistencia != "OK"]
    verif("waxman", "consistencia CSV ↔ estado.json ↔ log ↔ parámetros ↔ instancia", 0, len(malas), len(malas) == 0,
          " | ".join(f"{a}_s{b}: {c}" for a, b, c in zip(malas.caso, malas.semilla, malas.consistencia)))
    verif("waxman", "filas en corridas.csv = estado.json consolidados", 150, len(csv_filas), len(csv_filas) == 150,
          "el CSV se regenera desde estado.json tras cada corrida")
    verif("waxman", "estados", "", df.groupby(["caso", "estado"]).size().to_dict(), "INFO")
    verif("waxman", "pared máx. vs protección externa", "≤ 180 s", f"{df.tiempo_pared_s.max():.2f} s",
          df.tiempo_pared_s.max() <= 180)
    verif("waxman", "tiempo interno máx. vs límite interno", "≤ 120 s", f"{df.tiempo_interno_s.max():.2f} s",
          df.tiempo_interno_s.max() <= 120.5)
    verif("waxman", "posiciones idénticas entre variantes de una semilla",
          "longitud media reproducida con la misma secuencia de posiciones", "150/150" if
          not df.consistencia.str.contains("posiciones").any() else "fallas", not df.consistencia.str.contains("posiciones").any(),
          "posiciones reconstruidas con random.Random(f'{semilla}:posiciones') igual que el generador")
    verif("waxman", "generación dentro de 60 s", "sin timeout_preparacion",
          f"máx. generacion_s = {df.generacion_s.max():.2f} s (solo generación; diagnóstico y dibujo no se cronometran)",
          True)

    # Demandas idénticas entre las cinco variantes de cada semilla; W4/W5 misma topología.
    pares = []
    for s in range(1001, 1031):
        dems = {instancias[(c, s)]["dem"] for c in FAMILIAS_WAXMAN}
        e4 = instancias[("local_backbone", s)]["enlaces"]
        e5 = instancias[("local_backbone_x10", s)]["enlaces"]
        e1 = instancias[("local_extrema", s)]["enlaces"]
        misma_top = set(e4) == set(e5)
        x10 = {e for e in e4 if e in e5 and e5[e] != e4[e]}
        exactos = all(e5[e] == round(e4[e] * 10) for e in x10)
        hubs = {u for e in x10 for u in e}
        hub_hub_sin_x10 = [e for e in e4 if e[0] in hubs and e[1] in hubs and e not in x10]
        comunes = set(e1) & set(e4)
        pares.append(dict(semilla=s, demandas_identicas_5_variantes=len(dems) == 1, w4_w5_misma_topologia=misma_top,
                          enlaces_x10=len(x10), x10_exacto=exactos, hubs_identificados=len(hubs),
                          enlaces_hub_hub_sin_x10=len(hub_hub_sin_x10),
                          capacidad_igual_fuera_backbone=all(e4[e] == e5[e] for e in e4 if e not in x10),
                          enlaces_comunes_w1_w4=len(comunes),
                          misma_capacidad_en_enlaces_comunes_w1_w4=all(e1[e] == e4[e] for e in comunes)))
    p = pd.DataFrame(pares)
    p.to_csv(TABLAS / "waxman_verificacion_instancias.csv", index=False)
    verif("waxman", "demandas idénticas entre las 5 variantes de cada semilla", 30,
          int(p.demandas_identicas_5_variantes.sum()), bool(p.demandas_identicas_5_variantes.all()))
    ok45 = p.w4_w5_misma_topologia & p.x10_exacto & p.capacidad_igual_fuera_backbone & (p.enlaces_hub_hub_sin_x10 == 0)
    verif("waxman", "W4/W5: misma topología; solo enlaces hub–hub ×10", 30, int(ok45.sum()), bool(ok45.all()),
          f"enlaces ×10 por semilla: {p.enlaces_x10.min()}–{p.enlaces_x10.max()}; hubs identificados: "
          f"{sorted(p.hubs_identificados.unique())}")
    verif("waxman", "capacidad depende de la identidad del enlace (W1 vs W4 en enlaces comunes)", 30,
          int(p.misma_capacidad_en_enlaces_comunes_w1_w4.sum()), bool(p.misma_capacidad_en_enlaces_comunes_w1_w4.all()),
          f"enlaces comunes W1–W4: {p.enlaces_comunes_w1_w4.min()}–{p.enlaces_comunes_w1_w4.max()} de 800")

    # Orden de ejecución aleatorizado por semilla.
    distintos = 0
    for s in range(1001, 1031):
        orden = list(FAMILIAS_WAXMAN)
        random.Random(f"{s}:orden_formal").shuffle(orden)
        obs = list(df[df.semilla == s].sort_values("_fin_mtime").caso)
        distintos += orden != obs
    verif("waxman", "orden de ejecución = orden aleatorizado por semilla", 30, 30 - distintos, distintos == 0)
    return df


def secuencialidad(x3, x4, wx):
    """Las corridas no se solapan: fin(i-1) ≤ fin(i) − pared(i)."""
    ev = []
    for df, tag in ((x3, "x3"), (x4, "x4")):
        for _, r in df.iterrows():
            ev.append((r._log_mtime, r.tiempo_pared_s, f"{tag}:{r.instancia}:{r.metodo}"))
    for _, r in wx.iterrows():
        ev.append((r._fin_mtime, r.tiempo_pared_s, f"waxman:{r.caso}_s{r.semilla}"))
    ev.sort()
    solapes = [b[2] for a, b in zip(ev, ev[1:]) if b[0] - b[1] < a[0] - 1.0]
    verif("todas", "corridas secuenciales sin solapamiento (marcas de tiempo de archivos)", 0, len(solapes),
          not solapes, f"primera {utc(ev[0][0] - ev[0][1])} UTC, última {utc(ev[-1][0])} UTC; " + ",".join(solapes[:5]))
    for nombre, ruta in (("E3", "src/solvers/solver_columnas_e2_v2.py"),
                         ("GC base", "src/solvers/solver_columnas_pricing_gurobi.py"),
                         ("script X3", "experimentos/scripts/experimento_x3.py"),
                         ("script X4", "experimentos/scripts/experimento_x4.py"),
                         ("script Waxman", "experimentos/scripts/experimento_waxman.py")):
        t = (RAIZ / ruta).stat().st_mtime
        verif("todas", f"{nombre} sin modificar durante las baterías", f"modificado antes de {utc(ev[0][0] - ev[0][1])}",
              utc(t), t < ev[0][0] - ev[0][1], ruta)


def main():
    TABLAS.mkdir(parents=True, exist_ok=True)
    x3 = consolidar_x("x3")
    x4 = consolidar_x("x4")
    validar_z_x4(x4)
    wx = consolidar_waxman()
    secuencialidad(x3, x4, wx)
    verif("todas", "memoria (RAM) registrada", "medición por corrida", "no registrada en ninguna batería formal",
          "ALERTA", "los scripts formales no usan vigilar_memoria; columnas/iteraciones no son RAM")
    for df, nombre in ((x3, "x3_corridas_consolidadas"), (x4, "x4_corridas_consolidadas"),
                       (wx, "waxman_corridas_consolidadas")):
        df.drop(columns=[c for c in df.columns if c.startswith("_")]).to_csv(TABLAS / f"{nombre}.csv", index=False)
    v = pd.DataFrame(VERIF)
    v.to_csv(TABLAS / "verificaciones.csv", index=False)
    proc = []
    for ruta in ["experimentos/x3_formal/corridas.csv", "experimentos/x3_formal/resumen.csv",
                 "experimentos/x4_formal/corridas.csv", "experimentos/x4_formal/resumen.csv",
                 "experimentos/waxman_formal/corridas.csv", "experimentos/waxman_formal/resumen.csv",
                 "experimentos/waxman_formal/protocolo.json", "experimentos/waxman_formal/ultima_ejecucion.json"]:
        p = RAIZ / ruta
        proc.append(dict(archivo=ruta, sha256=sha256(p), bytes=p.stat().st_size, modificado_utc=utc(p.stat().st_mtime)))
    pd.DataFrame(proc).to_csv(TABLAS / "procedencia_archivos_originales.csv", index=False)
    print(v.to_string(max_colwidth=90))
    print(f"\nX3 {len(x3)} | X4 {len(x4)} | Waxman {len(wx)} corridas consolidadas en {rel(TABLAS)}")


if __name__ == "__main__":
    main()
