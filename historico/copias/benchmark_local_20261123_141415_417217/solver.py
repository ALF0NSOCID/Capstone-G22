import gurobipy as gp
from gurobipy import GRB

# Datos procesados por lector.py.
from lector import arcos, balances, demandas, n

# Usa exclusivamente los commodities que sobrevivieron al filtro de
# conectividad aplicado en lector.py. El diccionario `balances` puede
# conservar entradas de productos eliminados, pero no se usan porque el
# modelo itera solo sobre esta lista filtrada.
productos = [int(demanda["producto"]) for demanda in demandas]

# Conjuntos de nodos, productos y arcos usados por el modelo.
nodos = range(1, n + 1)
ids_arcos = [arco["id"] for arco in arcos]

# Parámetros de demanda y capacidad indexados por sus identificadores.
capacidad = {arco["id"]: arco["capacidad"] for arco in arcos}

# Listas de adyacencia para calcular el flujo que entra y sale de cada nodo.
salientes = {nodo: [] for nodo in nodos}
entrantes = {nodo: [] for nodo in nodos}

for arco in arcos:
    salientes[arco["origen"]].append(arco["id"])
    entrantes[arco["destino"]].append(arco["id"])


# Modelo lineal de flujo multiproducto con mínima congestión máxima.
modelo = gp.Model("flujo_multiproducto")

# x[k, a] es el flujo del producto k por el arco a.
# z representa la mayor proporción de capacidad utilizada en cualquier arco.
x = modelo.addVars(productos, ids_arcos, lb=0, name="x")
z = modelo.addVar(lb=0, name="z")

# Conservación de flujo para cada producto en cada nodo.
for producto in productos:
    for nodo in nodos:
        # El balance puede incluir varios origenes y destinos por producto.
        balance = balances.get((producto, nodo), 0)
        modelo.addConstr(
            gp.quicksum(x[producto, arco] for arco in salientes[nodo])
            - gp.quicksum(x[producto, arco] for arco in entrantes[nodo])
            == balance,
            name=f"balance_{producto}_{nodo}",
        )

# La suma de flujos de un arco no puede superar su capacidad multiplicada
# por z; por eso minimizar z reduce la peor congestión de toda la red.
for arco in ids_arcos:
    modelo.addConstr(
        gp.quicksum(x[producto, arco] for producto in productos)
        <= capacidad[arco] * z,
        name=f"capacidad_{arco}",
    )

# Función objetivo y límite máximo de ejecución.
modelo.setObjective(z, GRB.MINIMIZE)
modelo.Params.TimeLimit = 900
modelo.Params.Crossover = 0
modelo.optimize()


# Si existe una solución factible, se resume la congestión de la red.
if modelo.SolCount > 0:
    print(f"\nCongestión máxima: {z.X:.4f} ({100 * z.X:.2f}%)")

    resultados = []
    for arco in arcos:
        id_arco = arco["id"]
        flujo = sum(x[producto, id_arco].X for producto in productos)
        resultados.append((flujo / arco["capacidad"], arco, flujo))

    # Ordena los arcos desde el más congestionado al menos congestionado.
    print("\nDiez arcos más congestionados:")
    resultados.sort(key=lambda resultado: resultado[0], reverse=True)
    for congestion, arco, flujo in resultados[:10]:
        print(
            f"Arco {arco['id']}: {arco['origen']} -> {arco['destino']} | "
            f"flujo={flujo:.2f} | capacidad={arco['capacidad']} | "
            f"congestión={congestion:.4f}"
        )
# Mensajes para los casos en que no se obtiene una solución factible.
elif modelo.Status == GRB.INFEASIBLE:
    print("\nEl modelo es infactible.")
else:
    print(f"\nGurobi terminó sin solución factible. Estado: {modelo.Status}")
