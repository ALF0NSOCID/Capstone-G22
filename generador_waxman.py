import random
from pathlib import Path

import networkx as nx


def generar_instancia(
    nodos=400,
    productos=10000,
    arcos_objetivo=None,
    alpha=0.2,
    beta=0.4,
    demanda_min=10,
    demanda_max=50,
    capacidad_min=50,
    capacidad_max=150,
    semilla=42,
    porcentaje_hubs=0.0,
    multiplicador_capacidad_hubs=10.0,
    conexiones_por_hub=3,
):
    """Genera una red Waxman conexa con arcos en ambos sentidos.

    Si ``porcentaje_hubs`` es positivo, selecciona esa proporcion de nodos,
    conecta cada hub con sus vecinos geograficos mas cercanos y multiplica la
    capacidad de esos enlaces.
    """
    if nodos < 2:
        raise ValueError("La instancia debe tener al menos dos nodos.")
    if productos < 1:
        raise ValueError("La instancia debe tener al menos un producto.")
    if productos > nodos * (nodos - 1):
        raise ValueError(
            "No existen suficientes pares origen-destino distintos para "
            f"generar {productos} productos."
        )
    if arcos_objetivo is not None:
        if arcos_objetivo % 2 != 0:
            raise ValueError(
                "arcos_objetivo debe ser par porque cada enlace Waxman se "
                "convierte en dos arcos dirigidos."
            )
        if arcos_objetivo < 2 * (nodos - 1):
            raise ValueError(
                "Una red bidireccional conexa de "
                f"{nodos} nodos requiere al menos {2 * (nodos - 1)} arcos."
            )
        if arcos_objetivo > nodos * (nodos - 1):
            raise ValueError("arcos_objetivo supera el maximo posible.")
    if not 0 < alpha <= 1 or not 0 < beta <= 1:
        raise ValueError("alpha y beta deben pertenecer al intervalo (0, 1].")
    if demanda_min <= 0 or demanda_min > demanda_max:
        raise ValueError("El intervalo de demandas es invalido.")
    if capacidad_min <= 0 or capacidad_min > capacidad_max:
        raise ValueError("El intervalo de capacidades es invalido.")
    if not 0 <= porcentaje_hubs < 1:
        raise ValueError("porcentaje_hubs debe pertenecer al intervalo [0, 1).")
    if multiplicador_capacidad_hubs <= 0:
        raise ValueError("multiplicador_capacidad_hubs debe ser positivo.")
    if conexiones_por_hub < 1:
        raise ValueError("conexiones_por_hub debe ser al menos 1.")

    rng = random.Random(semilla)

    numero_hubs = 0
    if porcentaje_hubs > 0:
        numero_hubs = max(2, round(nodos * porcentaje_hubs))
        numero_hubs = min(numero_hubs, nodos)

    # Generar una red Waxman conexa. Cada intento usa una semilla obtenida
    # del mismo generador local, por lo que el resultado es reproducible.
    max_intentos = 10000
    for _ in range(max_intentos):
        grafo = nx.waxman_graph(
            nodos,
            alpha=alpha,
            beta=beta,
            seed=rng.randint(0, 1_000_000_000),
        )
        enlaces_necesarios = (
            arcos_objetivo // 2
            if arcos_objetivo is not None
            else 0
        )
        if (
            nx.is_connected(grafo)
            and grafo.number_of_edges() >= enlaces_necesarios
        ):
            break
    else:
        raise RuntimeError(
            "No fue posible generar una red Waxman conexa despues de "
            f"{max_intentos} intentos. Prueba aumentando alpha o beta."
        )

    hubs = set(rng.sample(list(grafo.nodes), numero_hubs))
    enlaces_obligatorios = generar_enlaces_hubs(
        grafo,
        hubs,
        conexiones_por_hub,
    )
    grafo.add_edges_from(enlaces_obligatorios)

    if arcos_objetivo is not None and enlaces_obligatorios:
        enlaces_objetivo = arcos_objetivo // 2
        componentes_backbone = 1
        minimo_con_backbone = (
            len(enlaces_obligatorios)
            + nodos
            - numero_hubs
            + componentes_backbone
            - 1
        )
        if minimo_con_backbone > enlaces_objetivo:
            raise ValueError(
                "No caben el backbone de hubs y una red conexa dentro de "
                f"{arcos_objetivo} arcos. Se requieren al menos "
                f"{2 * minimo_con_backbone} arcos dirigidos."
            )

    if arcos_objetivo is not None:
        if enlaces_obligatorios:
            grafo = seleccionar_subgrafo_conexo_con_obligatorios(
                grafo,
                arcos_objetivo // 2,
                rng,
                enlaces_obligatorios,
            )
        else:
            grafo = seleccionar_subgrafo_conexo(
                grafo,
                arcos_objetivo // 2,
                rng,
            )

    nx.set_node_attributes(
        grafo,
        {nodo: nodo in hubs for nodo in grafo.nodes},
        "es_hub",
    )

    # NetworkX usa nodos 0...n-1; los solvers usan 1...n.
    grafo = nx.relabel_nodes(
        grafo,
        {nodo: nodo + 1 for nodo in grafo.nodes},
    )

    # Cada enlace no dirigido se transforma en dos arcos dirigidos. Ambos
    # sentidos reciben la misma capacidad para conservar la simetria Waxman.
    arcos = []
    for origen, destino in grafo.edges():
        capacidad = rng.randint(capacidad_min, capacidad_max)
        es_backbone = (
            grafo.nodes[origen].get("es_hub", False)
            and grafo.nodes[destino].get("es_hub", False)
        )
        if es_backbone:
            capacidad = round(capacidad * multiplicador_capacidad_hubs)
        grafo.edges[origen, destino]["es_backbone"] = es_backbone
        grafo.edges[origen, destino]["capacidad"] = capacidad
        arcos.append({
            "id": len(arcos),
            "origen": origen,
            "destino": destino,
            "costo_fijo": 1,
            "capacidad": capacidad,
        })
        arcos.append({
            "id": len(arcos),
            "origen": destino,
            "destino": origen,
            "costo_fijo": 1,
            "capacidad": capacidad,
        })

    commodities = []
    pares_usados = set()
    lista_nodos = list(grafo.nodes)

    while len(commodities) < productos:
        origen, destino = rng.sample(lista_nodos, 2)
        if (origen, destino) in pares_usados:
            continue

        pares_usados.add((origen, destino))
        commodities.append({
            "producto": len(commodities) + 1,
            "origen": origen,
            "destino": destino,
            "demanda": rng.randint(demanda_min, demanda_max),
        })

    return grafo, arcos, commodities


def generar_enlaces_hubs(grafo, hubs, conexiones_por_hub):
    """Conecta cada hub con sus k hubs mas cercanos y une componentes."""
    if len(hubs) < 2:
        return []

    posiciones = nx.get_node_attributes(grafo, "pos")
    k = min(conexiones_por_hub, len(hubs) - 1)
    enlaces = set()

    def distancia_cuadrada(origen, destino):
        x1, y1 = posiciones[origen]
        x2, y2 = posiciones[destino]
        return (x1 - x2) ** 2 + (y1 - y2) ** 2

    # La union de los k vecinos mas cercanos de cada hub crea un backbone
    # local y redundante, sin formar un clique completo.
    for origen in sorted(hubs):
        vecinos = sorted(
            (destino for destino in hubs if destino != origen),
            key=lambda destino: (
                distancia_cuadrada(origen, destino),
                destino,
            ),
        )
        for destino in vecinos[:k]:
            enlaces.add(tuple(sorted((origen, destino))))

    backbone = nx.Graph()
    backbone.add_nodes_from(hubs)
    backbone.add_edges_from(enlaces)

    # Un k pequeno puede producir regiones separadas. En ese caso se conecta
    # repetidamente el par de componentes geograficamente mas cercano.
    while not nx.is_connected(backbone):
        componentes = [set(componente) for componente in nx.connected_components(backbone)]
        mejor = None
        for indice, primera in enumerate(componentes):
            for segunda in componentes[indice + 1:]:
                for origen in primera:
                    for destino in segunda:
                        candidato = (
                            distancia_cuadrada(origen, destino),
                            min(origen, destino),
                            max(origen, destino),
                        )
                        if mejor is None or candidato < mejor:
                            mejor = candidato
        _, origen, destino = mejor
        backbone.add_edge(origen, destino)
        enlaces.add((origen, destino))

    return sorted(enlaces)


def seleccionar_subgrafo_conexo_con_obligatorios(
    grafo,
    numero_enlaces,
    rng,
    enlaces_obligatorios,
):
    """Conserva enlaces obligatorios y completa un subgrafo conexo exacto."""
    claves_obligatorias = {
        frozenset((origen, destino))
        for origen, destino in enlaces_obligatorios
    }
    if len(claves_obligatorias) > numero_enlaces:
        raise ValueError("Los enlaces obligatorios superan el total solicitado.")

    padre = {nodo: nodo for nodo in grafo.nodes}
    rango = {nodo: 0 for nodo in grafo.nodes}
    componentes = len(padre)

    def encontrar(nodo):
        while padre[nodo] != nodo:
            padre[nodo] = padre[padre[nodo]]
            nodo = padre[nodo]
        return nodo

    def unir(origen, destino):
        nonlocal componentes
        raiz_origen = encontrar(origen)
        raiz_destino = encontrar(destino)
        if raiz_origen == raiz_destino:
            return False
        if rango[raiz_origen] < rango[raiz_destino]:
            raiz_origen, raiz_destino = raiz_destino, raiz_origen
        padre[raiz_destino] = raiz_origen
        if rango[raiz_origen] == rango[raiz_destino]:
            rango[raiz_origen] += 1
        componentes -= 1
        return True

    seleccionados = []
    claves_seleccionadas = set()
    for origen, destino in enlaces_obligatorios:
        clave = frozenset((origen, destino))
        if clave in claves_seleccionadas:
            continue
        seleccionados.append((origen, destino))
        claves_seleccionadas.add(clave)
        unir(origen, destino)

    candidatos = [
        (origen, destino)
        for origen, destino in grafo.edges
        if frozenset((origen, destino)) not in claves_seleccionadas
    ]
    rng.shuffle(candidatos)

    # Completa primero la conectividad, respetando todo el backbone.
    for origen, destino in candidatos:
        if unir(origen, destino):
            seleccionados.append((origen, destino))
            claves_seleccionadas.add(frozenset((origen, destino)))
            if componentes == 1:
                break

    if componentes != 1:
        raise RuntimeError("No fue posible conectar la red conservando los hubs.")
    if len(seleccionados) > numero_enlaces:
        raise ValueError(
            "El numero objetivo de enlaces es insuficiente para conservar "
            "el backbone y la conectividad."
        )

    restantes = [
        (origen, destino)
        for origen, destino in candidatos
        if frozenset((origen, destino)) not in claves_seleccionadas
    ]
    rng.shuffle(restantes)
    seleccionados.extend(
        restantes[:numero_enlaces - len(seleccionados)]
    )

    if len(seleccionados) != numero_enlaces:
        raise RuntimeError(
            "No existen suficientes enlaces candidatos para alcanzar el "
            "numero solicitado."
        )

    subgrafo = nx.Graph()
    subgrafo.add_nodes_from(grafo.nodes(data=True))
    subgrafo.add_edges_from(seleccionados)
    return subgrafo


def seleccionar_subgrafo_conexo(grafo, numero_enlaces, rng):
    """Conserva exactamente ``numero_enlaces`` sin perder conectividad."""
    enlaces = list(grafo.edges())
    rng.shuffle(enlaces)

    padre = {nodo: nodo for nodo in grafo.nodes}
    rango = {nodo: 0 for nodo in grafo.nodes}

    def encontrar(nodo):
        while padre[nodo] != nodo:
            padre[nodo] = padre[padre[nodo]]
            nodo = padre[nodo]
        return nodo

    def unir(origen, destino):
        raiz_origen = encontrar(origen)
        raiz_destino = encontrar(destino)
        if raiz_origen == raiz_destino:
            return False
        if rango[raiz_origen] < rango[raiz_destino]:
            raiz_origen, raiz_destino = raiz_destino, raiz_origen
        padre[raiz_destino] = raiz_origen
        if rango[raiz_origen] == rango[raiz_destino]:
            rango[raiz_origen] += 1
        return True

    seleccionados = []
    claves_seleccionadas = set()

    # El orden aleatorio de Kruskal produce primero un arbol generador.
    for origen, destino in enlaces:
        if unir(origen, destino):
            seleccionados.append((origen, destino))
            claves_seleccionadas.add(frozenset((origen, destino)))
            if len(seleccionados) == grafo.number_of_nodes() - 1:
                break

    restantes = [
        (origen, destino)
        for origen, destino in enlaces
        if frozenset((origen, destino)) not in claves_seleccionadas
    ]
    rng.shuffle(restantes)
    seleccionados.extend(
        restantes[:numero_enlaces - len(seleccionados)]
    )

    subgrafo = nx.Graph()
    subgrafo.add_nodes_from(grafo.nodes(data=True))
    subgrafo.add_edges_from(seleccionados)
    return subgrafo


def escribir_instancia(ruta, grafo, arcos, commodities):
    """Escribe la instancia en el formato Canad que consume ``lector.py``."""
    ruta = Path(ruta)
    with ruta.open("w", encoding="utf-8") as archivo:
        archivo.write(
            f"{grafo.number_of_nodes()} {len(arcos)} {len(commodities)}\n"
        )

        # El ultimo cero indica que no existen capacidades por commodity.
        for arco in arcos:
            archivo.write(
                f"{arco['origen']} {arco['destino']} "
                f"{arco['costo_fijo']} {arco['capacidad']} 0\n"
            )

        # Una oferta positiva en el origen y una demanda negativa en destino.
        for commodity in commodities:
            producto = commodity["producto"]
            demanda = commodity["demanda"]
            archivo.write(
                f"{producto} {commodity['origen']} {demanda}\n"
            )
            archivo.write(
                f"{producto} {commodity['destino']} {-demanda}\n"
            )

    return ruta
