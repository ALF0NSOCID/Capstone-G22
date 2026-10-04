import time

import gurobipy as gp
from gurobipy import GRB

try:
    from pricing_cpp import MotorCaminos
except ImportError as error:
    raise SystemExit(
        "No se encontró el módulo pricing_cpp. Compílalo una vez con:\n"
        "  python3 setup_pricing_cpp.py build_ext --inplace"
    ) from error

from lector import arcos, demandas, n


# Parámetros del algoritmo: iguales a solver_columnas.py.
TOLERANCIA = 1e-7
MAX_ITERACIONES = 1000
LIMITE_TIEMPO = 900
INTERVALO_PROGRESO = 1

# Conjuntos y parámetros de la red.
nodos = range(1, n + 1)
ids_arcos = [arco["id"] for arco in arcos]
capacidad = {arco["id"]: arco["capacidad"] for arco in arcos}
datos_producto = {demanda["producto"]: demanda for demanda in demandas}
productos = list(datos_producto)

# El motor C++ usa el índice de cada arco como identificador interno. El lector
# actual ya garantiza IDs consecutivos; esta validación evita errores silenciosos.
if ids_arcos != list(range(len(arcos))):
    raise ValueError(
        "solver_columnas_cpp requiere identificadores de arco consecutivos "
        "desde cero."
    )

motor_caminos = MotorCaminos(
    n,
    [arco["origen"] for arco in arcos],
    [arco["destino"] for arco in arcos],
    productos,
    [datos_producto[producto]["origen"] for producto in productos],
    [datos_producto[producto]["destino"] for producto in productos],
)


def vector_pesos(pesos):
    """Convierte el diccionario del maestro al vector contiguo usado por C++."""
    return [pesos[arco] for arco in ids_arcos]


def caminos_minimos(pesos):
    """Mantiene la interfaz del solver original usando el motor C++."""
    return {
        producto: (distancia, tuple(camino))
        for producto, distancia, camino in motor_caminos.caminos_minimos(
            vector_pesos(pesos)
        )
    }


# Problema maestro restringido.
inicio = time.perf_counter()
print("\nSolver: generación de columnas (pricing C++)", flush=True)
print(
    f"Productos: {len(productos)} | Arcos: {len(ids_arcos)}",
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

    # Una sola llamada entrega todos los términos de capacidad a Gurobi.
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
    # entrega pesos no negativos, aptos para Dijkstra.
    precios_arcos = [
        max(0, -restriccion_capacidad[arco].Pi)
        for arco in ids_arcos
    ]
    duales_productos = [
        restriccion_demanda[producto].Pi
        for producto in productos
    ]

    nuevas = 0
    inicio_pricing = time.perf_counter()
    menor_costo_reducido, candidatas = motor_caminos.pricing(
        precios_arcos,
        duales_productos,
        TOLERANCIA,
    )

    for producto, _, camino_cpp in candidatas:
        nuevas += agregar_columna(producto, tuple(camino_cpp))

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

    # Sin costos reducidos negativos, el óptimo del maestro completo queda
    # certificado por dualidad lineal.
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
