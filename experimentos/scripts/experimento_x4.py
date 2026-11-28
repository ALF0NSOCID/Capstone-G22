#!/usr/bin/env python3
"""X4: escalabilidad en tamaño (análisis de sensibilidad: escala del problema).

Redes Mulgen con grado 4 (arcos = 4N) y 25 productos por nodo (K = 25N), N = 200, 400, 800, 1.600
(3.200 incluido por defecto), 30 semillas por tamaño. Resuelve con solver_columnas_e2_v2.py (E3, límite 900 s) y,
para comparar, con el caso base (solver_columnas_pricing_gurobi.py) hasta N = 800.
Una fila por corrida en experimentos/x4/corridas.csv; si se corta, al relanzarlo retoma.

Uso (desde la raíz del repo):
  python experimento_x4.py prueba              # 1 corrida corta (N = 200, semilla 1)
  python experimento_x4.py plan                # 240 corridas por defecto, sin ejecutar
  python experimento_x4.py correr              # E3 en N = 200..3.200 + GC base en N = 200..800
  python experimento_x4.py correr --sin-3200   # omite N = 3.200
  python experimento_x4.py correr --sin-base   # solo E3 (150 corridas)
  python experimento_x4.py resumen             # tabla por tamaño y β (log-log) con intervalo de confianza 95 %
"""
import argparse, csv, math, os, re, statistics, subprocess, sys, time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
DATA = RAIZ / "Canad" / "Data"
SALIDA = RAIZ / "experimentos" / "x4_formal"
CSV = SALIDA / "corridas.csv"
LOGS = SALIDA / "logs"
SOLVERS = {"e2_v2": RAIZ / "compat" / "solver_columnas_e2_v2.py", "base": RAIZ / "compat" / "solver_columnas_pricing_gurobi.py"}
# nodos de Mulgen = scalex * scaley (mismas grillas que benchmark_escalabilidad.csv)
GRILLA = {200: (25, 8), 400: (40, 10), 800: (40, 20), 1600: (80, 20), 3200: (80, 40)}
GRADO, PROD_POR_NODO, SEMILLAS = 4, 25, tuple(range(1, 31))
CAMPOS = ["instancia", "metodo", "semilla", "nodos", "arcos", "productos_generados", "productos_efectivos",
          "k_por_arcos", "z", "cota_inferior", "gap_pct", "certificacion", "iteraciones", "columnas",
          "tiempo_interno_s", "tiempo_pared_s", "limite_s", "codigo_salida"]

if os.name == "nt":
    import ejecutar_windows as gen
else:
    import ejecutar as gen


def contenido_par(semilla, nodos, arcos, productos):
    sx, sy = GRILLA[nodos]
    return (f"nocca\ninseed {semilla}\nctight 60.0\nfixvar 0.01\nnoprll 10\ngrdarc 0\nscalex {sx}\nscaley {sy}\n"
            f"commod {productos}\naddarc {arcos}\nminsrc 1\nmaxsrc 1\nminsnk 1\nmaxsnk 1\nminfct 10\nmaxfct 100\n"
            f"mincst 1\nmaxcst 10\nminsup 15\nmaxsup 75\nmincap 100\nmaxcap 500\noutfil out\nend\n")


def ultimo(patron, texto, conv=float):
    m = re.findall(patron, texto, flags=re.MULTILINE)
    if not m:
        return ""
    return float("inf") if m[-1] == "inf" else conv(m[-1])


def generar(nodos, semilla):
    arcos, productos = GRADO * nodos, PROD_POR_NODO * nodos
    nombre = f"x4_n{nodos:04d}_s{semilla:02d}"
    (DATA / f"{nombre}.par").write_text(contenido_par(semilla, nodos, arcos, productos), encoding="utf-8")
    gen.generar_instancia(nombre)
    with open(RAIZ / "trabajo" / "out", encoding="utf-8") as fh:
        n_real = int(fh.readline().split()[0])
    if n_real != nodos:
        raise RuntimeError(f"Mulgen generó {n_real} nodos, se esperaban {nodos}")
    return nombre, arcos, productos


def resolver(nombre, metodo, nodos, arcos, productos, semilla, limite):
    env = dict(os.environ, ARCHIVO_INSTANCIA=str(RAIZ / "trabajo" / "out"), E2_LIMITE_TIEMPO=str(limite))
    t0 = time.perf_counter()
    try:
        p = subprocess.run([sys.executable, str(SOLVERS[metodo])], cwd=RAIZ, env=env, capture_output=True,
                           text=True, timeout=limite + 600)
        salida, codigo = p.stdout + p.stderr, p.returncode
    except subprocess.TimeoutExpired as e:
        salida, codigo = (e.stdout if isinstance(e.stdout, str) else ""), "timeout"
    pared = time.perf_counter() - t0
    (LOGS / f"{nombre}_{metodo}.txt").write_text(salida, encoding="utf-8")
    if "SIN CERTIFICAR" in salida:
        cert = "sin certificar"
    elif re.search(r"[oó]ptima certificada", salida):
        cert = "óptimo"
    elif "error relativo certificado" in salida:
        cert = "brecha <= 1%"
    elif "No se alcanz" in salida or codigo == "timeout":
        cert = "límite de tiempo"
    elif codigo == 0 and re.search(r"Congesti[oó]n m[aá]xima", salida):
        cert = "óptimo (sin cota)"   # el caso base no calcula cota inferior
    else:
        cert = f"error ({codigo})"
    k_ef = ultimo(r"^Productos: (\d+)", salida, int)
    return dict(instancia=nombre, metodo=metodo, semilla=semilla, nodos=nodos, arcos=arcos,
                productos_generados=productos, productos_efectivos=k_ef,
                k_por_arcos=(k_ef * arcos) if k_ef != "" else "",
                z=ultimo(r"Congesti[oó]n m[aá]xima:\s*([0-9.eE+\-]+)", salida),
                cota_inferior=ultimo(r"Cota inferior:\s*([0-9.eE+\-]+)", salida),
                gap_pct=ultimo(r"^Gap certificado(?: actual)?:\s*([0-9.eE+\-]+|inf)%", salida),
                certificacion=cert, iteraciones=ultimo(r"Iteraciones:\s*(\d+)", salida, int),
                columnas=ultimo(r"Columnas:\s*(\d+)", salida, int),
                tiempo_interno_s=ultimo(r"Tiempo total:\s*([0-9.]+)", salida),
                tiempo_pared_s=round(pared, 2), limite_s=limite, codigo_salida=codigo)


def hechas():
    if not CSV.exists():
        return set()
    with open(CSV, newline="", encoding="utf-8") as fh:
        return {(r["instancia"], r["metodo"]) for r in csv.DictReader(fh)}


def anexar(fila):
    nuevo = not CSV.exists()
    with open(CSV, "a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=CAMPOS)
        if nuevo:
            w.writeheader()
        w.writerow(fila)


def correr(args):
    tamanos = [200, 400, 800, 1600] + ([3200] if args.con_3200 else [])
    ya = hechas()
    plan = []
    for s in args.semillas:                  # semilla afuera: si se corta, todos los tamaños tienen datos parejos
        for n in tamanos:
            metodos = ["e2_v2"] + (["base"] if (not args.sin_base and n <= 800) else [])
            pend = [m for m in metodos if (f"x4_n{n:04d}_s{s:02d}", m) not in ya]
            if pend:
                plan.append((n, s, pend))
    total = sum(len(p) for _, _, p in plan)
    print(f"X4: {total} corridas pendientes. Límite {args.limite} s por corrida.", flush=True)
    print(f"Salida: {SALIDA}; tamaños: {tamanos}; semillas: {args.semillas}", flush=True)
    print("Métodos: E3 y GC base hasta 800 nodos" if not args.sin_base else "Método: E3", flush=True)
    if args.modo == "plan":
        return
    gen.compilar_mulgen()
    k = 0
    for n, s, metodos in plan:
        nombre, arcos, productos = generar(n, s)
        for m in metodos:
            k += 1
            print(f"\n[{k}/{total}] N = {n}, semilla {s}, método {m}", flush=True)
            fila = resolver(nombre, m, n, arcos, productos, s, args.limite); anexar(fila)
            print(f"  -> {fila['certificacion']} | z={fila['z']} | gap={fila['gap_pct']} % | "
                  f"iter={fila['iteraciones']} | {fila['tiempo_interno_s']} s", flush=True)


def ajuste_beta(xs, ys):
    """Regresión log-log: log(t) = a + β log(K·|A|). Devuelve β, IC95 % y R²."""
    lx, ly = [math.log10(x) for x in xs], [math.log10(y) for y in ys]
    n = len(lx); mx, my = sum(lx) / n, sum(ly) / n
    sxx = sum((x - mx) ** 2 for x in lx); sxy = sum((x - mx) * (y - my) for x, y in zip(lx, ly))
    b = sxy / sxx; a = my - b * mx
    res = [y - (a + b * x) for x, y in zip(lx, ly)]
    s2 = sum(r * r for r in res) / (n - 2); se = math.sqrt(s2 / sxx)
    t = {3: 3.18, 4: 2.78, 5: 2.57, 6: 2.45, 7: 2.36, 8: 2.31, 9: 2.26, 10: 2.23}.get(n - 2, 2.0)
    r2 = 1 - sum(r * r for r in res) / sum((y - my) ** 2 for y in ly)
    return b, t * se, r2


def resumen(_):
    with open(CSV, newline="", encoding="utf-8") as fh:
        filas = list(csv.DictReader(fh))
    ok = lambda r: r["certificacion"] in ("óptimo", "brecha <= 1%", "óptimo (sin cota)")
    salida = []
    for metodo in ("e2_v2", "base"):
        rs = [r for r in filas if r["metodo"] == metodo]
        if not rs:
            continue
        print(f"\n== {metodo} ==\n{'N':>6} {'certifica':>10} {'mediana s':>10} {'iter med':>9}")
        for n in sorted({int(r["nodos"]) for r in rs}):
            c = [r for r in rs if int(r["nodos"]) == n]; buenas = [r for r in c if ok(r)]
            med = statistics.median(float(r["tiempo_interno_s"]) for r in buenas) if 2 * len(buenas) > len(c) else None
            it = statistics.median(int(r["iteraciones"]) for r in c if r["iteraciones"]) if any(r["iteraciones"] for r in c) else ""
            print(f"{n:>6} {len(buenas)}/{len(c):<8} {(f'{med:.2f}' if med is not None else '> límite'):>10} {it:>9}")
            salida.append(dict(metodo=metodo, nodos=n, certificadas=len(buenas), corridas=len(c),
                               mediana_tiempo_s=med if med is not None else "", iteraciones_mediana=it))
        pts = [(float(r["k_por_arcos"]), float(r["tiempo_interno_s"])) for r in rs if ok(r) and r["k_por_arcos"]]
        if len(pts) >= 4:
            b, ic, r2 = ajuste_beta(*zip(*pts))
            print(f"β = {b:.2f} ± {ic:.2f} (IC 95 %, {len(pts)} corridas certificadas, R² = {r2:.2f})")
            salida.append(dict(metodo=metodo, nodos="beta", certificadas=len(pts), corridas="",
                               mediana_tiempo_s=f"{b:.3f} ± {ic:.3f}", iteraciones_mediana=f"R2={r2:.2f}"))
    with open(SALIDA / "resumen.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(salida[0])); w.writeheader(); w.writerows(salida)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("modo", choices=["prueba", "correr", "resumen", "plan"])
    ap.add_argument("--con-3200", dest="con_3200", action="store_true", default=True)
    ap.add_argument("--sin-3200", dest="con_3200", action="store_false")
    ap.add_argument("--sin-base", action="store_true")
    ap.add_argument("--semillas", type=int, nargs="+", default=list(SEMILLAS))
    ap.add_argument("--salida", type=Path, default=SALIDA)
    ap.add_argument("--limite", type=float, default=900)
    a = ap.parse_args()
    if a.limite <= 0 or min(a.semillas) < 1 or len(set(a.semillas)) != len(a.semillas):
        ap.error("Límite positivo y semillas positivas sin duplicados.")
    SALIDA = a.salida.expanduser().resolve(); CSV = SALIDA / "corridas.csv"; LOGS = SALIDA / "logs"
    if a.modo in ("prueba", "correr"):
        LOGS.mkdir(parents=True, exist_ok=True)
    if a.modo == "prueba":
        gen.compilar_mulgen()
        nombre, arcos, productos = generar(200, 1)
        f = resolver(nombre, "e2_v2", 200, arcos, productos, 1, 120)
        print({k: f[k] for k in ("instancia", "productos_efectivos", "z", "gap_pct", "certificacion", "iteraciones",
                                  "tiempo_interno_s")})
    elif a.modo in ("correr", "plan"):
        correr(a)
    else:
        resumen(a)
