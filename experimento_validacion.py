#!/usr/bin/env python3
"""V1: validación del solver final (solver_columnas_e2_v2.py, eta = 25) contra un LP exacto (HiGHS).

Para cada instancia se resuelve (a) el LP de congestión mínima agregado por origen (red_chile/scripts/resolver_referencia.py,
sobre la MISMA instancia ya filtrada de productos sin camino) y (b) el solver E2 v2. Se comprueba que:
  1. z_E2 coincide con z_LP (diferencia relativa <= 1e-6 cuando E2 declara óptimo),
  2. la cota inferior de E2 cumple LB <= z_LP <= UB (el certificado de error es verdadero),
y se mide cuántas veces más rápido es E2 (tiempo de pared de E2 incluyendo arranque de Python y lectura, contra tiempo del LP).

Bloque A (100 semillas): redes chicas de 50 nodos, 10 productos por nodo, cuatro familias:
  Mulgen grado 4, Mulgen grado 6, Waxman grado 4, Waxman grado 6  (400 corridas; Waxman con alpha = 0,4 y beta = 0,4 porque con 50 nodos alpha = 0,2 no alcanza grados altos; el LP en grado 8 tarda ~13 s, por eso se usa grado 6).
Bloque B (escala): Mulgen grado 4, 10 productos por nodo, N = 50, 100, 200, 400, semillas 1-3, para mostrar que el LP deja de ser viable.
Cada corrida agrega una fila a experimentos/validacion/corridas.csv; si se interrumpe, al relanzar salta las hechas.

Uso (desde la raíz del repo):
  python experimento_validacion.py prueba                   # 3 semillas de Mulgen grado 4 y N = 50
  python experimento_validacion.py correr                   # bloques A y B completos
  python experimento_validacion.py correr --semillas 20     # bloque A con 20 semillas (prueba rápida)
  python experimento_validacion.py correr --maxn 200        # bloque B hasta N = 200 (omite N = 400)
  python experimento_validacion.py resumen                  # tablas y resumen.csv
"""
import argparse, csv, math, statistics, sys, time

import experimento_s6 as s6
import experimento_x3 as x3
from generador_waxman import generar_instancia as gen_waxman, escribir_instancia
from corrector_conectividad import corregir_conectividad

RAIZ = x3.RAIZ
sys.path.insert(0, str(RAIZ / "red_chile" / "scripts"))
import resolver_referencia as rr

SALIDA = RAIZ / "experimentos" / "validacion"; SALIDA.mkdir(parents=True, exist_ok=True)
INST = SALIDA / "instancias"; INST.mkdir(exist_ok=True)
LOGS = SALIDA / "logs"; LOGS.mkdir(exist_ok=True)
CSV = SALIDA / "corridas.csv"
s6.LOGS = LOGS
ETA, PPN = 25, 10
GRILLA = {50: (10, 5), 100: (10, 10), 200: (25, 8), 400: (40, 10)}
CAMPOS = ["bloque", "familia", "instancia", "semilla", "nodos", "arcos", "productos_lp", "productos_e2", "estado_lp",
          "z_lp", "t_lp_s", "z_e2", "cota_inferior", "gap_pct", "certificacion", "iteraciones", "columnas",
          "t_e2_interno_s", "t_e2_pared_s", "dif_rel", "cota_ok", "aceleracion"]

# (E2 imprime z y la cota con 8 decimales: la comparación usa tolerancia relativa 1e-7.)
# El LP de referencia con límite de tiempo y estado.
_orig_linprog, _estado = rr.linprog, {}
LIMITE_LP = 600.0
def _lp(*a, **k):
    res = _orig_linprog(*a, **k, options={"time_limit": LIMITE_LP}); _estado["status"] = res.status; return res
rr.linprog = _lp


def contenido_par(semilla, nodos, arcos, productos):
    sx, sy = GRILLA[nodos]
    return (f"nocca\ninseed {semilla}\nctight 60.0\nfixvar 0.01\nnoprll 10\ngrdarc 0\nscalex {sx}\nscaley {sy}\n"
            f"commod {productos}\naddarc {arcos}\nminsrc 1\nmaxsrc 1\nminsnk 1\nmaxsnk 1\nminfct 10\nmaxfct 100\n"
            f"mincst 1\nmaxcst 10\nminsup 15\nmaxsup 75\nmincap 100\nmaxcap 500\noutfil out\nend\n")


def preparar(tipo, nodos, grado, semilla):
    nombre = f"v_{tipo}_n{nodos:04d}_g{grado:02d}_s{semilla:03d}"
    destino = INST / f"{nombre}.txt"
    if not destino.exists() or destino.stat().st_size == 0:
        if tipo == "mulgen":
            (x3.DATA / f"{nombre}.par").write_text(contenido_par(semilla, nodos, grado * nodos, PPN * nodos), encoding="utf-8")
            x3.gen.generar_instancia(nombre)
            import shutil; shutil.copyfile(RAIZ / "out", destino)
            with open(destino, encoding="utf-8") as fh:
                real = int(fh.readline().split()[0])
            if real != nodos:
                raise RuntimeError(f"Mulgen generó {real} nodos, se esperaban {nodos}")
        else:
            g, a, c = gen_waxman(nodos=nodos, productos=PPN * nodos, arcos_objetivo=grado * nodos, alpha=0.4, beta=0.4, semilla=semilla)
            escribir_instancia(destino, g, a, c)
    return f"{tipo}_g{grado}", nombre, destino


def leer_filtrada(ruta):
    """Lee la instancia Canad y aplica el mismo filtro de productos sin camino que usa el solver."""
    with open(ruta, encoding="utf-8") as fh:
        n, m, K = map(int, fh.readline().split())
        arcos = []
        for i in range(m):
            o, d, _, c, q = map(int, fh.readline().split())
            for _ in range(q): fh.readline()
            arcos.append({"id": i, "origen": o, "destino": d, "capacidad": c})
        bal = {}
        for linea in fh:
            if linea.strip():
                k, v, q = map(int, linea.split()); bal.setdefault(k, []).append((v, q))
    dem = []
    for k in range(1, K + 1):
        of = [(v, q) for v, q in bal[k] if q > 0]; de = [(v, -q) for v, q in bal[k] if q < 0]
        dem.append({"producto": k, "origen": of[0][0], "destino": de[0][0], "origenes": of, "destinos": de, "demanda": of[0][1]})
    corregir_conectividad(n, arcos, dem)
    return n, [(a["origen"], a["destino"], float(a["capacidad"])) for a in arcos], [(d["origen"], d["destino"], float(d["demanda"])) for d in dem]


def una(bloque, familia, nombre, archivo, semilla, nodos, grado):
    n, arcs, prods = leer_filtrada(archivo)
    t0 = time.perf_counter(); z_lp, _, _ = rr.resolver(n, arcs, prods); t_lp = time.perf_counter() - t0
    estado = "óptimo" if z_lp is not None else ("límite de tiempo" if _estado.get("status") == 1 else f"sin solución ({_estado.get('status')})")
    r = s6.correr_una(familia, nombre, archivo, ETA, 300)
    z, lb = r["z"], r["cota_inferior"]
    dif = abs(z - z_lp) / max(abs(z_lp), 1e-12) if (z_lp is not None and z != "") else ""
    ok = ""
    if z_lp is not None and z != "" and lb != "":
        ok = bool(lb <= z_lp * (1 + 1e-7) + 1e-12 and z_lp <= z * (1 + 1e-7) + 1e-12)
    acel = (t_lp / float(r["tiempo_pared_s"])) if (z_lp is not None and r["tiempo_pared_s"]) else ""
    return dict(bloque=bloque, familia=familia, instancia=nombre, semilla=semilla, nodos=nodos, arcos=grado * nodos,
                productos_lp=len(prods), productos_e2=r["productos_efectivos"], estado_lp=estado,
                z_lp=z_lp if z_lp is not None else "", t_lp_s=round(t_lp, 2), z_e2=z, cota_inferior=lb,
                gap_pct=r["gap_pct"], certificacion=r["certificacion"], iteraciones=r["iteraciones"], columnas=r["columnas"],
                t_e2_interno_s=r["tiempo_interno_s"], t_e2_pared_s=r["tiempo_pared_s"], dif_rel=dif, cota_ok=ok, aceleracion=acel)


def hechas():
    if not CSV.exists(): return set()
    with open(CSV, newline="", encoding="utf-8") as fh:
        return {r["instancia"] for r in csv.DictReader(fh)}


def anexar(fila):
    nuevo = not CSV.exists() or CSV.stat().st_size == 0
    with open(CSV, "a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=CAMPOS)
        if nuevo: w.writeheader()
        w.writerow(fila)


def plan(args):
    p = []
    for tipo in ("mulgen", "waxman"):
        for g in (4, 6):
            p += [("A", tipo, 50, g, s) for s in range(1, args.semillas + 1)]
    p += [("B", "mulgen", n, 4, s) for n in (50, 100, 200, 400) if n <= args.maxn for s in (1, 2, 3)]
    return p


def correr(args):
    x3.gen.compilar_mulgen()
    todo, ya = plan(args), hechas()
    pend = [c for c in todo if f"v_{c[1]}_n{c[2]:04d}_g{c[3]:02d}_s{c[4]:03d}" not in ya]
    print(f"V1: {len(todo)} corridas en el plan, {len(pend)} pendientes.", flush=True)
    for k, (b, tipo, n, g, s) in enumerate(pend, 1):
        fam, nombre, arch = preparar(tipo, n, g, s)
        print(f"[{k}/{len(pend)}] {nombre}", flush=True)
        f = una(b, fam, nombre, arch, s, n, g); anexar(f)
        print(f"  -> LP {f['estado_lp']} {f['t_lp_s']} s | E2 {f['certificacion']} {f['t_e2_pared_s']} s | dif={f['dif_rel']} | cota_ok={f['cota_ok']} | x{f['aceleracion'] if f['aceleracion']=='' else round(f['aceleracion'],1)}", flush=True)


def resumen(_):
    filas = list(csv.DictReader(open(CSV, newline="", encoding="utf-8")))
    salida = []
    print("Bloque A (100 semillas, N = 50)")
    print(f"{'familia':>12} {'n':>4} {'E2 óptimo':>10} {'dif máx':>9} {'cota ok':>8} {'acel. med':>10} {'acel. máx':>10} {'LP med s':>9} {'E2 med s':>9}")
    for fam in sorted({r["familia"] for r in filas if r["bloque"] == "A"}):
        rs = [r for r in filas if r["bloque"] == "A" and r["familia"] == fam]
        lp = [r for r in rs if r["estado_lp"] == "óptimo"]
        opt = sum(r["certificacion"] == "óptimo" for r in rs)
        difs = [float(r["dif_rel"]) for r in lp if r["dif_rel"] != ""]
        cota = sum(float(r["cota_inferior"]) <= float(r["z_lp"]) * (1 + 1e-7) and float(r["z_lp"]) <= float(r["z_e2"]) * (1 + 1e-7) for r in lp)
        ac = [float(r["aceleracion"]) for r in lp if r["aceleracion"] != ""]
        d = dict(bloque="A", familia=fam, instancias=len(rs), lp_resueltas=len(lp), e2_optimas=opt, dif_rel_max=max(difs) if difs else "",
                 cota_ok=cota, aceleracion_mediana=statistics.median(ac), aceleracion_media_geom=math.exp(statistics.mean(math.log(a) for a in ac)),
                 aceleracion_max=max(ac), t_lp_mediana_s=statistics.median(float(r["t_lp_s"]) for r in lp),
                 t_e2_pared_mediana_s=statistics.median(float(r["t_e2_pared_s"]) for r in lp))
        salida.append(d)
        print(f"{fam:>12} {len(rs):>4} {opt:>10} {d['dif_rel_max']:>9.1e} {cota:>5}/{len(lp):<2} {d['aceleracion_mediana']:>10.1f} {d['aceleracion_max']:>10.1f} {d['t_lp_mediana_s']:>9.2f} {d['t_e2_pared_mediana_s']:>9.2f}")
    print("\nBloque B (escala, Mulgen grado 4, 10 prod/nodo)")
    print(f"{'N':>5} {'LP resueltas':>13} {'LP med s':>9} {'E2 med s':>9} {'aceleración':>12}")
    for n in sorted({int(r["nodos"]) for r in filas if r["bloque"] == "B"}):
        rs = [r for r in filas if r["bloque"] == "B" and int(r["nodos"]) == n]
        lp = [r for r in rs if r["estado_lp"] == "óptimo"]
        tlp = statistics.median(float(r["t_lp_s"]) for r in rs)
        te2 = statistics.median(float(r["t_e2_pared_s"]) for r in rs)
        d = dict(bloque="B", familia=f"mulgen_g4_n{n}", instancias=len(rs), lp_resueltas=len(lp), t_lp_mediana_s=tlp, t_e2_pared_mediana_s=te2,
                 aceleracion_mediana=tlp / te2, dif_rel_max=max((float(r["dif_rel"]) for r in lp if r["dif_rel"] != ""), default=""))
        salida.append(d)
        print(f"{n:>5} {len(lp)}/{len(rs):<11} {tlp:>9.2f} {te2:>9.2f} {tlp / te2:>11.1f}x")
    campos = sorted({k for d in salida for k in d}, key=lambda k: ["bloque", "familia"].index(k) if k in ("bloque", "familia") else 9)
    with open(SALIDA / "resumen.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=campos); w.writeheader(); w.writerows(salida)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("modo", choices=["prueba", "correr", "resumen"])
    ap.add_argument("--semillas", type=int, default=100)
    ap.add_argument("--maxn", type=int, default=400)
    a = ap.parse_args()
    if a.modo == "prueba":
        a.semillas, a.maxn = 3, 50
        x3.gen.compilar_mulgen()
        for tipo, n, g, s in (("mulgen", 50, 4, 1), ("waxman", 50, 6, 1)):
            fam, nombre, arch = preparar(tipo, n, g, s)
            f = una("A", fam, nombre, arch, s, n, g)
            print({k: f[k] for k in ("instancia", "productos_lp", "productos_e2", "estado_lp", "z_lp", "t_lp_s", "z_e2", "certificacion", "dif_rel", "cota_ok", "t_e2_pared_s", "aceleracion")})
        print("\nLa prueba NO guarda en corridas.csv.")
    elif a.modo == "correr":
        correr(a)
    else:
        resumen(a)
