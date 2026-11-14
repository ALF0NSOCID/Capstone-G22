"""Convierte instancias XML de SNDlib al formato `out` utilizado por Mulgen.

No importa ni modifica `lector.py` ni los solvers. Solo biblioteca estándar.

Convenciones de la adaptación:
* Cada enlace XML permite tráfico en ambos sentidos, con capacidad propia en
  cada sentido (NO hay capacidad compartida).
* Arcos con el mismo (origen, destino) se fusionan sumando capacidades.
  Si el XML incluye A->B y B->A como enlaces distintos, esta regla también
  suma ambas capacidades en cada sentido; se registra en los metadatos.
* Capacidad por enlace: preinstalada positiva; si no existe, un módulo mínimo
  positivo (configurable a módulo máximo). NO se suman todos los módulos.
* Costo fijo del `out` = 0; los costos SNDlib no equivalen a ese campo.
* Una demanda positiva genera un commodity con dos balances.
* Formato `out`: n m K, seguido de m filas `u v 0 capacidad 0`, y dos
  filas `producto nodo balance` por cada commodity.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import BinaryIO, Iterable
import gzip
import json
import os
import tempfile
import xml.etree.ElementTree as ET


class ErrorSNDlib(ValueError):
    """Archivo o configuración SNDlib inválida/no compatible."""


def _tag(nombre: str) -> str:
    """Ignora el namespace XML sin depender de una versión de SNDlib."""
    return nombre.rsplit('}', 1)[-1]


def _hijo(elemento: ET.Element, nombre: str) -> ET.Element | None:
    return next((x for x in elemento if _tag(x.tag) == nombre), None)


def _descendiente(elemento: ET.Element, *camino: str) -> ET.Element | None:
    for nombre in camino:
        elemento = _hijo(elemento, nombre)
        if elemento is None:
            return None
    return elemento


def _texto(elemento: ET.Element, *camino: str) -> str | None:
    item = _descendiente(elemento, *camino)
    if item is None or item.text is None:
        return None
    return item.text.strip()


def _decimal(texto: str | None, descripcion: str, defecto: str | None = None) -> Decimal:
    if texto is None or texto == '':
        if defecto is None:
            raise ErrorSNDlib(f'Falta {descripcion}')
        texto = defecto
    try:
        valor = Decimal(texto)
    except (InvalidOperation, ValueError) as exc:
        raise ErrorSNDlib(f'{descripcion}: valor numérico inválido {texto!r}') from exc
    if not valor.is_finite():
        raise ErrorSNDlib(f'{descripcion}: debe ser finito')
    return valor


def _parsear_xml(origen: str | Path | BinaryIO) -> ET.Element:
    try:
        if isinstance(origen, (str, Path)):
            ruta = Path(origen)
            if ruta.name.lower().endswith('.xml.gz'):
                with gzip.open(ruta, 'rb') as archivo:
                    return ET.parse(archivo).getroot()
            return ET.parse(ruta).getroot()
        return ET.parse(origen).getroot()
    except (ET.ParseError, OSError) as exc:
        raise ErrorSNDlib(f'No se puede leer el XML {origen}: {exc}') from exc


@dataclass(frozen=True)
class Enlace:
    id_xml: str
    origen: str
    destino: str
    capacidad: Decimal
    capacidad_preinstalada: Decimal
    modulos: tuple[Decimal, ...]
    costos_modulos: tuple[str, ...]


@dataclass(frozen=True)
class Demanda:
    id_xml: str
    origen: str
    destino: str
    valor: Decimal


@dataclass
class Red:
    nombre: str
    archivo: str
    nodos: list[str]
    enlaces: list[Enlace]
    demandas_base: list[Demanda]
    meta_xml: dict[str, str]


def _leer_demandas_desde_raiz(raiz: ET.Element) -> list[Demanda]:
    """Acepta <network><demands>..., <demands>..., y un XML con <demand>.

    No interpreta formatos de matrices temporales no documentados: si no hay
    sección reconocible, lanza un error en lugar de inventar demandas.
    """
    seccion = raiz if _tag(raiz.tag) == 'demands' else _hijo(raiz, 'demands')
    if seccion is None:
        raise ErrorSNDlib(
            'No se encontró <demands>. Esta matriz temporal no usa el formato '
            'XML de demandas de SNDlib que admite el lector.'
        )

    resultado: list[Demanda] = []
    for i, nodo in enumerate(seccion):
        if _tag(nodo.tag) != 'demand':
            continue
        origen = _texto(nodo, 'source')
        destino = _texto(nodo, 'target')
        if not origen or not destino:
            raise ErrorSNDlib(f'Demanda {i} sin source/target')
        valor = _decimal(_texto(nodo, 'demandValue'), f'demandValue de {nodo.get("id", i)}')
        if valor < 0:
            raise ErrorSNDlib(f'Demanda negativa en {nodo.get("id", i)}')
        # El XML original de estas instancias guarda el volumen en demandValue.
        resultado.append(Demanda(nodo.get('id', f'demand_{i}'), origen, destino, valor))
    return resultado


def leer_demandas_xml(archivo: str | Path | BinaryIO) -> list[Demanda]:
    """Lee la sección de demandas de un XML completo o demands-only."""
    return _leer_demandas_desde_raiz(_parsear_xml(archivo))


def leer_red_sndlib(ruta: str | Path, *, capacidad: str = 'preinstalada_o_minima') -> Red:
    """Lee topología XML original, con capacidades de cada enlace.

    Políticas: `preinstalada_o_minima` (predeterminada), `minima`, `maxima`.
    `minima`/`maxima` prefieren módulos adicionales; si no hay, toman la
    preinstalada. Son escenarios adaptados, no instalaciones históricas.
    """
    if capacidad not in {'preinstalada_o_minima', 'minima', 'maxima'}:
        raise ErrorSNDlib(f'Política de capacidad desconocida: {capacidad}')
    ruta = Path(ruta)
    raiz = _parsear_xml(ruta)
    estructura = _hijo(raiz, 'networkStructure')
    if estructura is None:
        raise ErrorSNDlib(f'{ruta.name} no contiene <networkStructure>')
    bloque_nodos = _hijo(estructura, 'nodes')
    bloque_enlaces = _hijo(estructura, 'links')
    if bloque_nodos is None or bloque_enlaces is None:
        raise ErrorSNDlib(f'{ruta.name} no tiene <nodes> o <links>')

    nodos = [n.attrib['id'] for n in bloque_nodos if _tag(n.tag) == 'node' and n.get('id')]
    if not nodos or len(nodos) != len(set(nodos)):
        raise ErrorSNDlib('Lista de nodos vacía o con identificadores repetidos')
    conjunto_nodos = set(nodos)
    enlaces: list[Enlace] = []
    for i, link in enumerate(bloque_enlaces):
        if _tag(link.tag) != 'link':
            continue
        a, b = _texto(link, 'source'), _texto(link, 'target')
        identidad = link.get('id', f'link_{i}')
        if a not in conjunto_nodos or b not in conjunto_nodos:
            raise ErrorSNDlib(f'Enlace {identidad}: nodos desconocidos {a}, {b}')
        if a == b:
            raise ErrorSNDlib(f'Enlace {identidad}: lazo {a}->{b} no admitido')

        pre = _decimal(_texto(link, 'preInstalledModule', 'capacity'),
                       f'preInstalledModule/capacity del enlace {identidad}', '0')
        modulos: list[Decimal] = []
        costos_modulos: list[str] = []
        adicionales = _hijo(link, 'additionalModules')
        if adicionales is not None:
            for modulo in adicionales:
                if _tag(modulo.tag) != 'addModule':
                    continue
                cap = _decimal(_texto(modulo, 'capacity'), f'capacidad de módulo en {identidad}')
                if cap > 0:
                    modulos.append(cap)
                    costos_modulos.append(_texto(modulo, 'cost') or '0')
        if pre < 0:
            raise ErrorSNDlib(f'Capacidad preinstalada negativa en {identidad}')
        if capacidad == 'preinstalada_o_minima':
            elegida = pre if pre > 0 else (min(modulos) if modulos else Decimal(0))
        elif capacidad == 'minima':
            elegida = min(modulos) if modulos else pre
        else:
            elegida = max(modulos) if modulos else pre
        if elegida <= 0:
            raise ErrorSNDlib(
                f'Enlace {identidad} sin capacidad positiva. '
                'No se asignarán capacidades inventadas automáticamente.'
            )
        enlaces.append(Enlace(identidad, a, b, elegida, pre,
                              tuple(modulos), tuple(costos_modulos)))
    if not enlaces:
        raise ErrorSNDlib(f'{ruta.name} no contiene enlaces')

    metadatos = _hijo(raiz, 'meta')
    meta_xml = {}
    if metadatos is not None:
        for nodo in metadatos:
            if nodo.text:
                meta_xml[_tag(nodo.tag)] = nodo.text.strip()

    return Red(ruta.stem, str(ruta), nodos, enlaces,
               _leer_demandas_desde_raiz(raiz), meta_xml)


def generar_out(
    red: Red,
    demandas: Iterable[Demanda] | None = None,
    *,
    destino: str | Path = 'out',
    factor_capacidad: Decimal | str = Decimal(1),
    escala_fija: int | None = None,
) -> dict:
    """Escribe `out` de forma atómica. Devuelve metadatos de la conversión.

    Si escala_fija=None, usa la potencia mínima de 10 que haga enteras todas
    las capacidades y demandas de ESTA instancia. Si interesa comparar en una
    escala numérica idéntica diferentes tiempos, usar --escala-fija.
    """
    factor_capacidad = _decimal(str(factor_capacidad), 'factor_capacidad')
    if factor_capacidad <= 0:
        raise ErrorSNDlib('factor_capacidad debe ser positivo')
    id_nodos = {nombre: indice for indice, nombre in enumerate(red.nodos, 1)}

    # Cada enlace genera dos arcos; al sumar el diccionario evitamos duplicados.
    arcos: dict[tuple[int, int], Decimal] = defaultdict(lambda: Decimal(0))
    repetidos = 0
    for link in red.enlaces:
        a, b = id_nodos[link.origen], id_nodos[link.destino]
        cap = link.capacidad * factor_capacidad
        for arco in ((a, b), (b, a)):
            if arco in arcos:
                repetidos += 1
            arcos[arco] += cap

    lista_demandas = list(red.demandas_base if demandas is None else demandas)
    productos: list[tuple[int, int, Decimal, str]] = []
    omitidas_cero = 0
    omitidas_mismo_nodo = 0
    for d in lista_demandas:
        if d.origen not in id_nodos or d.destino not in id_nodos:
            raise ErrorSNDlib(f'Demanda {d.id_xml} tiene un nodo que no existe en {red.nombre}')
        if d.valor < 0:
            raise ErrorSNDlib(f'Demanda negativa: {d.id_xml}')
        if d.valor == 0:
            omitidas_cero += 1
            continue
        if d.origen == d.destino:
            omitidas_mismo_nodo += 1
            continue
        productos.append((id_nodos[d.origen], id_nodos[d.destino], d.valor, d.id_xml))
    if not productos:
        raise ErrorSNDlib('No quedan demandas positivas entre nodos distintos')

    todos = list(arcos.values()) + [d[2] for d in productos]
    if escala_fija is None:
        precision = max(max(0, -x.normalize().as_tuple().exponent) for x in todos)
        escala = 10 ** precision
    else:
        escala = int(escala_fija)
        if escala < 1:
            raise ErrorSNDlib('escala_fija debe ser un entero >= 1')

    def como_entero(valor: Decimal) -> int:
        x = valor * escala
        if x != x.to_integral_value():
            raise ErrorSNDlib(
                f'{valor} no es entero al multiplicar por escala={escala}. '
                'Usa --escala-fija con un factor mayor o déjalo automático.'
            )
        entero = int(x)
        if entero <= 0:
            raise ErrorSNDlib('La conversión produjo capacidad/demanda no positiva')
        return entero

    # Prevalidar antes de sustituir el archivo activo.
    filas_arcos = [(a, b, como_entero(cap)) for (a, b), cap in sorted(arcos.items())]
    filas_productos = [(a, b, como_entero(val), nombre) for a, b, val, nombre in productos]
    ruta_out = Path(destino)
    ruta_out.parent.mkdir(parents=True, exist_ok=True)
    temporal = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=ruta_out.parent,
                                         prefix='.out_sndlib_', delete=False) as salida:
            temporal = Path(salida.name)
            salida.write(f'{len(red.nodos)} {len(filas_arcos)} {len(filas_productos)}\n')
            for a, b, cap in filas_arcos:
                salida.write(f'{a} {b} 0 {cap} 0\n')
            for k, (a, b, volumen, _) in enumerate(filas_productos, 1):
                salida.write(f'{k} {a} {volumen}\n')
                salida.write(f'{k} {b} {-volumen}\n')
        os.replace(temporal, ruta_out)
    finally:
        if temporal and temporal.exists():
            temporal.unlink()

    return {
        'red': red.nombre,
        'archivo_red': red.archivo,
        'nodos': len(red.nodos),
        'enlaces_xml': len(red.enlaces),
        'arcos_dirigidos': len(filas_arcos),
        'colisiones_arcos_fusionados': repetidos,
        'commodities': len(filas_productos),
        'demandas_originales': len(lista_demandas),
        'demandas_cero_omitidas': omitidas_cero,
        'demandas_mismo_nodo_omitidas': omitidas_mismo_nodo,
        'factor_capacidad': str(factor_capacidad),
        'escala_enteros': escala,
        'capacidad_minima_out': min(cap for _, _, cap in filas_arcos),
        'capacidad_maxima_out': max(cap for _, _, cap in filas_arcos),
        'nodos_originales': {str(i): nombre for i, nombre in enumerate(red.nodos, 1)},
        'metadatos_xml': red.meta_xml,
        'convencion_arcos': 'ambos_sentidos_independientes;paralelos_sumados',
        'costo_fijo_out': 0,
    }


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Convierte un XML SNDlib a out')
    parser.add_argument('xml', type=Path)
    parser.add_argument('--salida', default='out', type=Path)
    parser.add_argument('--capacidad', choices=('preinstalada_o_minima', 'minima', 'maxima'),
                        default='preinstalada_o_minima')
    parser.add_argument('--factor-capacidad', default='1')
    parser.add_argument('--escala-fija', type=int)
    args = parser.parse_args()
    red = leer_red_sndlib(args.xml, capacidad=args.capacidad)
    metadatos = generar_out(red, destino=args.salida, factor_capacidad=args.factor_capacidad,
                            escala_fija=args.escala_fija)
    print(json.dumps(metadatos, ensure_ascii=False, indent=2))
