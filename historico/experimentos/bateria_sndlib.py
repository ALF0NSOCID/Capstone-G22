#!/usr/bin/env python3
"""Batería de pruebas SNDlib: no modifica lectores ni solvers existentes.

Coloca este archivo junto a ejecutar_sndlib.py y ejecuta:
    python3 bateria_sndlib.py --modo rapida
    python3 bateria_sndlib.py --modo completa --timeout 180
    python3 bateria_sndlib.py --modo capacidades
    python3 bateria_sndlib.py --modo escalado
    python3 bateria_sndlib.py --modo repeticiones --reps 10
    python3 bateria_sndlib.py --modo todos --timeout 180

Cada caso se ejecuta secuencialmente, tiene un timeout y deja registro en CSV.
La opción --timeout expresa segundos por prueba, no tiempo total.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import datetime
import os
from pathlib import Path
import re
import shutil
import signal
import statistics
import subprocess
import sys
import time

RAIZ = Path(__file__).resolve().parent
EJECUTOR = RAIZ / "compat" / 'ejecutar_sndlib.py'
BASE_RED = RAIZ / 'sndlib'
RAPIDAS = ('newyork', 'dfn-bwin', 'dfn-gwin', 'janos-us',
           'giul39', 'janos-us-ca', 'ta2', 'zib54')
REDES_CAPACIDADES = ('newyork', 'giul39', 'janos-us', 'janos-us-ca', 'ta2')
REDES_ESCALADO = ('germany50', 'giul39', 'janos-us')
REDES_REPETICION = ('giul39', 'ta2')
CAMPOS_CSV = (
    'prueba', 'red', 'capacidad', 'factor', 'repeticion', 'estado',
    'nodos', 'arcos', 'commodities', 'objetivo', 'gap_pct',
    'iteraciones', 'columnas', 'tiempo_interno_s', 'tiempo_proceso_s',
    'tiempo_orquestado_s', 'codigo_salida', 'log',
)

@dataclass(frozen=True)
class Caso:
    grupo: str
    red: str
    capacidad: str = 'preinstalada_o_minima'
    factor: str = '1'
    repeticion: int = 1

    @property
    def nombre(self) -> str:
        return f'{self.grupo}__{self.red}__{self.capacidad}__fc{self.factor}__r{self.repeticion:02d}'


def ruta_redes() -> Path:
    candidatas = [RAIZ / 'sndlib', RAIZ / 'SNDlib' / 'redes', RAIZ / 'SNDlib',
                  RAIZ / 'BendersNetworkDesign.jl' / 'data' / 'sndlib',
                  RAIZ / 'BendersNetworkDesign.jl-main' / 'data' / 'sndlib']
    for ruta in candidatas:
        if ruta.is_dir() and any(ruta.glob('*.xml')):
            return ruta
    raise FileNotFoundError('No encuentro carpeta sndlib con XML junto al proyecto.')


def crear_casos(modo: str, disponibles: list[str], reps: int) -> list[Caso]:
    conjunto = set(disponibles)
    def filtrar(redes):
        faltantes = sorted(set(redes) - conjunto)
        if faltantes:
            print(f'Aviso: se omiten redes no descargadas: {", ".join(faltantes)}')
        return [red for red in redes if red in conjunto]

    casos: list[Caso] = []
    if modo == 'rapida':
        casos += [Caso('rapida', r) for r in filtrar(RAPIDAS)]
    elif modo in ('completa', 'todos'):
        # Orden por tamaño del XML para encontrar problemas pronto y dejar Brain hacia el final.
        casos += [Caso('completa', r) for r in disponibles]
    if modo in ('capacidades', 'todos'):
        for r in filtrar(REDES_CAPACIDADES):
            for politica in ('minima', 'maxima'):
                casos.append(Caso('capacidades', r, politica))
    if modo in ('escalado', 'todos'):
        for r in filtrar(REDES_ESCALADO):
            for factor in ('1', '4', '0.25'):
                casos.append(Caso('escalado', r, factor=factor))
    if modo in ('repeticiones', 'todos'):
        for r in filtrar(REDES_REPETICION):
            casos += [Caso('repeticiones', r, repeticion=i) for i in range(1, reps + 1)]
    return casos


def ultimo(patron: str, texto: str, tipo=str):
    encontrados = re.findall(patron, texto, flags=re.IGNORECASE | re.MULTILINE)
    if not encontrados:
        return ''
    dato = encontrados[-1]
    try:
        return tipo(dato)
    except (ValueError, TypeError):
        return ''


def ejecutar(caso: Caso, solver: str, timeout: int, carpeta: Path) -> dict:
    comando = [sys.executable, '-u', str(EJECUTOR), caso.red, solver,
               '--capacidad', caso.capacidad, '--factor-capacidad', caso.factor]
    log = carpeta / f'{caso.nombre}.log'
    # Resguardar resultados que el ejecutor original sobrescribiría.
    id_instancia = f'sndlib_{caso.red}_base_{caso.capacidad}'
    if caso.factor != '1':
        id_instancia += '_fc' + re.sub(r'[^a-zA-Z0-9_-]+', '_', caso.factor).strip('_')
    nombre_archivo = f'{id_instancia}_{Path(solver).stem}'
    respaldos = carpeta / 'resultados_previos'
    for extension in ('.txt', '.json'):
        original = RAIZ / 'resultados' / (nombre_archivo + extension)
        copia = respaldos / original.name
        if original.exists() and not copia.exists():
            respaldos.mkdir(exist_ok=True)
            shutil.copy2(original, copia)
    inicio = time.perf_counter()
    codigo = None
    estado = 'error'
    with log.open('w', encoding='utf-8') as salida:
        salida.write('COMANDO: ' + ' '.join(comando) + '\n\n')
        salida.flush()
        proceso = subprocess.Popen(comando, cwd=RAIZ, stdout=salida,
                                   stderr=subprocess.STDOUT, start_new_session=True)
        try:
            codigo = proceso.wait(timeout=timeout)
            estado = 'ok' if codigo == 0 else 'error'
        except subprocess.TimeoutExpired:
            estado = 'timeout'
            try:
                os.killpg(proceso.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                proceso.wait(timeout=5)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(proceso.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                proceso.wait()
        salida.write(f'\n[FIN BATERIA] estado={estado}; codigo={codigo}\n')

    texto = log.read_text(encoding='utf-8', errors='replace')
    cabecera = re.search(r'out generado: (\d+) nodos, (\d+) arcos, (\d+) commodities', texto)
    valores = cabecera.groups() if cabecera else ('', '', '')
    return {
        'prueba': caso.grupo, 'red': caso.red, 'capacidad': caso.capacidad,
        'factor': caso.factor, 'repeticion': caso.repeticion, 'estado': estado,
        'nodos': valores[0], 'arcos': valores[1], 'commodities': valores[2],
        'objetivo': ultimo(r'^Objetivo/congestion:\s*([+-]?[0-9.eE-]+)', texto, float),
        'gap_pct': ultimo(r'^Gap certificado:\s*([0-9.eE+-]+)%', texto, float),
        'iteraciones': ultimo(r'^Iteraciones:\s*(\d+)', texto, int),
        'columnas': ultimo(r'^Columnas finales:\s*(\d+)', texto, int),
        'tiempo_interno_s': ultimo(r'^Tiempo interno del algoritmo:\s*([0-9.]+) s', texto, float),
        'tiempo_proceso_s': ultimo(r'^Tiempo de pared del proceso:\s*([0-9.]+) s', texto, float),
        'tiempo_orquestado_s': round(time.perf_counter() - inicio, 4),
        'codigo_salida': codigo if codigo is not None else '',
        'log': str(log.relative_to(RAIZ)),
    }


def validar_escalado(filas: list[dict]):
    grupos = {}
    for fila in filas:
        if fila['prueba'] == 'escalado' and fila['estado'] == 'ok' and fila['objetivo'] != '':
            grupos.setdefault(fila['red'], {})[fila['factor']] = fila['objetivo']
    print('\nVALIDACIÓN DE ESCALADO (la congestión debería ser inversamente proporcional al factor):')
    for red, resultados in grupos.items():
        z = resultados.get('1')
        if z is None:
            print(f'  {red}: sin referencia (factor 1)')
            continue
        for factor in ('4', '0.25'):
            valor = resultados.get(factor)
            if valor is None:
                print(f'  {red} factor {factor}: sin resultado')
            else:
                esperado = z / float(factor)
                error = abs(valor - esperado)
                ok = error <= 1e-6 * max(1, abs(esperado))
                print(f'  {red} factor {factor}: calculado={valor:.9g}, '
                      f'esperado={esperado:.9g} -> {"OK" if ok else "REVISAR"}')


def estadisticas_repeticiones(filas: list[dict]):
    por_red = {}
    for fila in filas:
        if fila['prueba'] == 'repeticiones' and fila['estado'] == 'ok' and fila['tiempo_interno_s'] != '':
            por_red.setdefault(fila['red'], []).append(fila['tiempo_interno_s'])
    if not por_red:
        return
    print('\nREPETICIONES (tiempos internos; usar medianas, no una sola corrida):')
    for red, tiempos in por_red.items():
        print(f'  {red}: {len(tiempos)} corridas; '
              f'mediana={statistics.median(tiempos):.4f}s; '
              f'mín={min(tiempos):.4f}s; máx={max(tiempos):.4f}s')


def main():
    parser = argparse.ArgumentParser(description='Pruebas SNDlib con CSV, logs y timeout por red.')
    parser.add_argument('--modo', choices=('rapida', 'completa', 'capacidades', 'escalado', 'repeticiones', 'todos'),
                        default='rapida')
    parser.add_argument('--solver', default='solver_columnas_e2.py')
    parser.add_argument('--timeout', type=int, default=120, help='Segundos máximos por caso')
    parser.add_argument('--reps', type=int, default=8)
    args = parser.parse_args()
    if args.timeout < 1 or args.reps < 1:
        parser.error('--timeout y --reps deben ser positivos')
    if not EJECUTOR.is_file():
        parser.error(f'No encuentro {EJECUTOR.name}')
    if not (RAIZ / "compat" / args.solver).is_file():
        parser.error(f'No encuentro solver {args.solver} en la raíz del proyecto')

    carpeta_redes = ruta_redes()
    archivos = sorted(carpeta_redes.glob('*.xml'), key=lambda p: (p.stat().st_size, p.name))
    disponibles = [p.stem for p in archivos]
    casos = crear_casos(args.modo, disponibles, args.reps)
    if not casos:
        parser.error('No hay casos disponibles')

    marca = datetime.now().strftime('%Y%m%d_%H%M%S')
    carpeta = RAIZ / 'resultados' / 'baterias' / f'{marca}_{args.modo}'
    carpeta.mkdir(parents=True, exist_ok=False)
    archivo_csv = carpeta / 'resumen.csv'
    print(f'SNDlib: {len(disponibles)} redes encontradas, {len(casos)} pruebas ({args.modo}).', flush=True)
    print(f'Timeout por prueba: {args.timeout}s | Resultados: {archivo_csv}', flush=True)

    filas = []
    try:
        with archivo_csv.open('w', newline='', encoding='utf-8') as archivo:
            writer = csv.DictWriter(archivo, fieldnames=CAMPOS_CSV)
            writer.writeheader()
            archivo.flush()
            for i, caso in enumerate(casos, 1):
                print(f'[{i}/{len(casos)}] {caso.nombre} ...', flush=True)
                fila = ejecutar(caso, args.solver, args.timeout, carpeta)
                writer.writerow(fila)
                archivo.flush()
                filas.append(fila)
                tiempo = fila['tiempo_interno_s']
                z = fila['objetivo']
                print(f'    {fila["estado"]} | n={fila["nodos"]} '
                      f'm={fila["arcos"]} K={fila["commodities"]} '
                      f'| z={z} | iter={fila["iteraciones"]} '
                      f'| alg={tiempo}s | pared={fila["tiempo_orquestado_s"]}s', flush=True)
    except KeyboardInterrupt:
        print(f'\nInterrumpido. El CSV parcial sigue disponible: {archivo_csv}')
        return
    print(f'\nTERMINADO: {sum(f["estado"] == "ok" for f in filas)}/{len(filas)} correctos.')
    print(f'CSV: {archivo_csv}')
    validar_escalado(filas)
    estadisticas_repeticiones(filas)

if __name__ == '__main__':
    main()
