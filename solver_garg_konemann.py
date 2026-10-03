"""Garg--Koenemann para congestion minima en flujo multiproducto.

Implementa la variante de caminos minimos de la seccion 7.1 de
Garg y Koenemann para productos con un unico origen, un unico destino
y demanda divisible.  No utiliza Gurobi.

El problema resuelto es

    min z
    s.a. cada producto k envia d_k desde s_k hasta t_k,
         sum_k x[k,e] <= z * c[e] para cada arco e,
         x >= 0.

Configuracion mediante variables de entorno:

    GK_ERROR_RELATIVO   Error teorico solicitado. 0.15 por defecto.
                        Para solicitar 1%, usar 0.01.
    GK_LIMITE_TIEMPO    Segundos maximos. 900 por defecto.
    GK_MAX_FASES        Limite adicional de fases. 10000000 por defecto.
    GK_IMPRIMIR_CADA    Frecuencia del progreso. 10 por defecto.
    GK_COMPROBAR_GAP_CADA Frecuencia del certificado primal-dual. 25 por
                        defecto; 0 lo desactiva.
    GK_GUARDAR_DETALLE  1 para conservar x[k,e] en memoria. 0 por defecto.
    GK_COTA_INICIAL     Cota B externa opcional para hacer warm start.
    GK_COTA_CERTIFICADA Debe valer 1 si la cota externa proviene de una
                        solucion factible. Sin esta marca no se anuncia la
                        garantia teorica relativa.

La implementacion evita calcular delta directamente. Para errores pequenos,
delta queda fuera del rango de ``float``. Las longitudes se almacenan en
logaritmos y Dijkstra suma longitudes mediante log-sum-exp.
"""

from __future__ import annotations

import heapq
import math
import os
import time
from dataclasses import dataclass
from typing import Iterable


INFINITO_NEGATIVO = -math.inf


@dataclass
class ResultadoGK:
    flujo_por_arco: dict[int, float]
    flujo_por_producto: dict[tuple[int, int], float] | None
    congestion: float
    cota_inferior: float
    gap_certificado_porcentual: float
    cota_superior_teorica: float | None
    fases_aceptadas: int
    fases_ejecutadas: int
    aumentos: int
    dijkstras: int
    epsilon_interno: float
    factor_teorico: float
    cota_inicial: float
    cota_construida: float
    normalizacion_certificada: bool
    origen_cota: str
    termino_teorico: bool
    motivo_termino: str
    fuente_solucion: str
    tiempo_total: float


def logaddexp(a: float, b: float) -> float:
    """Devuelve log(exp(a) + exp(b)) sin overflow ni underflow."""
    if a == INFINITO_NEGATIVO:
        return b
    if b == INFINITO_NEGATIVO:
        return a
    mayor = max(a, b)
    return mayor + math.log1p(math.exp(-abs(a - b)))


def logsumexp(valores: Iterable[float]) -> float:
    """Suma estable en dominio logaritmico."""
    valores = list(valores)
    if not valores:
        return INFINITO_NEGATIVO
    mayor = max(valores)
    if mayor == INFINITO_NEGATIVO:
        return INFINITO_NEGATIVO
    return mayor + math.log(math.fsum(math.exp(x - mayor) for x in valores))


def epsilon_para_factor(error_relativo: float) -> float:
    """Elige epsilon para que (1-epsilon)^(-3) <= 1+error."""
    if not math.isfinite(error_relativo) or error_relativo <= 0.0:
        raise ValueError("GK_ERROR_RELATIVO debe ser un numero positivo.")

    epsilon = -math.expm1(-math.log1p(error_relativo) / 3.0)
    factor_objetivo = 1.0 + error_relativo

    # Protege la desigualdad frente al redondeo de punto flotante.
    while (1.0 - epsilon) ** -3 > factor_objetivo:
        epsilon = math.nextafter(epsilon, 0.0)

    if not 0.0 < epsilon < 1.0:
        raise ValueError("No fue posible construir un epsilon valido.")
    return epsilon


def _validar_y_preparar(n, arcos, demandas, productos_no_od):
    if not isinstance(n, int) or n < 1:
        raise ValueError("El numero de nodos debe ser un entero positivo.")
    if not arcos:
        raise ValueError("La instancia no contiene arcos.")
    if productos_no_od:
        muestra = ", ".join(map(str, productos_no_od[:20]))
        raise ValueError(
            "La variante de Garg--Koenemann con Dijkstra requiere un solo "
            "origen y un solo destino por producto. Productos incompatibles: "
            + muestra
        )

    ids = [arco["id"] for arco in arcos]
    if len(ids) != len(set(ids)):
        raise ValueError("Los identificadores de arco deben ser unicos.")

    capacidades = []
    adyacencia = [[] for _ in range(n + 1)]

    for i, arco in enumerate(arcos):
        origen = arco["origen"]
        destino = arco["destino"]
        capacidad = float(arco["capacidad"])

        if not 1 <= origen <= n or not 1 <= destino <= n:
            raise ValueError(f"Extremos invalidos en el arco {arco['id']}.")
        if not math.isfinite(capacidad) or capacidad <= 0.0:
            raise ValueError(
                f"El arco {arco['id']} debe tener capacidad positiva y finita."
            )

        capacidades.append(capacidad)
        adyacencia[origen].append((destino, i))

    datos_productos = []
    ids_productos = set()
    for dato in demandas:
        producto = int(dato["producto"])
        origen = int(dato["origen"])
        destino = int(dato["destino"])
        demanda = float(dato["demanda"])

        if producto in ids_productos:
            raise ValueError(f"Producto repetido: {producto}.")
        if not 1 <= origen <= n or not 1 <= destino <= n:
            raise ValueError(f"Extremos invalidos para el producto {producto}.")
        if origen == destino:
            raise ValueError(
                f"El producto {producto} tiene el mismo origen y destino."
            )
        if not math.isfinite(demanda) or demanda <= 0.0:
            raise ValueError(
                f"La demanda del producto {producto} debe ser positiva y finita."
            )

        ids_productos.add(producto)
        datos_productos.append((producto, origen, destino, demanda))

    if not datos_productos:
        raise ValueError("La instancia no contiene productos.")

    return (
        ids,
        capacidades,
        adyacencia,
        datos_productos,
    )


def _dijkstra_camino_log(n, adyacencia, log_longitudes, origen, destino):
    """Camino minimo cuando cada peso se almacena como su logaritmo.

    Si la distancia ordinaria es a+b, su representacion es
    logaddexp(log(a), log(b)). Como log es monotona, el orden usado por
    Dijkstra coincide con el de las longitudes ordinarias.
    """
    distancias = [math.inf] * (n + 1)
    previo_nodo = [-1] * (n + 1)
    previo_arco = [-1] * (n + 1)

    # log(0) representa la distancia cero de la fuente.
    distancias[origen] = INFINITO_NEGATIVO
    cola = [(INFINITO_NEGATIVO, origen)]

    while cola:
        distancia, nodo = heapq.heappop(cola)
        if distancia > distancias[nodo]:
            continue
        if nodo == destino:
            break

        for siguiente, indice_arco in adyacencia[nodo]:
            nueva = logaddexp(distancia, log_longitudes[indice_arco])
            if nueva < distancias[siguiente]:
                distancias[siguiente] = nueva
                previo_nodo[siguiente] = nodo
                previo_arco[siguiente] = indice_arco
                heapq.heappush(cola, (nueva, siguiente))

    if math.isinf(distancias[destino]):
        return None

    camino = []
    nodo = destino
    while nodo != origen:
        indice_arco = previo_arco[nodo]
        if indice_arco < 0:
            return None
        camino.append(indice_arco)
        nodo = previo_nodo[nodo]

    camino.reverse()
    return camino


def _dijkstra_distancias_log(n, adyacencia, log_longitudes, origen):
    distancias = [math.inf] * (n + 1)
    distancias[origen] = INFINITO_NEGATIVO
    cola = [(INFINITO_NEGATIVO, origen)]

    while cola:
        distancia, nodo = heapq.heappop(cola)
        if distancia > distancias[nodo]:
            continue
        for siguiente, indice_arco in adyacencia[nodo]:
            nueva = logaddexp(distancia, log_longitudes[indice_arco])
            if nueva < distancias[siguiente]:
                distancias[siguiente] = nueva
                heapq.heappush(cola, (nueva, siguiente))

    return distancias


def _cota_inicial_factible(
    n,
    adyacencia,
    capacidades,
    datos_productos,
    guardar_detalle,
    instante_limite,
):
    """Enruta cada producto por un camino minimo con longitud 1/c.

    La congestion B obtenida es una cota superior factible. Ademas,
    B <= m*z*, de modo que el escalamiento satisface 1 <= beta <= m.
    """
    log_longitudes = [-math.log(c) for c in capacidades]
    carga = [0.0] * len(capacidades)
    detalle = {} if guardar_detalle else None
    dijkstras = 0

    for producto, origen, destino, demanda in datos_productos:
        if time.monotonic() >= instante_limite:
            raise TimeoutError(
                "El limite de tiempo termino antes de construir la cota inicial."
            )

        camino = _dijkstra_camino_log(
            n, adyacencia, log_longitudes, origen, destino
        )
        dijkstras += 1
        if not camino:
            raise ValueError(
                f"No existe camino dirigido para el producto {producto}: "
                f"{origen} -> {destino}."
            )

        for indice_arco in camino:
            carga[indice_arco] += demanda
            if detalle is not None:
                clave = (producto, indice_arco)
                detalle[clave] = detalle.get(clave, 0.0) + demanda

    B = max(carga[i] / capacidades[i] for i in range(len(capacidades)))
    if not math.isfinite(B) or B <= 0.0:
        raise ValueError("No se pudo construir una cota inicial positiva.")
    return B, carga, detalle, dijkstras


def _calcular_cota_inferior(
    n,
    adyacencia,
    capacidades,
    log_longitudes,
    datos_productos,
):
    """Cota dual valida para la congestion optima."""
    log_normalizador = logsumexp(
        math.log(capacidades[i]) + log_longitudes[i]
        for i in range(len(capacidades))
    )

    por_origen = {}
    terminos = []
    for _, origen, destino, demanda in datos_productos:
        if origen not in por_origen:
            por_origen[origen] = _dijkstra_distancias_log(
                n, adyacencia, log_longitudes, origen
            )
        log_distancia = por_origen[origen][destino]
        if math.isinf(log_distancia):
            raise ValueError(f"No existe camino dirigido {origen} -> {destino}.")
        terminos.append(math.log(demanda) + log_distancia)

    log_numerador = logsumexp(terminos)
    diferencia = log_numerador - log_normalizador
    if diferencia > math.log(float.fromhex("0x1.fffffffffffffp+1023")):
        return math.inf
    return math.exp(diferencia)


def resolver_garg_konemann(
    *,
    n,
    arcos,
    demandas,
    productos_no_od=(),
    error_relativo=0.15,
    limite_tiempo=900.0,
    max_fases=10_000_000,
    imprimir_cada=10,
    comprobar_gap_cada=25,
    guardar_detalle=False,
    cota_inicial_externa=None,
    cota_externa_certificada=False,
    verbose=True,
):
    """Resuelve una instancia OD simple y devuelve una solucion factible.

    La garantia relativa se obtiene solo si el potencial alcanza el umbral
    teorico antes del limite de tiempo/fases. En caso contrario se devuelve
    el promedio de las fases completas disponibles (o la cota inicial), que
    sigue siendo factible, pero no hereda automaticamente el factor pedido.
    """
    inicio = time.monotonic()
    if not math.isfinite(limite_tiempo) or limite_tiempo <= 0.0:
        raise ValueError("GK_LIMITE_TIEMPO debe ser positivo.")
    if max_fases < 1:
        raise ValueError("GK_MAX_FASES debe ser al menos 1.")
    if imprimir_cada < 1:
        raise ValueError("GK_IMPRIMIR_CADA debe ser al menos 1.")
    if comprobar_gap_cada < 0:
        raise ValueError("GK_COMPROBAR_GAP_CADA no puede ser negativo.")

    (
        ids_arcos,
        capacidades,
        adyacencia,
        datos_productos,
    ) = _validar_y_preparar(n, arcos, demandas, productos_no_od)

    epsilon = epsilon_para_factor(error_relativo)
    factor_teorico = (1.0 - epsilon) ** -3
    m = len(ids_arcos)

    # theta = log(1/delta). Nunca materializamos delta.
    theta = math.log(m / (1.0 - epsilon)) / epsilon
    escala_teorica = theta / math.log1p(epsilon)
    instante_limite = inicio + limite_tiempo

    if verbose:
        print("\nSolver: Garg--Koenemann, variante de caminos minimos")
        print(f"Error relativo solicitado: {100.0 * error_relativo:.4f}%")
        print(f"Epsilon interno: {epsilon:.12g}")
        print(f"Factor teorico: {factor_teorico:.12g}")
        print(f"log10(delta): {-theta / math.log(10.0):.3f}")
        print("Construyendo cota superior inicial factible...")

    (
        B_construida,
        carga_inicial,
        detalle_inicial,
        dijkstras,
    ) = _cota_inicial_factible(
        n,
        adyacencia,
        capacidades,
        datos_productos,
        guardar_detalle,
        instante_limite,
    )

    B = B_construida
    origen_cota = "enrutamiento inicial 1/c"
    normalizacion_certificada = True

    if cota_inicial_externa is not None:
        cota_inicial_externa = float(cota_inicial_externa)
        if (
            not math.isfinite(cota_inicial_externa)
            or cota_inicial_externa <= 0.0
        ):
            raise ValueError("GK_COTA_INICIAL debe ser positiva y finita.")

        if cota_inicial_externa < B_construida:
            B = cota_inicial_externa
            origen_cota = "cota externa de warm start"
            normalizacion_certificada = bool(cota_externa_certificada)
        elif verbose:
            print(
                "La cota externa no mejora la cota construida; "
                "se conservara la cota interna."
            )

    if verbose:
        print(f"Cota superior construida: {B_construida:.10g}")
        print(f"Cota superior inicial usada B: {B:.10g}")
        print(f"Origen de B: {origen_cota}")
        print(
            "B certificada como solucion factible: "
            f"{'si' if normalizacion_certificada else 'no'}"
        )
        print(
            "PARAMETROS INICIALES | "
            f"error_objetivo={100.0 * error_relativo:.4f}% | "
            f"epsilon={epsilon:.12g} | "
            f"log10_delta={-theta / math.log(10.0):.3f} | "
            f"L={escala_teorica:.3f} | "
            f"cota_superior_B={B:.10g}"
        )
        if normalizacion_certificada:
            if B == B_construida:
                print(f"Normalizacion demostrable: z* <= B <= {m} z*")
            else:
                print("Normalizacion demostrable: z* <= B")
        else:
            print(
                "ADVERTENCIA: no se puede afirmar z* <= B sin certificar "
                "que la cota externa proviene de una solucion factible."
            )
        if comprobar_gap_cada:
            print(
                "Certificado primal-dual: se comprobara cada "
                f"{comprobar_gap_cada} fases."
            )
        print("Comenzando fases de Garg--Koenemann...")

    # p_e = (B/delta) l_e. Inicialmente p_e=1/c_e. Multiplicar todas
    # las longitudes por una constante no cambia los caminos minimos.
    log_p = [-math.log(c) for c in capacidades]
    log_capacidades = [math.log(c) for c in capacidades]
    log_W = math.log(m)  # W=sum_e c_e*p_e=m inicialmente.

    carga_acumulada = [0.0] * m
    detalle_acumulado = {} if guardar_detalle else None
    fases_aceptadas = 0
    fases_ejecutadas = 0
    aumentos = 0
    potencial_alcanzo_umbral = False
    gap_alcanzo_objetivo = False
    motivo_termino = "maximo de fases"

    for numero_fase in range(1, max_fases + 1):
        if time.monotonic() >= instante_limite:
            motivo_termino = "limite de tiempo"
            break

        carga_fase = [0.0] * m
        detalle_fase = {} if guardar_detalle else None
        fase_completa = True

        for producto, origen, destino, demanda in datos_productos:
            restante = demanda

            while restante > 0.0:
                if time.monotonic() >= instante_limite:
                    fase_completa = False
                    motivo_termino = "limite de tiempo durante una fase"
                    break

                camino = _dijkstra_camino_log(
                    n, adyacencia, log_p, origen, destino
                )
                dijkstras += 1
                if not camino:
                    raise ValueError(
                        f"No existe camino para el producto {producto}: "
                        f"{origen} -> {destino}."
                    )

                # Las capacidades del problema concurrente se escalan por B.
                cuello = min(B * capacidades[i] for i in camino)
                if restante <= cuello:
                    envio = restante
                    restante = 0.0
                else:
                    envio = cuello
                    restante -= envio

                if not math.isfinite(envio) or envio <= 0.0:
                    raise ArithmeticError("Se obtuvo un aumento no positivo.")

                log_incremento_W_comun = math.log(epsilon * envio / B)
                for i in camino:
                    carga_fase[i] += envio
                    if detalle_fase is not None:
                        clave = (producto, i)
                        detalle_fase[clave] = detalle_fase.get(clave, 0.0) + envio

                    # W aumenta en p_e*epsilon*envio/B.
                    log_W = logaddexp(
                        log_W,
                        log_p[i] + log_incremento_W_comun,
                    )
                    log_p[i] += math.log1p(
                        epsilon * envio / (B * capacidades[i])
                    )

                aumentos += 1

            if not fase_completa:
                break

        if not fase_completa:
            break

        fases_ejecutadas += 1

        # El recalculo evita acumular error en la actualizacion incremental.
        log_W = logsumexp(
            log_capacidades[i] + log_p[i] for i in range(m)
        )
        log_D = log_W - theta

        if verbose and (
            numero_fase <= 3 or numero_fase % imprimir_cada == 0 or log_D >= 0.0
        ):
            if log_D > -700.0:
                potencial = f"{math.exp(log_D):.6e}"
            else:
                potencial = f"10^({log_D / math.log(10.0):.2f})"
            print(
                f"Fase {numero_fase}: D={potencial} | "
                f"aceptadas={fases_aceptadas} | aumentos={aumentos} | "
                f"tiempo={time.monotonic() - inicio:.1f}s"
            )

        # La fase t que cruza D>=1 se descarta: la prueba usa 1,...,t-1.
        if log_D >= 0.0:
            potencial_alcanzo_umbral = True
            motivo_termino = "potencial D(l) alcanzo 1"
            break

        for i in range(m):
            carga_acumulada[i] += carga_fase[i]
        if detalle_acumulado is not None:
            for clave, valor in detalle_fase.items():
                detalle_acumulado[clave] = (
                    detalle_acumulado.get(clave, 0.0) + valor
                )
        fases_aceptadas += 1

        # No es necesario esperar al muy conservador umbral D(l)>=1 si una
        # solucion primal factible y una solucion dual factible ya prueban
        # directamente el factor solicitado. Este corte es un certificado
        # a posteriori, no una heuristica.
        if (
            comprobar_gap_cada
            and fases_aceptadas % comprobar_gap_cada == 0
        ):
            z_promedio = max(
                carga_acumulada[i] / (fases_aceptadas * capacidades[i])
                for i in range(m)
            )
            z_candidato = min(B_construida, z_promedio)
            cota_dual_iteracion = _calcular_cota_inferior(
                n, adyacencia, capacidades, log_p, datos_productos
            )
            gap_iteracion = (
                100.0
                * (z_candidato - cota_dual_iteracion)
                / cota_dual_iteracion
                if cota_dual_iteracion > 0.0
                else math.inf
            )
            if verbose:
                print(
                    f"  CONTROL GAP fase {fases_aceptadas}: "
                    f"primal={z_candidato:.10g} | "
                    f"dual={cota_dual_iteracion:.10g} | "
                    f"gap={gap_iteracion:.4f}%"
                )
            tolerancia_gap = 1e-10 * max(1.0, z_candidato)
            if (
                z_candidato
                <= factor_teorico * cota_dual_iteracion + tolerancia_gap
            ):
                gap_alcanzo_objetivo = True
                motivo_termino = "gap primal-dual alcanzo el factor solicitado"
                break

    # Cada fase aceptada transporta una copia completa de las demandas.
    # Su promedio vuelve a satisfacer exactamente los balances originales.
    if fases_aceptadas > 0:
        carga_gk = [valor / fases_aceptadas for valor in carga_acumulada]
        z_gk = max(carga_gk[i] / capacidades[i] for i in range(m))
    else:
        carga_gk = None
        z_gk = math.inf

    # Elegir la mejor de dos soluciones factibles no debilita la garantia.
    # La cota externa solo normaliza el algoritmo: no contiene un flujo.
    # El candidato inicial disponible sigue siendo carga_inicial, cuya
    # congestion real es B_construida.
    if B_construida <= z_gk:
        carga_final = carga_inicial
        detalle_final_indices = detalle_inicial
        fuente_solucion = "enrutamiento inicial"
    else:
        carga_final = carga_gk
        detalle_final_indices = None
        if detalle_acumulado is not None:
            detalle_final_indices = {
                clave: valor / fases_aceptadas
                for clave, valor in detalle_acumulado.items()
            }
        fuente_solucion = "promedio de fases GK"

    congestion = max(carga_final[i] / capacidades[i] for i in range(m))
    cota_inferior = _calcular_cota_inferior(
        n, adyacencia, capacidades, log_p, datos_productos
    )
    gap = (
        100.0 * (congestion - cota_inferior) / cota_inferior
        if cota_inferior > 0.0
        else math.inf
    )
    # Pequenios residuos negativos solo pueden ser redondeo.
    if gap < 0.0 and gap > -1e-9:
        gap = 0.0

    cota_superior_teorica = None
    termino_por_potencial = (
        potencial_alcanzo_umbral
        and normalizacion_certificada
        and fases_aceptadas > 0
    )
    termino_teorico = termino_por_potencial or gap_alcanzo_objetivo
    if termino_por_potencial:
        cota_superior_teorica = B * escala_teorica / fases_aceptadas
        tolerancia = 1e-9 * max(1.0, cota_superior_teorica)
        if congestion > cota_superior_teorica + tolerancia:
            raise ArithmeticError(
                "La congestion calculada excede la cota teorica directa; "
                "revise la estabilidad numerica."
            )

    flujo_por_arco = {
        ids_arcos[i]: carga_final[i] for i in range(m)
    }
    flujo_por_producto = None
    if detalle_final_indices is not None:
        flujo_por_producto = {
            (producto, ids_arcos[i]): valor
            for (producto, i), valor in detalle_final_indices.items()
        }

    return ResultadoGK(
        flujo_por_arco=flujo_por_arco,
        flujo_por_producto=flujo_por_producto,
        congestion=congestion,
        cota_inferior=cota_inferior,
        gap_certificado_porcentual=gap,
        cota_superior_teorica=cota_superior_teorica,
        fases_aceptadas=fases_aceptadas,
        fases_ejecutadas=fases_ejecutadas,
        aumentos=aumentos,
        dijkstras=dijkstras,
        epsilon_interno=epsilon,
        factor_teorico=factor_teorico,
        cota_inicial=B,
        cota_construida=B_construida,
        normalizacion_certificada=normalizacion_certificada,
        origen_cota=origen_cota,
        termino_teorico=termino_teorico,
        motivo_termino=motivo_termino,
        fuente_solucion=fuente_solucion,
        tiempo_total=time.monotonic() - inicio,
    )


def _leer_configuracion():
    return {
        "error_relativo": float(os.environ.get("GK_ERROR_RELATIVO", "0.15")),
        "limite_tiempo": float(os.environ.get("GK_LIMITE_TIEMPO", "900")),
        "max_fases": int(os.environ.get("GK_MAX_FASES", "10000000")),
        "imprimir_cada": int(os.environ.get("GK_IMPRIMIR_CADA", "10")),
        "comprobar_gap_cada": int(
            os.environ.get("GK_COMPROBAR_GAP_CADA", "25")
        ),
        "guardar_detalle": os.environ.get("GK_GUARDAR_DETALLE", "0") == "1",
        "cota_inicial_externa": (
            float(os.environ["GK_COTA_INICIAL"])
            if "GK_COTA_INICIAL" in os.environ
            else None
        ),
        "cota_externa_certificada": (
            os.environ.get("GK_COTA_CERTIFICADA", "0") == "1"
        ),
    }


def main():
    # La importacion queda dentro de main para poder probar el algoritmo con
    # instancias pequenas sin ejecutar automaticamente lector.py.
    from lector import arcos, demandas, n, productos_no_od

    resultado = resolver_garg_konemann(
        n=n,
        arcos=arcos,
        demandas=demandas,
        productos_no_od=productos_no_od,
        verbose=True,
        **_leer_configuracion(),
    )

    print("\nResultado Garg--Koenemann")
    print(f"Motivo de termino: {resultado.motivo_termino}")
    print(f"Solucion utilizada: {resultado.fuente_solucion}")
    if resultado.termino_teorico:
        print(
            "Garantia teorica del esquema: "
            f"z_GK <= {resultado.factor_teorico:.10g} * z*"
        )
    else:
        print(
            "Garantia teorica solicitada: NO alcanzada; "
            "se entrega solamente una solucion factible."
        )

    print(
        f"Congestión máxima aproximada: {resultado.congestion:.10g} "
        f"({100.0 * resultado.congestion:.2f}%)"
    )
    print(f"Cota inferior dual: {resultado.cota_inferior:.10g}")
    if resultado.cota_superior_teorica is not None:
        print(
            "Cota superior teorica directa: "
            f"{resultado.cota_superior_teorica:.10g}"
        )
    print(
        "Gap de optimalidad certificado: "
        f"{resultado.gap_certificado_porcentual:.6f}%"
    )

    resultados = []
    for arco in arcos:
        flujo = resultado.flujo_por_arco[arco["id"]]
        congestion = flujo / float(arco["capacidad"])
        resultados.append((congestion, arco, flujo))
    resultados.sort(key=lambda fila: fila[0], reverse=True)

    print("\nDiez arcos más congestionados:")
    for congestion, arco, flujo in resultados[:10]:
        print(
            f"Arco {arco['id']}: {arco['origen']} -> {arco['destino']} | "
            f"flujo={flujo:.2f} | capacidad={arco['capacidad']} | "
            f"congestión={congestion:.4f}"
        )

    print(f"\nFases realizadas: {resultado.fases_aceptadas}")
    print(f"Fases ejecutadas: {resultado.fases_ejecutadas}")
    print(f"Aumentos de camino: {resultado.aumentos}")
    print(f"Dijkstras ejecutados: {resultado.dijkstras}")
    print(f"Tiempo total: {resultado.tiempo_total:.2f} segundos")


if __name__ == "__main__":
    main()