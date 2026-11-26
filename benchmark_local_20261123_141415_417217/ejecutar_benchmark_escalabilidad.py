"""Ejecuta un rango del benchmark ajustando los limites estaticos de Mulgen."""

import argparse
import re
import subprocess
import sys
from pathlib import Path


RAIZ = Path(__file__).resolve().parent
CARPETA_DATOS = RAIZ / "Canad" / "Data"
CARPETA_RESULTADOS = RAIZ / "resultados"
DIMENSIONES_MULGEN = RAIZ / "Canad" / "Mulgen" / "dim.par"
TOTAL_INSTANCIAS = 141


def leer_entero(texto, parametro):
    coincidencia = re.search(
        rf"^{re.escape(parametro)}\s+(\d+)\s*$",
        texto,
        flags=re.MULTILINE,
    )
    if coincidencia is None:
        raise ValueError(f"No se encontro {parametro} en el archivo .par.")
    return int(coincidencia.group(1))


def dimensiones_instancia(archivo):
    texto = archivo.read_text(encoding="utf-8")
    scalex = leer_entero(texto, "scalex")
    scaley = leer_entero(texto, "scaley")
    productos = leer_entero(texto, "commod")
    arcos = leer_entero(texto, "addarc")
    return scalex * scaley, arcos, productos


def ajustar_dimensiones_mulgen(nodos, arcos, productos):
    contenido = (
        f"       parameter(MAXNODES={nodos}, MAXARCS={arcos}, "
        f"MAXCOMM={productos})\n"
    )
    if (
        DIMENSIONES_MULGEN.exists()
        and DIMENSIONES_MULGEN.read_text(encoding="utf-8") == contenido
    ):
        return False
    DIMENSIONES_MULGEN.write_text(contenido, encoding="utf-8")
    return True


def resultado_completo(instancia, solver):
    archivo = CARPETA_RESULTADOS / f"{instancia}_{Path(solver).stem}.txt"
    if not archivo.exists():
        return False
    texto = archivo.read_text(encoding="utf-8", errors="replace")
    return "Estado: completado" in texto


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Ejecuta t_1.par a t_141.par y ajusta dim.par antes de cada "
            "configuracion para evitar reservas estaticas gigantes."
        )
    )
    parser.add_argument("solver", help="Solver sin o con extension .py.")
    parser.add_argument("--desde", type=int, default=1)
    parser.add_argument("--hasta", type=int, default=TOTAL_INSTANCIAS)
    parser.add_argument(
        "--forzar",
        action="store_true",
        help="Repite tambien resultados que ya figuran como completados.",
    )
    parser.add_argument(
        "--detener-en-error",
        action="store_true",
        help="Detiene todo el benchmark si una instancia falla.",
    )
    argumentos = parser.parse_args()

    if not 1 <= argumentos.desde <= argumentos.hasta <= TOTAL_INSTANCIAS:
        parser.error(
            f"El rango debe cumplir 1 <= desde <= hasta <= "
            f"{TOTAL_INSTANCIAS}."
        )

    completadas = 0
    omitidas = 0
    fallidas = 0

    for indice in range(argumentos.desde, argumentos.hasta + 1):
        instancia = f"t_{indice}"
        archivo_parametros = CARPETA_DATOS / f"{instancia}.par"
        if not archivo_parametros.exists():
            raise FileNotFoundError(
                f"Falta {archivo_parametros}. Ejecuta primero "
                "generar_benchmark_escalabilidad.py."
            )

        if not argumentos.forzar and resultado_completo(
            instancia,
            argumentos.solver,
        ):
            print(f"[{indice}/{argumentos.hasta}] {instancia}: ya completada.")
            omitidas += 1
            continue

        nodos, arcos, productos = dimensiones_instancia(archivo_parametros)
        recompila = ajustar_dimensiones_mulgen(nodos, arcos, productos)
        print(
            f"\n[{indice}/{argumentos.hasta}] {instancia}: "
            f"N={nodos}, M={arcos}, K={productos}"
            + (" | se recompilara Mulgen" if recompila else ""),
            flush=True,
        )

        proceso = subprocess.run(
            [
                sys.executable,
                "-u",
                str(RAIZ / "ejecutar.py"),
                instancia,
                argumentos.solver,
            ],
            cwd=RAIZ,
            check=False,
        )
        if proceso.returncode == 0:
            completadas += 1
        else:
            fallidas += 1
            print(
                f"{instancia} fallo con codigo {proceso.returncode}.",
                flush=True,
            )
            if argumentos.detener_en_error:
                raise SystemExit(proceso.returncode)

    print(
        "\nBenchmark terminado: "
        f"completadas={completadas}, omitidas={omitidas}, fallidas={fallidas}."
    )


if __name__ == "__main__":
    main()
