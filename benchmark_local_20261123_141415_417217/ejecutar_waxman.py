import argparse
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

from analisis_red import analizar_red_generada
from generador_waxman import escribir_instancia, generar_instancia
from metricas_ejecucion import construir_resumen_kpi, vigilar_memoria


# ---------------------------------------------------------
# RUTAS PRINCIPALES
# ---------------------------------------------------------

RAIZ = Path(__file__).resolve().parent
CARPETA_RESULTADOS = RAIZ / "resultados"
SALIDA_ACTIVA = RAIZ / "out"


# ---------------------------------------------------------
# SELECCIONAR SOLVER
# ---------------------------------------------------------

def obtener_solver(nombre_solver):
    """Busca el solver solicitado dentro de la raiz del repositorio."""
    if not nombre_solver.endswith(".py"):
        nombre_solver += ".py"

    nombre_solver = Path(nombre_solver).name
    archivo_solver = RAIZ / nombre_solver

    if not archivo_solver.exists():
        raise FileNotFoundError(f"No existe el solver {archivo_solver}")
    if archivo_solver == Path(__file__).resolve():
        raise ValueError("ejecutar_waxman.py no puede utilizarse como solver")

    return archivo_solver


# ---------------------------------------------------------
# EJECUTAR SOLVER
# ---------------------------------------------------------

def ejecutar_solver(nombre_instancia, archivo_solver):
    """Ejecuta el solver y guarda su salida junto con sus KPI."""
    CARPETA_RESULTADOS.mkdir(exist_ok=True)
    nombre_metodo = archivo_solver.stem
    archivo_resultado = (
        CARPETA_RESULTADOS
        / f"{nombre_instancia}_{nombre_metodo}.txt"
    )

    print(f"Ejecutando solver: {archivo_solver.name}")
    print(f"Los resultados se guardaran en {archivo_resultado}")

    entorno_solver = os.environ.copy()
    entorno_solver["ARCHIVO_INSTANCIA"] = str(SALIDA_ACTIVA)

    tiempos_antes = os.times()
    inicio_solver = time.perf_counter()
    proceso = subprocess.Popen(
        [sys.executable, "-u", str(archivo_solver)],
        cwd=RAIZ,
        env=entorno_solver,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    detener_monitor = threading.Event()
    memoria_maxima_kb = [0]
    monitor = threading.Thread(
        target=vigilar_memoria,
        args=(proceso.pid, detener_monitor, memoria_maxima_kb),
        daemon=True,
    )
    monitor.start()

    with archivo_resultado.open("w", encoding="utf-8") as resultado:
        if proceso.stdout is None:
            raise RuntimeError("No fue posible capturar la salida del solver")

        lineas_salida = []
        for linea in proceso.stdout:
            print(linea, end="")
            resultado.write(linea)
            lineas_salida.append(linea)

        codigo_salida = proceso.wait()
        detener_monitor.set()
        monitor.join(timeout=1)

        tiempo_pared = time.perf_counter() - inicio_solver
        tiempos_despues = os.times()
        tiempo_cpu = (
            tiempos_despues.children_user
            + tiempos_despues.children_system
            - tiempos_antes.children_user
            - tiempos_antes.children_system
        )

        resumen = construir_resumen_kpi(
            nombre_instancia,
            archivo_solver,
            codigo_salida,
            tiempo_pared,
            tiempo_cpu,
            memoria_maxima_kb,
            "".join(lineas_salida),
            archivo_resultado,
            SALIDA_ACTIVA,
        )
        print(resumen, end="")
        resultado.write(resumen)

    if codigo_salida != 0:
        raise RuntimeError(
            f"{archivo_solver.name} termino con codigo {codigo_salida}"
        )


# ---------------------------------------------------------
# PROGRAMA PRINCIPAL
# ---------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description=(
            "Genera una instancia Waxman y la resuelve utilizando el "
            "solver seleccionado."
        )
    )
    parser.add_argument(
        "solver",
        help="Solver que resolvera la instancia, por ejemplo solver_columnas.",
    )
    parser.add_argument("--nodos", type=int, default=400)
    parser.add_argument("--productos", type=int, default=10000)
    parser.add_argument(
        "--arcos",
        type=int,
        help=(
            "Numero exacto de arcos dirigidos reciprocos. Si se omite, "
            "se conserva la densidad natural del grafo Waxman."
        ),
    )
    parser.add_argument("--alpha", type=float, default=0.2)
    parser.add_argument("--beta", type=float, default=0.4)
    parser.add_argument("--demanda-min", type=int, default=10)
    parser.add_argument("--demanda-max", type=int, default=50)
    parser.add_argument("--capacidad-min", type=int, default=50)
    parser.add_argument("--capacidad-max", type=int, default=150)
    parser.add_argument(
        "--demanda-gravedad",
        action="store_true",
        help=(
            "Genera pares y demandas con un modelo gravitacional. "
            "Al activarlo, demanda-min y demanda-max no se utilizan."
        ),
    )
    parser.add_argument(
        "--demanda-media",
        type=float,
        default=30.0,
        help="Demanda media objetivo del modelo gravitacional.",
    )
    parser.add_argument(
        "--sigma-masa",
        type=float,
        default=1.0,
        help="Dispersion lognormal de las masas del modelo gravitacional.",
    )
    parser.add_argument(
        "--capacidad-escalones",
        action="store_true",
        help=(
            "Asigna capacidades por escalones segun la centralidad de los "
            "enlaces. Al activarlo, capacidad-max no se utiliza."
        ),
    )
    parser.add_argument(
        "--factores-escalon",
        type=float,
        nargs="+",
        default=(1.0, 2.5, 5.0, 10.0),
        metavar="FACTOR",
        help="Factores de capacidad para cada escalon.",
    )
    parser.add_argument(
        "--cuantiles-escalon",
        type=float,
        nargs="+",
        default=(0.40, 0.75, 0.93),
        metavar="CUANTIL",
        help="Cuantiles que separan los escalones de capacidad.",
    )
    parser.add_argument(
        "--porcentaje-hubs",
        type=float,
        default=0.0,
        help=(
            "Proporcion de nodos que forman un backbone local conectado. "
            "Por ejemplo, 0.05 selecciona aproximadamente 5%% de hubs."
        ),
    )
    parser.add_argument(
        "--multiplicador-hubs",
        type=float,
        default=10.0,
        help="Multiplicador de capacidad para los enlaces entre hubs.",
    )
    parser.add_argument(
        "--vecinos-hub",
        type=int,
        default=3,
        help="Numero de hubs geograficamente cercanos buscados por cada hub.",
    )
    parser.add_argument("--semilla", type=int, default=42)
    parser.add_argument(
        "--nombre",
        help="Nombre opcional usado para identificar el archivo de resultados.",
    )
    parser.add_argument(
        "--analizar-red",
        action="store_true",
        help="Imprime un diagnostico estructural antes de ejecutar el solver.",
    )
    argumentos = parser.parse_args()

    archivo_solver = obtener_solver(argumentos.solver)

    print(
        "Generando instancia Waxman "
        f"(n={argumentos.nodos}, M={argumentos.arcos or 'natural'}, "
        f"K={argumentos.productos}, "
        f"alpha={argumentos.alpha}, beta={argumentos.beta}, "
        f"hubs={100 * argumentos.porcentaje_hubs:g}%, "
        f"vecinos-hub={argumentos.vecinos_hub}, "
        f"demanda={'gravedad' if argumentos.demanda_gravedad else 'uniforme'}, "
        f"capacidad={'escalones' if argumentos.capacidad_escalones else 'uniforme'}, "
        f"semilla={argumentos.semilla})..."
    )
    grafo, arcos, commodities = generar_instancia(
        nodos=argumentos.nodos,
        productos=argumentos.productos,
        arcos_objetivo=argumentos.arcos,
        alpha=argumentos.alpha,
        beta=argumentos.beta,
        demanda_min=argumentos.demanda_min,
        demanda_max=argumentos.demanda_max,
        capacidad_min=argumentos.capacidad_min,
        capacidad_max=argumentos.capacidad_max,
        demanda_gravedad=argumentos.demanda_gravedad,
        demanda_media=argumentos.demanda_media,
        sigma_masa=argumentos.sigma_masa,
        capacidad_escalones=argumentos.capacidad_escalones,
        factores_escalon=tuple(argumentos.factores_escalon),
        cuantiles_escalon=tuple(argumentos.cuantiles_escalon),
        semilla=argumentos.semilla,
        porcentaje_hubs=argumentos.porcentaje_hubs,
        multiplicador_capacidad_hubs=argumentos.multiplicador_hubs,
        conexiones_por_hub=argumentos.vecinos_hub,
    )
    escribir_instancia(SALIDA_ACTIVA, grafo, arcos, commodities)

    sufijo_realismo = ""
    if argumentos.demanda_gravedad:
        sufijo_realismo += "_dg"
    if argumentos.capacidad_escalones:
        sufijo_realismo += "_ce"

    nombre_instancia = argumentos.nombre or (
        f"waxman_n{argumentos.nodos}"
        f"_m{argumentos.arcos or len(arcos)}"
        f"_k{argumentos.productos}"
        f"_h{100 * argumentos.porcentaje_hubs:g}"
        f"_v{argumentos.vecinos_hub}"
        f"{sufijo_realismo}"
        f"_s{argumentos.semilla}"
    )

    print(
        "Instancia generada: "
        f"{grafo.number_of_nodes()} nodos, "
        f"{len(arcos)} arcos y "
        f"{len(commodities)} productos."
    )
    print(f"Instancia guardada en {SALIDA_ACTIVA}")

    if argumentos.analizar_red:
        analizar_red_generada(SALIDA_ACTIVA)

    ejecutar_solver(nombre_instancia, archivo_solver)


if __name__ == "__main__":
    main()
