import os
from collections import defaultdict
from pathlib import Path

from corrector_conectividad import corregir_conectividad


RUTA_INSTANCIA = Path(
    os.environ.get(
        "ARCHIVO_INSTANCIA",
        Path(__file__).resolve().parent / "out",
    )
)


def _leer_enteros(linea, cantidad, descripcion):
    """Interpreta enteros separados por espacios o en campos Fortran ``i8``."""
    if linea == "":
        raise ValueError(f"{descripcion}: fin de archivo inesperado")

    campos = linea.split()
    if len(campos) == cantidad:
        try:
            return tuple(map(int, campos))
        except ValueError:
            pass

    # Mulgen escribe sus datos con FORMAT(...i8). Si un numero negativo ocupa
    # los ocho caracteres, queda pegado al campo anterior (por ejemplo,
    # ``     107-1059620``) y split() no puede separarlos.
    texto = linea.rstrip("\r\n")
    ancho_total = cantidad * 8
    if len(texto) >= ancho_total and not texto[ancho_total:].strip():
        campos_fijos = [
            texto[inicio:inicio + 8].strip()
            for inicio in range(0, ancho_total, 8)
        ]
        if all(campos_fijos):
            try:
                return tuple(map(int, campos_fijos))
            except ValueError:
                pass

    raise ValueError(f"{descripcion}: {campos}")


def leer_instancia(ruta):
    """Lee una instancia Canad y valida todos sus balances."""
    with Path(ruta).open("r", encoding="utf-8") as archivo:
        numero_nodos, numero_arcos, numero_productos = _leer_enteros(
            archivo.readline(),
            3,
            "La cabecera debe contener n, m y K",
        )
        lista_arcos = []

        for id_arco in range(numero_arcos):
            origen, destino, costo_fijo, capacidad_global, q = _leer_enteros(
                archivo.readline(),
                5,
                f"Cabecera invalida para el arco {id_arco}",
            )

            # Los solvers usan únicamente la capacidad global. MULGEN escribe
            # además una fila por commodity y arco; se consume ese bloque sin
            # convertirlo ni conservarlo para evitar millones de objetos sin uso.
            for _ in range(q):
                if archivo.readline() == "":
                    raise ValueError(
                        f"Detalle incompleto para el arco {id_arco}: "
                        "fin de archivo inesperado"
                    )

            lista_arcos.append({
                "id": id_arco,
                "origen": origen,
                "destino": destino,
                "costo_fijo": costo_fijo,
                "capacidad": capacidad_global,
            })

        diccionario_balances = {}
        for numero_linea, linea in enumerate(archivo, start=numero_arcos + 2):
            if not linea.strip():
                continue

            producto, nodo, cantidad = _leer_enteros(
                linea,
                3,
                f"Balance invalido en la linea {numero_linea}",
            )
            clave = (producto, nodo)
            diccionario_balances[clave] = (
                diccionario_balances.get(clave, 0) + cantidad
            )

    productos_instancia = list(range(1, numero_productos + 1))
    ofertas = defaultdict(list)
    destinos = defaultdict(list)

    for (producto, nodo), cantidad in diccionario_balances.items():
        if not 1 <= producto <= numero_productos:
            raise ValueError(f"Producto fuera de rango: {producto}")
        if not 1 <= nodo <= numero_nodos:
            raise ValueError(f"Nodo fuera de rango: {nodo}")

        if cantidad > 0:
            ofertas[producto].append((nodo, cantidad))
        elif cantidad < 0:
            destinos[producto].append((nodo, -cantidad))

    datos_demandas = []
    productos_no_od = []

    for producto in productos_instancia:
        oferta_total = sum(cantidad for _, cantidad in ofertas[producto])
        demanda_total = sum(cantidad for _, cantidad in destinos[producto])

        if oferta_total != demanda_total:
            raise ValueError(
                f"Producto {producto} desbalanceado: "
                f"oferta total={oferta_total}, demanda total={demanda_total}"
            )
        if oferta_total == 0:
            raise ValueError(f"El producto {producto} no tiene oferta ni demanda.")

        datos = {
            "producto": producto,
            "origenes": ofertas[producto],
            "destinos": destinos[producto],
            "demanda": demanda_total,
        }

        if len(ofertas[producto]) == 1 and len(destinos[producto]) == 1:
            datos["origen"] = ofertas[producto][0][0]
            datos["destino"] = destinos[producto][0][0]
        else:
            productos_no_od.append(producto)

        datos_demandas.append(datos)

    return (
        numero_nodos,
        numero_arcos,
        numero_productos,
        lista_arcos,
        productos_instancia,
        diccionario_balances,
        datos_demandas,
        productos_no_od,
    )


(
    n,
    m,
    K,
    arcos,
    productos,
    balances,
    demandas,
    productos_no_od,
) = leer_instancia(RUTA_INSTANCIA)

# Comenta la siguiente linea para usar la red original sin corregir.
arcos = corregir_conectividad(n, arcos, demandas, semilla=1010)

es_origen_destino_simple = not productos_no_od

print(f"Nodos: {n}")
print(f"Arcos: {m}")
print(f"Productos: {K}")
if productos_no_od:
    print(
        "Productos con multiples origenes o destinos: "
        f"{len(productos_no_od)}"
    )
