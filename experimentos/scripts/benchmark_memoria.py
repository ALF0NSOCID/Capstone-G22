#!/usr/bin/env python3
"""Mide RAM de LP, GC con pricing Gurobi y E3 en procesos independientes.

Solo E3 se ejecuta sobre la instancia grande. No modifica fuentes ni `out`.
macOS/Linux; usa el mismo Python, Gurobi y pricing_cpp del proyecto.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import re
import shutil
import signal
import statistics
import subprocess
import sys
import time
from datetime import datetime


SOLVERS = {
    "LP": "solver.py",
    "GC_Gurobi": "solver_columnas_pricing_gurobi.py",
    "E3": "solver_columnas_e2_v2.py",
    "E2_historico": "solver_columnas_e2.py",
}
FORTRAN = ["main.f", "mulgen.f", "ran2.f", "outdat.f", "mps.f", "lp.f",
           "append.f", "traitenom.f", "int2char.f"]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rss_bytes(pid):
    """ps informa RSS en KiB en macOS y Linux. Error: detener, no continuar ciego."""
    p = subprocess.run(["ps", "-o", "rss=", "-p", str(pid)],
                       capture_output=True, text=True, timeout=3)
    if p.returncode == 0 and p.stdout.strip():
        return int(p.stdout.split()[0]) * 1024
    # ps devuelve 1 si el proceso ya terminó; el padre lo comprueba con wait4.
    if not p.stdout.strip() and not p.stderr.strip():
        return None
    raise RuntimeError("No se puede consultar la RAM con ps: " + p.stderr.strip())


def medir(comando, cwd, env, log, limite_s, limite_bytes, lector_rss=rss_bytes):
    """Pico del SO por corrida con wait4; RSS muestreada para cortar por memoria.

    Los solvers no lanzan procesos hijos: sus hilos Gurobi/C++ están incluidos.
    El límite de RAM es un vigilante muestreado, no una reserva estricta del SO.
    """
    if not hasattr(os, "wait4"):
        raise RuntimeError("Este script requiere macOS o Linux (os.wait4).")
    inicio = time.perf_counter()
    pico_muestra = 0
    motivo = "terminado"
    fallo_monitor = None
    with Path(log).open("w", encoding="utf-8") as salida:
        proc = subprocess.Popen(comando, cwd=cwd, env=env, stdout=salida,
                                stderr=subprocess.STDOUT, start_new_session=True)
        estado = uso = None

        def detener():
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass

        try:
            while True:
                pid, estado, uso = os.wait4(proc.pid, os.WNOHANG)
                if pid:
                    break
                if time.perf_counter() - inicio >= limite_s:
                    motivo = "corte_tiempo"
                    detener()
                else:
                    try:
                        rss = lector_rss(proc.pid)
                        pico_muestra = max(pico_muestra, rss or 0)
                        if rss is not None and rss >= limite_bytes:
                            motivo = "corte_ram"
                            detener()
                    except Exception as exc:
                        motivo = "error_monitor"
                        fallo_monitor = str(exc)
                        detener()
                if motivo != "terminado":
                    _, estado, uso = os.wait4(proc.pid, 0)
                    break
                time.sleep(0.08)
        except BaseException:
            detener()
            try:
                _, estado, uso = os.wait4(proc.pid, 0)
            except ChildProcessError:
                pass
            raise
        finally:
            if estado is not None:
                proc.returncode = os.waitstatus_to_exitcode(estado)
        pico_so = uso.ru_maxrss * (1 if sys.platform == "darwin" else 1024)
        return dict(estado=motivo, codigo=proc.returncode,
                    ram_pico_bytes=int(pico_so), ram_muestreada_bytes=pico_muestra,
                    tiempo_proceso_s=round(time.perf_counter() - inicio, 4),
                    error_monitor=fallo_monitor or "")


def usa_matrices_densas(texto):
    """Inspecciona código Fortran fijo, excluyendo comentarios completos/en línea."""
    codigo = "\n".join(
        linea[6:].split("!", 1)[0]
        for linea in texto.splitlines()
        if linea and linea[0] not in "cC*!"
    )
    return bool(re.search(r"\b(?:cap|cost|b)\s*\(\s*MAXCOMM\s*,", codigo, re.I))


def compilar_privado(repo, destino, nmax, limite_bytes):
    compiler = shutil.which("gfortran")
    if not compiler:
        raise RuntimeError("Falta gfortran, necesario para regenerar Mulgen.")
    carpeta = destino / "mulgen_privado"
    carpeta.mkdir()
    fuente = repo / "Canad" / "Mulgen"
    cmn = (fuente / "mulgen.cmn").read_text()
    if nmax >= 3200 and usa_matrices_densas(cmn):
        raise RuntimeError("Esta copia de Mulgen reserva matrices estáticas gigantes. "
                           "Usa la versión compacta del repositorio antes de generar 3.200 nodos.")
    for nombre in FORTRAN + ["mulgen.cmn", "ran2.cmn"]:
        shutil.copy2(fuente / nombre, carpeta / nombre)
    (carpeta / "dim.par").write_text(
        f"      parameter(MAXNODES={nmax}, MAXARCS={4*nmax}, MAXCOMM={25*nmax})\n")
    comando = [compiler, "-std=legacy", "-ffixed-line-length-none",
               "-fno-stack-protector", *FORTRAN, "-o", "mulgen"]
    resultado = medir(comando, carpeta, dict(os.environ), carpeta / "compilacion.log",
                      90, limite_bytes)
    if resultado["codigo"] != 0:
        raise RuntimeError(f"Falló compilación: {carpeta / 'compilacion.log'} ({resultado['estado']}).")
    return carpeta / "mulgen"


def dimensiones(n):
    x = math.isqrt(n)
    while n % x:
        x -= 1
    return n // x, x


def generar(binario, carpeta, n, semilla, limite_bytes):
    carpeta.mkdir(parents=True)
    sx, sy = (80, 40) if n == 3200 else dimensiones(n)
    par = (f"nocca\ninseed {semilla}\nctight 60.0\nfixvar 0.01\nnoprll 10\n"
           f"grdarc 0\nscalex {sx}\nscaley {sy}\ncommod {25*n}\naddarc {4*n}\n"
           "minsrc 1\nmaxsrc 1\nminsnk 1\nmaxsnk 1\nminfct 10\nmaxfct 100\n"
           "mincst 1\nmaxcst 10\nminsup 15\nmaxsup 75\nmincap 100\nmaxcap 500\n"
           "outfil out\nend\n")
    (carpeta / "entrada.par").write_text(par)
    meta = medir([str(binario), "entrada.par"], carpeta, dict(os.environ),
                 carpeta / "generacion.log", 90, limite_bytes)
    ruta = carpeta / "out"
    log = (carpeta / "generacion.log").read_text(errors="replace")
    if meta["codigo"] != 0 or "EXECUTION ABORTED" in log or not ruta.exists():
        raise RuntimeError(f"Falló generación: {carpeta} ({meta['estado']}).")
    with ruta.open() as fh:
        cabecera = tuple(map(int, fh.readline().split()))
    if cabecera != (n, 4*n, 25*n):
        raise RuntimeError(f"Cabecera inesperada {cabecera}; ver {carpeta}.")
    (carpeta / "generacion_medicion.json").write_text(json.dumps(meta, indent=2))
    return ruta


def worker():
    """Carga la instancia una sola vez y ejecuta la entrada pública original."""
    import runpy
    repo, solver, instancia, max_vars = sys.argv[2:]
    sys.path.insert(0, str(Path(repo) / "compat"))
    os.environ["ARCHIVO_INSTANCIA"] = instancia
    import lector
    info = dict(nodos=lector.n, arcos=len(lector.arcos),
                productos_efectivos=len(lector.demandas))
    info["variables_lp_equivalentes"] = info["arcos"] * info["productos_efectivos"]
    print("BENCH_INSTANCIA=" + json.dumps(info), flush=True)
    if solver == "LP" and info["variables_lp_equivalentes"] > int(max_vars):
        raise SystemExit("Se rechazó el LP por superar el máximo de variables permitido.")
    runpy.run_path(str(Path(repo) / "compat" / SOLVERS[solver]), run_name="__main__")


def resumir(filas, destino, objetivo):
    print("\nRAM PICO DEL PROCESO, incluida lectura, Python, librerías y solver")
    print(f"{'Bloque':<9} {'Método':<14} {'N':>5} {'K·A efectivo':>15} {'MiB':>10} {'Corridas':>9}")
    grupos = {}
    for f in filas:
        grupos.setdefault((f["bloque"], f["metodo"], f["nodos_solicitados"]), []).append(f)
    resumen = []
    for (bloque, metodo, n), rr in grupos.items():
        buenas = [x for x in rr if x["estado"] == "completado"]
        usar = buenas or rr
        v = [x["variables_lp_equivalentes"] for x in usar if x.get("variables_lp_equivalentes")]
        medianav = statistics.median(v) if v else None
        ram = statistics.median(x["ram_pico_mib"] for x in usar)
        print(f"{bloque:<9} {metodo:<14} {n:>5} {int(medianav or 0):>15,} {ram:>10.1f} {len(buenas):>3}/{len(rr):<3}")
        resumen.append(dict(bloque=bloque, metodo=metodo, nodos=n,
                            variables_mediana=medianav, ram_mediana_mib=ram,
                            completas=len(buenas), corridas=len(rr)))
    (destino / "resumen.json").write_text(json.dumps(resumen, indent=2))
    puntos = [r for r in resumen if r["bloque"] == "pequeno" and r["metodo"] == "LP"
              and r["completas"] == r["corridas"] and r["variables_mediana"]]
    estimacion = {"tipo": "extrapolacion_exploratoria_no_medida", "variables_objetivo": objetivo}
    if len(puntos) >= 3:
        xs = [p["variables_mediana"] for p in puntos]
        ys = [p["ram_mediana_mib"] for p in puntos]
        mx, my = statistics.mean(xs), statistics.mean(ys)
        slope = sum((x-mx)*(y-my) for x,y in zip(xs,ys)) / sum((x-mx)**2 for x in xs)
        intercept = my - slope*mx
        denom = sum((y-my)**2 for y in ys)
        r2 = 1-sum((y-intercept-slope*x)**2 for x,y in zip(xs,ys))/denom if denom else 0
        estimacion.update(intercepto_mib=intercept, pendiente_mib_por_variable=slope, r2=r2,
                           variables_maximas_medidas=max(xs))
        if slope > 0:
            gib = (intercept+slope*objetivo)/1024
            estimacion["lp_estimado_gib"] = gib
            print(f"\nExtrapolación lineal exploratoria del LP: {gib:,.1f} GiB para {objetivo:,} variables.")
            print(f"Ajuste con intercepto: RAM(MiB)={intercept:.2f}+{slope:.8f}·variables; R²={r2:.3f}.")
        else:
            print("\nLa serie pequeña no permite estimar una pendiente positiva de RAM para el LP.")
    print("La extrapolación NO es RAM medida del LP grande ni un certificado de su consumo.")
    print("Puede omitir cambios de régimen, restricciones, presolve y factorizaciones.")
    (destino / "extrapolacion_lp.json").write_text(json.dumps(estimacion, indent=2))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo", type=Path, default=Path(__file__).resolve().parent)
    ap.add_argument("--salida", type=Path)
    ap.add_argument("--nodos", type=int, nargs="+", default=[8, 12, 20, 40])
    ap.add_argument("--semillas", type=int, nargs="+", default=[1, 2, 3])
    ap.add_argument("--metodos", nargs="+", choices=["LP", "GC_Gurobi", "E3"], default=["LP", "GC_Gurobi", "E3"])
    ap.add_argument("--max-vars-lp", type=int, default=200000)
    ap.add_argument("--ram-mb", type=int, default=1024, help="Corte por RSS muestreada, en MiB. Por defecto 1 GiB.")
    ap.add_argument("--limite", type=float, default=60, help="Segundos por corrida pequeña, incluida construcción.")
    ap.add_argument("--limite-grande", type=float, default=180)
    ap.add_argument("--sin-grande", action="store_true")
    ap.add_argument("--solo-grande", action="store_true", help="Mide solo E3 en N=3.200, sin repetir la serie pequeña.")
    ap.add_argument("--solver-grande", choices=["E3", "E2_historico"], default="E3")
    ap.add_argument("--semilla-grande", type=int, default=10)
    a = ap.parse_args()
    if a.sin_grande and a.solo_grande:
        ap.error("Elige --sin-grande o --solo-grande, no ambos.")
    if os.name != "posix" or not hasattr(os,"wait4"):
        ap.error("Se requiere macOS o Linux.")
    if min(a.nodos) < 8 or max(a.nodos) > 80:
        ap.error("La serie pequeña admite entre 8 y 80 nodos. El LP grande está excluido.")
    if min(a.semillas + [a.semilla_grande]) < 1 or min(a.limite,a.limite_grande) <= 0:
        ap.error("Semillas y tiempos deben ser positivos.")
    if not 128 <= a.ram_mb <= 4096 or not 1 <= a.max_vars_lp <= 1000000:
        ap.error("RAM permitida: 128–4096 MiB. Máximo del LP pequeño: 1.000.000 variables.")
    repo = a.repo.expanduser().resolve()
    if not (repo/"compat/solver.py").is_file() or not (repo/"Canad/Mulgen/main.f").is_file():
        ap.error(f"No encuentro el repositorio en {repo}")
    if rss_bytes(os.getpid()) is None:
        ap.error("No se puede comprobar la lectura de RAM con ps.")
    destino = (a.salida or repo/"experimentos"/("memoria_"+datetime.now().strftime("%Y%m%d_%H%M%S_%f"))).expanduser().resolve()
    destino.mkdir(parents=True, exist_ok=False)
    limite_bytes = a.ram_mb*1024**2
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONUNBUFFERED="1")
    protocolo = dict(vars(a), repo=str(repo), salida=str(destino), python=sys.executable,
                     plataforma=platform.platform(), fecha=datetime.now().astimezone().isoformat(),
                     ram_unidades="MiB=2^20 bytes; GiB=2^30 bytes",
                     medida="ru_maxrss del SO por proceso; RSS muestreada para corte",
                     grande="N=3200,A=12800,K_solicitados=80000; E3 por defecto; nunca LP")
    protocolo["sha256_fuentes"] = {}
    mapa_path = repo/"docs/entradas_compatibles.json"
    mapa = json.loads(mapa_path.read_text()) if mapa_path.exists() else {}
    for archivo in set(SOLVERS.values()):
        p = repo/mapa.get(archivo, archivo)
        if p.exists():protocolo["sha256_fuentes"][str(p.relative_to(repo))]=sha(p)
    for archivo in FORTRAN + ["mulgen.cmn", "ran2.cmn"]:
        p = repo/"Canad"/"Mulgen"/archivo
        protocolo["sha256_fuentes"][str(p.relative_to(repo))]=sha(p)
    (destino/"protocolo.json").write_text(json.dumps(protocolo,default=str,indent=2))
    print(f"Resultados: {destino}", flush=True)
    print(f"Corte de RAM: {a.ram_mb} MiB por proceso; LP solo hasta {a.max_vars_lp:,} variables.",flush=True)
    print("Ctrl+C detiene la corrida activa y conserva las filas ya guardadas.",flush=True)
    binario = compilar_privado(repo,destino,max(a.nodos) if a.sin_grande else 3200,limite_bytes)
    filas=[]
    columnas=["bloque","metodo","script","semilla","nodos_solicitados","nodos","arcos",
              "productos_efectivos","variables_lp_equivalentes","ram_pico_mib","ram_pico_bytes",
              "ram_muestreada_bytes","tiempo_proceso_s","tiempo_interno_s","z","gap_pct",
              "estado","codigo","error_monitor","instancia_sha256","log"]

    def correr(bloque,n,s,instancia,metodo,limite):
        log=destino/f"{bloque}_n{n}_s{s}_{metodo}.log"
        comando=[sys.executable,str(Path(__entry_file__).resolve()),"_worker",str(repo),metodo,str(instancia),str(a.max_vars_lp)]
        entorno=dict(env,E2_LIMITE_TIEMPO=str(limite),E2_ETA="25",E2_TOLERANCIA="1e-7")
        print(f"\n{bloque}: {metodo}, N={n}, semilla={s}",flush=True)
        res=medir(comando,repo,entorno,log,limite,limite_bytes)
        texto=log.read_text(errors="replace")
        info=re.findall(r"^BENCH_INSTANCIA=(.+)$",texto,re.M)
        info=json.loads(info[-1]) if info else {}
        estado=res["estado"]
        if estado=="terminado":
            if res["codigo"] != 0:estado="error_solver"
            elif re.search(r"SIN CERTIFICAR|No se alcanz[oó]",texto):estado="sin_certificar"
            elif re.search(r"[oó]ptima certificada|error relativo certificado|Optimal objective",texto):estado="completado"
            else:estado="sin_confirmacion_optimalidad"
        fila=dict(bloque=bloque,metodo=metodo,script=SOLVERS[metodo],semilla=s,
                  nodos_solicitados=n,**info,**res,instancia_sha256=sha(instancia),log=str(log))
        fila["estado"]=estado;fila["ram_pico_mib"]=round(res["ram_pico_bytes"]/1024**2,3)
        for key,pat in [("z",r"Congesti[oó]n m[aá]xima:\s*([\d.eE+\-]+)"),
                        ("gap_pct",r"^Gap certificado(?: actual)?:\s*([\d.eE+\-]+|inf)%"),
                        ("tiempo_interno_s",r"Tiempo total:\s*([\d.]+)")]:
            matches=re.findall(pat,texto,re.M);fila[key]=matches[-1] if matches else ""
        filas.append(fila)
        with (destino/"corridas.csv").open("a",newline="") as f:
            w=csv.DictWriter(f,fieldnames=columnas)
            if f.tell()==0:w.writeheader()
            w.writerow({k:fila.get(k,"") for k in columnas})
        print(f"  {estado}: pico {fila['ram_pico_mib']:.1f} MiB; proceso {res['tiempo_proceso_s']:.2f} s.",flush=True)
        if estado=="error_monitor":raise RuntimeError(res["error_monitor"])
        if estado=="error_solver":
            print("  Revisar el log antes de continuar: "+str(log),flush=True)
            raise RuntimeError("El solver falló; las corridas anteriores están guardadas.")
        return fila

    bloqueados=set()
    for s in ([] if a.solo_grande else a.semillas):
        for n in sorted(set(a.nodos)):
            instancia=generar(binario,destino/"instancias"/f"pequeno_n{n}_s{s}",n,s,limite_bytes)
            for metodo in a.metodos:
                if metodo in bloqueados:continue
                if metodo=="LP" and 100*n*n>a.max_vars_lp:
                    print(f"Se omite LP N={n}: máximo teórico {100*n*n:,} supera el tope.",flush=True);continue
                fila=correr("pequeno",n,s,instancia,metodo,a.limite)
                if fila["estado"] in ["corte_ram","corte_tiempo"]:
                    bloqueados.add(metodo)
                    print(f"Se detienen las siguientes pruebas pequeñas de {metodo} por ese límite.",flush=True)
    objetivo=992230400
    if not a.sin_grande:
        instancia=generar(binario,destino/"instancias"/f"grande_n3200_s{a.semilla_grande}",3200,a.semilla_grande,limite_bytes)
        f=correr("grande",3200,a.semilla_grande,instancia,a.solver_grande,a.limite_grande)
        objetivo=f.get("variables_lp_equivalentes",objetivo)
        if f["estado"] == "completado":
            print("Pico de RAM de la resolución grande completada, incluidas lectura e importaciones.")
        else:
            print("La corrida grande no completó: el pico registrado es parcial; revisar estado y log.")
    resumir(filas,destino,objetivo)
    print(f"\nCSV y logs guardados en: {destino}")


if __name__=="__main__":
    try:
        if len(sys.argv)>1 and sys.argv[1]=="_worker":worker()
        else:main()
    except KeyboardInterrupt:
        print("\nInterrumpido. Se conservaron las corridas ya guardadas.",file=sys.stderr)
        raise SystemExit(130)
    except Exception as exc:
        print(f"\nERROR: {exc}",file=sys.stderr)
        raise SystemExit(1)
