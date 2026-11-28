import argparse
import json
from pathlib import Path

from analisis_red import analizar_red_generada
from generador_waxman import escribir_instancia, generar_instancia


# ---------------------------------------------------------
# RUTAS PRINCIPALES
# ---------------------------------------------------------

RAIZ = Path(__file__).resolve().parent


# ---------------------------------------------------------
# SELECCIONAR SOLVER
# ---------------------------------------------------------

from ejecutar import obtener_solver, ejecutar_solver
from src.ejecucion.gestion import crear_corrida


# ---------------------------------------------------------
# PROGRAMA PRINCIPAL
# ---------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description=(
            "Genera una instancia Waxman y la resuelve utilizando el "
            "solver seleccionado."
        )
    )
    parser.add_argument(
        "solver",
        help="Solver que resolvera la instancia, por ejemplo solver_columnas.",
    )
    parser.add_argument("--nodos", type=int, default=400)
    parser.add_argument("--productos", type=int, default=10000)
    parser.add_argument(
        "--arcos",
        type=int,
        help=(
            "Numero exacto de arcos dirigidos reciprocos. Si se omite, "
            "se conserva la densidad natural del grafo Waxman."
        ),
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
        help=(
            "Genera pares y demandas con un modelo gravitacional. "
            "Al activarlo, demanda-min y demanda-max no se utilizan."
        ),
    )
    parser.add_argument(
        "--demanda-media",
        type=float,
        default=30.0,
        help="Demanda media objetivo del modelo gravitacional.",
    )
    parser.add_argument(
        "--sigma-masa",
        type=float,
        default=1.0,
        help="Dispersion lognormal de las masas del modelo gravitacional.",
    )
    parser.add_argument(
        "--capacidad-escalones",
        action="store_true",
        help=(
            "Asigna capacidades por escalones segun la centralidad de los "
            "enlaces. Al activarlo, capacidad-max no se utiliza."
        ),
    )
    parser.add_argument(
        "--factores-escalon",
        type=float,
        nargs="+",
        default=(1.0, 2.5, 5.0, 10.0),
        metavar="FACTOR",
        help="Factores de capacidad para cada escalon.",
    )
    parser.add_argument(
        "--cuantiles-escalon",
        type=float,
        nargs="+",
        default=(0.40, 0.75, 0.93),
        metavar="CUANTIL",
        help="Cuantiles que separan los escalones de capacidad.",
    )
    parser.add_argument(
        "--porcentaje-hubs",
        type=float,
        default=0.0,
        help=(
            "Proporcion de nodos que forman un backbone local conectado. "
            "Por ejemplo, 0.05 selecciona aproximadamente 5%% de hubs."
        ),
    )
    parser.add_argument(
        "--multiplicador-hubs",
        type=float,
        default=10.0,
        help="Multiplicador de capacidad para los enlaces entre hubs.",
    )
    parser.add_argument(
        "--vecinos-hub",
        type=int,
        default=3,
        help="Numero de hubs geograficamente cercanos buscados por cada hub.",
    )
    parser.add_argument("--semilla", type=int, default=42)
    parser.add_argument("--prob-acceso-backbone", type=float, default=0.0)
    parser.add_argument("--prob-segundo-hub", type=float, default=0.0)
    parser.add_argument("--secuencias-independientes", action="store_true")
    parser.add_argument(
        "--nombre",
        help="Nombre opcional usado para identificar el archivo de resultados.",
    )
    parser.add_argument(
        "--analizar-red",
        action="store_true",
        help="Imprime un diagnostico estructural antes de ejecutar el solver.",
    )
    parser.add_argument("--salida", type=Path, help="Carpeta base para las nuevas ejecuciones")
    argumentos = parser.parse_args()

    archivo_solver = obtener_solver(argumentos.solver)

    print(
        "Generando instancia Waxman "
        f"(n={argumentos.nodos}, M={argumentos.arcos or 'natural'}, "
        f"K={argumentos.productos}, "
        f"alpha={argumentos.alpha}, beta={argumentos.beta}, "
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
        prob_acceso_backbone=argumentos.prob_acceso_backbone,
        prob_segundo_hub=argumentos.prob_segundo_hub,
        secuencias_independientes=argumentos.secuencias_independientes,
    )

    sufijo_realismo = ""
    if argumentos.demanda_gravedad:
        sufijo_realismo += "_dg"
    if argumentos.capacidad_escalones:
        sufijo_realismo += "_ce"

    nombre_instancia = argumentos.nombre or (
        f"waxman_n{argumentos.nodos}"
        f"_m{argumentos.arcos or len(arcos)}"
        f"_k{argumentos.productos}"
        f"_h{100 * argumentos.porcentaje_hubs:g}"
        f"_v{argumentos.vecinos_hub}"
        f"_a{argumentos.alpha:g}_b{argumentos.beta:g}"
        f"_p{argumentos.prob_acceso_backbone:g}_q{argumentos.prob_segundo_hub:g}"
        f"_x{argumentos.multiplicador_hubs:g}_ind{int(argumentos.secuencias_independientes)}"
        f"{sufijo_realismo}"
        f"_s{argumentos.semilla}"
    )

    carpeta = crear_corrida(nombre_instancia, argumentos.salida)
    instancia = carpeta / "instancia.txt"
    escribir_instancia(instancia, grafo, arcos, commodities)
    print(f"Instancia generada: {grafo.number_of_nodes()} nodos, "
          f"{len(arcos)} arcos y {len(commodities)} productos.")
    parametros = dict(vars(argumentos), generacion=grafo.graph.get("generacion", {}))
    parametros["salida"] = str(argumentos.salida) if argumentos.salida else None
    (carpeta / "parametros.json").write_text(
        json.dumps(parametros, indent=2), encoding="utf-8")
    if argumentos.analizar_red:
        diagnostico = analizar_red_generada(instancia, grafo=grafo)
        (carpeta / "diagnostico.json").write_text(
            json.dumps(diagnostico, indent=2), encoding="utf-8")
    ejecutar_solver(nombre_instancia, archivo_solver, instancia=instancia, carpeta=carpeta)



if __name__ == "__main__":
    main()
