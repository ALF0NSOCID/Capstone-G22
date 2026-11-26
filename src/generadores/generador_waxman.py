import math
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
    demanda_gravedad=False,
    demanda_media=30,
    sigma_masa=1.0,
    capacidad_escalones=False,
    factores_escalon=(1.0, 2.5, 5.0, 10.0),
    cuantiles_escalon=(0.40, 0.75, 0.93),
    prob_acceso_backbone=0.0,
    prob_segundo_hub=0.0,
    secuencias_independientes=False,
):
    """Genera una red Waxman conexa con arcos en ambos sentidos.

    Opciones de realismo (por defecto desactivadas: el comportamiento original
    no cambia y las semillas siguen reproduciendo las mismas instancias):

    - ``demanda_gravedad``: los pares origen-destino se eligen con
      probabilidad proporcional a masa(origen) * masa(destino) y la demanda
      de cada par es proporcional a ese mismo producto (media ``demanda_media``).
      Las masas son lognormales con parametro ``sigma_masa``.
    - ``capacidad_escalones``: la capacidad de cada enlace se elige entre
      escalones ``capacidad_min * factor`` segun su centralidad (betweenness
      de arista): los enlaces mas centrales reciben escalones mayores.

    Si ``porcentaje_hubs`` es positivo, selecciona esa proporcion de nodos,
    conecta cada hub con sus vecinos geograficos mas cercanos y multiplica la
    capacidad de esos enlaces.

    ``prob_acceso_backbone`` impone acceso al hub mas cercano por nodo normal;
    ``prob_segundo_hub`` agrega un segundo acceso condicionado al primero.
    Todos estos enlaces cuentan dentro del presupuesto y sobreviven al recorte.
    Con ``secuencias_independientes`` se fijan posiciones y demandas entre
    variantes, se distribuyen hubs espacialmente y la capacidad base se asigna
    por identidad de enlace. Las probabilidades cero y el modo independiente
    desactivado conservan las instancias historicas.
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
    for valor in (prob_acceso_backbone, prob_segundo_hub):
        if not 0 <= valor <= 1:
            raise ValueError("Las probabilidades de acceso deben estar entre 0 y 1.")
    if (prob_acceso_backbone or prob_segundo_hub) and porcentaje_hubs == 0:
        raise ValueError("El acceso al backbone requiere porcentaje_hubs > 0.")

    if demanda_media <= 0:
        raise ValueError("demanda_media debe ser positiva.")
    if sigma_masa < 0:
        raise ValueError("sigma_masa no puede ser negativo.")
    if len(cuantiles_escalon) != len(factores_escalon) - 1:
        raise ValueError(
            "Debe haber un cuantil menos que factores de escalon."
        )

    rng = random.Random(semilla)
    rng_hubs = random.Random(f"{semilla}:hubs") if secuencias_independientes else rng
    rng_acceso = random.Random(f"{semilla}:acceso")
    rng_demanda = random.Random(f"{semilla}:demanda") if secuencias_independientes else rng
    posiciones = None
    if secuencias_independientes:
        rng_pos = random.Random(f"{semilla}:posiciones")
        posiciones = {u: (rng_pos.random(), rng_pos.random()) for u in range(nodos)}
        candidatos = [(u, v, math.dist(posiciones[u], posiciones[v]))
                      for u in range(nodos) for v in range(u + 1, nodos)]
        longitud = max(d for _, _, d in candidatos)
        probabilidades = [(u, v, beta * math.exp(-d / (alpha * longitud)))
                          for u, v, d in candidatos]
        rng = random.Random(f"{semilla}:topologia")

    numero_hubs = 0
    if porcentaje_hubs > 0:
        numero_hubs = max(2, round(nodos * porcentaje_hubs))
        numero_hubs = min(numero_hubs, nodos)

    # Generar una red Waxman conexa. Cada intento usa una semilla obtenida
    # del mismo generador local, por lo que el resultado es reproducible.
    max_intentos = 10000
    for _ in range(max_intentos):
        if posiciones is None:
            grafo = nx.waxman_graph(nodos, alpha=alpha, beta=beta,
                                   seed=rng.randint(0, 1_000_000_000))
        else:
            grafo = nx.Graph()
            grafo.add_nodes_from(range(nodos))
            nx.set_node_attributes(grafo, posiciones, "pos")
            grafo.add_edges_from((u, v) for u, v, p in probabilidades if rng.random() < p)
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

    hubs = (seleccionar_hubs_espaciales(grafo, numero_hubs, rng_hubs)
            if secuencias_independientes else set(rng.sample(list(grafo.nodes), numero_hubs)))
    enlaces_backbone = generar_enlaces_hubs(
        grafo,
        hubs,
        conexiones_por_hub,
    )
    enlaces_acceso = generar_enlaces_acceso(
        grafo, hubs, prob_acceso_backbone, prob_segundo_hub, rng_acceso)
    enlaces_obligatorios = sorted(set(enlaces_backbone) | set(enlaces_acceso))
    if secuencias_independientes:
        rng = random.Random(f"{semilla}:seleccion_enlaces")
    grafo.add_edges_from(enlaces_obligatorios)

    if arcos_objetivo is not None and enlaces_obligatorios:
        enlaces_objetivo = arcos_objetivo // 2
        obligatorios = nx.Graph()
        obligatorios.add_nodes_from(grafo.nodes)
        obligatorios.add_edges_from(enlaces_obligatorios)
        minimo_con_backbone = len(enlaces_obligatorios) + nx.number_connected_components(obligatorios) - 1
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
    accesos_obligatorios = {frozenset((u + 1, v + 1)) for u, v in enlaces_acceso}
    for u, v in grafo.edges:
        grafo.edges[u, v]["acceso_obligatorio"] = frozenset((u, v)) in accesos_obligatorios
        grafo.edges[u, v]["es_acceso"] = (u - 1 in hubs) != (v - 1 in hubs)
    grafo.graph["generacion"] = {
        "semilla": semilla, "alpha": alpha, "beta": beta,
        "porcentaje_hubs": porcentaje_hubs, "conexiones_por_hub": conexiones_por_hub,
        "prob_acceso_backbone": prob_acceso_backbone, "prob_segundo_hub": prob_segundo_hub,
        "secuencias_independientes": secuencias_independientes,
        "intentos": _ + 1, "multiplicador_capacidad_hubs": multiplicador_capacidad_hubs,
    }

    # Cada enlace no dirigido se transforma en dos arcos dirigidos. Ambos
    # sentidos reciben la misma capacidad para conservar la simetria Waxman.
    escalon_enlace = {}
    if capacidad_escalones:
        escalon_enlace = _asignar_escalones(grafo, cuantiles_escalon)

    arcos = []
    for origen, destino in grafo.edges():
        if capacidad_escalones:
            nivel = escalon_enlace[frozenset((origen, destino))]
            capacidad = max(1, round(capacidad_min * factores_escalon[nivel]))
        else:
            rng_cap = (random.Random(f"{semilla}:capacidad:{min(origen, destino)}:{max(origen, destino)}")
                       if secuencias_independientes else rng)
            capacidad = rng_cap.randint(capacidad_min, capacidad_max)
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

    if demanda_gravedad:
        commodities = _commodities_gravedad(
            lista_nodos,
            productos,
            demanda_media,
            sigma_masa,
            rng_demanda,
        )

    while len(commodities) < productos:
        origen, destino = rng_demanda.sample(lista_nodos, 2)
        if (origen, destino) in pares_usados:
            continue

        pares_usados.add((origen, destino))
        commodities.append({
            "producto": len(commodities) + 1,
            "origen": origen,
            "destino": destino,
            "demanda": rng_demanda.randint(demanda_min, demanda_max),
        })

    return grafo, arcos, commodities


def seleccionar_hubs_espaciales(grafo, cantidad, rng):
    """Muestreo de punto mas lejano: distribuye los hubs sobre posiciones fijas."""
    if not cantidad:
        return set()
    pos = nx.get_node_attributes(grafo, "pos")
    hubs = {rng.choice(sorted(grafo.nodes))}
    while len(hubs) < cantidad:
        hubs.add(max((u for u in grafo if u not in hubs),
                     key=lambda u: (min(math.dist(pos[u], pos[h]) for h in hubs), -u)))
    return hubs


def generar_enlaces_acceso(grafo, hubs, prob_primero, prob_segundo, rng):
    """Segundo acceso condicional al primero; ambos sobreviven al recorte."""
    pos = nx.get_node_attributes(grafo, "pos")
    enlaces = set()
    for u in sorted(set(grafo) - hubs):
        primero, segundo = rng.random(), rng.random()
        if primero >= prob_primero:
            continue
        cercanos = sorted(hubs, key=lambda h: (math.dist(pos[u], pos[h]), h))
        enlaces.add(tuple(sorted((u, cercanos[0]))))
        if len(cercanos) > 1 and segundo < prob_segundo:
            enlaces.add(tuple(sorted((u, cercanos[1]))))
    return sorted(enlaces)


def _asignar_escalones(grafo, cuantiles):
    """Nivel de escalon (0 = menor) de cada enlace segun su betweenness."""
    centralidad = nx.edge_betweenness_centrality(grafo)
    valores = sorted(centralidad.values())
    cortes = [
        valores[min(len(valores) - 1, int(q * len(valores)))]
        for q in cuantiles
    ]
    niveles = {}
    for (origen, destino), valor in centralidad.items():
        niveles[frozenset((origen, destino))] = sum(
            valor > corte for corte in cortes
        )
    return niveles


def _commodities_gravedad(nodos, productos, demanda_media, sigma_masa, rng):
    """Pares (s, t) distintos con probabilidad ~ w_s * w_t (modelo de gravedad).

    Muestreo sin reemplazo con pesos (Efraimidis-Spirakis): a cada par se le
    asigna la clave log(U) / peso y se conservan los ``productos`` mayores.
    La demanda de cada par es proporcional a w_s * w_t, con media
    ``demanda_media`` y minimo 1 (los solvers leen enteros).
    """
    masa = {nodo: rng.lognormvariate(0.0, sigma_masa) for nodo in nodos}
    claves = []
    for origen in nodos:
        for destino in nodos:
            if origen == destino:
                continue
            peso = masa[origen] * masa[destino]
            claves.append((math.log(1.0 - rng.random()) / peso, origen, destino, peso))

    claves.sort(reverse=True)
    elegidos = claves[:productos]
    peso_medio = sum(c[3] for c in elegidos) / len(elegidos)

    return [
        {
            "producto": indice,
            "origen": origen,
            "destino": destino,
            "demanda": max(1, round(demanda_media * peso / peso_medio)),
        }
        for indice, (_, origen, destino, peso) in enumerate(elegidos, start=1)
    ]


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
