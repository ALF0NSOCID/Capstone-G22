"""Resuelve una instancia Canad existente y conserva cada corrida por separado."""
import argparse
from pathlib import Path

from ejecutar import ejecutar_analisis_red, ejecutar_solver, obtener_solver
from src.ejecucion.gestion import crear_corrida, preparar_archivo


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('instancia', type=Path, help='Instancia Canad con enteros')
    parser.add_argument('solver', help='E3, base, LP o nombre de solver compatible')
    parser.add_argument('--analizar-red', action='store_true')
    parser.add_argument('--salida', type=Path, help='Carpeta base para las nuevas ejecuciones')
    args = parser.parse_args()
    origen = args.instancia.resolve()
    if not origen.is_file():
        parser.error(f'No existe {origen}')
    solver = obtener_solver(args.solver)
    nombre = 'chile_' + origen.stem
    carpeta = crear_corrida(nombre, args.salida)
    instancia = preparar_archivo(origen, carpeta)
    if args.analizar_red:
        ejecutar_analisis_red(nombre, instancia)
    ejecutar_solver(nombre, solver, instancia=instancia, carpeta=carpeta)


if __name__ == '__main__':
    main()
