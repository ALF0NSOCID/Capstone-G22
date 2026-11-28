"""Ejecuta un solver sobre un archivo de instancia en formato Canad con enteros (p. ej. las de
red_chile/instancias_enteras/). Copia el archivo a `out` y reutiliza ejecutar.ejecutar_solver, igual que ejecutar_sndlib.py.

Uso:  python ejecutar_instancia.py red_chile/instancias_enteras/base.txt solver_columnas_e2 [--analizar-red]
"""
import argparse
import shutil
from pathlib import Path

from ejecutar import SALIDA_ACTIVA, ejecutar_analisis_red, ejecutar_solver, obtener_solver

parser = argparse.ArgumentParser()
parser.add_argument('instancia', help='Archivo de instancia con enteros')
parser.add_argument('solver', help='Ej. solver_columnas o solver_columnas_e2')
parser.add_argument('--analizar-red', action='store_true')
args = parser.parse_args()

origen = Path(args.instancia).resolve()
if not origen.is_file():
    raise SystemExit(f'No existe {origen}')
shutil.copyfile(origen, SALIDA_ACTIVA)
nombre = 'chile_' + origen.stem
print(f'Instancia {origen.name} copiada a {SALIDA_ACTIVA.name}')
if args.analizar_red:
    ejecutar_analisis_red(nombre)
ejecutar_solver(nombre, obtener_solver(args.solver))
