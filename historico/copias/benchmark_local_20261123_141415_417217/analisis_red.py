"""Diagnóstico estructural para instancias de redes multiproducto."""

import os
import sys


def analizar_red_generada(ruta_instancia):
    """
    Analiza la estructura de la instancia usando EXACTAMENTE la misma red que
    ya fue interpretada por lector.py y que reciben los solvers.

    No vuelve a parsear el archivo `out`: reutiliza `lector.arcos` y
    `lector.demandas`, evitando inconsistencias con el formato histórico de
    MULGEN/Canad. No modifica la instancia.
    """
    from collections import Counter, defaultdict, deque
    import importlib
    import math
    import statistics

    # lector.py usa ARCHIVO_INSTANCIA para decidir qué archivo cargar.
    # Forzamos aquí la misma salida activa generada por ejecutar.py.
    os.environ["ARCHIVO_INSTANCIA"] = str(ruta_instancia)

    # Si lector hubiese sido importado antes en este proceso, recargarlo para
    # garantizar que corresponde a la instancia recién generada.
    if "lector" in sys.modules:
        lector = importlib.reload(sys.modules["lector"])
    else:
        lector = importlib.import_module("lector")

    n = int(lector.n)

    arcos_lector = list(lector.arcos)
    demandas_lector = list(lector.demandas)

    def _valor(objeto, claves, default=None):
        """Obtiene un campo tanto de dicts como de objetos simples."""
        if isinstance(objeto, dict):
            for clave in claves:
                if clave in objeto:
                    return objeto[clave]
        else:
            for clave in claves:
                if hasattr(objeto, clave):
                    return getattr(objeto, clave)
        return default

    arcos = []
    for idx, arco in enumerate(arcos_lector, start=1):
        u = _valor(arco, ["origen", "from", "u", "inicio", "tail"])
        v = _valor(arco, ["destino", "to", "v", "fin", "head"])
        c = _valor(arco, ["capacidad", "capacity", "c", "cap"])

        # Compatibilidad con tuplas/listas por si lector cambia de estructura.
        if (u is None or v is None or c is None) and isinstance(arco, (tuple, list)):
            if len(arco) >= 3:
                u, v, c = arco[-3], arco[-2], arco[-1]

        if u is None or v is None or c is None:
            raise ValueError(
                f"No se pudo interpretar el arco #{idx} entregado por lector.py: {arco!r}"
            )

        u = int(u)
        v = int(v)
        c = float(c)

        if not (1 <= u <= n and 1 <= v <= n):
            raise ValueError(
                f"lector.py entregó un arco fuera de rango en #{idx}: {u} -> {v}"
            )

        arcos.append((u, v, c))

    demandas = []
    for idx, demanda in enumerate(demandas_lector, start=1):
        s = _valor(demanda, ["origen", "source", "s", "from"])
        t = _valor(demanda, ["destino", "sink", "t", "to"])
        d = _valor(demanda, ["demanda", "demand", "d", "cantidad"])

        if (s is None or t is None or d is None) and isinstance(demanda, (tuple, list)):
            if len(demanda) >= 3:
                s, t, d = demanda[-3], demanda[-2], demanda[-1]

        if s is None or t is None or d is None:
            raise ValueError(
                f"No se pudo interpretar el producto #{idx} entregado por lector.py: {demanda!r}"
            )

        s = int(s)
        t = int(t)
        d = float(d)

        if not (1 <= s <= n and 1 <= t <= n):
            raise ValueError(
                f"lector.py entregó un producto fuera de rango en #{idx}: {s} -> {t}"
            )

        demandas.append((s, t, d))

    m = len(arcos)
    k = len(demandas)

    capacidades = [c for _, _, c in arcos]
    volumen_demandas = [d for _, _, d in demandas]

    ady = [[] for _ in range(n + 1)]
    rev = [[] for _ in range(n + 1)]
    ady_no_dirigida = [set() for _ in range(n + 1)]
    grado_salida = [0] * (n + 1)
    grado_entrada = [0] * (n + 1)

    for u, v, capacidad in arcos:
        grado_salida[u] += 1
        grado_entrada[v] += 1
        if capacidad > 0:
            ady[u].append(v)
            rev[v].append(u)
            ady_no_dirigida[u].add(v)
            ady_no_dirigida[v].add(u)

    print(
        "Fuente del análisis: lector.py "
        f"({n} nodos, {m} arcos, {k} commodities efectivos)."
    )

    def percentil(datos, q):
        if not datos:
            return float("nan")
        ordenados = sorted(datos)
        pos = (len(ordenados) - 1) * q
        inferior = math.floor(pos)
        superior = math.ceil(pos)
        if inferior == superior:
            return ordenados[inferior]
        peso = pos - inferior
        return ordenados[inferior] * (1 - peso) + ordenados[superior] * peso

    def resumen_numerico(datos):
        if not datos:
            return None
        promedio = statistics.fmean(datos)
        desviacion = statistics.pstdev(datos) if len(datos) > 1 else 0.0
        cv = desviacion / promedio if promedio != 0 else float("inf")
        return {
            "min": min(datos),
            "p25": percentil(datos, 0.25),
            "mediana": percentil(datos, 0.50),
            "p75": percentil(datos, 0.75),
            "max": max(datos),
            "promedio": promedio,
            "cv": cv,
        }

    # Componentes débilmente conexas.
    visitado = [False] * (n + 1)
    componentes_debiles = []
    for inicio in range(1, n + 1):
        if visitado[inicio]:
            continue
        cola = deque([inicio])
        visitado[inicio] = True
        tam = 0
        while cola:
            u = cola.popleft()
            tam += 1
            for v in ady_no_dirigida[u]:
                if not visitado[v]:
                    visitado[v] = True
                    cola.append(v)
        componentes_debiles.append(tam)

    componentes_debiles.sort(reverse=True)

    # SCC mediante Kosaraju iterativo.
    visitado = [False] * (n + 1)
    orden = []

    for inicio in range(1, n + 1):
        if visitado[inicio]:
            continue
        pila = [(inicio, 0)]
        visitado[inicio] = True
        while pila:
            u, idx = pila[-1]
            if idx < len(ady[u]):
                v = ady[u][idx]
                pila[-1] = (u, idx + 1)
                if not visitado[v]:
                    visitado[v] = True
                    pila.append((v, 0))
            else:
                orden.append(u)
                pila.pop()

    componente = [-1] * (n + 1)
    tamanos_scc = []

    for inicio in reversed(orden):
        if componente[inicio] != -1:
            continue
        cid = len(tamanos_scc)
        pila = [inicio]
        componente[inicio] = cid
        tam = 0
        while pila:
            u = pila.pop()
            tam += 1
            for v in rev[u]:
                if componente[v] == -1:
                    componente[v] = cid
                    pila.append(v)
        tamanos_scc.append(tam)

    tamanos_scc.sort(reverse=True)

    # Alcanzabilidad de los commodities efectivos, cacheada por origen.
    por_origen = defaultdict(list)
    for idx, (s, t, d) in enumerate(demandas):
        por_origen[s].append((idx, t, d))

    alcanzables = [False] * len(demandas)
    distancias_od = []

    for s, productos_origen in por_origen.items():
        dist = [-1] * (n + 1)
        dist[s] = 0
        cola = deque([s])
        while cola:
            u = cola.popleft()
            for v in ady[u]:
                if dist[v] == -1:
                    dist[v] = dist[u] + 1
                    cola.append(v)

        for idx, t, _ in productos_origen:
            if dist[t] >= 0:
                alcanzables[idx] = True
                distancias_od.append(dist[t])

    k_alcanzable = sum(alcanzables)
    k_no_alcanzable = k - k_alcanzable

    pares_dirigidos = {(u, v) for u, v, c in arcos if c > 0}
    arcos_reciprocos = sum(1 for u, v in pares_dirigidos if (v, u) in pares_dirigidos)
    reciprocidad = arcos_reciprocos / len(pares_dirigidos) if pares_dirigidos else 0.0

    contador_arcos = Counter((u, v) for u, v, _ in arcos)
    duplicados = sum(cantidad - 1 for cantidad in contador_arcos.values() if cantidad > 1)
    lazos = sum(1 for u, v, _ in arcos if u == v)
    capacidades_no_positivas = sum(1 for _, _, c in arcos if c <= 0)
    demandas_no_positivas = sum(1 for _, _, d in demandas if d <= 0)
    productos_s_t_iguales = sum(1 for s, t, _ in demandas if s == t)

    nodos_sin_salida = sum(1 for u in range(1, n + 1) if grado_salida[u] == 0)
    nodos_sin_entrada = sum(1 for u in range(1, n + 1) if grado_entrada[u] == 0)
    nodos_aislados = sum(
        1
        for u in range(1, n + 1)
        if grado_salida[u] == 0 and grado_entrada[u] == 0
    )

    densidad = m / (n * (n - 1)) if n > 1 else 0.0
    grado_promedio = m / n if n else 0.0

    resumen_cap = resumen_numerico(capacidades)
    resumen_dem = resumen_numerico(volumen_demandas)
    resumen_dist = resumen_numerico(distancias_od)
    resumen_out = resumen_numerico(grado_salida[1:])
    resumen_in = resumen_numerico(grado_entrada[1:])

    alertas = []
    if nodos_aislados > 0:
        alertas.append(f"hay {nodos_aislados} nodos completamente aislados")
    if len(componentes_debiles) > 1:
        fraccion_gigante = componentes_debiles[0] / n
        if fraccion_gigante < 0.95:
            alertas.append(
                f"la mayor componente débil contiene sólo {100 * fraccion_gigante:.1f}% de los nodos"
            )
    if tamanos_scc:
        fraccion_scc = tamanos_scc[0] / n
        if fraccion_scc < 0.70:
            alertas.append(
                f"la SCC principal contiene sólo {100 * fraccion_scc:.1f}% de los nodos"
            )
    if k > 0 and k_no_alcanzable / k > 0.10:
        alertas.append(
            f"{100 * k_no_alcanzable / k:.1f}% de los commodities efectivos no tiene camino dirigido"
        )
    if duplicados > 0:
        alertas.append(f"hay {duplicados} arcos paralelos/duplicados adicionales")
    if lazos > 0:
        alertas.append(f"hay {lazos} lazos u->u")
    if capacidades_no_positivas > 0:
        alertas.append(f"hay {capacidades_no_positivas} capacidades no positivas")
    if demandas_no_positivas > 0:
        alertas.append(f"hay {demandas_no_positivas} demandas no positivas")
    if resumen_cap and resumen_cap["cv"] > 2.0:
        alertas.append("las capacidades son muy heterogéneas (CV > 2)")
    if resumen_out and resumen_out["cv"] > 1.5:
        alertas.append("el grado de salida es muy desigual (CV > 1.5)")

    print()
    print("=" * 70)
    print("ANALISIS ESTRUCTURAL DE LA RED")
    print("=" * 70)
    print(f"Nodos: {n}")
    print(f"Arcos: {m}")
    print(f"Commodities efectivos analizados: {k}")
    print(f"Densidad dirigida: {densidad:.6f}")
    print(f"Grado medio de salida/entrada: {grado_promedio:.3f}")
    print(f"Nodos sin salida: {nodos_sin_salida}")
    print(f"Nodos sin entrada: {nodos_sin_entrada}")
    print(f"Nodos aislados: {nodos_aislados}")
    print(f"Lazos: {lazos}")
    print(f"Arcos duplicados adicionales: {duplicados}")
    print(f"Reciprocidad de arcos: {100 * reciprocidad:.2f}%")

    print()
    print("CONECTIVIDAD")
    print(f"Componentes débiles: {len(componentes_debiles)}")
    if componentes_debiles:
        print(
            "Mayor componente débil: "
            f"{componentes_debiles[0]}/{n} nodos "
            f"({100 * componentes_debiles[0] / n:.2f}%)"
        )
    print(f"Componentes fuertemente conexas (SCC): {len(tamanos_scc)}")
    if tamanos_scc:
        print(
            "Mayor SCC: "
            f"{tamanos_scc[0]}/{n} nodos "
            f"({100 * tamanos_scc[0] / n:.2f}%)"
        )
        print(f"Cinco SCC más grandes: {tamanos_scc[:5]}")

    print()
    print("COMMODITIES")
    if k:
        print(
            f"Con camino dirigido: {k_alcanzable}/{k} "
            f"({100 * k_alcanzable / k:.2f}%)"
        )
        print(
            f"Sin camino dirigido: {k_no_alcanzable}/{k} "
            f"({100 * k_no_alcanzable / k:.2f}%)"
        )
    else:
        print("Sin commodities")
    print(f"Productos con origen=destino: {productos_s_t_iguales}")
    if resumen_dist:
        print(
            "Longitud OD en saltos: "
            f"media={resumen_dist['promedio']:.2f}, "
            f"mediana={resumen_dist['mediana']:.2f}, "
            f"p75={resumen_dist['p75']:.2f}, "
            f"max={resumen_dist['max']:.0f}"
        )

    print()
    print("DISTRIBUCION DE GRADOS")
    if resumen_out and resumen_in:
        print(
            "Salida: "
            f"min={resumen_out['min']:.0f}, "
            f"mediana={resumen_out['mediana']:.1f}, "
            f"media={resumen_out['promedio']:.2f}, "
            f"max={resumen_out['max']:.0f}, "
            f"CV={resumen_out['cv']:.2f}"
        )
        print(
            "Entrada: "
            f"min={resumen_in['min']:.0f}, "
            f"mediana={resumen_in['mediana']:.1f}, "
            f"media={resumen_in['promedio']:.2f}, "
            f"max={resumen_in['max']:.0f}, "
            f"CV={resumen_in['cv']:.2f}"
        )

    print()
    print("CAPACIDADES")
    if resumen_cap:
        print(
            f"min={resumen_cap['min']:.2f}, "
            f"p25={resumen_cap['p25']:.2f}, "
            f"mediana={resumen_cap['mediana']:.2f}, "
            f"p75={resumen_cap['p75']:.2f}, "
            f"max={resumen_cap['max']:.2f}, "
            f"media={resumen_cap['promedio']:.2f}, "
            f"CV={resumen_cap['cv']:.2f}"
        )
    print(f"Capacidades no positivas: {capacidades_no_positivas}")

    print()
    print("DEMANDAS")
    if resumen_dem:
        print(
            f"min={resumen_dem['min']:.2f}, "
            f"p25={resumen_dem['p25']:.2f}, "
            f"mediana={resumen_dem['mediana']:.2f}, "
            f"p75={resumen_dem['p75']:.2f}, "
            f"max={resumen_dem['max']:.2f}, "
            f"media={resumen_dem['promedio']:.2f}, "
            f"CV={resumen_dem['cv']:.2f}"
        )
    print(f"Demandas no positivas: {demandas_no_positivas}")

    print()
    print("DIAGNOSTICO ORIENTATIVO")
    if alertas:
        print("La red merece revisión por los siguientes motivos:")
        for alerta in alertas:
            print(f"  - {alerta}")
    else:
        print(
            "No aparecen anomalías estructurales obvias con estos indicadores. "
            "Esto no demuestra que la red sea realista, pero sí descarta varias "
            "formas comunes de degeneración topológica."
        )

    print("=" * 70)
    print()

    return {
        "n": n,
        "m": m,
        "k": k,
        "densidad": densidad,
        "componentes_debiles": len(componentes_debiles),
        "mayor_componente_debil": componentes_debiles[0] if componentes_debiles else 0,
        "scc": len(tamanos_scc),
        "mayor_scc": tamanos_scc[0] if tamanos_scc else 0,
        "commodities_alcanzables": k_alcanzable,
        "commodities_no_alcanzables": k_no_alcanzable,
        "reciprocidad": reciprocidad,
        "alertas": alertas,
    }

