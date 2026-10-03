"""Generacion de columnas con el problema satelite resuelto por Gurobi.

El problema maestro y la salida son compatibles con ``solver_columnas.py``.
La diferencia es que, para cada origen, las etiquetas de caminos minimos se
obtienen resolviendo con Gurobi el LP dual de caminos minimos:

    max  sum_v distancia[v]
    s.a. distancia[v] - distancia[u] <= peso[u, v]
         distancia[origen] = 0

Como todos los nodos alcanzables aparecen con coeficiente positivo en el
objetivo, sus valores optimos son simultaneamente las distancias minimas desde
el origen. Los modelos se construyen una sola vez y se reoptimizan cambiando
unicamente los lados derechos de las restricciones de arco.
"""

from collections import defaultdict, deque
import math
import time

import gurobipy as gp
from gurobipy import GRB

from lector import arcos, demandas, n


# Parametros del algoritmo.
TOLERANCIA = 1e-7
MAX_ITERACIONES = 1000
LIMITE_TIEMPO = 900
INTERVALO_PROGRESO = 1

# Conjuntos y parametros de la red.
nodos = range(1, n + 1)
ids_arcos = [arco["id"] for arco in arcos]
capacidad = {arco["id"]: arco["capacidad"] for arco in arcos}
datos_producto = {demanda["producto"]: demanda for demanda in demandas}
productos = list(datos_producto)

datos_arco = {
    arco["id"]: (arco["origen"], arco["destino"])
    for arco in arcos
}
adyacencia = {nodo: [] for nodo in nodos}
for arco in arcos:
    adyacencia[arco["origen"]].append((arco["destino"], arco["id"]))

productos_por_origen = defaultdict(list)
for producto, datos in datos_producto.items():
    productos_por_origen[datos["origen"]].append(producto)


def nodos_alcanzables(origen):
    """Devuelve los nodos alcanzables desde un origen, ignorando los pesos."""
    vistos = {origen}
    cola = [origen]
    while cola:
        nodo = cola.pop()
        for destino, _ in adyacencia[nodo]:
            if destino not in vistos:
                vistos.add(destino)
                cola.append(destino)
    return vistos


class SateliteGurobi:
    """LP reutilizable que obtiene todos los caminos minimos de un origen."""

    def __init__(self, origen, destinos_requeridos):
        self.origen = origen
        self.destinos_requeridos = set(destinos_requeridos)
        self.alcanzables = nodos_alcanzables(origen)

        faltantes = self.destinos_requeridos - self.alcanzables
        if faltantes:
            muestra = sorted(faltantes)[:10]
            raise ValueError(
                f"No existen caminos desde {origen} a los destinos {muestra}"
            )

        self.modelo = gp.Model(f"pricing_origen_{origen}")
        self.modelo.Params.OutputFlag = 0
        # Al cambiar RHS, la base anterior conserva factibilidad dual.
        self.modelo.Params.Method = 1
        self.modelo.Params.Presolve = 0
        self.modelo.Params.Threads = 1

        self.distancia = self.modelo.addVars(
            sorted(self.alcanzables),
            lb=-GRB.INFINITY,
            name="distancia",
        )
        self.modelo.addConstr(
            self.distancia[origen] == 0,
            name="ancla",
        )

        self.ids_restricciones = []
        self.restricciones_arco = []
        for arco in ids_arcos:
            u, v = datos_arco[arco]
            if u not in self.alcanzables:
                continue
            # Si u es alcanzable, v tambien debe serlo.
            restriccion = self.modelo.addConstr(
                self.distancia[v] - self.distancia[u] <= 0,
                name=f"arco_{arco}",
            )
            self.ids_restricciones.append(arco)
            self.restricciones_arco.append(restriccion)

        self.modelo.setObjective(
            gp.quicksum(
                self.distancia[nodo]
                for nodo in self.alcanzables
                if nodo != origen
            ),
            GRB.MAXIMIZE,
        )
        self.modelo.update()

    def resolver(self, pesos, limite_tiempo):
        """Resuelve el pricing y devuelve costo y camino por destino."""
        if limite_tiempo <= 0:
            raise TimeoutError("Se agoto el limite global de tiempo")

        self.modelo.Params.TimeLimit = limite_tiempo
        self.modelo.setAttr(
            GRB.Attr.RHS,
            self.restricciones_arco,
            [pesos[arco] for arco in self.ids_restricciones],
        )
        self.modelo.optimize()

        if self.modelo.Status != GRB.OPTIMAL:
            if self.modelo.Status == GRB.TIME_LIMIT:
                raise TimeoutError("El pricing alcanzo el limite de tiempo")
            raise RuntimeError(
                f"Pricing de origen {self.origen}: estado Gurobi "
                f"{self.modelo.Status}"
            )

        etiquetas = {
            nodo: self.distancia[nodo].X
            for nodo in self.alcanzables
        }
        predecesor = self._arbol_de_arcos_ajustados(etiquetas, pesos)

        resultado = {}
        for destino in self.destinos_requeridos:
            camino = self._reconstruir(destino, predecesor)
            # Se recalcula con los pesos originales para que el costo reducido
            # no dependa del error numerico de las etiquetas de Gurobi.
            costo = math.fsum(pesos[arco] for arco in camino)
            resultado[destino] = costo, camino
        return resultado

    def _arbol_de_arcos_ajustados(self, etiquetas, pesos):
        """Construye un arbol usando arcos ajustados del LP de distancias."""
        # Normalmente 1e-9 basta. Los valores mayores son una proteccion frente
        # al escalamiento y a las tolerancias internas del solver.
        for tolerancia in (1e-9, 1e-8, 1e-7, 1e-6, 1e-5):
            visitados = {self.origen}
            predecesor = {}
            cola = deque([self.origen])

            while cola:
                u = cola.popleft()
                for v, arco in adyacencia[u]:
                    if v in visitados or v not in self.alcanzables:
                        continue
                    peso = pesos[arco]
                    holgura = peso - (etiquetas[v] - etiquetas[u])
                    escala = max(
                        1.0,
                        abs(peso),
                        abs(etiquetas[u]),
                        abs(etiquetas[v]),
                    )
                    if holgura <= tolerancia * escala:
                        visitados.add(v)
                        predecesor[v] = (u, arco)
                        cola.append(v)

            if self.destinos_requeridos <= visitados:
                return predecesor

        faltantes = sorted(self.destinos_requeridos - visitados)[:10]
        raise ArithmeticError(
            f"No se pudo reconstruir un camino ajustado desde "
            f"{self.origen} a {faltantes}; revise el escalamiento numerico"
        )

    def _reconstruir(self, destino, predecesor):
        camino = []
        nodo = destino
        while nodo != self.origen:
            if nodo not in predecesor:
                raise ArithmeticError(
                    f"Arbol de pricing incompleto: {self.origen} -> {destino}"
                )
            nodo, arco = predecesor[nodo]
            camino.append(arco)
        camino.reverse()
        return tuple(camino)


# Problema maestro restringido.
inicio = time.perf_counter()
print("\nSolver: generación de columnas", flush=True)
print(
    f"Productos: {len(productos)} | Arcos: {len(ids_arcos)}",
    flush=True,
)
print("Construyendo el problema maestro restringido...", flush=True)

modelo = gp.Model("generacion_columnas")
modelo.Params.Method = 1
modelo.Params.OutputFlag = 0

z = modelo.addVar(lb=0, obj=1, name="z")

restriccion_demanda = {
    producto: modelo.addConstr(
        gp.LinExpr() == datos_producto[producto]["demanda"],
        name=f"demanda_{producto}",
    )
    for producto in productos
}

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

    restricciones = [restriccion_demanda[producto]]
    restricciones.extend(restriccion_capacidad[arco] for arco in camino)
    columna = gp.Column([1.0] * len(restricciones), restricciones)

    numero = len(caminos_conocidos[producto])
    variables[producto, camino] = modelo.addVar(
        lb=0,
        obj=0,
        name=f"f_{producto}_{numero}",
        column=columna,
    )
    caminos_conocidos[producto].add(camino)
    return True


# Se crea un LP satelite por origen y se reutiliza durante toda la ejecucion.
satelites = {}
for origen, grupo in productos_por_origen.items():
    destinos = {
        datos_producto[producto]["destino"]
        for producto in grupo
    }
    satelites[origen] = SateliteGurobi(origen, destinos)


def caminos_minimos(pesos, tiempo_disponible):
    """Obtiene mediante Gurobi la ruta de menor precio de cada producto."""
    resultado = {}
    instante_limite = time.perf_counter() + tiempo_disponible

    for origen, grupo in productos_por_origen.items():
        restante = instante_limite - time.perf_counter()
        por_destino = satelites[origen].resolver(pesos, restante)
        for producto in grupo:
            destino = datos_producto[producto]["destino"]
            resultado[producto] = por_destino[destino]
    return resultado


# Una ruta inicial por producto hace factible el primer maestro restringido.
pesos_iniciales = {arco: 1 / capacidad[arco] for arco in ids_arcos}
inicio_caminos = time.perf_counter()
print("Calculando caminos iniciales...", flush=True)
tiempo_restante = LIMITE_TIEMPO - (time.perf_counter() - inicio)
for producto, (_, camino) in caminos_minimos(
    pesos_iniciales,
    tiempo_restante,
).items():
    agregar_columna(producto, camino)
modelo.update()
tiempo_caminos = time.perf_counter() - inicio_caminos
print(
    f"Caminos iniciales listos: {len(variables)} columnas "
    f"en {tiempo_caminos:.2f}s.",
    flush=True,
)


# Ciclo clasico: resolver el maestro, obtener duales y ejecutar el pricing.
optimo_certificado = False
iteracion = 0

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
    precios_arcos = {
        arco: max(0.0, -restriccion_capacidad[arco].Pi)
        for arco in ids_arcos
    }

    nuevas = 0
    menor_costo_reducido = 0.0

    inicio_pricing = time.perf_counter()
    tiempo_restante = LIMITE_TIEMPO - (time.perf_counter() - inicio)
    try:
        resultado_pricing = caminos_minimos(precios_arcos, tiempo_restante)
    except TimeoutError:
        break

    for producto, (precio_ruta, camino) in resultado_pricing.items():
        dual_demanda = restriccion_demanda[producto].Pi
        costo_reducido = precio_ruta - dual_demanda
        menor_costo_reducido = min(menor_costo_reducido, costo_reducido)

        if costo_reducido < -TOLERANCIA:
            nuevas += agregar_columna(producto, camino)

    tiempo_pricing = time.perf_counter() - inicio_pricing
    modelo.update()
    if mostrar_progreso or nuevas == 0:
        print(
            f"Iteración {iteracion}: z={valor_z:.8f} | "
            f"columnas={len(variables)} | nuevas={nuevas} | "
            f"costo reducido={menor_costo_reducido:.3e} | "
            f"maestro={tiempo_maestro:.2f}s | pricing={tiempo_pricing:.2f}s",
            flush=True,
        )

    if nuevas == 0:
        optimo_certificado = True
        break


# Recuperacion y presentacion de la solucion por arcos.
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
