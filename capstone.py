"""Entrada principal del proyecto; accesos anteriores disponibles en compat/."""
import argparse
import os
from pathlib import Path
import subprocess
import sys

RAIZ = Path(__file__).resolve().parent
if sys.pycache_prefix is None:
    sys.pycache_prefix = str(RAIZ / "trabajo" / "pycache")
COMANDOS = {
    "mulgen": "ejecutar.py",
    "instancia": "ejecutar_instancia.py",
    "waxman": "ejecutar_waxman.py",
    "sndlib": "ejecutar_sndlib.py",
    "x3": "experimento_x3.py",
    "x4": "experimento_x4.py",
    "topologia": "experimento_waxman.py",
    "validacion": "experimento_validacion.py",
    "eta": "experimento_s6.py",
    "visualizar": "visualizar_waxman.py",
    "compilar": "setup_pricing_cpp.py",
    "memoria": "benchmark_memoria.py",
    "perfil-waxman": "comparar_waxman.py",
}


def main():
    parser = argparse.ArgumentParser(
        description="Capstone G22: ejecutar redes o consultar baterías.",
        epilog="Ejemplo: python3 capstone.py instancia red_chile/instancias_enteras/base.txt E3")
    parser.add_argument("comando", choices=COMANDOS)
    parser.add_argument("argumentos", nargs=argparse.REMAINDER,
                        help="Opciones del comando; usar COMANDO --help para verlas.")
    args = parser.parse_args()
    comando = [sys.executable, str(RAIZ / "compat" / COMANDOS[args.comando])]
    if args.comando == "compilar" and not args.argumentos:
        comando += ["build_ext", "--build-lib", str(RAIZ / "src/nativo"),
                    "--build-temp", str(RAIZ / "trabajo/build")]
    try:
        return subprocess.call([*comando, *args.argumentos], cwd=RAIZ,
                               env=dict(os.environ, PYTHONPYCACHEPREFIX=sys.pycache_prefix))
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
