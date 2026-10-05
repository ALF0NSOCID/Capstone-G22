import argparse
import webbrowser
from pathlib import Path

import matplotlib
import networkx as nx

from generador_waxman import generar_instancia


# La imagen se genera correctamente incluso al ejecutar desde una terminal
# sin una ventana grafica disponible.
matplotlib.use("Agg")
import matplotlib.pyplot as plt


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
    dpi=220,
    mostrar=False,
    etiquetas=False,
):
    """Dibuja la topologia completa usando las posiciones de Waxman."""
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

    # Un tamano moderado permite distinguir nodos de alto grado sin ocultar
    # la estructura cuando se visualizan cientos de nodos.
    tamanos = [12 + 5 * grados[nodo] for nodo in grafo.nodes]
    ancho_arista = max(0.25, min(0.8, 250 / max(1, grafo.number_of_edges())))

    figura, eje = plt.subplots(figsize=(12, 10))
    nx.draw_networkx_edges(
        grafo,
        posiciones,
        ax=eje,
        edgelist=enlaces_normales,
        width=ancho_arista,
        alpha=0.30,
        edge_color="#52789c",
    )
    if enlaces_backbone:
        nx.draw_networkx_edges(
            grafo,
            posiciones,
            ax=eje,
            edgelist=enlaces_backbone,
            width=max(0.9, 2.5 * ancho_arista),
            alpha=0.65,
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
            node_size=[80 + 6 * grados[nodo] for nodo in hubs],
            node_color="#d62828",
            node_shape="*",
            linewidths=0.8,
            edgecolors="white",
            label="Hubs",
        )
        eje.legend(loc="upper right", frameon=True)

    if etiquetas:
        nx.draw_networkx_labels(
            grafo,
            posiciones,
            ax=eje,
            font_size=6,
            font_color="#202020",
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
        f"capacidad backbone=x{multiplicador_hubs:g}",
        fontsize=13,
        pad=14,
    )
    eje.set_xlabel("Coordenada espacial X")
    eje.set_ylabel("Coordenada espacial Y")
    eje.set_aspect("equal", adjustable="box")
    eje.grid(alpha=0.12, linewidth=0.5)

    barra = figura.colorbar(nodos_dibujados, ax=eje, shrink=0.75, pad=0.02)
    barra.set_label("Grado del nodo")

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
    argumentos = parser.parse_args()

    print(
        "Generando red Waxman para visualizar "
        f"(n={argumentos.nodos}, M={argumentos.arcos}, "
        f"K={argumentos.productos}, alpha={argumentos.alpha}, "
        f"beta={argumentos.beta}, "
        f"hubs={100 * argumentos.porcentaje_hubs:g}%, "
        f"vecinos-hub={argumentos.vecinos_hub}, "
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
        dpi=argumentos.dpi,
        mostrar=argumentos.mostrar,
        etiquetas=argumentos.etiquetas,
    )


if __name__ == "__main__":
    main()
