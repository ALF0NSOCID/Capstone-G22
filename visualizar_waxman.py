import argparse
import math
import webbrowser
from collections import defaultdict
from pathlib import Path

import matplotlib
import networkx as nx

from generador_waxman import generar_instancia


# La imagen se genera correctamente incluso al ejecutar desde una terminal
# sin una ventana grafica disponible.
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D


RAIZ = Path(__file__).resolve().parent
CARPETA_IMAGENES = RAIZ / "resultados" / "visualizaciones"


def visualizar_red(
    grafo,
    arcos,
    commodities,
    salida,
    alpha,
    beta,
    semilla,
    porcentaje_hubs=0.0,
    multiplicador_hubs=10.0,
    vecinos_hub=3,
    demanda_gravedad=False,
    capacidad_escalones=False,
    dpi=220,
    mostrar=False,
    etiquetas=False,
    top_demanda=5,
):
    """Dibuja topologia, demanda nodal, capacidades, hubs y backbone."""
    posiciones = nx.get_node_attributes(grafo, "pos")
    if len(posiciones) != grafo.number_of_nodes():
        raise ValueError("El grafo no contiene posiciones para todos los nodos.")

    grados = dict(grafo.degree())
    valores_grado = [grados[nodo] for nodo in grafo.nodes]
    grado_maximo = max(valores_grado, default=0)
    hubs = [
        nodo
        for nodo in grafo.nodes
        if grafo.nodes[nodo].get("es_hub", False)
    ]
    enlaces_backbone = [
        (origen, destino)
        for origen, destino in grafo.edges
        if grafo.edges[origen, destino].get("es_backbone", False)
    ]
    claves_backbone = {
        frozenset((origen, destino))
        for origen, destino in enlaces_backbone
    }
    enlaces_normales = [
        (origen, destino)
        for origen, destino in grafo.edges
        if frozenset((origen, destino)) not in claves_backbone
    ]

    demanda_nodo = defaultdict(float)
    for commodity in commodities:
        demanda = commodity["demanda"]
        demanda_nodo[commodity["origen"]] += demanda
        demanda_nodo[commodity["destino"]] += demanda

    demanda_nodal_maxima = max(demanda_nodo.values(), default=1.0)
    tamanos_por_nodo = {
        nodo: 14 + 180 * math.sqrt(
            demanda_nodo[nodo] / demanda_nodal_maxima
        )
        for nodo in grafo.nodes
    }
    tamanos = [tamanos_por_nodo[nodo] for nodo in grafo.nodes]

    capacidades = [
        grafo.edges[origen, destino].get("capacidad", 1)
        for origen, destino in grafo.edges
    ]
    capacidad_minima = min(capacidades, default=1)
    capacidad_maxima = max(capacidades, default=1)

    def ancho_por_capacidad(origen, destino):
        capacidad = grafo.edges[origen, destino].get("capacidad", 1)
        if capacidad_maxima == capacidad_minima:
            return 0.6
        minimo = math.log1p(capacidad_minima)
        maximo = math.log1p(capacidad_maxima)
        proporcion = (math.log1p(capacidad) - minimo) / (maximo - minimo)
        return 0.25 + 2.25 * proporcion

    figura, eje = plt.subplots(figsize=(12, 10))
    nx.draw_networkx_edges(
        grafo,
        posiciones,
        ax=eje,
        edgelist=enlaces_normales,
        width=[ancho_por_capacidad(*enlace) for enlace in enlaces_normales],
        alpha=0.30,
        edge_color="#52789c",
    )
    if enlaces_backbone:
        nx.draw_networkx_edges(
            grafo,
            posiciones,
            ax=eje,
            edgelist=enlaces_backbone,
            width=[
                max(1.1, ancho_por_capacidad(*enlace))
                for enlace in enlaces_backbone
            ],
            alpha=0.75,
            edge_color="#e76f51",
        )
    nodos_dibujados = nx.draw_networkx_nodes(
        grafo,
        posiciones,
        ax=eje,
        node_size=tamanos,
        node_color=valores_grado,
        cmap="viridis",
        vmin=0,
        vmax=max(1, grado_maximo),
        linewidths=0.25,
        edgecolors="white",
    )
    if hubs:
        nx.draw_networkx_nodes(
            grafo,
            posiciones,
            ax=eje,
            nodelist=hubs,
            node_size=[
                max(90, 1.6 * tamanos_por_nodo[nodo])
                for nodo in hubs
            ],
            node_color="#d62828",
            node_shape="*",
            linewidths=0.8,
            edgecolors="white",
        )

    if etiquetas:
        nx.draw_networkx_labels(
            grafo,
            posiciones,
            ax=eje,
            font_size=6,
            font_color="#202020",
        )
    elif top_demanda > 0:
        nodos_destacados = sorted(
            grafo.nodes,
            key=lambda nodo: demanda_nodo[nodo],
            reverse=True,
        )[:top_demanda]
        desplazamientos_y = (-18, 18, 30, -30, 0)
        for indice, nodo in enumerate(nodos_destacados):
            x, y = posiciones[nodo]
            hacia_izquierda = x > 0.72
            eje.annotate(
                f"{nodo}\nD={demanda_nodo[nodo]:g}",
                xy=(x, y),
                xytext=(-7 if hacia_izquierda else 7,
                        desplazamientos_y[indice % len(desplazamientos_y)]),
                textcoords="offset points",
                ha="right" if hacia_izquierda else "left",
                va="center",
                fontsize=6,
                color="#202020",
                arrowprops={
                    "arrowstyle": "-",
                    "color": "#666666",
                    "linewidth": 0.35,
                },
            )

    grado_medio = (
        sum(valores_grado) / len(valores_grado)
        if valores_grado
        else 0.0
    )
    clustering = nx.average_clustering(grafo)

    eje.set_title(
        "Red espacial Waxman\n"
        f"n={grafo.number_of_nodes()} | "
        f"enlaces={grafo.number_of_edges()} | "
        f"arcos={len(arcos)} | productos={len(commodities)}\n"
        f"alpha={alpha:g} | beta={beta:g} | semilla={semilla} | "
        f"grado medio={grado_medio:.2f} | clustering={clustering:.3f}\n"
        f"hubs={len(hubs)} ({100 * porcentaje_hubs:g}%) | "
        f"vecinos por hub={vecinos_hub} | "
        f"capacidad backbone=x{multiplicador_hubs:g}\n"
        f"demanda={'gravedad' if demanda_gravedad else 'uniforme'} | "
        f"capacidad={'escalones' if capacidad_escalones else 'uniforme'} | "
        "tamano nodo=demanda OD | ancho enlace=capacidad",
        fontsize=13,
        pad=14,
    )
    eje.set_xlabel("Coordenada espacial X")
    eje.set_ylabel("Coordenada espacial Y")
    eje.set_aspect("equal", adjustable="box")
    eje.grid(alpha=0.12, linewidth=0.5)

    barra = figura.colorbar(nodos_dibujados, ax=eje, shrink=0.75, pad=0.02)
    barra.set_label("Grado del nodo")

    leyenda = [
        Line2D(
            [0], [0], marker="*", linestyle="none", markersize=12,
            markerfacecolor="#d62828", markeredgecolor="white", label="Hub",
        ),
        Line2D(
            [0], [0], color="#e76f51", linewidth=2.2,
            label="Enlace de backbone",
        ),
        Line2D(
            [0], [0], color="#52789c", linewidth=0.5,
            label=f"Capacidad baja ({capacidad_minima:g})",
        ),
        Line2D(
            [0], [0], color="#52789c", linewidth=2.5,
            label=f"Capacidad alta ({capacidad_maxima:g})",
        ),
    ]
    eje.legend(handles=leyenda, loc="upper right", frameon=True, fontsize=8)

    salida = Path(salida)
    salida.parent.mkdir(parents=True, exist_ok=True)
    figura.tight_layout()
    figura.savefig(salida, dpi=dpi, bbox_inches="tight")

    print(f"Visualizacion guardada en: {salida.resolve()}")
    print(
        "Resumen: "
        f"{grafo.number_of_nodes()} nodos, "
        f"{grafo.number_of_edges()} enlaces no dirigidos, "
        f"grado medio {grado_medio:.2f}, "
        f"grado maximo {grado_maximo}."
    )

    plt.close(figura)
    if mostrar:
        webbrowser.open(salida.resolve().as_uri())


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Genera una red Waxman con generador_waxman.py y guarda una "
            "imagen completa de su topologia espacial."
        )
    )
    parser.add_argument("--nodos", type=int, default=400)
    parser.add_argument("--productos", type=int, default=10000)
    parser.add_argument(
        "--arcos",
        type=int,
        default=1600,
        help="Numero de arcos dirigidos reciprocos.",
    )
    parser.add_argument("--alpha", type=float, default=0.2)
    parser.add_argument("--beta", type=float, default=0.4)
    parser.add_argument("--demanda-min", type=int, default=10)
    parser.add_argument("--demanda-max", type=int, default=50)
    parser.add_argument("--capacidad-min", type=int, default=50)
    parser.add_argument("--capacidad-max", type=int, default=150)
    parser.add_argument(
        "--demanda-gravedad",
        action="store_true",
        help="Genera pares y demandas mediante el modelo gravitacional.",
    )
    parser.add_argument("--demanda-media", type=float, default=30.0)
    parser.add_argument("--sigma-masa", type=float, default=1.0)
    parser.add_argument(
        "--capacidad-escalones",
        action="store_true",
        help="Asigna capacidades escalonadas segun centralidad.",
    )
    parser.add_argument(
        "--factores-escalon",
        type=float,
        nargs="+",
        default=(1.0, 2.5, 5.0, 10.0),
        metavar="FACTOR",
    )
    parser.add_argument(
        "--cuantiles-escalon",
        type=float,
        nargs="+",
        default=(0.40, 0.75, 0.93),
        metavar="CUANTIL",
    )
    parser.add_argument(
        "--porcentaje-hubs",
        type=float,
        default=0.0,
        help="Proporcion de hubs; 0.05 representa aproximadamente 5%%.",
    )
    parser.add_argument(
        "--multiplicador-hubs",
        type=float,
        default=10.0,
        help="Multiplicador de capacidad para enlaces entre hubs.",
    )
    parser.add_argument(
        "--vecinos-hub",
        type=int,
        default=3,
        help="Numero de hubs geograficamente cercanos buscados por cada hub.",
    )
    parser.add_argument("--semilla", type=int, default=42)
    parser.add_argument("--dpi", type=int, default=220)
    parser.add_argument(
        "--salida",
        type=Path,
        help="Ruta opcional del PNG generado.",
    )
    parser.add_argument(
        "--mostrar",
        action="store_true",
        help="Abre el PNG despues de guardarlo.",
    )
    parser.add_argument(
        "--etiquetas",
        action="store_true",
        help="Muestra el numero de cada nodo; puede saturar redes grandes.",
    )
    parser.add_argument(
        "--top-demanda",
        type=int,
        default=5,
        help="Etiqueta esta cantidad de nodos con mayor demanda OD.",
    )
    argumentos = parser.parse_args()

    print(
        "Generando red Waxman para visualizar "
        f"(n={argumentos.nodos}, M={argumentos.arcos}, "
        f"K={argumentos.productos}, alpha={argumentos.alpha}, "
        f"beta={argumentos.beta}, "
        f"hubs={100 * argumentos.porcentaje_hubs:g}%, "
        f"vecinos-hub={argumentos.vecinos_hub}, "
        f"demanda={'gravedad' if argumentos.demanda_gravedad else 'uniforme'}, "
        f"capacidad={'escalones' if argumentos.capacidad_escalones else 'uniforme'}, "
        f"semilla={argumentos.semilla})..."
    )
    grafo, arcos, commodities = generar_instancia(
        nodos=argumentos.nodos,
        productos=argumentos.productos,
        arcos_objetivo=argumentos.arcos,
        alpha=argumentos.alpha,
        beta=argumentos.beta,
        demanda_min=argumentos.demanda_min,
        demanda_max=argumentos.demanda_max,
        capacidad_min=argumentos.capacidad_min,
        capacidad_max=argumentos.capacidad_max,
        demanda_gravedad=argumentos.demanda_gravedad,
        demanda_media=argumentos.demanda_media,
        sigma_masa=argumentos.sigma_masa,
        capacidad_escalones=argumentos.capacidad_escalones,
        factores_escalon=tuple(argumentos.factores_escalon),
        cuantiles_escalon=tuple(argumentos.cuantiles_escalon),
        semilla=argumentos.semilla,
        porcentaje_hubs=argumentos.porcentaje_hubs,
        multiplicador_capacidad_hubs=argumentos.multiplicador_hubs,
        conexiones_por_hub=argumentos.vecinos_hub,
    )

    salida = argumentos.salida or (
        CARPETA_IMAGENES
        / (
            f"waxman_n{argumentos.nodos}"
            f"_m{argumentos.arcos}"
            f"_a{argumentos.alpha:g}"
            f"_b{argumentos.beta:g}"
            f"_h{100 * argumentos.porcentaje_hubs:g}"
            f"_v{argumentos.vecinos_hub}"
            f"{'_dg' if argumentos.demanda_gravedad else ''}"
            f"{'_ce' if argumentos.capacidad_escalones else ''}"
            f"_s{argumentos.semilla}.png"
        )
    )
    visualizar_red(
        grafo=grafo,
        arcos=arcos,
        commodities=commodities,
        salida=salida,
        alpha=argumentos.alpha,
        beta=argumentos.beta,
        semilla=argumentos.semilla,
        porcentaje_hubs=argumentos.porcentaje_hubs,
        multiplicador_hubs=argumentos.multiplicador_hubs,
        vecinos_hub=argumentos.vecinos_hub,
        demanda_gravedad=argumentos.demanda_gravedad,
        capacidad_escalones=argumentos.capacidad_escalones,
        dpi=argumentos.dpi,
        mostrar=argumentos.mostrar,
        etiquetas=argumentos.etiquetas,
        top_demanda=argumentos.top_demanda,
    )


if __name__ == "__main__":
    main()
