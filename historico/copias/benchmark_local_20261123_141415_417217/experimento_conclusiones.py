"""Benchmark controlado para contrastar las conclusiones de escalabilidad.

No modifica ningun solver. Usa ``solver_columnas_e2.py`` tal como se encuentre
configurado y organiza las salidas dentro de ``resultados E2/Conclusiones``.

Comandos principales:

    python3 experimento_conclusiones.py plan
    python3 experimento_conclusiones.py preparar
    python3 experimento_conclusiones.py ejecutar --bloque minimo
    python3 experimento_conclusiones.py ejecutar --bloque e4
    python3 experimento_conclusiones.py resumir
"""

from __future__ import annotations

import argparse
import csv
import math
import re
import shutil
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path


RAIZ = Path(__file__).resolve().parent
DATOS = RAIZ / "Canad" / "Data"
DIMENSIONES = RAIZ / "Canad" / "Mulgen" / "dim.par"
SALIDA_ACTIVA = RAIZ / "out"
RESULTADOS_TEMPORALES = RAIZ / "resultados"
DESTINO = RAIZ / "resultados E2" / "Conclusiones"
INSTANCIAS = DESTINO / "instancias"
MANIFIESTO = DESTINO / "manifiesto.csv"
RESUMEN = DESTINO / "resumen.csv"
SOLVER = RAIZ / "solver_columnas_e2.py"

COMPARACION_METODOS = DESTINO / "Comparacion_Metodos"
MANIFIESTO_METODOS = COMPARACION_METODOS / "manifiesto_metodos.csv"
RESUMEN_METODOS = COMPARACION_METODOS / "resumen_metodos.csv"
PARES_METODOS = COMPARACION_METODOS / "comparacion_pareada.csv"
GRADOS_METODOS = (4, 8, 10, 12, 14, 16)

SEMILLAS_BASE = tuple(range(1, 6))
SEMILLAS_CRITICAS_EXTRA = tuple(range(6, 21))

BLOQUES = {
    "e1": "E1_MK_constante",
    "e2": "E2_Transicion_grado",
    "e3": "E3_Efecto_K",
    "e4": "E4_Semillas_criticas",
}

CAMPOS_MANIFIESTO = [
    "bloque",
    "carpeta",
    "instancia",
    "semilla",
    "nodos",
    "arcos",
    "productos",
    "grado",
    "productos_por_nodo",
    "variables_potenciales_mk",
    "fuente",
    "entrada",
    "escala_capacidad",
    "demanda_total",
    "descripcion",
]


def configuraciones():
    """Construye las 65 corridas nucleares y 15 extensiones opcionales."""
    filas = []

    # E1: mismo M*K=32 millones, distinta composicion M/K.
    for semilla in SEMILLAS_BASE:
        for grado, arcos, productos in (
            (4, 1600, 20000),
            (8, 3200, 10000),
            (16, 6400, 5000),
        ):
            nombre = f"conc_e1_d{grado:02d}_s{semilla:02d}"
            filas.append(fila_configuracion(
                "e1", nombre, semilla, arcos, productos, "mulgen",
                f"{nombre}.par",
                "MK=32 millones; varia la composicion entre M y K.",
            ))

    # E2: barrido fino del grado con N y K fijos.
    for semilla in SEMILLAS_BASE:
        for grado in (8, 10, 12, 14, 16):
            arcos = 400 * grado
            nombre = f"conc_e2_d{grado:02d}_s{semilla:02d}"
            filas.append(fila_configuracion(
                "e2", nombre, semilla, arcos, 4000, "mulgen",
                f"{nombre}.par",
                "Barrido del grado para buscar un cambio de regimen.",
            ))

    # E3: misma red y commodities anidados. Se materializan en preparar().
    for semilla in SEMILLAS_BASE:
        for productos in (1000, 2000, 4000, 8000, 16000):
            nombre = f"conc_e3_k{productos:05d}_s{semilla:02d}"
            entrada = Path(BLOQUES["e3"]) / f"{nombre}.dat"
            filas.append(fila_configuracion(
                "e3", nombre, semilla, 3200, productos, "instancia",
                str(entrada),
                "Red fija, commodities prefijo y capacidad normalizada.",
            ))

    # E4: completa 20 semillas en el punto potencialmente critico d=14.
    # Las semillas 1-5 ya estan en E2; aqui solo se agregan 6-20.
    for semilla in SEMILLAS_CRITICAS_EXTRA:
        nombre = f"conc_e4_d14_s{semilla:02d}"
        filas.append(fila_configuracion(
            "e4", nombre, semilla, 5600, 4000, "mulgen",
            f"{nombre}.par",
            "Extension de semillas cerca del posible grado critico d=14.",
        ))

    return filas


def configuraciones_metodos():
    filas = []
    for semilla in SEMILLAS_BASE:
        for grado in GRADOS_METODOS:
            nombre = f"method_d{grado:02d}_s{semilla:02d}"
            filas.append({
                "instancia": nombre,
                "semilla": semilla,
                "nodos": 400,
                "arcos": 400 * grado,
                "productos": 4000,
                "grado": grado,
                "productos_por_nodo": 10,
                "variables_potenciales_mk": 400 * grado * 4000,
                "parametro": f"{nombre}.par",
                "archivo_instancia": str(
                    Path("instancias") / f"{nombre}.dat"
                ),
            })
    return filas


def fila_configuracion(
    bloque, nombre, semilla, arcos, productos, fuente, entrada, descripcion
):
    nodos = 400
    return {
        "bloque": bloque,
        "carpeta": BLOQUES[bloque],
        "instancia": nombre,
        "semilla": semilla,
        "nodos": nodos,
        "arcos": arcos,
        "productos": productos,
        "grado": arcos / nodos,
        "productos_por_nodo": productos / nodos,
        "variables_potenciales_mk": arcos * productos,
        "fuente": fuente,
        "entrada": entrada,
        "escala_capacidad": "",
        "demanda_total": "",
        "descripcion": descripcion,
    }


def contenido_par(semilla, arcos, productos):
    return f"""nocca
inseed {semilla}
ctight 60.0
fixvar 0.01
noprll 10
grdarc 0
scalex 40
scaley 10
commod {productos}
addarc {arcos}
minsrc 1
maxsrc 1
minsnk 1
maxsnk 1
minfct 10
maxfct 100
mincst 1
maxcst 10
minsup 15
maxsup 75
mincap 100
maxcap 500
outfil out
end
"""


def escribir_parametros(filas):
    DATOS.mkdir(parents=True, exist_ok=True)
    for fila in filas:
        if fila["fuente"] != "mulgen":
            continue
        archivo = DATOS / fila["entrada"]
        archivo.write_text(
            contenido_par(
                int(fila["semilla"]),
                int(fila["arcos"]),
                int(fila["productos"]),
            ),
            encoding="utf-8",
        )

    # Cinco bases maximas para construir el experimento K anidado.
    for semilla in SEMILLAS_BASE:
        nombre = f"conc_e3_base_s{semilla:02d}"
        (DATOS / f"{nombre}.par").write_text(
            contenido_par(semilla, 3200, 16000),
            encoding="utf-8",
        )


def validar_dimensiones_mulgen():
    texto = DIMENSIONES.read_text(encoding="utf-8")
    limites = {}
    for nombre in ("MAXNODES", "MAXARCS", "MAXCOMM"):
        coincidencia = re.search(rf"{nombre}\s*=\s*(\d+)", texto, re.I)
        if coincidencia is None:
            raise ValueError(f"No se pudo leer {nombre} en {DIMENSIONES}.")
        limites[nombre] = int(coincidencia.group(1))

    requeridos = {"MAXNODES": 400, "MAXARCS": 6400, "MAXCOMM": 20000}
    insuficientes = [
        f"{nombre}={limites[nombre]} < {valor}"
        for nombre, valor in requeridos.items()
        if limites[nombre] < valor
    ]
    if insuficientes:
        raise ValueError(
            "dim.par no alcanza para el experimento: " + ", ".join(insuficientes)
        )


def configuracion_solver():
    texto = SOLVER.read_text(encoding="utf-8")

    def extraer(patron, conversion):
        coincidencia = re.search(patron, texto, flags=re.M)
        if coincidencia is None:
            raise ValueError(
                f"No se pudo identificar {patron!r} en {SOLVER.name}."
            )
        return conversion(coincidencia.group(1))

    return {
        "limite_tiempo": extraer(
            r"^LIMITE_TIEMPO\s*=\s*([0-9.]+)", float
        ),
        "eta": extraer(r"^ETA\s*=\s*([0-9.]+)", float),
        "gap_objetivo": extraer(
            r"^GAP_OBJETIVO\s*=\s*([0-9.]+)", float
        ),
        "metodo": extraer(
            r"modelo\.Params\.Method\s*=\s*([0-9]+)", int
        ),
    }


def validar_solver_experimental():
    parametros = configuracion_solver()
    esperados = {
        "limite_tiempo": 120.0,
        "eta": 25.0,
        "gap_objetivo": 0.01,
        "metodo": 0,
    }
    diferencias = [
        f"{clave}={parametros[clave]} (esperado {valor})"
        for clave, valor in esperados.items()
        if parametros[clave] != valor
    ]
    if diferencias:
        raise ValueError(
            "solver_columnas_e2.py no coincide con el protocolo: "
            + ", ".join(diferencias)
        )
    return parametros


def leer_enteros(linea, cantidad):
    campos = linea.split()
    if len(campos) == cantidad:
        return tuple(map(int, campos))
    texto = linea.rstrip("\r\n")
    campos = [
        texto[inicio:inicio + 8].strip()
        for inicio in range(0, cantidad * 8, 8)
    ]
    if len(campos) == cantidad and all(campos):
        return tuple(map(int, campos))
    raise ValueError(f"Linea invalida: {linea!r}")


def leer_instancia_cruda(ruta):
    with Path(ruta).open("r", encoding="utf-8") as archivo:
        n, m, k = leer_enteros(archivo.readline(), 3)
        arcos = []
        for _ in range(m):
            arco = leer_enteros(archivo.readline(), 5)
            origen, destino, costo, capacidad, q = arco
            if q != 0:
                raise ValueError("El experimento requiere instancias nocca (q=0).")
            arcos.append((origen, destino, costo, capacidad, 0))
        balances = [leer_enteros(linea, 3) for linea in archivo if linea.strip()]
    return n, m, k, arcos, balances


def escribir_instancia_anidada(ruta, n, arcos, balances, productos, escala):
    balances_filtrados = [fila for fila in balances if fila[0] <= productos]
    ids = {producto for producto, _, _ in balances_filtrados}
    if ids != set(range(1, productos + 1)):
        raise ValueError("El prefijo de commodities no es completo.")

    with Path(ruta).open("w", encoding="utf-8") as archivo:
        archivo.write(f"{n:8d}{len(arcos):8d}{productos:8d}\n")
        for origen, destino, costo, capacidad, _ in arcos:
            capacidad_escalada = max(1, int(round(capacidad * escala)))
            archivo.write(
                f"{origen:8d}{destino:8d}{costo:8d}"
                f"{capacidad_escalada:8d}{0:8d}\n"
            )
        for producto, nodo, cantidad in balances_filtrados:
            archivo.write(f"{producto:8d}{nodo:8d}{cantidad:8d}\n")


def demanda_total(balances, productos):
    return sum(
        cantidad
        for producto, _, cantidad in balances
        if producto <= productos and cantidad > 0
    )


def preparar():
    if not SOLVER.exists():
        raise FileNotFoundError(f"No existe {SOLVER}.")
    validar_dimensiones_mulgen()
    filas = configuraciones()
    DESTINO.mkdir(parents=True, exist_ok=True)
    INSTANCIAS.mkdir(parents=True, exist_ok=True)
    escribir_parametros(filas)

    # Se reutilizan las funciones oficiales para compilar y generar las cinco
    # redes base de E3. No se ejecuta ningun solver durante la preparacion.
    import ejecutar

    ejecutar.compilar_mulgen()
    metadatos_e3 = {}
    carpeta_e3 = INSTANCIAS / BLOQUES["e3"]
    carpeta_e3.mkdir(parents=True, exist_ok=True)

    for semilla in SEMILLAS_BASE:
        base = f"conc_e3_base_s{semilla:02d}"
        print(f"\nPreparando red anidada E3, semilla {semilla}...", flush=True)
        ejecutar.generar_instancia(base)
        n, m, kmax, arcos, balances = leer_instancia_cruda(SALIDA_ACTIVA)
        if (n, m, kmax) != (400, 3200, 16000):
            raise ValueError(f"Cabecera inesperada en {base}: {(n, m, kmax)}")

        demanda_maxima = demanda_total(balances, kmax)
        for productos in (1000, 2000, 4000, 8000, 16000):
            demanda = demanda_total(balances, productos)
            escala = demanda / demanda_maxima
            nombre = f"conc_e3_k{productos:05d}_s{semilla:02d}"
            ruta = carpeta_e3 / f"{nombre}.dat"
            escribir_instancia_anidada(
                ruta, n, arcos, balances, productos, escala
            )
            metadatos_e3[nombre] = (escala, demanda)

    for fila in filas:
        if fila["instancia"] in metadatos_e3:
            escala, demanda = metadatos_e3[fila["instancia"]]
            fila["escala_capacidad"] = f"{escala:.12g}"
            fila["demanda_total"] = demanda

    escribir_csv(MANIFIESTO, CAMPOS_MANIFIESTO, filas)
    resumir(filas)
    print("\nPreparacion terminada.")
    print(f"Manifiesto: {MANIFIESTO}")
    print("Corridas nucleares: 65")
    print("Extension opcional E4: 15")


def escribir_csv(ruta, campos, filas):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    temporal = ruta.with_suffix(ruta.suffix + ".tmp")
    with temporal.open("w", newline="", encoding="utf-8") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=campos)
        escritor.writeheader()
        escritor.writerows(filas)
    temporal.replace(ruta)


def leer_manifiesto():
    if not MANIFIESTO.exists():
        raise FileNotFoundError(
            f"No existe {MANIFIESTO}. Ejecuta primero el comando preparar."
        )
    with MANIFIESTO.open("r", encoding="utf-8") as archivo:
        return list(csv.DictReader(archivo))


def carpeta_bloque(fila):
    return DESTINO / fila["carpeta"]


def ruta_resultado(fila):
    return (
        carpeta_bloque(fila)
        / "resultados"
        / f"{fila['instancia']}_solver_columnas_e2.txt"
    )


def guardar_instancia_activa(fila, instante_inicio):
    if not SALIDA_ACTIVA.exists():
        return
    if SALIDA_ACTIVA.stat().st_mtime_ns < instante_inicio:
        return
    try:
        with SALIDA_ACTIVA.open("r", encoding="utf-8") as archivo:
            cabecera = leer_enteros(archivo.readline(), 3)
    except (OSError, ValueError):
        return
    esperada = (
        int(fila["nodos"]), int(fila["arcos"]), int(fila["productos"])
    )
    if cabecera != esperada:
        return
    destino = carpeta_bloque(fila) / "instancias" / f"{fila['instancia']}.dat"
    destino.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SALIDA_ACTIVA, destino)


def anexar_metadatos_solver(ruta, parametros):
    with ruta.open("a", encoding="utf-8") as archivo:
        archivo.write("\nMETADATOS DEL EXPERIMENTO\n")
        archivo.write(f"Metodo Gurobi experimental: {parametros['metodo']}\n")
        archivo.write(f"ETA experimental: {parametros['eta']:g}\n")
        archivo.write(
            f"Gap objetivo experimental: "
            f"{100 * parametros['gap_objetivo']:g}%\n"
        )
        archivo.write(
            f"Limite de tiempo experimental: "
            f"{parametros['limite_tiempo']:g} s\n"
        )


def mover_resultado(fila, instante_inicio, exito, parametros):
    origen = (
        RESULTADOS_TEMPORALES
        / f"{fila['instancia']}_solver_columnas_e2.txt"
    )
    if not origen.exists() or origen.stat().st_mtime_ns < instante_inicio:
        return False

    destino = ruta_resultado(fila)
    destino.parent.mkdir(parents=True, exist_ok=True)
    if exito:
        shutil.move(str(origen), str(destino))
        anexar_metadatos_solver(destino, parametros)
    else:
        marca = time.strftime("%Y%m%d_%H%M%S")
        fallo = destino.with_name(destino.stem + f"_FALLO_{marca}.txt")
        shutil.move(str(origen), str(fallo))
        anexar_metadatos_solver(fallo, parametros)
    return True


def ejecutar_fila(fila, parametros):
    destino = ruta_resultado(fila)
    if destino.exists():
        print(f"OMITIDA | {fila['instancia']} | resultado existente")
        return True

    print(
        f"\nEJECUTANDO | {fila['bloque']} | {fila['instancia']} | "
        f"N={fila['nodos']} M={fila['arcos']} K={fila['productos']}",
        flush=True,
    )
    instante_inicio = time.time_ns()

    if fila["fuente"] == "mulgen":
        proceso = subprocess.run(
            [
                sys.executable,
                "-u",
                str(RAIZ / "ejecutar.py"),
                fila["instancia"],
                "solver_columnas_e2",
            ],
            cwd=RAIZ,
            check=False,
        )
        codigo = proceso.returncode
        guardar_instancia_activa(fila, instante_inicio)
    else:
        entrada = INSTANCIAS / fila["entrada"]
        if not entrada.exists():
            raise FileNotFoundError(
                f"Falta {entrada}. Ejecuta nuevamente preparar."
            )
        shutil.copy2(entrada, SALIDA_ACTIVA)
        instante_inicio = min(instante_inicio, SALIDA_ACTIVA.stat().st_mtime_ns)
        try:
            import ejecutar
            ejecutar.ejecutar_solver(fila["instancia"], SOLVER)
            codigo = 0
        except Exception as error:  # conserva el resultado parcial y continua
            codigo = 1
            print(f"ERROR | {fila['instancia']} | {error}", flush=True)

    movido = mover_resultado(
        fila, instante_inicio, codigo == 0, parametros
    )
    if codigo == 0 and not movido:
        print(f"ERROR | No aparecio el resultado de {fila['instancia']}.")
        return False
    if codigo != 0:
        print(f"FALLO | {fila['instancia']} | codigo={codigo}")
        return False
    return True


def orden_rotado(filas_semilla, semilla):
    ordenadas = sorted(
        filas_semilla,
        key=lambda f: (float(f["grado"]), int(f["productos"])),
    )
    if not ordenadas:
        return []
    desplazamiento = (int(semilla) - 1) % len(ordenadas)
    return ordenadas[desplazamiento:] + ordenadas[:desplazamiento]


def ejecutar_bloques(seleccion):
    parametros = validar_solver_experimental()
    filas = leer_manifiesto()
    if seleccion == "minimo":
        bloques = {"e1", "e2", "e3"}
    elif seleccion == "todos":
        bloques = set(BLOQUES)
    else:
        bloques = {seleccion}

    elegidas = [fila for fila in filas if fila["bloque"] in bloques]
    por_semilla = defaultdict(list)
    for fila in elegidas:
        por_semilla[int(fila["semilla"])].append(fila)

    exitos = 0
    fallos = 0
    for semilla in sorted(por_semilla):
        print("\n" + "=" * 68)
        print(f"SEMILLA {semilla} | bloques {', '.join(sorted(bloques))}")
        print("=" * 68)
        for fila in orden_rotado(por_semilla[semilla], semilla):
            if ejecutar_fila(fila, parametros):
                exitos += 1
            else:
                fallos += 1
            resumir(filas)

    print(f"\nEjecucion terminada: exitos/omitidos={exitos}, fallos={fallos}.")
    print(f"Resumen actualizado: {RESUMEN}")


def ultimo(texto, patron, conversion=float):
    valores = re.findall(patron, texto, flags=re.I | re.M)
    if not valores:
        return None
    return conversion(valores[-1])


def analizar_resultado(texto):
    iteraciones = re.findall(
        r"Iteraci[oó]n\s+(\d+):.*?columnas=(\d+).*?nuevas=(\d+)"
        r".*?maestro=([0-9.eE+\-]+)s\s*\|\s*pricing=([0-9.eE+\-]+)s",
        texto,
    )
    columnas_acumuladas = sum(int(fila[1]) for fila in iteraciones)
    columnas_nuevas = sum(int(fila[2]) for fila in iteraciones)
    tiempo_maestro = sum(float(fila[3]) for fila in iteraciones)
    tiempo_pricing = sum(float(fila[4]) for fila in iteraciones)

    exacta = "Solución óptima certificada" in texto
    gap_certificado = "Solución con error relativo certificado" in texto
    sin_certificar = "No se alcanzó la certificación solicitada" in texto
    if exacta:
        estado = "optimo_exacto"
    elif gap_certificado:
        estado = "gap_certificado"
    elif sin_certificar:
        estado = "limite_sin_certificar"
    elif "Estado: error" in texto:
        estado = "error"
    else:
        estado = "terminacion_no_clasificada"

    tiempo = ultimo(
        texto, r"^Tiempo interno del algoritmo:\s*([0-9.eE+\-]+)\s*s$"
    )
    if tiempo is None:
        tiempo = ultimo(texto, r"Tiempo total:\s*([0-9.eE+\-]+)\s*segundos")

    return {
        "estado_experimental": estado,
        "certificada": int(exacta or gap_certificado),
        "metodo_gurobi": ultimo(
            texto,
            r"(?:Metodo Gurobi experimental:|Set parameter Method to value)"
            r"\s*(\d+)",
            int,
        ),
        "eta": ultimo(texto, r"ETA experimental:\s*([0-9.eE+\-]+)"),
        "gap_objetivo_pct": ultimo(
            texto, r"Gap objetivo experimental:\s*([0-9.eE+\-]+)%"
        ),
        "limite_tiempo_s": ultimo(
            texto,
            r"Limite de tiempo experimental:\s*([0-9.eE+\-]+)\s*s",
        ),
        "productos_efectivos": ultimo(
            texto, r"Productos:\s*(\d+)\s*\|\s*Arcos:", int
        ),
        "tiempo_interno_s": tiempo,
        "tiempo_pared_s": ultimo(
            texto, r"^Tiempo de pared del proceso:\s*([0-9.eE+\-]+)\s*s$"
        ),
        "tiempo_cpu_s": ultimo(
            texto, r"^Tiempo de CPU acumulado:\s*([0-9.eE+\-]+)\s*s$"
        ),
        "memoria_mb": ultimo(
            texto,
            r"^Memoria residente maxima observada:\s*([0-9.eE+\-]+)\s*MB$",
        ),
        "objetivo": ultimo(
            texto, r"^Objetivo/congestion:\s*([0-9.eE+\-]+)$"
        ),
        "cota_superior": ultimo(
            texto, r"^Cota superior:\s*([0-9.eE+\-]+)$"
        ),
        "cota_inferior": ultimo(
            texto, r"^Cota inferior:\s*([0-9.eE+\-]+)$"
        ),
        "gap_pct": ultimo(
            texto, r"^Gap certificado:\s*([0-9.eE+\-]+)%$"
        ),
        "iteraciones": ultimo(texto, r"^Iteraciones:\s*(\d+)\s*$", int),
        "columnas_finales": ultimo(
            texto, r"^Columnas finales:\s*(\d+)\s*$", int
        ),
        "suma_columnas_iteraciones": columnas_acumuladas,
        "columnas_nuevas_acumuladas": columnas_nuevas,
        "tiempo_maestro_acumulado_s": tiempo_maestro,
        "tiempo_pricing_acumulado_s": tiempo_pricing,
    }


def resumir(filas=None):
    if filas is None:
        filas = leer_manifiesto()
    salida = []
    campos_metricas = [
        "archivo_resultado",
        "estado_experimental",
        "certificada",
        "metodo_gurobi",
        "eta",
        "gap_objetivo_pct",
        "limite_tiempo_s",
        "productos_efectivos",
        "tiempo_interno_s",
        "tiempo_pared_s",
        "tiempo_cpu_s",
        "memoria_mb",
        "objetivo",
        "cota_superior",
        "cota_inferior",
        "gap_pct",
        "iteraciones",
        "columnas_finales",
        "suma_columnas_iteraciones",
        "columnas_nuevas_acumuladas",
        "tiempo_maestro_acumulado_s",
        "tiempo_pricing_acumulado_s",
        "tiempo_no_atribuido_s",
        "fraccion_tiempo_maestro",
        "fraccion_tiempo_pricing",
        "columnas_por_producto",
        "fraccion_columnas_sobre_mk",
    ]

    for fila_original in filas:
        fila = dict(fila_original)
        ruta = ruta_resultado(fila)
        metricas = {campo: "" for campo in campos_metricas}
        metricas["archivo_resultado"] = str(ruta.relative_to(RAIZ))
        if ruta.exists():
            metricas.update(analizar_resultado(ruta.read_text(
                encoding="utf-8", errors="replace"
            )))
            tiempo = metricas.get("tiempo_interno_s")
            maestro = metricas.get("tiempo_maestro_acumulado_s") or 0.0
            pricing = metricas.get("tiempo_pricing_acumulado_s") or 0.0
            if tiempo is not None:
                metricas["tiempo_no_atribuido_s"] = max(
                    0.0, tiempo - maestro - pricing
                )
                if tiempo > 0:
                    metricas["fraccion_tiempo_maestro"] = maestro / tiempo
                    metricas["fraccion_tiempo_pricing"] = pricing / tiempo

            columnas = metricas.get("columnas_finales")
            k_efectivo = metricas.get("productos_efectivos")
            mk = int(fila["variables_potenciales_mk"])
            if columnas is not None and k_efectivo:
                metricas["columnas_por_producto"] = columnas / k_efectivo
                metricas["fraccion_columnas_sobre_mk"] = columnas / mk
        else:
            metricas["estado_experimental"] = "pendiente"

        fila.update(metricas)
        salida.append(fila)

    escribir_csv(
        RESUMEN,
        CAMPOS_MANIFIESTO + campos_metricas,
        salida,
    )
    return salida


def mostrar_plan():
    filas = configuraciones()
    conteos = defaultdict(int)
    for fila in filas:
        conteos[fila["bloque"]] += 1
    print("Benchmark de conclusiones")
    print("Solver: solver_columnas_e2.py (sin modificaciones)")
    for bloque in ("e1", "e2", "e3", "e4"):
        sufijo = " (opcional)" if bloque == "e4" else ""
        print(f"  {bloque}: {conteos[bloque]} ejecuciones{sufijo}")
    print(f"  nucleo e1+e2+e3: {sum(conteos[b] for b in ('e1','e2','e3'))}")
    print(f"  total con e4: {len(filas)}")
    print(f"Destino: {DESTINO}")


CAMPOS_MANIFIESTO_METODOS = [
    "instancia",
    "semilla",
    "nodos",
    "arcos",
    "productos",
    "grado",
    "productos_por_nodo",
    "variables_potenciales_mk",
    "parametro",
    "archivo_instancia",
    "primer_metodo",
]


def validar_base_comparacion_metodos():
    parametros = configuracion_solver()
    esperados = {
        "limite_tiempo": 120.0,
        "eta": 25.0,
        "gap_objetivo": 0.01,
    }
    diferencias = [
        f"{clave}={parametros[clave]} (esperado {valor})"
        for clave, valor in esperados.items()
        if parametros[clave] != valor
    ]
    if diferencias:
        raise ValueError(
            "E2 no coincide con el protocolo de comparacion: "
            + ", ".join(diferencias)
        )
    return parametros


def preparar_comparacion_metodos():
    validar_dimensiones_mulgen()
    validar_base_comparacion_metodos()
    COMPARACION_METODOS.mkdir(parents=True, exist_ok=True)
    (COMPARACION_METODOS / "instancias").mkdir(parents=True, exist_ok=True)
    (COMPARACION_METODOS / "resultados" / "Method0").mkdir(
        parents=True, exist_ok=True
    )
    (COMPARACION_METODOS / "resultados" / "Method1").mkdir(
        parents=True, exist_ok=True
    )

    filas = configuraciones_metodos()
    for fila in filas:
        grado = int(fila["grado"])
        semilla = int(fila["semilla"])
        parametro = DATOS / fila["parametro"]
        parametro.write_text(
            contenido_par(semilla, int(fila["arcos"]), int(fila["productos"])),
            encoding="utf-8",
        )
        indice_grado = GRADOS_METODOS.index(grado)
        fila["primer_metodo"] = (
            0 if (semilla + indice_grado) % 2 == 0 else 1
        )

    escribir_csv(
        MANIFIESTO_METODOS,
        CAMPOS_MANIFIESTO_METODOS,
        filas,
    )
    return filas


def crear_solvers_temporales():
    texto = SOLVER.read_text(encoding="utf-8")
    patron = r"(modelo\.Params\.Method\s*=\s*)[01]"
    identificador = time.time_ns()
    encabezado = (
        "import sys\n"
        f"sys.path.insert(0, {str(RAIZ)!r})\n"
    )
    temporales = {}
    for metodo in (0, 1):
        modificado, cantidad = re.subn(
            patron,
            rf"\g<1>{metodo}",
            texto,
            count=1,
        )
        if cantidad != 1:
            raise ValueError(
                "No se pudo crear la variante temporal de Method."
            )
        ruta = Path("/tmp") / (
            f"solver_columnas_e2_method{metodo}_experimental_"
            f"{identificador}.py"
        )
        ruta.write_text(encabezado + modificado, encoding="utf-8")
        temporales[metodo] = ruta
    return temporales


def ruta_instancia_metodos(fila):
    return COMPARACION_METODOS / fila["archivo_instancia"]


def ruta_resultado_metodo(fila, metodo):
    return (
        COMPARACION_METODOS
        / "resultados"
        / f"Method{metodo}"
        / f"{fila['instancia']}_method{metodo}.txt"
    )


def asegurar_instancia_metodos(fila, modulo_ejecutar):
    destino = ruta_instancia_metodos(fila)
    if destino.exists():
        with destino.open("r", encoding="utf-8") as archivo:
            cabecera = leer_enteros(archivo.readline(), 3)
        esperada = (
            int(fila["nodos"]), int(fila["arcos"]), int(fila["productos"])
        )
        if cabecera != esperada:
            raise ValueError(
                f"La instancia guardada {destino} tiene cabecera {cabecera}, "
                f"pero se esperaba {esperada}."
            )
        return destino

    modulo_ejecutar.generar_instancia(fila["instancia"])
    destino.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SALIDA_ACTIVA, destino)
    return destino


def ejecutar_un_metodo(fila, metodo, solver_temporal, modulo_ejecutar):
    destino = ruta_resultado_metodo(fila, metodo)
    if destino.exists():
        print(
            f"OMITIDA | {fila['instancia']} | Method={metodo} | ya existe"
        )
        return True

    instancia = ruta_instancia_metodos(fila)
    shutil.copy2(instancia, SALIDA_ACTIVA)
    inicio = time.time_ns()
    print(
        f"EJECUTANDO | {fila['instancia']} | d={fila['grado']} | "
        f"Method={metodo}",
        flush=True,
    )
    try:
        modulo_ejecutar.ejecutar_solver(fila["instancia"], solver_temporal)
        codigo = 0
    except Exception as error:
        codigo = 1
        print(
            f"FALLO | {fila['instancia']} | Method={metodo} | {error}",
            flush=True,
        )

    origen = (
        RESULTADOS_TEMPORALES
        / f"{fila['instancia']}_{solver_temporal.stem}.txt"
    )
    if not origen.exists() or origen.stat().st_mtime_ns < inicio:
        print(
            f"ERROR | no aparecio un resultado nuevo para "
            f"{fila['instancia']} Method={metodo}"
        )
        return False

    parametros = validar_base_comparacion_metodos()
    parametros["metodo"] = metodo
    if codigo == 0:
        destino.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(origen), str(destino))
        anexar_metadatos_solver(destino, parametros)
        return True

    marca = time.strftime("%Y%m%d_%H%M%S")
    fallo = destino.with_name(destino.stem + f"_FALLO_{marca}.txt")
    shutil.move(str(origen), str(fallo))
    anexar_metadatos_solver(fallo, parametros)
    return False


def resumir_comparacion_metodos(filas=None):
    if filas is None:
        if not MANIFIESTO_METODOS.exists():
            raise FileNotFoundError(
                "Todavia no existe el manifiesto de comparacion de metodos."
            )
        with MANIFIESTO_METODOS.open("r", encoding="utf-8") as archivo:
            filas = list(csv.DictReader(archivo))

    campos_largos = CAMPOS_MANIFIESTO_METODOS + [
        "metodo",
        "archivo_resultado",
        "estado_experimental",
        "certificada",
        "tiempo_interno_s",
        "tiempo_par2_s",
        "tiempo_maestro_s",
        "tiempo_pricing_s",
        "iteraciones",
        "columnas_finales",
        "suma_columnas_iteraciones",
        "objetivo",
        "gap_pct",
    ]
    filas_largas = []
    por_instancia = defaultdict(dict)

    for fila_original in filas:
        for metodo in (0, 1):
            fila = dict(fila_original)
            ruta = ruta_resultado_metodo(fila, metodo)
            registro = dict(fila)
            registro.update({
                "metodo": metodo,
                "archivo_resultado": str(ruta.relative_to(RAIZ)),
                "estado_experimental": "pendiente",
                "certificada": "",
                "tiempo_interno_s": "",
                "tiempo_par2_s": "",
                "tiempo_maestro_s": "",
                "tiempo_pricing_s": "",
                "iteraciones": "",
                "columnas_finales": "",
                "suma_columnas_iteraciones": "",
                "objetivo": "",
                "gap_pct": "",
            })
            if ruta.exists():
                metricas = analizar_resultado(
                    ruta.read_text(encoding="utf-8", errors="replace")
                )
                tiempo = metricas.get("tiempo_interno_s")
                certificada = bool(metricas.get("certificada"))
                par2 = tiempo if certificada and tiempo is not None else 240.0
                registro.update({
                    "estado_experimental": metricas["estado_experimental"],
                    "certificada": int(certificada),
                    "tiempo_interno_s": tiempo,
                    "tiempo_par2_s": par2,
                    "tiempo_maestro_s": metricas[
                        "tiempo_maestro_acumulado_s"
                    ],
                    "tiempo_pricing_s": metricas[
                        "tiempo_pricing_acumulado_s"
                    ],
                    "iteraciones": metricas["iteraciones"],
                    "columnas_finales": metricas["columnas_finales"],
                    "suma_columnas_iteraciones": metricas[
                        "suma_columnas_iteraciones"
                    ],
                    "objetivo": metricas["objetivo"],
                    "gap_pct": metricas["gap_pct"],
                })
                por_instancia[fila["instancia"]][metodo] = registro
            filas_largas.append(registro)

    escribir_csv(RESUMEN_METODOS, campos_largos, filas_largas)

    campos_pares = CAMPOS_MANIFIESTO_METODOS + [
        "estado_par",
        "certificada_m0",
        "certificada_m1",
        "tiempo_m0_s",
        "tiempo_m1_s",
        "par2_m0_s",
        "par2_m1_s",
        "speedup_m1_sobre_m0",
        "log_speedup",
        "ganador_par2",
        "maestro_m0_s",
        "maestro_m1_s",
        "pricing_m0_s",
        "pricing_m1_s",
        "iteraciones_m0",
        "iteraciones_m1",
        "columnas_m0",
        "columnas_m1",
        "suma_columnas_m0",
        "suma_columnas_m1",
    ]
    pares = []
    for fila_original in filas:
        fila = dict(fila_original)
        metodos = por_instancia.get(fila["instancia"], {})
        par = dict(fila)
        par.update({campo: "" for campo in campos_pares if campo not in par})
        if 0 in metodos and 1 in metodos:
            m0 = metodos[0]
            m1 = metodos[1]
            p0 = float(m0["tiempo_par2_s"])
            p1 = float(m1["tiempo_par2_s"])
            speedup = p1 / p0
            if p0 < p1:
                ganador = "Method0"
            elif p1 < p0:
                ganador = "Method1"
            else:
                ganador = "empate"
            par.update({
                "estado_par": "completo",
                "certificada_m0": m0["certificada"],
                "certificada_m1": m1["certificada"],
                "tiempo_m0_s": m0["tiempo_interno_s"],
                "tiempo_m1_s": m1["tiempo_interno_s"],
                "par2_m0_s": p0,
                "par2_m1_s": p1,
                "speedup_m1_sobre_m0": speedup,
                "log_speedup": math.log(speedup),
                "ganador_par2": ganador,
                "maestro_m0_s": m0["tiempo_maestro_s"],
                "maestro_m1_s": m1["tiempo_maestro_s"],
                "pricing_m0_s": m0["tiempo_pricing_s"],
                "pricing_m1_s": m1["tiempo_pricing_s"],
                "iteraciones_m0": m0["iteraciones"],
                "iteraciones_m1": m1["iteraciones"],
                "columnas_m0": m0["columnas_finales"],
                "columnas_m1": m1["columnas_finales"],
                "suma_columnas_m0": m0["suma_columnas_iteraciones"],
                "suma_columnas_m1": m1["suma_columnas_iteraciones"],
            })
        else:
            par["estado_par"] = "pendiente"
        pares.append(par)

    escribir_csv(PARES_METODOS, campos_pares, pares)
    return filas_largas, pares


def ejecutar_comparacion_metodos():
    filas = preparar_comparacion_metodos()
    import ejecutar

    ejecutar.compilar_mulgen()
    temporales = crear_solvers_temporales()
    exitos = 0
    fallos = 0
    try:
        por_semilla = defaultdict(list)
        for fila in filas:
            por_semilla[int(fila["semilla"])].append(fila)

        for semilla in sorted(por_semilla):
            print("\n" + "=" * 68)
            print(f"SEMILLA {semilla} | COMPARACION METHOD 0 VS 1")
            print("=" * 68)
            grupo = sorted(
                por_semilla[semilla], key=lambda fila: int(fila["grado"])
            )
            desplazamiento = (semilla - 1) % len(grupo)
            grupo = grupo[desplazamiento:] + grupo[:desplazamiento]
            for fila in grupo:
                asegurar_instancia_metodos(fila, ejecutar)
                primer_metodo = int(fila["primer_metodo"])
                orden = (primer_metodo, 1 - primer_metodo)
                for metodo in orden:
                    if ejecutar_un_metodo(
                        fila, metodo, temporales[metodo], ejecutar
                    ):
                        exitos += 1
                    else:
                        fallos += 1
                resumir_comparacion_metodos(filas)
    finally:
        for ruta in temporales.values():
            ruta.unlink(missing_ok=True)

    print(
        f"\nComparacion terminada: exitos/omitidos={exitos}, "
        f"fallos={fallos}."
    )
    print(f"Resumen largo: {RESUMEN_METODOS}")
    print(f"Comparacion pareada: {PARES_METODOS}")


def main():
    parser = argparse.ArgumentParser(
        description="Prepara y ejecuta el benchmark de conclusiones."
    )
    subparsers = parser.add_subparsers(dest="comando", required=True)
    subparsers.add_parser("plan")
    subparsers.add_parser("preparar")
    ejecutar_parser = subparsers.add_parser("ejecutar")
    ejecutar_parser.add_argument(
        "--bloque",
        choices=("e1", "e2", "e3", "e4", "minimo", "todos"),
        default="minimo",
    )
    subparsers.add_parser("resumir")
    subparsers.add_parser("comparar-metodos")
    subparsers.add_parser("resumir-metodos")
    argumentos = parser.parse_args()

    if argumentos.comando == "plan":
        mostrar_plan()
    elif argumentos.comando == "preparar":
        preparar()
    elif argumentos.comando == "ejecutar":
        ejecutar_bloques(argumentos.bloque)
    elif argumentos.comando == "resumir":
        resumir()
        print(f"Resumen actualizado: {RESUMEN}")
    elif argumentos.comando == "comparar-metodos":
        ejecutar_comparacion_metodos()
    elif argumentos.comando == "resumir-metodos":
        resumir_comparacion_metodos()
        print(f"Resumen actualizado: {RESUMEN_METODOS}")
        print(f"Comparacion pareada: {PARES_METODOS}")


if __name__ == "__main__":
    main()
