"""Filtro de commodities sin camino para instancias Canad/MULGEN.

La red generada por MULGEN se conserva EXACTAMENTE como fue producida: no se
modifica ningun arco, extremo, capacidad, ID ni atributo.

Si un commodity no posee camino dirigido entre su origen y destino en el grafo
de arcos con capacidad positiva, ese commodity se elimina de ``demandas``.
De esta forma los solvers trabajan sobre una subinstancia factible en
conectividad, pero sobre la topologia oficial y sin manipulaciones de la red.

Se conserva la interfaz publica usada actualmente por ``lector.py``:

    corregir_conectividad(numero_nodos, arcos, demandas, semilla=1010)

La funcion modifica ``demandas`` IN-PLACE y devuelve ``arcos`` sin cambios. El
argumento ``semilla`` se mantiene solo por compatibilidad con el codigo actual;
no se utiliza porque el procedimiento es completamente determinista.
"""

from __future__ import annotations


def _nodos_origen_destino(demanda):
    if "origen" in demanda and "destino" in demanda:
        return [int(demanda["origen"])], [int(demanda["destino"])]

    origenes = [
        int(nodo)
        for nodo, cantidad in demanda.get("origenes", ())
        if cantidad
    ]
    destinos = [
        int(nodo)
        for nodo, cantidad in demanda.get("destinos", ())
        if cantidad
    ]
    return origenes, destinos


def _crear_adyacencia(numero_nodos, arcos):
    adyacencia = [[] for _ in range(numero_nodos + 1)]

    for arco in arcos:
        if float(arco["capacidad"]) <= 0.0:
            continue

        origen = int(arco["origen"])
        destino = int(arco["destino"])
        if not 1 <= origen <= numero_nodos or not 1 <= destino <= numero_nodos:
            raise ValueError(
                f"Extremos invalidos en el arco {arco['id']}: "
                f"{origen} -> {destino}."
            )

        adyacencia[origen].append(destino)

    return adyacencia


def _alcanzables(origen, adyacencia):
    vistos = {origen}
    pila = [origen]

    while pila:
        nodo = pila.pop()
        for siguiente in adyacencia[nodo]:
            if siguiente not in vistos:
                vistos.add(siguiente)
                pila.append(siguiente)

    return vistos


def _demanda_tiene_camino(demanda, alcanzables_por_origen, adyacencia):
    origenes, destinos = _nodos_origen_destino(demanda)
    if not origenes or not destinos:
        return False

    for origen in origenes:
        if origen not in alcanzables_por_origen:
            alcanzables_por_origen[origen] = _alcanzables(origen, adyacencia)

        vistos = alcanzables_por_origen[origen]
        if any(destino not in vistos for destino in destinos):
            return False

    return True


def corregir_conectividad(numero_nodos, arcos, demandas, semilla=1010):
    """Elimina commodities sin camino y conserva intacta la red original.

    ``demandas`` se modifica in-place para mantener compatibilidad con el resto
    del proyecto. ``arcos`` se devuelve exactamente sin modificaciones.
    """
    if numero_nodos < 1:
        raise ValueError("El numero de nodos debe ser positivo.")
    if not arcos:
        raise ValueError("No hay arcos en la instancia.")

    cantidad_arcos = len(arcos)
    ids_originales = [arco["id"] for arco in arcos]
    extremos_originales = [
        (int(arco["origen"]), int(arco["destino"])) for arco in arcos
    ]
    capacidades_originales = [arco["capacidad"] for arco in arcos]

    adyacencia = _crear_adyacencia(numero_nodos, arcos)
    alcanzables_por_origen = {}

    demandas_originales = len(demandas)
    conectadas = []
    eliminadas = []

    for demanda in demandas:
        if _demanda_tiene_camino(
            demanda,
            alcanzables_por_origen,
            adyacencia,
        ):
            conectadas.append(demanda)
        else:
            eliminadas.append(int(demanda["producto"]))

    # Modificacion in-place: cualquier referencia existente a ``demandas`` ve
    # inmediatamente la subinstancia filtrada.
    demandas[:] = conectadas

    if eliminadas:
        print(
            "Filtro de conectividad: "
            f"{len(eliminadas)} productos sin camino eliminados."
        )
        print(
            "Filtro de conectividad: "
            f"{demandas_originales} -> {len(demandas)} productos."
        )
        muestra = eliminadas[:20]
        sufijo = " ..." if len(eliminadas) > len(muestra) else ""
        print(
            "Filtro de conectividad: productos eliminados (muestra): "
            f"{muestra}{sufijo}"
        )
    else:
        print(
            "Filtro de conectividad: todos los productos poseen camino; "
            "no se elimina ninguno."
        )

    # Verificaciones explicitas: la red debe quedar byte-logicamente igual en
    # todos los campos relevantes utilizados por el proyecto.
    if len(arcos) != cantidad_arcos:
        raise AssertionError("El filtro cambio la cantidad de arcos.")
    if [arco["id"] for arco in arcos] != ids_originales:
        raise AssertionError("El filtro cambio los IDs de los arcos.")
    if [
        (int(arco["origen"]), int(arco["destino"])) for arco in arcos
    ] != extremos_originales:
        raise AssertionError("El filtro cambio la topologia de la red.")
    if [arco["capacidad"] for arco in arcos] != capacidades_originales:
        raise AssertionError("El filtro cambio capacidades de la red.")

    # Verificacion final de los commodities conservados.
    alcanzables_verificacion = {}
    for demanda in demandas:
        if not _demanda_tiene_camino(
            demanda,
            alcanzables_verificacion,
            adyacencia,
        ):
            raise AssertionError(
                "El filtro conservo un producto sin camino: "
                f"{demanda['producto']}"
            )

    print(
        "Filtro de conectividad: red original preservada y verificacion final "
        "superada."
    )
    return arcos