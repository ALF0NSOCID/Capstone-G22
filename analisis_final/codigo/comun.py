"""Utilidades compartidas del análisis final (solo lectura de resultados originales).

Requiere numpy, pandas y matplotlib. No usa scipy ni networkx para poder
ejecutarse en el mismo entorno de las baterías.
"""
from __future__ import annotations

import hashlib
import math
import re
from pathlib import Path

import numpy as np

RAIZ = Path(__file__).resolve().parents[2]
EXP = RAIZ / "experimentos"
SALIDA = RAIZ / "analisis_final"
TABLAS = SALIDA / "tablas"
FIGURAS = SALIDA / "figuras"

SEMILLA_BOOTSTRAP = 2122
B_BOOTSTRAP = 10000

ESTADOS_CERT = ("optimo", "brecha_1pct")
ESTADOS_CENSURA = ("limite_interno", "timeout_externo")

FAMILIAS_WAXMAN = ["local_extrema", "intermedia", "larga", "local_backbone", "local_backbone_x10"]
ETIQUETAS_WAXMAN = {
    "local_extrema": "W1 local\nα=0,04 β=1",
    "intermedia": "W2 intermedia\nα=0,20 β=0,40",
    "larga": "W3 larga\nα=0,70 β=0,40",
    "local_backbone": "W4 backbone\ncapacidad ×1",
    "local_backbone_x10": "W5 backbone\nhubs ×10",
}


def rel(p) -> str:
    """Ruta relativa a la raíz del repositorio (procedencia)."""
    return str(Path(p).resolve().relative_to(RAIZ))


def sha256(p) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def _num(x):
    if x is None:
        return None
    if x == "inf":
        return math.inf
    try:
        return float(x)
    except ValueError:
        return None


def ultimo(patron, texto, conv=float):
    m = re.findall(patron, texto, flags=re.MULTILINE)
    if not m:
        return None
    v = m[-1]
    if isinstance(v, tuple):
        v = v[0]
    return math.inf if v == "inf" else conv(v)


def analizar_log_solver(texto: str) -> dict:
    """Extrae de un log de E3 o GC base solo las líneas pertinentes."""
    d = {}
    m = re.findall(r"^Productos: (\d+) \| Arcos: (\d+)", texto, re.M)
    d["productos_log"] = int(m[-1][0]) if m else None
    d["arcos_log"] = int(m[-1][1]) if m else None
    d["productos_lector_log"] = ultimo(r"^Productos: (\d+)\s*$", texto, int)
    d["nodos_log"] = ultimo(r"^Nodos: (\d+)\s*$", texto, int)
    d["eliminados_filtro"] = ultimo(r"^Filtro de conectividad: (\d+) productos sin camino eliminados", texto, int) or 0
    d["limite_log_s"] = ultimo(r"^L[ií]mite de tiempo: ([0-9.]+) s", texto)
    d["eta_log"] = ultimo(r"^ETA: ([0-9.]+)", texto)
    d["tolerancia_log"] = ultimo(r"Tolerancia: ([0-9.eE+\-]+)", texto)
    d["escala_capacidad_log"] = ultimo(r"^Escala de capacidad \(m[aá]xima\): ([0-9.eE+]+)", texto)
    d["licencia_log"] = ultimo(r"LicenseID to value (\d+)", texto, str)
    d["z_log"] = ultimo(r"Congesti[oó]n m[aá]xima:\s*([0-9.eE+\-]+)", texto)
    d["cota_superior_log"] = ultimo(r"^Cota superior:\s*([0-9.eE+\-]+)", texto)
    d["cota_inferior_log"] = ultimo(r"^Cota inferior:\s*([0-9.eE+\-]+)", texto)
    d["gap_log_pct"] = ultimo(r"^Gap certificado(?: actual)?:\s*([0-9.eE+\-]+|inf)%", texto)
    d["iteraciones_log"] = ultimo(r"Iteraciones:\s*(\d+)", texto, int)
    d["columnas_log"] = ultimo(r"Columnas:\s*(\d+)", texto, int)
    d["tiempo_total_log_s"] = ultimo(r"Tiempo total:\s*([0-9.]+)", texto)
    m = re.findall(r"Caminos iniciales listos: (\d+) columnas en ([0-9.]+)s", texto)
    d["t_caminos_iniciales_s"] = float(m[-1][1]) if m else None
    mp = re.findall(r"maestro=([0-9.]+)s \| pricing=([0-9.]+)s", texto)
    d["n_lineas_iteracion"] = len(mp)
    d["suma_maestro_s"] = round(sum(float(a) for a, _ in mp), 4)
    d["suma_pricing_s"] = round(sum(float(b) for _, b in mp), 4)
    d["max_maestro_s"] = max((float(a) for a, _ in mp), default=None)
    d["nuevas_total"] = sum(int(x) for x in re.findall(r"nuevas=(\d+)", texto))
    d["traceback"] = "Traceback" in texto
    if "SIN CERTIFICAR" in texto:
        e = "sin_certificar"
    elif re.search(r"No se alcanz[oó] la certificaci[oó]n", texto):
        e = "limite_interno"
    elif re.search(r"No se certific[oó] el [oó]ptimo", texto):
        e = "limite_interno_base"
    elif re.search(r"Soluci[oó]n [oó]ptima certificada", texto):
        e = "optimo"
    elif "error relativo certificado" in texto:
        e = "brecha_1pct"
    else:
        e = "sin_mensaje_final"
    d["estado_log"] = e
    d["log_completo"] = bool(re.search(r"Tiempo total:\s*[0-9.]+ segundos", texto))
    return d


ESTADO_CSV_X = {
    "óptimo": "optimo",
    "óptimo (sin cota)": "optimo",
    "brecha <= 1%": "brecha_1pct",
    "límite de tiempo": "limite_interno",
    "sin certificar": "sin_certificar",
    "error (timeout)": "timeout_externo",
}


def normalizar_estado_x(cert: str) -> str:
    if cert in ESTADO_CSV_X:
        return ESTADO_CSV_X[cert]
    return "error"


def normalizar_estado_waxman(e: str) -> str:
    return {"optimo": "optimo", "brecha_1pct": "brecha_1pct", "sin_certificar": "sin_certificar_o_limite",
            "timeout_externo": "timeout_externo", "error": "error", "revisar_log": "error",
            "timeout_preparacion": "timeout_preparacion", "error_generacion": "error_generacion"}.get(e, "error")


# ---------------------------------------------------------------- estadística

def cuantil_censurado(valores, censura, q):
    """Cuantil lineal (tipo 7) tratando los censurados como +inf (≥ límite).

    Si la interpolación toca un valor censurado devuelve inf: el cuantil solo
    se sabe acotado inferiormente por el límite.
    """
    x = np.where(np.asarray(censura, bool), np.inf, np.asarray(valores, float))
    x = np.sort(x)
    if len(x) == 0:
        return np.nan
    pos = q * (len(x) - 1)
    lo, hi = int(math.floor(pos)), int(math.ceil(pos))
    if np.isinf(x[hi]):
        return np.inf
    return float(x[lo] + (x[hi] - x[lo]) * (pos - lo))


def _percentil_sin_interp(muestras, p):
    s = np.sort(np.asarray(muestras, float))
    k = min(len(s) - 1, max(0, int(math.floor(p / 100 * (len(s) - 1) + 0.5))))
    return float(s[k])


def ic_mediana_censurada(valores, censura, rng, B=B_BOOTSTRAP):
    v = np.asarray(valores, float)
    c = np.asarray(censura, bool)
    n = len(v)
    idx = rng.integers(0, n, size=(B, n))
    meds = np.array([cuantil_censurado(v[i], c[i], 0.5) for i in idx])
    return _percentil_sin_interp(meds, 2.5), _percentil_sin_interp(meds, 97.5)


def resumen_razones(r, rng, B=B_BOOTSTRAP):
    """Resumen de razones pareadas por semilla con remuestreo de semillas."""
    r = np.asarray(r, float)
    lr = np.log(r)
    n = len(r)
    idx = rng.integers(0, n, size=(B, n))
    med_b = np.median(r[idx], axis=1)
    gm_b = np.exp(lr[idx].mean(axis=1))
    return dict(
        n_pares=n,
        mediana=float(np.median(r)),
        q1=float(np.quantile(r, 0.25)),
        q3=float(np.quantile(r, 0.75)),
        minimo=float(r.min()),
        maximo=float(r.max()),
        media_geometrica=float(np.exp(lr.mean())),
        ic95_mediana_inf=_percentil_sin_interp(med_b, 2.5),
        ic95_mediana_sup=_percentil_sin_interp(med_b, 97.5),
        ic95_mgeom_inf=_percentil_sin_interp(gm_b, 2.5),
        ic95_mgeom_sup=_percentil_sin_interp(gm_b, 97.5),
        frac_mayor_que_1=float(np.mean(r > 1)),
    )


def resumen_diferencias(d, rng, B=B_BOOTSTRAP):
    """Resumen de diferencias porcentuales pareadas (mediana con IC bootstrap)."""
    d = np.asarray(d, float)
    n = len(d)
    idx = rng.integers(0, n, size=(B, n))
    med_b = np.median(d[idx], axis=1)
    return dict(n_pares=n, mediana=float(np.median(d)), q1=float(np.quantile(d, 0.25)),
                q3=float(np.quantile(d, 0.75)), minimo=float(d.min()), maximo=float(d.max()),
                ic95_mediana_inf=_percentil_sin_interp(med_b, 2.5),
                ic95_mediana_sup=_percentil_sin_interp(med_b, 97.5),
                frac_negativa=float(np.mean(d < 0)))


def ols_loglog(x, y):
    lx, ly = np.log10(x), np.log10(y)
    b, a = np.polyfit(lx, ly, 1)
    res = ly - (a + b * lx)
    r2 = 1 - (res ** 2).sum() / ((ly - ly.mean()) ** 2).sum()
    return float(b), float(a), float(r2)
