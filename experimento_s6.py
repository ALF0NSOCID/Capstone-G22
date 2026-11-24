#!/usr/bin/env python3
"""S6: sensibilidad al parámetro eta de la partida con conciencia de congestión (solver_columnas_e2_v2.py).

eta pondera la utilización estimada en el costo de los caminos iniciales: peso = base * (1 + eta * utilización).
eta = 0 equivale a la partida por caminos mínimos sin considerar congestión (caso de referencia del barrido).
Familias de instancias:
  - Mulgen de 400 nodos (mismos parámetros que X3): (grado 4, 25 prod/nodo), (grado 8, 10) y (grado 8, 25), semillas 1-3.
  - Red chilena (instancias enteras en kbps): base, extendida_200 y base_mas_20_candidatos.
Cada corrida agrega una fila a experimentos/s6/corridas.csv; si se interrumpe, al relanzar salta las ya hechas.

Uso (desde la raíz del repo):
  python experimento_s6.py prueba     # 2 corridas cortas para comprobar que todo funciona
  python experimento_s6.py correr     # barrido completo
  python experimento_s6.py resumen    # tabla por familia y eta, y resumen.csv
"""
import argparse, csv, os, re, shutil, statistics, subprocess, sys, time

import experimento_x3 as x3

RAIZ = x3.RAIZ
SALIDA = RAIZ / "experimentos" / "s6"; SALIDA.mkdir(parents=True, exist_ok=True)
INST = SALIDA / "instancias"; INST.mkdir(exist_ok=True)
LOGS = SALIDA / "logs"; LOGS.mkdir(exist_ok=True)
CSV = SALIDA / "corridas.csv"
ETAS = (0, 1, 5, 10, 25, 50, 100)
MULGEN = ((4, 25), (8, 10), (8, 25))
SEMILLAS = (1, 2, 3)
CHILE = ("base", "extendida_200", "base_mas_20_candidatos")
CHILE_DIR = RAIZ / "red_chile" / "instancias_enteras"
CAMPOS = ["familia", "instancia", "eta", "productos_efectivos", "z", "cota_inferior", "gap_pct", "certificacion",
          "iteraciones", "columnas", "tiempo_interno_s", "tiempo_maestro_s", "tiempo_pared_s", "limite_s",
          "codigo_salida"]


def preparar_mulgen(grado, ppn, semilla):
    nombre = f"s6_g{grado:02d}_p{ppn:02d}_s{semilla:02d}"
    destino = INST / f"{nombre}.txt"
    if not destino.exists():
        arcos, productos = grado * x3.N, ppn * x3.N
        (x3.DATA / f"{nombre}.par").write_text(x3.contenido_par(semilla, arcos, productos), encoding="utf-8")
        x3.gen.generar_instancia(nombre)
        shutil.copyfile(RAIZ / "out", destino)
    return f"mulgen_g{grado}_p{ppn}", nombre, destino


def preparar_chile(nombre):
    destino = INST / f"chile_{nombre}.txt"
    if not destino.exists():
        shutil.copyfile(CHILE_DIR / f"{nombre}.txt", destino)
    return "chile", f"chile_{nombre}", destino


def correr_una(familia, nombre, archivo, eta, limite):
    shutil.copyfile(archivo, RAIZ / "out")
    env = dict(os.environ, ARCHIVO_INSTANCIA=str(RAIZ / "out"), E2_LIMITE_TIEMPO=str(limite), E2_ETA=str(eta))
    t0 = time.perf_counter()
    try:
        p = subprocess.run([sys.executable, str(x3.SOLVER)], cwd=RAIZ, env=env, capture_output=True, text=True,
                           timeout=limite + 300)
        salida, codigo = p.stdout + p.stderr, p.returncode
    except subprocess.TimeoutExpired as e:
        salida, codigo = (e.stdout or "") if isinstance(e.stdout, str) else "", "timeout"
    pared = time.perf_counter() - t0
    (LOGS / f"{nombre}_eta{eta}.txt").write_text(salida, encoding="utf-8")
    if "SIN CERTIFICAR" in salida:
        cert = "sin certificar"
    elif "ptima certificada" in salida:
        cert = "óptimo"
    elif "error relativo certificado" in salida:
        cert = "brecha <= 1%"
    elif "No se alcanz" in salida:
        cert = "límite de tiempo"
    else:
        cert = f"error ({codigo})"
    u = x3.ultimo
    maestro = sum(float(v) for v in re.findall(r"maestro=([0-9.]+)s", salida))
    return dict(familia=familia, instancia=nombre, eta=eta,
                productos_efectivos=u(r"^Productos: (\d+) \|", salida, int),
                z=u(r"Congesti[oó]n m[aá]xima:\s*([0-9.eE+\-]+)", salida),
                cota_inferior=u(r"Cota inferior:\s*([0-9.eE+\-]+)", salida),
                gap_pct=u(r"^Gap certificado(?: actual)?:\s*([0-9.eE+\-]+|inf)%", salida),
                certificacion=cert, iteraciones=u(r"Iteraciones:\s*(\d+)", salida, int),
                columnas=u(r"Columnas:\s*(\d+)", salida, int),
                tiempo_interno_s=u(r"Tiempo total:\s*([0-9.]+)", salida),
                tiempo_maestro_s=round(maestro, 2), tiempo_pared_s=round(pared, 2), limite_s=limite,
                codigo_salida=codigo)


def hechas():
    if not CSV.exists():
        return set()
    with open(CSV, newline="", encoding="utf-8") as fh:
        return {(r["instancia"], int(r["eta"])) for r in csv.DictReader(fh)}


def anexar(fila):
    nuevo = not CSV.exists()
    with open(CSV, "a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=CAMPOS)
        if nuevo:
            w.writeheader()
        w.writerow(fila)


def correr(args):
    x3.gen.compilar_mulgen()
    instancias = [preparar_chile(c) for c in CHILE]
    instancias += [preparar_mulgen(g, p, s) for s in SEMILLAS for (g, p) in MULGEN]
    ya = hechas()
    plan = [(f, n, a, e) for (f, n, a) in instancias for e in ETAS]
    pendientes = [c for c in plan if (c[1], c[3]) not in ya]
    print(f"S6: {len(plan)} corridas en el plan, {len(pendientes)} pendientes. Límite {args.limite} s.", flush=True)
    for i, (f, n, a, e) in enumerate(pendientes, 1):
        print(f"\n[{i}/{len(pendientes)}] {n}, eta={e}", flush=True)
        fila = correr_una(f, n, a, e, args.limite); anexar(fila)
        print(f"  -> {fila['certificacion']} | z={fila['z']} | gap={fila['gap_pct']} % | "
              f"iter={fila['iteraciones']} | {fila['tiempo_interno_s']} s", flush=True)


def resumen(_):
    with open(CSV, newline="", encoding="utf-8") as fh:
        filas = list(csv.DictReader(fh))
    grupos = {}
    for r in filas:
        grupos.setdefault((r["familia"], int(r["eta"])), []).append(r)
    salida = []
    print(f"{'familia':>14} {'eta':>5} {'certifica':>10} {'mediana s':>10} {'iter med':>9} {'cols med':>9}")
    for (fam, eta), rs in sorted(grupos.items()):
        ok = [r for r in rs if r["certificacion"] in ("óptimo", "brecha <= 1%")]
        med = statistics.median(float(r["tiempo_interno_s"]) for r in ok) if ok else None
        it = statistics.median(int(r["iteraciones"]) for r in rs if r["iteraciones"])
        cols = statistics.median(int(r["columnas"]) for r in rs if r["columnas"])
        print(f"{fam:>14} {eta:>5} {len(ok)}/{len(rs):<8} {(f'{med:.2f}' if med is not None else '-'):>10} {it:>9} {cols:>9}")
        salida.append(dict(familia=fam, eta=eta, certificadas=len(ok), corridas=len(rs),
                           mediana_tiempo_s=med if med is not None else "", iteraciones_mediana=it,
                           columnas_mediana=cols))
    with open(SALIDA / "resumen.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(salida[0])); w.writeheader(); w.writerows(salida)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("modo", choices=["prueba", "correr", "resumen"])
    ap.add_argument("--limite", type=float, default=300)
    a = ap.parse_args()
    if a.modo == "prueba":
        x3.gen.compilar_mulgen()
        f, n, arch = preparar_chile("base")
        for e in (0, 25):
            r = correr_una(f, n, arch, e, 120)
            print({k: r[k] for k in ("instancia", "eta", "z", "gap_pct", "certificacion", "iteraciones",
                                      "tiempo_interno_s")})
    elif a.modo == "correr":
        correr(a)
    else:
        resumen(a)
