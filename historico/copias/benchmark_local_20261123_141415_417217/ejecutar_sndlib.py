"""Ejecuta redes XML de SNDlib usando el mismo `out` y solvers que Mulgen.

Ejemplos (desde la raíz del repositorio):
    python ejecutar_sndlib.py germany50 solver.py
    python ejecutar_sndlib.py germany50 --solo-generar
    python ejecutar_sndlib.py all solver.py
    python ejecutar_sndlib.py germany50 --serie 5min --listar
    python ejecutar_sndlib.py germany50 solver.py --serie 5min --t 3
    python ejecutar_sndlib.py germany50 solver.py --serie 5min --todas
    python ejecutar_sndlib.py germany50 solver.py --serie 5min --desde 1 --hasta 50 --cada 10

Las matrices temporales NO vienen en el GitHub de BendersNetworkDesign.
Cuando se obtengan deben ir en sndlib/temporales/<red>/<serie>/ como XML,
XML.GZ o un archivo TGZ con XMLs. Si se encuentra un TGZ se extrae a disco
una sola vez (los datos grandes pueden ocupar mucho espacio descomprimidos).
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from decimal import Decimal
import json
import os
from pathlib import Path, PurePosixPath
import re
import sys
import tarfile

from lector_sndlib import ErrorSNDlib, generar_out, leer_demandas_xml, leer_red_sndlib

RAIZ = Path(__file__).resolve().parent
OUT = RAIZ / 'out'
RESULTADOS = RAIZ / 'resultados'


def _buscar_carpeta_redes(especificada: str | None) -> Path:
    if especificada:
        opciones = [Path(especificada).expanduser()]
    else:
        opciones = [RAIZ / p for p in (
            'sndlib', 'SNDlib/redes', 'SNDlib',
            'BendersNetworkDesign.jl/data/sndlib',
            'BendersNetworkDesign.jl-main/data/sndlib',
        )]
    for ruta in opciones:
        if ruta.is_dir() and any(ruta.glob('*.xml')):
            return ruta.resolve()
    raise FileNotFoundError(
        'No encontré XML SNDlib. Copia la carpeta "sndlib" (con brain.xml, '
        'germany50.xml, etc.) junto a ejecutar_sndlib.py, o especifica '
        '--carpeta-redes RUTA.'
    )


def _buscar_red(nombre: str, carpeta: Path) -> Path:
    red = next((x for x in carpeta.glob('*.xml') if x.stem.casefold() == nombre.casefold()), None)
    if red is None:
        opciones = ', '.join(sorted(x.stem for x in carpeta.glob('*.xml')))
        raise FileNotFoundError(f'Red {nombre!r} no encontrada en {carpeta}. Opciones: {opciones}')
    return red


def _nombre_limpio(texto: str) -> str:
    return re.sub(r'[^a-zA-Z0-9_-]+', '_', texto).strip('_') or 'sin_nombre'


def _orden_natural(ruta: Path):
    return [int(x) if x.isdigit() else x.casefold()
            for x in re.split(r'(\d+)', str(ruta))]


def _extraer_tgz(archivo: Path, carpeta: Path) -> None:
    """Extrae XMLs del .tgz sin permitir rutas fuera de carpeta.

    Extracción idempotente. Evita sobrescribir archivos ya extraídos.
    Los archivos comprimidos oficiales pueden contener directorios internos.
    """
    contador = 0
    with tarfile.open(archivo, 'r:gz') as paquete:
        for miembro in paquete:
            if not miembro.isfile() or not miembro.name.lower().endswith('.xml'):
                continue
            partes = PurePosixPath(miembro.name).parts
            if any(x in ('..', '', '/') for x in partes) or miembro.name.startswith('/'):
                raise ErrorSNDlib(f'Ruta insegura dentro de {archivo.name}: {miembro.name}')
            # Conservar estructura interna relativa del archivo TGZ.
            destino = carpeta.joinpath(*partes)
            destino.parent.mkdir(parents=True, exist_ok=True)
            if destino.exists() and destino.stat().st_size == miembro.size:
                continue
            f = paquete.extractfile(miembro)
            if f is None:
                continue
            temporal = destino.with_name(destino.name + '.parcial_sndlib')
            try:
                with temporal.open('wb') as out:
                    while True:
                        datos = f.read(1024 * 1024)
                        if not datos:
                            break
                        out.write(datos)
                os.replace(temporal, destino)
                contador += 1
            finally:
                f.close()
                if temporal.exists():
                    temporal.unlink()
    print(f'  {archivo.name}: {contador} XML extraídos (los demás ya existían).')


def _buscar_temporales(red: str, serie: str, carpeta_redes: Path,
                      carpeta_temporales: str | None) -> list[Path]:
    if carpeta_temporales:
        base = Path(carpeta_temporales).expanduser()
    else:
        candidatas = [
            carpeta_redes / 'temporales',
            carpeta_redes.parent / 'temporales',
            RAIZ / 'sndlib' / 'temporales',
            RAIZ / 'SNDlib' / 'temporales',
        ]
        base = next((p for p in candidatas if (p / red / serie).is_dir()), candidatas[0])
    carpeta = base / red / serie
    if not carpeta.is_dir():
        raise FileNotFoundError(
            f'No existe {carpeta}. Las series temporales NO vienen en los 26 XML '
            f'estáticos. Pon las matrices de {red}/{serie} en esa carpeta.'
        )
    paquetes = sorted((p for p in carpeta.rglob('*') if p.is_file()
                        and p.name.lower().endswith(('.tgz', '.tar.gz'))), key=_orden_natural)
    if paquetes:
        print(f'Descomprimiendo {len(paquetes)} paquete(s) temporal(es) (si es necesario)...')
        for paquete in paquetes:
            _extraer_tgz(paquete, paquete.parent)
    rutas = sorted((p for p in carpeta.rglob('*') if p.is_file()
                    and p.name.lower().endswith(('.xml', '.xml.gz'))), key=_orden_natural)
    if not rutas:
        raise FileNotFoundError(f'No encontré matrices XML en {carpeta}')
    return rutas


def _elegir_indices(total: int, args: argparse.Namespace) -> list[int]:
    if args.t is not None:
        if not 1 <= args.t <= total:
            raise ErrorSNDlib(f'--t debe estar entre 1 y {total}')
        return [args.t]
    if args.todas:
        return list(range(1, total + 1))
    if args.desde is not None or args.hasta is not None or args.cada != 1:
        primero = args.desde if args.desde is not None else 1
        ultimo = args.hasta if args.hasta is not None else total
        if primero < 1 or ultimo > total or primero > ultimo:
            raise ErrorSNDlib(f'Rango temporal inválido: {primero}..{ultimo} (1..{total})')
        return list(range(primero, ultimo + 1, args.cada))
    return [1]


def _guardar_json(ruta: Path, datos: dict) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    tmp = ruta.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(datos, indent=2, ensure_ascii=False, default=str), encoding='utf-8')
    os.replace(tmp, ruta)


def _procesar(red_xml: Path, solver: Path | None, args: argparse.Namespace) -> None:
    red = leer_red_sndlib(red_xml, capacidad=args.capacidad)
    if args.serie:
        rutas = _buscar_temporales(red.nombre, args.serie, red_xml.parent, args.carpeta_temporales)
        if args.listar:
            print(f'\n{red.nombre} — serie {args.serie}, {len(rutas)} matrices (t inicia en 1)')
            for t, archivo in enumerate(rutas, 1):
                print(f'  t={t:>6}: {archivo.name}')
            return
        indices = _elegir_indices(len(rutas), args)
    else:
        if args.listar:
            print(f'{red.nombre}: base (única instancia del XML estático)')
            return
        if args.t is not None or args.todas or args.desde is not None or args.hasta is not None or args.cada != 1:
            raise ErrorSNDlib('Las opciones de tiempos requieren --serie (ej. --serie 5min).')
        rutas = []
        indices = [0]

    for indice in indices:
        archivo_matriz = rutas[indice - 1] if indice else None
        demandas = leer_demandas_xml(archivo_matriz) if archivo_matriz else None
        serie_nombre = f'{_nombre_limpio(args.serie)}_t{indice:06d}' if indice else 'base'
        nombre = f'sndlib_{_nombre_limpio(red.nombre)}_{serie_nombre}_{args.capacidad}'
        if args.factor_capacidad != '1':
            nombre += '_fc' + _nombre_limpio(args.factor_capacidad)
        if args.escala_fija is not None:
            nombre += f'_esc{args.escala_fija}'
        metodo = solver.stem if solver else 'solo_generar'
        ruta_resultado = RESULTADOS / f'{nombre}_{metodo}.txt'
        ruta_metadata = RESULTADOS / f'{nombre}_{metodo}.json'

        if args.reanudar and solver and ruta_resultado.is_file() and ruta_metadata.is_file():
            try:
                actual = json.loads(ruta_metadata.read_text(encoding='utf-8'))
                if (actual.get('estado') == 'ok'
                        and actual.get('ruta_red') == str(red_xml.resolve())
                        and actual.get('ruta_matriz') == (str(archivo_matriz.resolve()) if archivo_matriz else None)):
                    print(f'\n[Ya completada] {nombre} — {metodo}')
                    continue
            except (OSError, ValueError):
                pass

        print(f'\n--- {nombre} ---')
        info = generar_out(red, demandas, destino=OUT,
                           factor_capacidad=args.factor_capacidad,
                           escala_fija=args.escala_fija)
        info.update({
            'id_instancia': nombre,
            'ruta_red': str(red_xml.resolve()),
            'ruta_matriz': str(archivo_matriz.resolve()) if archivo_matriz else None,
            'serie': args.serie or 'base',
            't': indice if indice else None,
            'timestamp_matriz': archivo_matriz.stem if archivo_matriz else None,
            'capacidad_politica': args.capacidad,
            'solver': solver.name if solver else None,
            'fecha_ejecucion_utc': datetime.now(timezone.utc).isoformat(),
            'estado': 'generado',
        })
        print(f"out generado: {info['nodos']} nodos, {info['arcos_dirigidos']} arcos, "
              f"{info['commodities']} commodities; escala={info['escala_enteros']}.")
        if info['colisiones_arcos_fusionados']:
            print(f"  Arcos dirigidos fusionados: {info['colisiones_arcos_fusionados']} ")
        if args.analizar_red:
            from ejecutar import ejecutar_analisis_red
            ejecutar_analisis_red(nombre)
        if solver is None:
            print(f'Archivo disponible en {OUT}; no se ejecutó un solver.')
            continue

        _guardar_json(ruta_metadata, info)
        try:
            # Mismos indicadores, archivos y monitor de memoria que ejecutar.py.
            from ejecutar import ejecutar_solver
            ejecutar_solver(nombre, solver)
        except Exception:
            info['estado'] = 'error'
            _guardar_json(ruta_metadata, info)
            raise
        info['estado'] = 'ok'
        _guardar_json(ruta_metadata, info)


def main() -> None:
    parser = argparse.ArgumentParser(
        description='Convierte y ejecuta redes SNDlib XML con el pipeline actual de Mulgen.'
    )
    parser.add_argument('red', help='Nombre sin .xml, o "all" para todas las redes estáticas')
    parser.add_argument('solver', nargs='?', help='Ej. solver.py (opcional con --listar/--solo-generar)')
    parser.add_argument('--carpeta-redes', help='Carpeta con los 26 XML originales')
    parser.add_argument('--carpeta-temporales', help='Carpeta base de series temporales')
    parser.add_argument('--serie', help='Ej. 5min, 1day, 1min (requiere matrices separadas)')
    parser.add_argument('--t', type=int, help='Índice temporal desde 1')
    parser.add_argument('--todas', action='store_true', help='Ejecutar todas las matrices de la serie')
    parser.add_argument('--desde', type=int)
    parser.add_argument('--hasta', type=int)
    parser.add_argument('--cada', type=int, default=1)
    parser.add_argument('--listar', action='store_true', help='Mostrar índices y archivos sin ejecutar')
    parser.add_argument('--solo-generar', action='store_true', help='Solo crear out; no ejecutar solver')
    parser.add_argument('--reanudar', action='store_true', help='Omitir ejecuciones que terminaron exitosamente')
    parser.add_argument('--analizar-red', action='store_true', help='Usar diagnóstico del ejecutar.py original')
    parser.add_argument('--capacidad', default='preinstalada_o_minima',
                        choices=('preinstalada_o_minima', 'minima', 'maxima'))
    parser.add_argument('--factor-capacidad', default='1',
                        help='Multiplicador para capacidades: 1, 2, 0.5 ...')
    parser.add_argument('--escala-fija', type=int,
                        help='Factor de escala entero común entre distintas instancias; opcional')
    args = parser.parse_args()

    if args.cada < 1:
        parser.error('--cada debe ser >= 1')
    if args.solo_generar and args.solver:
        parser.error('Con --solo-generar omite el argumento solver.')
    if not args.listar and not args.solo_generar and not args.solver:
        parser.error('Falta el solver. Usa --solo-generar para probar el conversor.')
    if args.red.lower() == 'all' and args.serie:
        parser.error('all es para las redes base; las series se ejecutan por red.')
    if args.red.lower() == 'all' and args.solo_generar:
        parser.error('No se admite all con --solo-generar: el out se sobrescribiría.')

    try:
        carpeta = _buscar_carpeta_redes(args.carpeta_redes)
        if args.red.casefold() == 'all':
            redes = sorted(carpeta.glob('*.xml'), key=_orden_natural)
        else:
            redes = [_buscar_red(args.red.removesuffix('.xml'), carpeta)]

        solver = None
        if args.solver and not args.listar:
            # Reutilizar búsqueda del archivo original sin recompilar Mulgen.
            from ejecutar import obtener_solver
            solver = obtener_solver(args.solver)
        for red_xml in redes:
            _procesar(red_xml, solver, args)
    except (ErrorSNDlib, FileNotFoundError, OSError) as exc:
        print(f'ERROR SNDlib: {exc}', file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
