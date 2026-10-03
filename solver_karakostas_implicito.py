"""Karakostas FPTAS para Maximum Concurrent Flow — version IMPLICITA (Fig. 2).

Basado en:
George Karakostas, "Faster Approximation Schemes for Fractional
Multicommodity Flow Problems", ACM Transactions on Algorithms, 2008.

Esta version NO construye x_e(q), NO reconstruye un camino por commodity y
NO genera el flujo explicito commodity-arco. Solo mantiene la solucion dual y,
opcionalmente, los shortest-path trees usados por la representacion implicita.

Entrada esperada (lector.py):
    arcos: lista de dicts con id, origen, destino, capacidad
    balances[(producto, nodo)]: balance del producto en el nodo
    productos: iterable de ids de producto

Convencion de balances:
    salida - entrada = balance
por lo que el origen tiene +d y el destino -d.

El paper supone un unico origen y un unico destino por commodity. Si varios
productos tienen el mismo par (s,t), se agregan en un solo commodity OD, tal
como permite Karakostas.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import heapq
import math
import os
import time
from typing import Any, Dict, Hashable, Iterable, List, Mapping, MutableMapping, Tuple


@dataclass(frozen=True)
class Commodity:
    producto: Hashable
    origen: Hashable
    destino: Hashable
    demanda: float


@dataclass
class KarakostasImplicitResult:
    # Fraccion comun de demanda obtenida despues del scaling final.
    lambda_aprox: float

    # Congestion equivalente para tu formulacion min-z.
    # Si existe un flujo que satisface lambda*d bajo capacidades u,
    # entonces al escalarlo por 1/lambda satisface d con congestion 1/lambda.
    z_aprox: float

    # Congestion de la solucion implicita convertida a demandas completas.
    z_factible: float
    edge_load: Dict[Hashable, float]
    congestion: Dict[Hashable, float]
    routed_ratio_by_source: Dict[Hashable, float]

    # Metricas de ejecucion.
    stats: Dict[str, Any]

    # Representacion implicita opcional.
    # Cada registro corresponde a un shortest-path tree usado en un step.
    implicit_trees: List[Dict[str, Any]] | None = None


# ---------------------------------------------------------------------------
# Preprocesamiento
# ---------------------------------------------------------------------------


def _extraer_commodities(
    productos: Iterable[Hashable],
    balances: Mapping[Tuple[Hashable, Hashable], float],
    tol: float,
) -> Dict[Hashable, Commodity]:
    """Convierte balances a (s_i, t_i, d_i) y valida el supuesto del paper."""
    por_producto: MutableMapping[Hashable, List[Tuple[Hashable, float]]] = defaultdict(list)

    for (producto, nodo), balance in balances.items():
        b = float(balance)
        if abs(b) > tol:
            por_producto[producto].append((nodo, b))

    resultado: Dict[Hashable, Commodity] = {}

    for producto in productos:
        positivos = [(v, b) for v, b in por_producto.get(producto, []) if b > tol]
        negativos = [(v, -b) for v, b in por_producto.get(producto, []) if b < -tol]

        if len(positivos) != 1 or len(negativos) != 1:
            raise ValueError(
                f"Producto {producto!r}: Karakostas requiere exactamente un origen "
                f"y un destino por commodity. Positivos={positivos}; negativos={negativos}."
            )

        origen, d_out = positivos[0]
        destino, d_in = negativos[0]

        escala = max(1.0, abs(d_out), abs(d_in))
        if abs(d_out - d_in) > 1e-9 * escala:
            raise ValueError(
                f"Producto {producto!r}: el balance no cierra. "
                f"Sale {d_out} y entra {d_in}."
            )

        if d_out <= tol:
            raise ValueError(f"Producto {producto!r}: demanda no positiva.")

        if origen == destino:
            raise ValueError(f"Producto {producto!r}: origen y destino son iguales.")

        resultado[producto] = Commodity(
            producto=producto,
            origen=origen,
            destino=destino,
            demanda=float(d_out),
        )

    return resultado


def _agrupar_por_od(
    commodities: Mapping[Hashable, Commodity],
) -> Dict[Hashable, Dict[Hashable, float]]:
    """Agrupa commodities con el mismo (source, sink), como permite el paper."""
    por_origen: MutableMapping[Hashable, MutableMapping[Hashable, float]] = defaultdict(
        lambda: defaultdict(float)
    )

    for c in commodities.values():
        por_origen[c.origen][c.destino] += c.demanda

    return {
        s: dict(demandas_por_sink)
        for s, demandas_por_sink in por_origen.items()
    }


def epsilon_interno_para_error(error_relativo: float) -> float:
    """Escoge epsilon para que (1-epsilon)^(-3) = 1+error_relativo."""
    if not (0.0 < error_relativo < 1.0):
        raise ValueError("error_relativo debe estar estrictamente entre 0 y 1.")
    return 1.0 - (1.0 + float(error_relativo)) ** (-1.0 / 3.0)


def _logaddexp(a: float, b: float) -> float:
    if a == -math.inf:
        return b
    if b == -math.inf:
        return a
    mayor = max(a, b)
    menor = min(a, b)
    return mayor + math.log1p(math.exp(menor - mayor))


def _logsumexp(valores: Iterable[float]) -> float:
    total = -math.inf
    for valor in valores:
        total = _logaddexp(total, valor)
    return total


# ---------------------------------------------------------------------------
# Widest path para el scaling inicial de la seccion 3.2
# ---------------------------------------------------------------------------


def _widest_paths(
    source: Hashable,
    adj: Mapping[Hashable, List[Tuple[Hashable, Hashable]]],
    capacidad: Mapping[Hashable, float],
) -> Dict[Hashable, float]:
    """Maximum-bottleneck path desde source a todos los nodos."""
    width: Dict[Hashable, float] = {source: math.inf}
    heap: List[Tuple[float, Hashable]] = [(-math.inf, source)]

    while heap:
        neg_w, u = heapq.heappop(heap)
        w = -neg_w

        if w < width.get(u, -1.0):
            continue

        for v, arco in adj.get(u, []):
            candidato = min(w, capacidad[arco])
            if candidato > width.get(v, -1.0):
                width[v] = candidato
                heapq.heappush(heap, (-candidato, v))

    return width


# ---------------------------------------------------------------------------
# Dijkstra: un shortest-path tree por source y step
# ---------------------------------------------------------------------------


def _dijkstra_tree(
    source: Hashable,
    targets: Iterable[Hashable],
    adj: Mapping[Hashable, List[Tuple[Hashable, Hashable]]],
    log_longitud: Mapping[Hashable, float],
) -> Tuple[
    Dict[Hashable, float],
    Dict[Hashable, Hashable],
    List[Hashable],
]:
    """Dijkstra desde source hasta haber fijado todos los sinks requeridos.

    Retorna:
        dist[v]      distancia final
        pred_arc[v] arco padre de v en el shortest-path tree
        orden        nodos fijados por Dijkstra, en orden creciente de distancia

    `orden` se usa al reves para acumular demanda desde las hojas hacia la raiz,
    evitando reconstruir un camino por commodity.
    """
    targets = set(targets)
    targets.discard(source)

    log_dist: Dict[Hashable, float] = {source: -math.inf}
    pred_arc: Dict[Hashable, Hashable] = {}
    orden: List[Hashable] = []
    heap: List[Tuple[float, Hashable]] = [(-math.inf, source)]
    pendientes = set(targets)
    fijado = set()

    while heap and pendientes:
        du, u = heapq.heappop(heap)

        if u in fijado:
            continue
        if du != log_dist.get(u, math.inf):
            continue

        fijado.add(u)
        orden.append(u)
        pendientes.discard(u)

        for v, arco in adj.get(u, []):
            nd = _logaddexp(du, log_longitud[arco])
            if nd < log_dist.get(v, math.inf):
                log_dist[v] = nd
                pred_arc[v] = arco
                heapq.heappush(heap, (nd, v))

    if pendientes:
        faltantes = list(pendientes)[:10]
        raise RuntimeError(
            f"Dijkstra desde {source!r} no alcanzo {len(pendientes)} sinks. "
            f"Ejemplos: {faltantes}"
        )

    return log_dist, pred_arc, orden


def _calcular_cota_inferior(
    demanda_por_origen,
    adj,
    capacidad,
    log_longitud,
):
    """Construye una cota dual valida para la congestion optima."""
    log_normalizador = _logsumexp(
        math.log(capacidad[arco]) + log_longitud[arco]
        for arco in log_longitud
    )
    terminos = []
    ejecuciones_dijkstra = 0

    for source, demandas_sink in demanda_por_origen.items():
        distancias, _, _ = _dijkstra_tree(
            source=source,
            targets=demandas_sink,
            adj=adj,
            log_longitud=log_longitud,
        )
        ejecuciones_dijkstra += 1
        for sink, demanda in demandas_sink.items():
            terminos.append(math.log(demanda) + distancias[sink])

    diferencia = _logsumexp(terminos) - log_normalizador
    if diferencia > math.log(float.fromhex("0x1.fffffffffffffp+1023")):
        return math.inf, ejecuciones_dijkstra
    return math.exp(diferencia), ejecuciones_dijkstra


def _construir_solucion_factible(
    edge_flow_by_source,
    routed_ratio_by_source,
    capacidad,
    tol,
):
    """Normaliza el flujo acumulado para satisfacer todas las demandas."""
    if any(ratio <= tol for ratio in routed_ratio_by_source.values()):
        return math.inf, None, None

    edge_load = {arco: 0.0 for arco in capacidad}
    for source, flujo_arcos in edge_flow_by_source.items():
        ratio = routed_ratio_by_source[source]
        for arco, flujo in flujo_arcos.items():
            edge_load[arco] += flujo / ratio

    congestion = {
        arco: (
            edge_load[arco] / cap
            if cap > tol
            else (0.0 if edge_load[arco] <= tol else math.inf)
        )
        for arco, cap in capacidad.items()
    }
    return max(congestion.values(), default=0.0), edge_load, congestion


# ---------------------------------------------------------------------------
# Acumulacion bottom-up en el shortest-path tree
# ---------------------------------------------------------------------------


def _carga_restante_en_arbol(
    source: Hashable,
    demanda_por_sink: Mapping[Hashable, float],
    multiplicador_demanda: float,
    pred_arc: Mapping[Hashable, Hashable],
    orden_dijkstra: List[Hashable],
    arco_por_id: Mapping[Hashable, Mapping[str, Any]],
) -> Dict[Hashable, float]:
    """Calcula sum_{q:e in P_q} d'_q para cada arco del tree en O(n).

    Esta es la operacion clave de la version implicita: no se reconstruye el
    camino de cada commodity. Se pone la demanda de cada sink en su nodo y se
    acumula desde las hojas hacia la raiz del shortest-path tree.
    """
    carga_nodo: MutableMapping[Hashable, float] = defaultdict(float)

    for sink, demanda_original in demanda_por_sink.items():
        carga_nodo[sink] += demanda_original * multiplicador_demanda

    carga_arco: Dict[Hashable, float] = {}

    for v in reversed(orden_dijkstra):
        if v == source:
            continue

        carga = carga_nodo.get(v, 0.0)
        if carga <= 0.0:
            continue

        arco = pred_arc.get(v)
        if arco is None:
            raise RuntimeError(
                f"Nodo {v!r} tiene demanda acumulada pero no tiene predecesor "
                f"en el shortest-path tree desde {source!r}."
            )

        carga_arco[arco] = carga
        padre = arco_por_id[arco]["origen"]
        carga_nodo[padre] += carga

    return carga_arco


# ---------------------------------------------------------------------------
# Solver principal: Figura 2
# ---------------------------------------------------------------------------


def resolver_karakostas_implicito(
    arcos: List[Mapping[str, Any]],
    balances: Mapping[Tuple[Hashable, Hashable], float],
    productos: Iterable[Hashable],
    epsilon: float | None = None,
    error_relativo: float = 0.30,
    tol: float = 1e-12,
    max_steps: int = 10_000_000,
    verbose: bool = False,
    guardar_representacion: bool = False,
    lambda_lower_bound: float | None = None,
    imprimir_cada: int = 1000,
    comprobar_gap_cada: int = 25,
) -> KarakostasImplicitResult:
    """Maximum Concurrent Flow con Karakostas, representacion IMPLICITA.

    Esta funcion implementa la logica de la Figura 2:

        f_q = d'_q / sigma

        sigma = max(
            1,
            max_e [ sum_{q:e in P_q} d'_q / u(e) ]
        )

        l(e) <- l(e) * (1 + epsilon * F(e)/u(e))

    donde todos los commodities con el mismo source usan un unico
    shortest-path tree.

    No se construye x_e(q). Para calcular lambda basta llevar, por source, la
    fraccion acumulada de demanda original que se ha ruteado.

    ``epsilon`` es el parametro interno del paper. Si se omite, se calcula a
    partir de ``error_relativo`` para garantizar el factor 1+error_relativo.

    `lambda_lower_bound` es una extension opcional. Si se entrega una cota inferior
    CERTIFICADA para lambda*, se usa como scaling inicial y se evita el widest
    path de la seccion 3.2. Para tu formulacion min-z, una solucion factible con
    congestion z da la cota lambda_lower_bound = 1/z.
    """
    if epsilon is None:
        epsilon = epsilon_interno_para_error(error_relativo)
    if not (0.0 < epsilon < 1.0):
        raise ValueError("epsilon debe estar estrictamente entre 0 y 1.")
    if imprimir_cada < 1:
        raise ValueError("imprimir_cada debe ser al menos 1.")
    if comprobar_gap_cada < 0:
        raise ValueError("comprobar_gap_cada no puede ser negativo.")

    productos = list(productos)
    if not productos:
        raise ValueError("No hay productos/commodities.")

    commodities = _extraer_commodities(productos, balances, tol)
    demanda_por_origen = _agrupar_por_od(commodities)

    k_original = len(productos)
    k_od = sum(len(d) for d in demanda_por_origen.values())

    # ----- Grafo -----
    capacidad: Dict[Hashable, float] = {}
    arco_por_id: Dict[Hashable, Mapping[str, Any]] = {}
    adj: MutableMapping[Hashable, List[Tuple[Hashable, Hashable]]] = defaultdict(list)
    ids_positivos: List[Hashable] = []
    nodos = set()

    for arco in arcos:
        aid = arco["id"]
        if aid in arco_por_id:
            raise ValueError(f"ID de arco duplicado: {aid!r}")

        cap = float(arco["capacidad"])
        if cap < 0.0:
            raise ValueError(f"Capacidad negativa en arco {aid!r}.")

        arco_por_id[aid] = arco
        capacidad[aid] = cap
        nodos.add(arco["origen"])
        nodos.add(arco["destino"])

        if cap > tol:
            ids_positivos.append(aid)
            adj[arco["origen"]].append((arco["destino"], aid))

    m = len(ids_positivos)
    if m == 0:
        raise ValueError("No hay arcos con capacidad positiva.")

    # ----- Scaling inicial de la seccion 3.2 -----
    widest_runs = 0

    if lambda_lower_bound is not None:
        demand_scale = float(lambda_lower_bound)
        if not (demand_scale > 0.0 and math.isfinite(demand_scale)):
            raise ValueError("lambda_lower_bound debe ser positivo y finito.")
        initial_scaling_method = "certified_lambda_lower_bound"

    else:
        zeta_hat = math.inf

        for source, demandas in demanda_por_origen.items():
            widths = _widest_paths(source, adj, capacidad)
            widest_runs += 1

            for sink, demanda in demandas.items():
                bottleneck = widths.get(sink, 0.0)
                if bottleneck <= tol:
                    raise ValueError(
                        f"No existe camino de capacidad positiva desde "
                        f"{source!r} hasta {sink!r}."
                    )

                zeta_hat = min(zeta_hat, bottleneck / demanda)

        # Ruta factible trivial: cada commodity OD recibe 1/k_od de su
        # bottleneck-path. Esto da una cota inferior valida para lambda*.
        demand_scale = zeta_hat / k_od
        initial_scaling_method = "widest_path_paper_scaling"

    initial_demand_scale = demand_scale

    if demand_scale <= 0.0 or not math.isfinite(demand_scale):
        raise RuntimeError("No se pudo construir el scaling inicial.")

    # ----- Parametros del FPTAS -----
    eps = float(epsilon)

    # Ecuacion (3) del paper.
    log_delta = (
        (1.0 / eps) * math.log((1.0 - eps) / m)
        - ((1.0 - eps) / eps) * math.log(1.0 + eps)
    )

    # log_{1+eps}((1+eps)/delta)
    log_uno_mas_eps = math.log1p(eps)
    scale_down = (log_uno_mas_eps - log_delta) / log_uno_mas_eps

    log_capacidad = {a: math.log(capacidad[a]) for a in ids_positivos}
    log_longitud: Dict[Hashable, float] = {
        a: log_delta - log_capacidad[a]
        for a in ids_positivos
    }

    # D(l) = sum_e u(e) l(e); inicialmente D = m*delta.
    log_D = math.log(m) + log_delta

    # Seccion 3.2.
    A_para_T = (
        (1.0 / eps)
        * math.log(((1.0 + eps) * m) / (1.0 - eps))
        / log_uno_mas_eps
    )
    T = 2 * math.ceil(A_para_T)

    # Como todos los commodities con un source reciben la misma fraccion en
    # cada step de la Figura 2, basta guardar la fraccion total ruteada por
    # source. No necesitamos un contador por commodity ni x_e(q).
    routed_ratio_by_source: Dict[Hashable, float] = {
        source: 0.0 for source in demanda_por_origen
    }
    # Flujo agregado por source y arco. Esto no materializa x_e(q): permite
    # calcular la congestion y convertir la solucion a demandas completas sin
    # perder la representacion implicita del paper.
    edge_flow_by_source: Dict[Hashable, MutableMapping[Hashable, float]] = {
        source: defaultdict(float) for source in demanda_por_origen
    }

    implicit_trees: List[Dict[str, Any]] | None
    implicit_trees = [] if guardar_representacion else None

    phases = 0
    phases_since_double = 0
    steps = 0
    dijkstra_runs = 0
    dijkstra_gap_runs = 0
    doublings = 0
    controles_gap = 0
    cota_inferior = 0.0
    gap_certificado = math.inf
    termino_anticipado = False
    motivo_termino = "potencial D(l) alcanzo 1"
    start_time = time.perf_counter()

    # ------------------------------------------------------------------
    # Figura 2
    # ------------------------------------------------------------------
    while log_D < 0.0:
        phases += 1
        phases_since_double += 1

        # Una iteracion por source.
        for source, demandas_sink in demanda_por_origen.items():
            if log_D >= 0.0:
                break

            targets = tuple(demandas_sink.keys())

            # d'_q = demand_scale * d_q al comienzo de la iteracion.
            # Como cada step envia d'_q/sigma para TODOS los q activos, todos
            # conservan el mismo multiplicador relativo `remaining_fraction`.
            remaining_fraction = 1.0

            while log_D < 0.0 and remaining_fraction > tol:
                steps += 1
                if steps > max_steps:
                    raise RuntimeError(
                        f"Se supero max_steps={max_steps}. "
                        "Prueba un epsilon mayor o revisa el scaling."
                    )

                _, pred_arc, orden = _dijkstra_tree(
                    source=source,
                    targets=targets,
                    adj=adj,
                    log_longitud=log_longitud,
                )
                dijkstra_runs += 1

                # Cantidad de demanda aun no ruteada en este step:
                # d'_q = d_q * demand_scale * remaining_fraction.
                multiplicador_restante = demand_scale * remaining_fraction

                # S_e = sum_{q:e in P_q} d'_q, calculado bottom-up en el tree.
                carga_restante = _carga_restante_en_arbol(
                    source=source,
                    demanda_por_sink=demandas_sink,
                    multiplicador_demanda=multiplicador_restante,
                    pred_arc=pred_arc,
                    orden_dijkstra=orden,
                    arco_por_id=arco_por_id,
                )

                if not carga_restante:
                    raise RuntimeError(
                        f"Shortest-path tree desde {source!r} no lleva demanda."
                    )

                # Figura 2:
                # sigma = max{1, max_e S_e/u(e)}.
                sigma = 1.0
                for a, carga in carga_restante.items():
                    ratio = carga / capacidad[a]
                    if ratio > sigma:
                        sigma = ratio

                if not math.isfinite(sigma) or sigma <= 0.0:
                    raise RuntimeError(f"sigma invalido: {sigma}")

                fraccion_step = 1.0 / sigma

                # Cada commodity del source envia la misma fraccion de lo que
                # le queda. La fraccion de DEMANDA ORIGINAL enviada en este
                # step es demand_scale * remaining_fraction / sigma.
                incremento_ratio = demand_scale * remaining_fraction * fraccion_step
                routed_ratio_by_source[source] += incremento_ratio

                if guardar_representacion:
                    implicit_trees.append(
                        {
                            "source": source,
                            # El factor /scale_down se aplica al terminar, tal
                            # como en la ultima linea de la Figura 2.
                            "raw_fraction_of_original_demand": incremento_ratio,
                            "pred_arc": dict(pred_arc),
                        }
                    )

                # F(e) = S_e / sigma.
                # Actualizacion multiplicativa de l(e) y D(l).
                terminos_incremento_D: List[float] = []

                for a, carga in carga_restante.items():
                    flujo_step = carga * fraccion_step
                    edge_flow_by_source[source][a] += flujo_step
                    terminos_incremento_D.append(
                        log_longitud[a] + math.log(flujo_step)
                    )
                    log_longitud[a] += math.log1p(
                        eps * flujo_step / capacidad[a]
                    )

                log_incremento_D = (
                    math.log(eps) + _logsumexp(terminos_incremento_D)
                )
                log_D = _logaddexp(log_D, log_incremento_D)

                # d'_q <- d'_q - f_q para todos los q.
                if sigma <= 1.0 + 1e-14:
                    remaining_fraction = 0.0
                else:
                    remaining_fraction *= 1.0 - fraccion_step

                if remaining_fraction < tol:
                    remaining_fraction = 0.0

        if verbose and (
            phases <= 3 or phases % imprimir_cada == 0 or log_D >= 0.0
        ):
            print(
                f"Fase {phases}: log10(D)={log_D / math.log(10.0):.6f} | "
                f"steps={steps} | Dijkstra={dijkstra_runs} | "
                f"tiempo={time.perf_counter() - start_time:.2f}s"
            )

        # Certificado a posteriori: el flujo acumulado, normalizado por source,
        # es primal factible. Las longitudes normalizadas producen una solucion
        # dual factible y, por tanto, una cota inferior para z*.
        if (
            log_D < 0.0
            and comprobar_gap_cada
            and phases % comprobar_gap_cada == 0
        ):
            controles_gap += 1
            z_candidato, _, _ = _construir_solucion_factible(
                edge_flow_by_source,
                routed_ratio_by_source,
                capacidad,
                tol,
            )
            cota_inferior, nuevas_dijkstras = _calcular_cota_inferior(
                demanda_por_origen,
                adj,
                capacidad,
                log_longitud,
            )
            dijkstra_gap_runs += nuevas_dijkstras
            dijkstra_runs += nuevas_dijkstras
            gap_certificado = (
                100.0 * (z_candidato - cota_inferior) / cota_inferior
                if cota_inferior > 0.0
                else math.inf
            )
            factor_teorico = (1.0 - eps) ** -3
            tolerancia_gap = 1e-10 * max(1.0, z_candidato)
            cumple_gap = (
                z_candidato
                <= factor_teorico * cota_inferior + tolerancia_gap
            )
            if verbose and (
                phases % imprimir_cada == 0 or cumple_gap
            ):
                print(
                    f"  CONTROL GAP fase {phases}: "
                    f"primal={z_candidato:.10g} | "
                    f"dual={cota_inferior:.10g} | "
                    f"gap={gap_certificado:.4f}%"
                )

            if cumple_gap:
                termino_anticipado = True
                motivo_termino = (
                    "gap primal-dual alcanzo el factor solicitado"
                )
                break

        # Si no termino tras T fases, se duplican todas las demandas.
        if log_D < 0.0 and phases_since_double >= T:
            demand_scale *= 2.0
            doublings += 1
            phases_since_double = 0

            if verbose:
                print(
                    f"[scaling] T={T} fases sin terminar -> "
                    f"demand_scale={demand_scale:.6g}"
                )

            max_doublings = math.ceil(math.log2(max(1, k_od * m))) + 5
            if doublings > max_doublings:
                raise RuntimeError(
                    "Demasiadas duplicaciones de demanda. Revisa datos/tolerancias."
                )

    # Scaling final de la Figura 2. Todos los commodities de un mismo source
    # reciben exactamente el mismo multiplicador de su demanda original.
    routed_ratio_mcf = {
        source: ratio / scale_down
        for source, ratio in routed_ratio_by_source.items()
    }
    lambda_aprox = min(routed_ratio_mcf.values())
    z_aprox = math.inf if lambda_aprox <= 0.0 else 1.0 / lambda_aprox

    # Conversion a la formulacion min-z. Para cada source multiplicamos su
    # flujo por el inverso de la fraccion de demanda que alcanzo. Esto preserva
    # implicitamente todos los balances OD sin construir x_e(q).
    z_factible, edge_load, congestion = _construir_solucion_factible(
        edge_flow_by_source,
        routed_ratio_by_source,
        capacidad,
        tol,
    )
    if edge_load is None or congestion is None:
        raise RuntimeError("No todos los sources recibieron flujo positivo.")

    # Si el algoritmo termino por potencial o el control estaba desactivado,
    # calcula igualmente un certificado final para dejar el resultado auditable.
    if not termino_anticipado:
        cota_inferior, nuevas_dijkstras = _calcular_cota_inferior(
            demanda_por_origen,
            adj,
            capacidad,
            log_longitud,
        )
        dijkstra_gap_runs += nuevas_dijkstras
        dijkstra_runs += nuevas_dijkstras
        gap_certificado = (
            100.0 * (z_factible - cota_inferior) / cota_inferior
            if cota_inferior > 0.0
            else math.inf
        )

    if implicit_trees is not None:
        for registro in implicit_trees:
            source = registro["source"]
            raw_fraction = registro.pop("raw_fraction_of_original_demand")
            fraction_mcf = raw_fraction / scale_down
            fraction_full = raw_fraction / routed_ratio_by_source[source]
            registro["flow_by_sink_mcf"] = {
                sink: demanda * fraction_mcf
                for sink, demanda in demanda_por_origen[source].items()
            }
            registro["flow_by_sink_full"] = {
                sink: demanda * fraction_full
                for sink, demanda in demanda_por_origen[source].items()
            }

    elapsed = time.perf_counter() - start_time

    stats = {
        "n_nodes": len(nodos),
        "m_positive_capacity": m,
        "k_original": k_original,
        "k_od": k_od,
        "n_sources": len(demanda_por_origen),
        "epsilon": eps,
        "factor_aproximacion_teorico": (1.0 - eps) ** -3,
        "error_relativo_teorico": (1.0 - eps) ** -3 - 1.0,
        "delta": math.exp(log_delta) if log_delta > -745.0 else 0.0,
        "log_delta": log_delta,
        "log10_delta": log_delta / math.log(10.0),
        "scale_down": scale_down,
        "T": T,
        "initial_scaling_method": initial_scaling_method,
        "initial_demand_scale": initial_demand_scale,
        "final_demand_scale": demand_scale,
        "demand_doublings": doublings,
        "phases": phases,
        "steps": steps,
        "dijkstra_runs": dijkstra_runs,
        "dijkstra_gap_runs": dijkstra_gap_runs,
        "widest_path_runs": widest_runs,
        "D_final": math.exp(log_D),
        "log_D_final": log_D,
        "elapsed_seconds": elapsed,
        "implicit_trees_stored": 0 if implicit_trees is None else len(implicit_trees),
        "comprobar_gap_cada": comprobar_gap_cada,
        "controles_gap": controles_gap,
        "cota_inferior": cota_inferior,
        "gap_certificado_porcentual": max(0.0, gap_certificado),
        "termino_anticipado": termino_anticipado,
        "motivo_termino": motivo_termino,
    }

    return KarakostasImplicitResult(
        lambda_aprox=lambda_aprox,
        z_aprox=z_aprox,
        z_factible=z_factible,
        edge_load=edge_load,
        congestion=congestion,
        routed_ratio_by_source=routed_ratio_mcf,
        stats=stats,
        implicit_trees=implicit_trees,
    )


def materializar_flujo_implicito(
    resultado: KarakostasImplicitResult,
    arcos: List[Mapping[str, Any]],
    balances: Mapping[Tuple[Hashable, Hashable], float],
    productos: Iterable[Hashable],
    tol: float = 1e-12,
) -> Dict[Hashable, Dict[Hashable, float]]:
    """Expande los arboles a ``x[producto][arco]`` cuando se necesita auditar.

    Esta operacion paga justamente el costo que la representacion implicita
    evita durante el algoritmo. Requiere haber ejecutado con
    ``guardar_representacion=True``.
    """
    if resultado.implicit_trees is None:
        raise ValueError(
            "No se guardaron arboles. Ejecuta con guardar_representacion=True."
        )

    productos = list(productos)
    commodities = _extraer_commodities(productos, balances, tol)
    arco_por_id = {arco["id"]: arco for arco in arcos}
    por_od: MutableMapping[
        Tuple[Hashable, Hashable], List[Hashable]
    ] = defaultdict(list)
    demanda_od: MutableMapping[Tuple[Hashable, Hashable], float] = defaultdict(float)
    for producto, commodity in commodities.items():
        od = (commodity.origen, commodity.destino)
        por_od[od].append(producto)
        demanda_od[od] += commodity.demanda

    flow: Dict[Hashable, MutableMapping[Hashable, float]] = {
        producto: defaultdict(float) for producto in productos
    }

    for registro in resultado.implicit_trees:
        source = registro["source"]
        pred_arc = registro["pred_arc"]
        for sink, flujo_od in registro["flow_by_sink_full"].items():
            camino: List[Hashable] = []
            actual = sink
            while actual != source:
                aid = pred_arc.get(actual)
                if aid is None:
                    raise RuntimeError(
                        f"Representacion invalida: {actual!r} no tiene padre "
                        f"en el arbol con raiz {source!r}."
                    )
                camino.append(aid)
                actual = arco_por_id[aid]["origen"]

            od = (source, sink)
            total_demanda_od = demanda_od[od]
            for producto in por_od[od]:
                proporcion = commodities[producto].demanda / total_demanda_od
                valor = flujo_od * proporcion
                for aid in camino:
                    flow[producto][aid] += valor

    return {producto: dict(valores) for producto, valores in flow.items()}


# Alias para que puedas usar el mismo nombre que en otros solvers.
resolver_karakostas = resolver_karakostas_implicito


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------


def imprimir_resumen(
    resultado: KarakostasImplicitResult,
    arcos: List[Mapping[str, Any]],
    top: int = 10,
) -> None:
    s = resultado.stats

    print("\n=== Karakostas: Maximum Concurrent Flow (IMPLICITO, Fig. 2) ===")
    print(f"lambda aproximado:      {resultado.lambda_aprox:.6f}")
    print(f"cota z=1/lambda:        {resultado.z_aprox:.6f}")
    print(f"z factible construido:  {resultado.z_factible:.6f}")
    print(f"Epsilon interno: {s['epsilon']:.12g}")
    print(
        "Error relativo teorico: "
        f"{100.0 * s['error_relativo_teorico']:.6f}%"
    )
    print(f"log10(delta): {s['log10_delta']:.6f}")
    print(f"T de la Seccion 3.2: {s['T']}")
    print(f"Motivo de termino: {s['motivo_termino']}")
    print(f"Cota inferior dual: {s['cota_inferior']:.10g}")
    print(
        "Gap certificado: "
        f"{s['gap_certificado_porcentual']:.6f}%"
    )

    print(
        "\nInstancia: "
        f"n={s['n_nodes']} | "
        f"m={s['m_positive_capacity']} | "
        f"k={s['k_original']} -> k_OD={s['k_od']} | "
        f"sources={s['n_sources']}"
    )

    print(
        "Scaling inicial: "
        f"{s['initial_scaling_method']} | "
        f"demand_scale={s['initial_demand_scale']:.6g}"
    )

    print(
        "Ejecucion: "
        f"{s['elapsed_seconds']:.3f}s | "
        f"fases={s['phases']} | "
        f"steps={s['steps']} | "
        f"Dijkstra={s['dijkstra_runs']} | "
        f"doublings={s['demand_doublings']}"
    )

    print(
        "Representacion: "
        f"trees guardados={s['implicit_trees_stored']} "
        "(0 = modo value-only, sin x_e(q))"
    )

    filas = [
        (
            resultado.congestion[arco["id"]],
            arco,
            resultado.edge_load[arco["id"]],
        )
        for arco in arcos
    ]
    filas.sort(key=lambda fila: fila[0], reverse=True)
    print(f"\n{top} arcos mas congestionados:")
    for cong, arco, flujo in filas[:top]:
        print(
            f"Arco {arco['id']}: {arco['origen']} -> {arco['destino']} | "
            f"flujo={flujo:.2f} | capacidad={arco['capacidad']} | "
            f"congestion={cong:.4f}"
        )

    print(
        f"\nCongestión máxima aproximada: {resultado.z_factible:.8f} "
        f"({100.0 * resultado.z_factible:.2f}%)"
    )
    print(f"Fases realizadas: {s['phases']}")
    print(f"Aumentos de camino: {s['steps']}")
    print(f"Tiempo total: {s['elapsed_seconds']:.6f} segundos")


def main() -> None:
    from lector import arcos, balances, n, productos  # noqa: F401

    error_solicitado = float(
        os.environ.get("KARAKOSTAS_ERROR_RELATIVO", "0.30")
    )
    epsilon_texto = os.environ.get("KARAKOSTAS_EPSILON_INTERNO")
    epsilon_interno = float(epsilon_texto) if epsilon_texto else None
    max_steps = int(os.environ.get("KARAKOSTAS_MAX_STEPS", "10000000"))
    imprimir_cada = int(os.environ.get("KARAKOSTAS_IMPRIMIR_CADA", "1000"))
    comprobar_gap_cada = int(
        os.environ.get("KARAKOSTAS_COMPROBAR_GAP_CADA", "25")
    )
    guardar = os.environ.get("KARAKOSTAS_GUARDAR_REPRESENTACION", "0") == "1"

    print("\nSolver: Karakostas, version implicita de la Figura 2")
    print(f"Error relativo solicitado: {100.0 * error_solicitado:.6f}%")
    if epsilon_interno is not None:
        print(
            "KARAKOSTAS_EPSILON_INTERNO reemplaza el error solicitado: "
            f"epsilon={epsilon_interno:.12g}"
        )

    resultado = resolver_karakostas_implicito(
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
