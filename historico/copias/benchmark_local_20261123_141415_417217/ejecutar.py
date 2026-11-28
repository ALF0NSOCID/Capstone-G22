import argparse
import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

from analisis_red import analizar_red_generada
from metricas_ejecucion import construir_resumen_kpi, vigilar_memoria


# ---------------------------------------------------------
# RUTAS PRINCIPALES
# ---------------------------------------------------------

RAIZ = Path(__file__).resolve().parent

CARPETA_MULGEN = RAIZ / "Canad" / "Mulgen"
CARPETA_DATA = RAIZ / "Canad" / "Data"
CARPETA_RESULTADOS = RAIZ / "resultados"

# En Windows el ejecutable termina en .exe.
NOMBRE_EJECUTABLE = "mulgen.exe" if os.name == "nt" else "mulgen"
EJECUTABLE_MULGEN = CARPETA_MULGEN / NOMBRE_EJECUTABLE

SALIDA_MULGEN = CARPETA_MULGEN / "out"
SALIDA_ACTIVA = RAIZ / "out"


# ---------------------------------------------------------
# COMPILAR MULGEN
# ---------------------------------------------------------

def compilar_mulgen():
    """
    Compila Mulgen cuando no existe el ejecutable o cuando
    alguno de sus archivos fuente fue modificado posteriormente.
    """

    archivos_fortran = [
        "main.f",
        "mulgen.f",
        "ran2.f",
        "outdat.f",
        "mps.f",
        "lp.f",
        "append.f",
        "traitenom.f",
        "int2char.f",
    ]

    archivos_fuente = [
        CARPETA_MULGEN / "dim.par",
        CARPETA_MULGEN / "mulgen.cmn",
        *(CARPETA_MULGEN / nombre for nombre in archivos_fortran),
    ]

    necesita_compilar = not EJECUTABLE_MULGEN.exists()

    if not necesita_compilar:
        fecha_ejecutable = EJECUTABLE_MULGEN.stat().st_mtime
        necesita_compilar = any(
            archivo.stat().st_mtime > fecha_ejecutable
            for archivo in archivos_fuente
        )

    if not necesita_compilar:
        print("Mulgen ya está compilado.")
        return

    print("Compilando Mulgen...")

    comando = [
        "gfortran",
        "-std=legacy",
        "-ffixed-line-length-none",
        # Enlace estático: evita que el ejecutable dependa de las DLLs de
        # gfortran del sistema, que en Windows suelen chocar entre distintas
        # instalaciones de MinGW y producen errores como
        # "No se encuentra el punto de entrada... clock_gettime64".

        # Evita falsos positivos de STATUS_STACK_BUFFER_OVERRUN en Windows
        # con este código Fortran heredado de los 90.
        "-fno-stack-protector",
        *archivos_fortran,
        "-o",
        EJECUTABLE_MULGEN.name,
    ]

    subprocess.run(comando, cwd=CARPETA_MULGEN, check=True)

    if not EJECUTABLE_MULGEN.exists():
        raise FileNotFoundError(
            "La compilación terminó, pero no se encontró "
            f"el ejecutable {EJECUTABLE_MULGEN}"
        )

    print("Mulgen compilado correctamente.")


# ---------------------------------------------------------
# GENERAR INSTANCIA
# ---------------------------------------------------------

def generar_instancia(nombre_parametro):
    """
    Ejecuta Mulgen utilizando el archivo .par seleccionado.
    """

    if not nombre_parametro.endswith(".par"):
        nombre_parametro += ".par"

    # Impide utilizar archivos externos a Canad/Data.
    nombre_parametro = Path(nombre_parametro).name

    archivo_parametro = CARPETA_DATA / nombre_parametro

    if not archivo_parametro.exists():
        raise FileNotFoundError(f"No existe el archivo {archivo_parametro}")

    print(f"Generando instancia con {nombre_parametro}...")

    # Eliminar la salida anterior para que un fallo de Mulgen no pueda
    # confundirse con una instancia recién generada.
    if SALIDA_MULGEN.exists():
        SALIDA_MULGEN.unlink()

    # Mulgen utiliza campos de texto antiguos y puede cortar
    # rutas absolutas largas. Por eso se entrega una ruta
    # relativa corta desde Canad/Mulgen.
    ruta_parametro_mulgen = Path("..") / "Data" / nombre_parametro

    proceso = subprocess.run(
        [
            str(EJECUTABLE_MULGEN),
            str(ruta_parametro_mulgen),
        ],
        cwd=CARPETA_MULGEN,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    if proceso.stdout:
        print(proceso.stdout, end="")

    if proceso.returncode != 0:
        raise RuntimeError(
            "Mulgen termino durante la generacion con codigo "
            f"{proceso.returncode}."
        )

    if "EXECUTION ABORTED" in proceso.stdout:
        raise RuntimeError(
            f"Mulgen rechazó los parámetros de {nombre_parametro}."
        )

    if not SALIDA_MULGEN.exists():
        raise FileNotFoundError(
            "Mulgen terminó, pero no generó "
            "el archivo out"
        )

    # Copiar la instancia a la raíz, que es donde
    # los distintos solvers esperan encontrar out.
    shutil.copy2(SALIDA_MULGEN, SALIDA_ACTIVA)

    with open(SALIDA_ACTIVA, "r", encoding="utf-8") as archivo:
        cabecera = archivo.readline().split()

    if len(cabecera) != 3:
        raise ValueError("La instancia generada tiene una cabecera inválida")

    nodos, arcos, productos = map(int, cabecera)

    print(
        "Instancia generada: "
        f"{nodos} nodos, "
        f"{arcos} arcos y "
        f"{productos} productos."
    )

    return Path(nombre_parametro).stem


# ---------------------------------------------------------
# ANALISIS ESTRUCTURAL DE LA RED
# ---------------------------------------------------------

def ejecutar_analisis_red(nombre_instancia):
    """Ejecuta el diagnóstico estructural de la instancia activa."""
    print(f"Analizando estructura de la instancia {nombre_instancia}...")
    return analizar_red_generada(SALIDA_ACTIVA)


# ---------------------------------------------------------
# SELECCIONAR SOLVER
# ---------------------------------------------------------

def obtener_solver(nombre_solver):
    """Busca el solver solicitado dentro de la raíz del repositorio."""

    if not nombre_solver.endswith(".py"):
        nombre_solver += ".py"

    # Solo se acepta el nombre del archivo, no una ruta
    # fuera del repositorio.
    nombre_solver = Path(nombre_solver).name

    archivo_solver = RAIZ / nombre_solver

    if not archivo_solver.exists():
        raise FileNotFoundError(f"No existe el solver {archivo_solver}")

    if archivo_solver == Path(__file__).resolve():
        raise ValueError("ejecutar.py no puede utilizarse como solver")

    return archivo_solver


# ---------------------------------------------------------
# EJECUTAR SOLVER
# ---------------------------------------------------------

def ejecutar_solver(nombre_instancia, archivo_solver):
    """
    Ejecuta el solver seleccionado y guarda su salida
    en un archivo que identifica la instancia y el método.
    """

    CARPETA_RESULTADOS.mkdir(exist_ok=True)
    nombre_metodo = archivo_solver.stem
    archivo_resultado = CARPETA_RESULTADOS / f"{nombre_instancia}_{nombre_metodo}.txt"

    print(f"Ejecutando solver: {archivo_solver.name}")
    print(f"Los resultados se guardarán en {archivo_resultado}")

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

    with open(archivo_resultado, "w", encoding="utf-8") as resultado:
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
        raise RuntimeError(f"{archivo_solver.name} terminó con código {codigo_salida}")

# ---------------------------------------------------------
# PROGRAMA PRINCIPAL
# ---------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description=(
            "Compila Mulgen, genera una instancia "
            "y la resuelve utilizando el solver "
            "seleccionado."
        )
    )

    parser.add_argument(
        "parametro",
        help=(
            "Nombre del archivo de parámetros. "
            "Ejemplos: d33, estres40 o estres50"
        ),
    )

    parser.add_argument(
        "solver",
        help=(
            "Archivo Python que resolverá la instancia. "
            "Ejemplos: solver.py, solver_columnas.py "
            "o solver_garg_konemann.py"
        ),
    )

    parser.add_argument(
        "--analizar-red",
        action="store_true",
        help=(
            "Imprime un diagnóstico estructural de la red generada "
            "antes de ejecutar el solver."
        ),
    )

    argumentos = parser.parse_args()

    archivo_solver = obtener_solver(argumentos.solver)

    compilar_mulgen()

    nombre_instancia = generar_instancia(argumentos.parametro)

    if argumentos.analizar_red:
        ejecutar_analisis_red(nombre_instancia)

    ejecutar_solver(nombre_instancia, archivo_solver)


if __name__ == "__main__":
    main()
