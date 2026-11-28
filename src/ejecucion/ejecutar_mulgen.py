import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

from analisis_red import analizar_red_generada


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
SALIDA_ACTIVA = RAIZ / "trabajo" / "out"


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
    SALIDA_ACTIVA.parent.mkdir(parents=True, exist_ok=True)
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

def ejecutar_analisis_red(nombre_instancia, instancia=None):
    """Ejecuta el diagnóstico estructural de la instancia activa."""
    print(f"Analizando estructura de la instancia {nombre_instancia}...")
    return analizar_red_generada(instancia or SALIDA_ACTIVA)


# ---------------------------------------------------------
# SELECCIONAR SOLVER
# ---------------------------------------------------------

def obtener_solver(nombre_solver):
    """Busca el solver solicitado dentro de la raíz del repositorio."""

    nombre_solver = {"E3": "solver_columnas_e2_v2", "e3": "solver_columnas_e2_v2",
                     "base": "solver_columnas_pricing_gurobi", "LP": "solver",
                     "lp": "solver"}.get(nombre_solver, nombre_solver)
    if not nombre_solver.endswith(".py"):
        nombre_solver += ".py"

    # Solo se acepta el nombre del archivo, no una ruta
    # fuera del repositorio.
    nombre_solver = Path(nombre_solver).name

    archivo_solver = RAIZ / "compat" / nombre_solver

    if not archivo_solver.exists():
        raise FileNotFoundError(f"No existe el solver {archivo_solver}")

    if archivo_solver == Path(__entry_file__).resolve():
        raise ValueError("ejecutar.py no puede utilizarse como solver")

    return archivo_solver


# ---------------------------------------------------------
# EJECUTAR SOLVER
# ---------------------------------------------------------

def ejecutar_solver(nombre_instancia, archivo_solver, *, instancia=None, carpeta=None, salida=None):
    """Interfaz compatible; las salidas nuevas se guardan por corrida."""
    from src.ejecucion.gestion import ejecutar_solver as ejecutar_registrado
    return ejecutar_registrado(nombre_instancia, archivo_solver,
                              instancia or SALIDA_ACTIVA, carpeta, salida)


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

    parser.add_argument("--salida", type=Path, help="Carpeta base para las nuevas ejecuciones")
    argumentos = parser.parse_args()

    archivo_solver = obtener_solver(argumentos.solver)

    from src.ejecucion.gestion import crear_corrida, generar_mulgen_aislado
    nombre_instancia = Path(argumentos.parametro).stem
    carpeta = crear_corrida(nombre_instancia, argumentos.salida)
    instancia = generar_mulgen_aislado(argumentos.parametro, carpeta)
    if argumentos.analizar_red:
        ejecutar_analisis_red(nombre_instancia, instancia)
    ejecutar_solver(nombre_instancia, archivo_solver, instancia=instancia, carpeta=carpeta)



if __name__ == "__main__":
    main()
