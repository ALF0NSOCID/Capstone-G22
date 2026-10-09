"""Genera el diseño experimental de escalabilidad para Mulgen.

El experimento contiene 47 configuraciones y tres semillas por configuracion.
Los archivos se escriben como Canad/Data/t_1.par, ..., t_141.par junto con
un manifiesto CSV que documenta cada ejecucion.
"""

import csv
from pathlib import Path


RAIZ = Path(__file__).resolve().parent
CARPETA_DATOS = RAIZ / "Canad" / "Data"
MANIFIESTO = RAIZ / "benchmark_escalabilidad.csv"
SEMILLAS = (42, 2068, 363524)

# Factores elegidos para conservar una geometria rectangular parecida a la
# instancia oficial, sin dejar de cumplir scalex * scaley = nodos.
DIMENSIONES = {
    50: (10, 5),
    80: (20, 4),
    100: (20, 5),
    160: (20, 8),
    200: (25, 8),
    320: (40, 8),
    400: (40, 10),
    800: (50, 16),
    1200: (60, 20),
    1600: (80, 20),
    2500: (100, 25),
}


def agregar(configuraciones, vistos, bloque, nodos, grado, productos_nodo):
    """Agrega una configuracion una sola vez."""
    arcos = round(grado * nodos)
    productos = round(productos_nodo * nodos)
    clave = (nodos, arcos, productos)
    if clave in vistos:
        return
    vistos.add(clave)
    configuraciones.append(
        {
            "bloque": bloque,
            "nodos": nodos,
            "arcos": arcos,
            "productos": productos,
            "grado_objetivo": grado,
            "productos_por_nodo": productos_nodo,
        }
    )


def construir_configuraciones():
    configuraciones = []
    vistos = set()

    # 1. Escalamiento disperso con las proporciones de la instancia oficial.
    for nodos in DIMENSIONES:
        agregar(configuraciones, vistos, "escalamiento", nodos, 6.5, 25)

    # 2. Efecto del grado medio en tres escalas.
    for nodos in (100, 400, 1600):
        for grado in (3, 4, 6.5, 8, 12, 16, 24):
            agregar(configuraciones, vistos, "grado", nodos, grado, 25)

    # 3. Efecto de la cantidad de productos.
    for nodos in (100, 400, 1600):
        for productos_nodo in (2, 5, 10, 25, 50):
            agregar(
                configuraciones,
                vistos,
                "productos",
                nodos,
                6.5,
                productos_nodo,
            )

    # 4. Interaccion densidad-productos alrededor de N=400.
    for grado in (4, 8, 16):
        for productos_nodo in (10, 50):
            agregar(
                configuraciones,
                vistos,
                "interaccion",
                400,
                grado,
                productos_nodo,
            )

    if len(configuraciones) != 47:
        raise RuntimeError(
            f"Se esperaban 47 configuraciones y se obtuvieron "
            f"{len(configuraciones)}."
        )
    return configuraciones


def contenido_par(configuracion, semilla):
    nodos = configuracion["nodos"]
    scalex, scaley = DIMENSIONES[nodos]
    return f"""nocca
inseed {semilla}
ctight 60.0
fixvar 0.01
noprll 10
grdarc 0
scalex {scalex}
scaley {scaley}
commod {configuracion['productos']}
addarc {configuracion['arcos']}
minsrc 1
maxsrc 1
minsnk 1
maxsnk 1
minfct 10
maxfct 100
mincst 1
maxcst 10
minsup 15
maxsup 75
mincap 100
maxcap 500
outfil out
end
"""


def main():
    CARPETA_DATOS.mkdir(parents=True, exist_ok=True)
    configuraciones = construir_configuraciones()
    filas = []
    indice = 1

    for numero_configuracion, configuracion in enumerate(configuraciones, 1):
        for semilla in SEMILLAS:
            nombre = f"t_{indice}"
            archivo = CARPETA_DATOS / f"{nombre}.par"
            archivo.write_text(
                contenido_par(configuracion, semilla),
                encoding="utf-8",
            )

            nodos = configuracion["nodos"]
            arcos = configuracion["arcos"]
            productos = configuracion["productos"]
            scalex, scaley = DIMENSIONES[nodos]
            filas.append(
                {
                    "instancia": nombre,
                    "configuracion": numero_configuracion,
                    "bloque": configuracion["bloque"],
                    "semilla": semilla,
                    "nodos": nodos,
                    "arcos": arcos,
                    "productos": productos,
                    "scalex": scalex,
                    "scaley": scaley,
                    "grado_objetivo": configuracion["grado_objetivo"],
                    "productos_por_nodo": configuracion[
                        "productos_por_nodo"
                    ],
                    "densidad_dirigida": arcos / (nodos * (nodos - 1)),
                    "variables_arco_producto": arcos * productos,
                }
            )
            indice += 1

    with MANIFIESTO.open("w", newline="", encoding="utf-8") as archivo_csv:
        escritor = csv.DictWriter(archivo_csv, fieldnames=filas[0].keys())
        escritor.writeheader()
        escritor.writerows(filas)

    print(
        f"Generados {len(filas)} archivos .par y el manifiesto "
        f"{MANIFIESTO.name}."
    )


if __name__ == "__main__":
    main()
