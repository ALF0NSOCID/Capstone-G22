#!/usr/bin/env python3
"""X3: densidad con carga controlada (análisis de sensibilidad del supuesto S3).

Factorial grado {4, 8, 12, 16} x productos por nodo {10, 25, 50} con N = 400 nodos (Mulgen),
5 semillas iguales en todas las celdas, resuelto con solver_columnas_e2_v2.py y límite de 900 s.
Cada corrida agrega una fila a experimentos/x3/corridas.csv; si se interrumpe, al volver a lanzarlo
salta las que ya están (se puede cortar y retomar).

Uso (desde la raíz del repo):
  python experimento_x3.py prueba                 # 1 corrida corta (grado 4, 10 prod/nodo, semilla 1, 120 s)
  python experimento_x3.py correr                 # las 60 corridas
  python experimento_x3.py correr --recortado     # 24 corridas: 10 y 25 prod/nodo, semillas 1-3
  python experimento_x3.py correr --semillas 1 2  # solo esas semillas (para repartir entre computadores)
  python experimento_x3.py resumen                # tabla por celda: tasa de certificación y mediana de tiempo
"""
import argparse, csv, os, re, statistics, subprocess, sys, time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
DATA = RAIZ / "Canad" / "Data"
SALIDA = RAIZ / "experimentos" / "x3"; SALIDA.mkdir(parents=True, exist_ok=True)
CSV = SALIDA / "corridas.csv"
LOGS = SALIDA / "logs"; LOGS.mkdir(exist_ok=True)
SOLVER = RAIZ / "solver_columnas_e2_v2.py"
N = 400
GRADOS = (4, 8, 12, 16)
PROD_POR_NODO = (10, 25, 50)
CAMPOS = ["instancia", "semilla", "grado", "productos_por_nodo", "nodos", "arcos", "productos_generados",
          "productos_efectivos", "z", "cota_inferior", "gap_pct", "certificacion", "iteraciones", "columnas",
          "tiempo_interno_s", "tiempo_maestro_s", "tiempo_pared_s", "limite_s", "codigo_salida"]

if os.name == "nt":
    import ejecutar_windows as gen
else:
    import ejecutar as gen


def contenido_par(semilla, arcos, productos):
    # Mismos parámetros Mulgen que la Entrega 2 (t1-t100 y experimento_conclusiones.py).
    return (f"nocca\ninseed {semilla}\nctight 60.0\nfixvar 0.01\nnoprll 10\ngrdarc 0\nscalex 40\nscaley 10\n"
            f"commod {productos}\naddarc {arcos}\nminsrc 1\nmaxsrc 1\nminsnk 1\nmaxsnk 1\nminfct 10\nmaxfct 100\n"
            f"mincst 1\nmaxcst 10\nminsup 15\nmaxsup 75\nmincap 100\nmaxcap 500\noutfil out\nend\n")


def ultimo(patron, texto, conv=float):
    m = re.findall(patron, texto, flags=re.MULTILINE)
    if not m:
        return ""
    return float("inf") if m[-1] == "inf" else conv(m[-1])


def correr_una(grado, ppn, semilla, limite):
    arcos, productos = grado * N, ppn * N
    nombre = f"x3_g{grado:02d}_p{ppn:02d}_s{semilla:02d}"
    (DATA / f"{nombre}.par").write_text(contenido_par(semilla, arcos, productos), encoding="utf-8")
    gen.generar_instancia(nombre)
    env = dict(os.environ, ARCHIVO_INSTANCIA=str(RAIZ / "out"), E2_LIMITE_TIEMPO=str(limite))
    t0 = time.perf_counter()
    try:
        p = subprocess.run([sys.executable, str(SOLVER)], cwd=RAIZ, env=env, capture_output=True, text=True,
                           timeout=limite + 300)
        salida, codigo = p.stdout + p.stderr, p.returncode
    except subprocess.TimeoutExpired as e:
        salida, codigo = (e.stdout or "") if isinstance(e.stdout, str) else "", "timeout"
    pared = time.perf_counter() - t0
    (LOGS / f"{nombre}.txt").write_text(salida, encoding="utf-8")
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
    maestro = sum(float(x) for x in re.findall(r"maestro=([0-9.]+)s", salida))
    return dict(instancia=nombre, semilla=semilla, grado=grado, productos_por_nodo=ppn, nodos=N, arcos=arcos,
                productos_generados=productos,
                productos_efectivos=ultimo(r"^Productos: (\d+) \|", salida, int),
                z=ultimo(r"Congesti[oó]n m[aá]xima:\s*([0-9.eE+\-]+)", salida),
                cota_inferior=ultimo(r"Cota inferior:\s*([0-9.eE+\-]+)", salida),
                gap_pct=ultimo(r"^Gap certificado(?: actual)?:\s*([0-9.eE+\-]+|inf)%", salida),
                certificacion=cert, iteraciones=ultimo(r"Iteraciones:\s*(\d+)", salida, int),
                columnas=ultimo(r"Columnas:\s*(\d+)", salida, int),
                tiempo_interno_s=ultimo(r"Tiempo total:\s*([0-9.]+)", salida),
                tiempo_maestro_s=round(maestro, 2), tiempo_pared_s=round(pared, 2), limite_s=limite,
                codigo_salida=codigo)


def hechas():
    if not CSV.exists():
        return set()
    with open(CSV, newline="", encoding="utf-8") as fh:
        return {r["instancia"] for r in csv.DictReader(fh)}


def anexar(fila):
    nuevo = not CSV.exists()
    with open(CSV, "a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=CAMPOS)
        if nuevo:
            w.writeheader()
        w.writerow(fila)


def correr(args):
    semillas = args.semillas or ([1, 2, 3] if args.recortado else [1, 2, 3, 4, 5])
    ppns = (10, 25) if args.recortado else PROD_POR_NODO
    ya = hechas()
    plan = [(g, p, s) for s in semillas for p in ppns for g in GRADOS]   # semilla afuera: resultados parejos si se corta
    pendientes = [c for c in plan if f"x3_g{c[0]:02d}_p{c[1]:02d}_s{c[2]:02d}" not in ya]
    print(f"X3: {len(plan)} corridas en el plan, {len(pendientes)} pendientes. Límite {args.limite} s.", flush=True)
    gen.compilar_mulgen()
    for i, (g, p, s) in enumerate(pendientes, 1):
        print(f"\n[{i}/{len(pendientes)}] grado {g}, {p} productos/nodo, semilla {s}", flush=True)
        fila = correr_una(g, p, s, args.limite); anexar(fila)
        print(f"  -> {fila['certificacion']} | z={fila['z']} | gap={fila['gap_pct']} % | "
              f"iter={fila['iteraciones']} | {fila['tiempo_interno_s']} s", flush=True)


def resumen(_):
    with open(CSV, newline="", encoding="utf-8") as fh:
        filas = list(csv.DictReader(fh))
    celdas = {}
    for r in filas:
        celdas.setdefault((int(r["grado"]), int(r["productos_por_nodo"])), []).append(r)
    salida = []
    print(f"{'grado':>5} {'prod/nodo':>9} {'certifica':>10} {'mediana s':>10} {'iter med':>9}")
    for (g, p), rs in sorted(celdas.items()):
        ok = [r for r in rs if r["certificacion"] in ("óptimo", "brecha <= 1%")]
        med = statistics.median(float(r["tiempo_interno_s"]) for r in ok) if 2 * len(ok) > len(rs) else None
        it = statistics.median(int(r["iteraciones"]) for r in rs if r["iteraciones"])
        txt = f"{med:.2f}" if med is not None else f"> {rs[0]['limite_s']}"
        print(f"{g:>5} {p:>9} {len(ok)}/{len(rs):<8} {txt:>10} {it:>9}")
        salida.append(dict(grado=g, productos_por_nodo=p, certificadas=len(ok), corridas=len(rs),
                           mediana_tiempo_s=med if med is not None else "", iteraciones_mediana=it))
    with open(SALIDA / "resumen.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(salida[0])); w.writeheader(); w.writerows(salida)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("modo", choices=["prueba", "correr", "resumen"])
    ap.add_argument("--recortado", action="store_true")
    ap.add_argument("--semillas", type=int, nargs="+")
    ap.add_argument("--limite", type=float, default=900)
    a = ap.parse_args()
    if a.modo == "prueba":
        gen.compilar_mulgen()
        f = correr_una(4, 10, 1, 120)
        print({k: f[k] for k in ("instancia", "productos_efectivos", "z", "gap_pct", "certificacion", "iteraciones",
                                  "tiempo_interno_s")})
    elif a.modo == "correr":
        correr(a)
    else:
        resumen(a)
