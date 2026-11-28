"""Karakostas implicito con escalamiento inicial certificado y fuerte.

La implementacion base sigue siendo la Figura 2 de Karakostas. La diferencia
es la fase de escalamiento: antes de ejecutar el FPTAS se construye una
solucion factible enrutando, para cada origen, todas sus demandas sobre un
arbol de caminos minimos con longitudes 1/u(e).

Si B es la congestion de esa solucion, entonces z* <= B y, por la equivalencia
lambda* = 1/z*, se obtiene la cota certificada lambda* >= 1/B. Esa cota se usa
como ``lambda_lower_bound`` en vez del conservador zeta_hat/k.

El archivo es deliberadamente independiente del punto de entrada del solver
de referencia, para poder comparar ambas inicializaciones sin modificarlo.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import math
import os
import time
from typing import Any, Dict, Hashable, Iterable, List, Mapping, MutableMapping, Tuple

from solver_karakostas_implicito import (
    KarakostasImplicitResult,
    _agrupar_por_od,
    _carga_restante_en_arbol,
    _dijkstra_tree,
    _extraer_commodities,
    imprimir_resumen,
    resolver_karakostas_implicito,
)


@dataclass(frozen=True)
class CotaInicialRapida:
    """Solucion factible usada para certificar el escalamiento inicial."""

    congestion: float
    lambda_lower_bound: float
    edge_load: Dict[Hashable, float]
    dijkstra_runs: int
    elapsed_seconds: float


def construir_cota_inicial_rapida(
    arcos: List[Mapping[str, Any]],
    balances: Mapping[Tuple[Hashable, Hashable], float],
    productos: Iterable[Hashable],
    tol: float = 1e-12,
) -> CotaInicialRapida:
    """Construye B con un shortest-path tree por origen.

    Las longitudes 1/u(e) favorecen caminos con buena capacidad. Enrutar todas
    las demandas completas produce siempre una solucion factible para el
    modelo min-z: no se exige respetar las capacidades, porque B mide
    precisamente la maxima violacion relativa de ellas.
    """
    inicio = time.perf_counter()
    productos = list(productos)
    if not productos:
        raise ValueError("No hay productos/commodities.")

    commodities = _extraer_commodities(productos, balances, tol)
    demanda_por_origen = _agrupar_por_od(commodities)

    capacidad: Dict[Hashable, float] = {}
    arco_por_id: Dict[Hashable, Mapping[str, Any]] = {}
    adj: MutableMapping[
        Hashable, List[Tuple[Hashable, Hashable]]
    ] = defaultdict(list)
    log_longitud: Dict[Hashable, float] = {}

    for arco in arcos:
        aid = arco["id"]
        if aid in arco_por_id:
            raise ValueError(f"ID de arco duplicado: {aid!r}")
        cap = float(arco["capacidad"])
        if cap < 0.0:
            raise ValueError(f"Capacidad negativa en arco {aid!r}.")

        arco_por_id[aid] = arco
        capacidad[aid] = cap
        if cap > tol:
            adj[arco["origen"]].append((arco["destino"], aid))
            log_longitud[aid] = -math.log(cap)

    if not log_longitud:
        raise ValueError("No hay arcos con capacidad positiva.")

    edge_load = {aid: 0.0 for aid in capacidad}
    dijkstra_runs = 0

    for source, demandas_sink in demanda_por_origen.items():
        targets = tuple(demandas_sink)
        distancias, pred_arc, orden = _dijkstra_tree(
            source=source,
            targets=targets,
            adj=adj,
            log_longitud=log_longitud,
        )
        dijkstra_runs += 1

        inalcanzables = [sink for sink in targets if sink not in distancias]
        if inalcanzables:
            raise ValueError(
                f"No existe camino de capacidad positiva desde {source!r} "
                f"hasta {inalcanzables!r}."
            )

        carga_arbol = _carga_restante_en_arbol(
            source=source,
            demanda_por_sink=demandas_sink,
            multiplicador_demanda=1.0,
            pred_arc=pred_arc,
            orden_dijkstra=orden,
            arco_por_id=arco_por_id,
        )
        for aid, carga in carga_arbol.items():
            edge_load[aid] += carga

    congestion = max(
        (
            edge_load[aid] / cap
            for aid, cap in capacidad.items()
            if cap > tol
        ),
        default=0.0,
    )
    if not math.isfinite(congestion) or congestion <= 0.0:
        raise RuntimeError("No se pudo construir una cota inicial positiva.")

    return CotaInicialRapida(
        congestion=congestion,
        lambda_lower_bound=1.0 / congestion,
        edge_load=edge_load,
        dijkstra_runs=dijkstra_runs,
        elapsed_seconds=time.perf_counter() - inicio,
    )


def resolver_karakostas_implicito_rapido(
    arcos: List[Mapping[str, Any]],
    balances: Mapping[Tuple[Hashable, Hashable], float],
    productos: Iterable[Hashable],
    epsilon: float | None = None,
    error_relativo: float = 0.30,
    tol: float = 1e-12,
    max_steps: int = 10_000_000,
    verbose: bool = False,
    guardar_representacion: bool = False,
    imprimir_cada: int = 1000,
    comprobar_gap_cada: int = 25,
) -> KarakostasImplicitResult:
    """Ejecuta Karakostas implicito desde la cota certificada 1/B."""
    productos = list(productos)
    cota = construir_cota_inicial_rapida(
        arcos=arcos,
        balances=balances,
        productos=productos,
        tol=tol,
    )

    if verbose:
        print(
            "Inicializacion rapida certificada: "
            f"B={cota.congestion:.10g} | "
            f"lambda_lower_bound=1/B={cota.lambda_lower_bound:.10g} | "
            f"Dijkstra={cota.dijkstra_runs} | "
            f"tiempo={cota.elapsed_seconds:.3f}s"
        )

    resultado = resolver_karakostas_implicito(
        arcos=arcos,
        balances=balances,
        productos=productos,
        epsilon=epsilon,
        error_relativo=error_relativo,
        tol=tol,
        max_steps=max_steps,
        verbose=verbose,
        guardar_representacion=guardar_representacion,
        lambda_lower_bound=cota.lambda_lower_bound,
        imprimir_cada=imprimir_cada,
        comprobar_gap_cada=comprobar_gap_cada,
    )

    resultado.stats["cota_superior_inicial_B"] = cota.congestion
    resultado.stats["lambda_lower_bound_inicial"] = cota.lambda_lower_bound
    resultado.stats["dijkstra_inicializacion"] = cota.dijkstra_runs
    resultado.stats["tiempo_inicializacion"] = cota.elapsed_seconds
    resultado.stats["elapsed_core_seconds"] = resultado.stats["elapsed_seconds"]
    resultado.stats["elapsed_seconds"] += cota.elapsed_seconds
    return resultado


def main() -> None:
    from lector import arcos, balances, demandas, n  # noqa: F401

    # Usa exclusivamente los commodities que sobrevivieron al filtro de
    # conectividad aplicado en lector.py. `balances` puede seguir conteniendo
    # entradas de productos eliminados, pero Karakostas solo extrae commodities
    # para los IDs presentes en esta lista filtrada.
    productos = [int(demanda["producto"]) for demanda in demandas]

    error_solicitado = float(
        os.environ.get("KARAKOSTAS_ERROR_RELATIVO", "0.15")
    )
    epsilon_texto = os.environ.get("KARAKOSTAS_EPSILON_INTERNO")
    epsilon_interno = float(epsilon_texto) if epsilon_texto else None
    max_steps = int(os.environ.get("KARAKOSTAS_MAX_STEPS", "10000000"))
    imprimir_cada = int(os.environ.get("KARAKOSTAS_IMPRIMIR_CADA", "1000"))
    comprobar_gap_cada = int(
        os.environ.get("KARAKOSTAS_COMPROBAR_GAP_CADA", "25")
    )
    guardar = os.environ.get("KARAKOSTAS_GUARDAR_REPRESENTACION", "0") == "1"

    print("\nSolver: Karakostas implicito rapido con cota certificada 1/B")
    print(f"Error relativo solicitado: {100.0 * error_solicitado:.6f}%")

    resultado = resolver_karakostas_implicito_rapido(
        arcos=arcos,
        balances=balances,
        productos=productos,
        epsilon=epsilon_interno,
        error_relativo=error_solicitado,
        max_steps=max_steps,
        verbose=True,
        guardar_representacion=guardar,
        imprimir_cada=imprimir_cada,
        comprobar_gap_cada=comprobar_gap_cada,
    )

    imprimir_resumen(resultado, arcos)


if __name__ == "__main__":
    main()
