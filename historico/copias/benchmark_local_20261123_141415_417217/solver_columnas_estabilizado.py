import heapq
import math
import time
from collections import defaultdict

import gurobipy as gp
from gurobipy import GRB

from lector import arcos, demandas, n


# Parámetros del algoritmo.
TOLERANCIA = 1e-7
MAX_ITERACIONES = 1000
LIMITE_TIEMPO = 900
INTERVALO_PROGRESO = 1

# Peso de los duales actuales en el promedio estabilizado.
# ALPHA = 1.0 reproduce el pricing del solver original.
ALPHA = 0.4

if not 0.0 < ALPHA <= 1.0:
    raise ValueError("ALPHA debe pertenecer al intervalo (0, 1].")

# Conjuntos y parámetros de la red.
nodos = range(1, n + 1)
ids_arcos = [arco["id"] for arco in arcos]
capacidad = {arco["id"]: arco["capacidad"] for arco in arcos}
datos_producto = {demanda["producto"]: demanda for demanda in demandas}
productos = list(datos_producto)

# Grafo dirigido y productos agrupados por origen.
adyacencia = {nodo: [] for nodo in nodos}
for arco in arcos:
    adyacencia[arco["origen"]].append((arco["destino"], arco["id"]))

productos_por_origen = defaultdict(list)
for producto, datos in datos_producto.items():
    productos_por_origen[datos["origen"]].append(producto)


def dijkstra(origen, pesos):
    """Calcula caminos mínimos desde un origen con pesos no negativos."""
    distancia = {origen: 0.0}
    predecesor = {}
    cola = [(0.0, origen)]

    while cola:
        distancia_actual, nodo = heapq.heappop(cola)
        if distancia_actual > distancia.get(nodo, math.inf):
            continue

        for destino, arco in adyacencia[nodo]:
            nueva_distancia = distancia_actual + pesos[arco]
            if nueva_distancia < distancia.get(destino, math.inf) - 1e-15:
                distancia[destino] = nueva_distancia
                predecesor[destino] = (nodo, arco)
                heapq.heappush(cola, (nueva_distancia, destino))

    return distancia, predecesor


def reconstruir_camino(origen, destino, predecesor):
    """Reconstruye una ruta como una tupla de identificadores de arcos."""
    camino = []
    nodo = destino

    while nodo != origen:
        if nodo not in predecesor:
            return None
        nodo, arco = predecesor[nodo]
        camino.append(arco)

    return tuple(reversed(camino))


def caminos_minimos(pesos):
    """Obtiene la ruta de menor precio para cada producto."""
    resultado = {}

    # Los productos con igual origen comparten una ejecución de Dijkstra.
    for origen, grupo in productos_por_origen.items():
        distancias, predecesor = dijkstra(origen, pesos)

        for producto in grupo:
            destino = datos_producto[producto]["destino"]
            camino = reconstruir_camino(origen, destino, predecesor)
            if camino is None:
                raise ValueError(
                    f"No existe camino para el producto {producto}: "
                    f"{origen} -> {destino}"
                )
            resultado[producto] = distancias[destino], camino

    return resultado


# Problema maestro restringido.
inicio = time.perf_counter()
print("\nSolver: generación de columnas con estabilización dual", flush=True)
print(
    f"Productos: {len(productos)} | Arcos: {len(ids_arcos)} | "
    f"ALPHA: {ALPHA}",
    flush=True,
)
print("Construyendo el problema maestro restringido...", flush=True)

modelo = gp.Model("generacion_columnas")
modelo.Params.Method = 1  # Dual simplex facilita la reoptimización.
modelo.Params.OutputFlag = 0

# z mide la máxima utilización relativa de los arcos.
z = modelo.addVar(lb=0, obj=1, name="z")

# Cada producto debe enviar exactamente toda su demanda.
restriccion_demanda = {
    producto: modelo.addConstr(
        gp.LinExpr() == datos_producto[producto]["demanda"],
        name=f"demanda_{producto}",
    )
    for producto in productos
}

# El flujo total del arco queda limitado por capacidad[a] * z.
restriccion_capacidad = {
    arco: modelo.addConstr(
        -capacidad[arco] * z <= 0,
        name=f"capacidad_{arco}",
    )
    for arco in ids_arcos
}

variables = {}
caminos_conocidos = {producto: set() for producto in productos}


def agregar_columna(producto, camino):
    """Agrega al maestro una variable de flujo asociada a una ruta."""
    if camino in caminos_conocidos[producto]:
        return False

    columna = gp.Column()
    columna.addTerms(1, restriccion_demanda[producto])
    for arco in camino:
        columna.addTerms(1, restriccion_capacidad[arco])

    numero = len(caminos_conocidos[producto])
    variables[producto, camino] = modelo.addVar(
        lb=0,
        obj=0,
        name=f"f_{producto}_{numero}",
        column=columna,
    )
    caminos_conocidos[producto].add(camino)
    return True


# Una ruta inicial por producto hace factible el primer maestro restringido.
pesos_iniciales = {arco: (1 / capacidad[arco]) for arco in ids_arcos}
inicio_caminos = time.perf_counter()
print("Calculando caminos iniciales...", flush=True)
for producto, (_, camino) in caminos_minimos(pesos_iniciales).items():
    agregar_columna(producto, camino)
modelo.update()
tiempo_caminos = time.perf_counter() - inicio_caminos
print(
    f"Caminos iniciales listos: {len(variables)} columnas "
    f"en {tiempo_caminos:.2f}s.",
    flush=True,
)


# Ciclo clásico: resolver el maestro, obtener duales y ejecutar el pricing.
optimo_certificado = False
iteracion = 0
precios_estabilizados = None
duales_demanda_estabilizados = None

while iteracion < MAX_ITERACIONES:
    iteracion += 1
    mostrar_progreso = (
        iteracion <= 3
        or iteracion % INTERVALO_PROGRESO == 0
    )
    tiempo_restante = LIMITE_TIEMPO - (time.perf_counter() - inicio)
    if tiempo_restante <= 0:
        break

    modelo.Params.TimeLimit = tiempo_restante
    inicio_maestro = time.perf_counter()
    if mostrar_progreso:
        print(
            f"Iteración {iteracion}: resolviendo maestro con "
            f"{len(variables)} columnas...",
            flush=True,
        )
    modelo.optimize()
    tiempo_maestro = time.perf_counter() - inicio_maestro
    if modelo.Status != GRB.OPTIMAL:
        break

    valor_z = z.X

    # En estas restricciones <=, los duales son no positivos. Su opuesto
    # entrega pesos no negativos, aptos para el camino mínimo de Dijkstra.
    precios_actuales = {
        arco: max(0, -restriccion_capacidad[arco].Pi)
        for arco in ids_arcos
    }
    duales_demanda_actuales = {
        producto: restriccion_demanda[producto].Pi
        for producto in productos
    }

    # En la primera iteración el pricing coincide con el original. Luego se
    # utiliza un promedio exponencial entre los duales actuales y el centro.
    pricing_estabilizado_es_exacto = precios_estabilizados is None
    if precios_estabilizados is None:
        precios_estabilizados = dict(precios_actuales)
        duales_demanda_estabilizados = dict(duales_demanda_actuales)
    else:
        precios_estabilizados = {
            arco: (
                ALPHA * precios_actuales[arco]
                + (1.0 - ALPHA) * precios_estabilizados[arco]
            )
            for arco in ids_arcos
        }
        duales_demanda_estabilizados = {
            producto: (
                ALPHA * duales_demanda_actuales[producto]
                + (1.0 - ALPHA) * duales_demanda_estabilizados[producto]
            )
            for producto in productos
        }
        if ALPHA == 1.0:
            pricing_estabilizado_es_exacto = True

    nuevas = 0
    menor_costo_reducido = 0.0
    pricing_exacto_respaldo = False

    inicio_pricing = time.perf_counter()
    resultado_estabilizado = caminos_minimos(precios_estabilizados)
    for producto, (precio_estabilizado, camino) in resultado_estabilizado.items():
        costo_reducido_estabilizado = (
            precio_estabilizado
            - duales_demanda_estabilizados[producto]
        )
        if costo_reducido_estabilizado >= -TOLERANCIA:
            continue

        # Una ruta sugerida por los duales suavizados solo se incorpora si
        # también mejora el maestro bajo los duales actuales.
        precio_actual = math.fsum(
            precios_actuales[arco]
            for arco in camino
        )
        costo_reducido_actual = (
            precio_actual
            - duales_demanda_actuales[producto]
        )
        menor_costo_reducido = min(
            menor_costo_reducido,
            costo_reducido_actual,
        )
        if costo_reducido_actual < -TOLERANCIA:
            nuevas += agregar_columna(producto, camino)

    # Si el pricing estabilizado no logra avanzar, se ejecuta el pricing
    # original. Solo este chequeo exacto puede certificar que no quedan
    # columnas de costo reducido negativo.
    if nuevas == 0 and not pricing_estabilizado_es_exacto:
        pricing_exacto_respaldo = True
        resultado_exacto = caminos_minimos(precios_actuales)
        for producto, (precio_ruta, camino) in resultado_exacto.items():
            costo_reducido = (
                precio_ruta
                - duales_demanda_actuales[producto]
            )
            menor_costo_reducido = min(
                menor_costo_reducido,
                costo_reducido,
            )
            if costo_reducido < -TOLERANCIA:
                nuevas += agregar_columna(producto, camino)

    tiempo_pricing = time.perf_counter() - inicio_pricing
    modelo.update()
    if mostrar_progreso or nuevas == 0:
        respaldo = "sí" if pricing_exacto_respaldo else "no"
        print(
            f"Iteración {iteracion}: z={valor_z:.8f} | "
            f"columnas={len(variables)} | nuevas={nuevas} | "
            f"costo reducido={menor_costo_reducido:.3e} | "
            f"respaldo exacto={respaldo} | "
            f"maestro={tiempo_maestro:.2f}s | pricing={tiempo_pricing:.2f}s",
            flush=True,
        )

    # Si no se agregaron columnas después de un pricing exacto, el óptimo
    # del maestro completo queda certificado por dualidad lineal.
    if nuevas == 0:
        optimo_certificado = True
        break


# Recuperación y presentación de la solución por arcos.
tiempo_total = time.perf_counter() - inicio

if optimo_certificado:
    flujo_arco = {arco: 0.0 for arco in ids_arcos}
    for (_, camino), variable in variables.items():
        if variable.X > 1e-10:
            for arco in camino:
                flujo_arco[arco] += variable.X

    resultados = [
        (flujo_arco[arco["id"]] / arco["capacidad"], flujo_arco[arco["id"]], arco)
        for arco in arcos
    ]
    resultados.sort(key=lambda resultado: resultado[0], reverse=True)

    print("\nSolución óptima certificada")
    print(f"Congestión máxima: {z.X:.8f} ({100 * z.X:.2f}%)")
    print(f"Iteraciones: {iteracion} | Columnas: {len(variables)}")
    print(f"Tiempo total: {tiempo_total:.2f} segundos")
    print("\nDiez arcos más congestionados:")

    for utilizacion, flujo, arco in resultados[:10]:
        print(
            f"Arco {arco['id']}: {arco['origen']} -> {arco['destino']} | "
            f"flujo={flujo:.2f} | capacidad={arco['capacidad']} | "
            f"congestión={utilizacion:.4f}"
        )
else:
    print("\nNo se certificó el óptimo mediante generación de columnas.")
    print(f"Iteraciones: {iteracion} | Columnas: {len(variables)}")
    print(f"Tiempo total: {tiempo_total:.2f} segundos")
