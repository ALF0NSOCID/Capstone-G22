"""Exploracion acotada de Waxman; no modifica el repositorio ni su out."""
import argparse
import csv
import datetime
import hashlib
import json
import os
from pathlib import Path
from compatibilidad import archivo_fuente
import platform
import re
import statistics
import subprocess
import sys
import time

# Son puntos de exploracion, no configuraciones cuya viabilidad se garantice.
CASOS = {
    'local_extrema': dict(alpha=0.04, beta=1.0),
    'intermedia': dict(alpha=0.20, beta=0.40),
    'larga': dict(alpha=0.70, beta=0.40),
    'local_backbone': dict(alpha=0.04, beta=1.0, porcentaje_hubs=0.05,
                          conexiones_por_hub=2, prob_acceso_backbone=0.80,
                          prob_segundo_hub=0.25),
    'local_backbone_x10': dict(alpha=0.04, beta=1.0, porcentaje_hubs=0.05,
                          conexiones_por_hub=2, prob_acceso_backbone=0.80,
                          prob_segundo_hub=0.25, multiplicador_capacidad_hubs=10),
}


def worker(repo, carpeta, caso, semilla):
    sys.path.insert(0, str(repo))
    import networkx as nx
    from generador_waxman import generar_instancia, escribir_instancia
    from visualizar_waxman import visualizar_red
    from analisis_red import analizar_red_generada

    ajustes = dict(nodos=400, productos=10000, arcos_objetivo=1600,
                   demanda_min=10, demanda_max=50, capacidad_min=50,
                   capacidad_max=150, multiplicador_capacidad_hubs=1,
                   semilla=semilla, secuencias_independientes=True)
    ajustes.update(CASOS[caso])
    (carpeta / 'parametros.json').write_text(json.dumps(ajustes, indent=2))
    inicio = time.perf_counter()
    g, arcos, demandas = generar_instancia(**ajustes)
    generacion = time.perf_counter() - inicio
    escribir_instancia(carpeta / 'instancia.txt', g, arcos, demandas)
    diagnostico = analizar_red_generada(carpeta / 'instancia.txt', grafo=g)
    (carpeta / 'generacion_metadata.json').write_text(json.dumps(g.graph, indent=2))
    pos = nx.get_node_attributes(g, 'pos')
    distancias = [((pos[u][0]-pos[v][0])**2 +
                  (pos[u][1]-pos[v][1])**2)**0.5 for u, v in g.edges]
    hubs = {u for u in g if g.nodes[u].get('es_hub', False)}
    accesos = [(u, v) for u, v in g.edges if (u in hubs) != (v in hubs)]
    cobertura = {v if u in hubs else u for u, v in accesos}
    grados = [g.degree(u) for u in g]
    puentes = list(nx.bridges(g))
    diagnostico.update(
        generacion_s=generacion, enlaces=g.number_of_edges(),
        longitud_media=statistics.mean(distancias),
        grado_max=max(grados), grado_cv=statistics.pstdev(grados)/statistics.mean(grados),
        clustering=nx.average_clustering(g), puentes=len(puentes),
        hubs=len(hubs), enlaces_hub_normal=len(accesos),
        normales_con_hub=len(cobertura),
        grado_medio_hubs=statistics.mean(g.degree(u) for u in hubs) if hubs else None,
        grado_medio_normales=statistics.mean(g.degree(u) for u in g if u not in hubs),
        demanda_total=sum(d['demanda'] for d in demandas),
        capacidad_total_arcos=sum(a['capacidad'] for a in arcos),
        networkx=nx.__version__,
    )
    (carpeta / 'diagnostico.json').write_text(json.dumps(diagnostico, indent=2))
    visualizar_red(g, arcos, demandas, carpeta / 'red.png',
        ajustes['alpha'], ajustes['beta'], semilla,
        porcentaje_hubs=ajustes.get('porcentaje_hubs', 0),
        multiplicador_hubs=ajustes['multiplicador_capacidad_hubs'],
        vecinos_hub=ajustes.get('conexiones_por_hub', 3),
        prob_acceso_backbone=ajustes.get('prob_acceso_backbone', 0),
        prob_segundo_hub=ajustes.get('prob_segundo_hub', 0),
        demanda_gravedad=ajustes.get('demanda_gravedad', False))


def resolver(repo, carpeta, limite):
    entorno = dict(os.environ, ARCHIVO_INSTANCIA=str(carpeta / 'instancia.txt'),
                   E2_LIMITE_TIEMPO=str(limite), E2_TOLERANCIA='1e-7', E2_ETA='25')
    inicio = time.perf_counter()
    with (carpeta / 'solver.log').open('w') as log:
        try:
            p = subprocess.run([sys.executable, str(repo / "compat" / 'solver_columnas_e2_v2.py')],
                               cwd=carpeta, env=entorno, stdout=log,
                               stderr=subprocess.STDOUT, timeout=limite+60)
            codigo = p.returncode
        except subprocess.TimeoutExpired:
            codigo = 'timeout_externo'
    texto = (carpeta / 'solver.log').read_text(errors='replace')
    if codigo == 'timeout_externo':
        estado = 'timeout_externo'
    elif codigo != 0:
        estado = 'error'
    elif 'SIN CERTIFICAR' in texto or 'No se alcanz' in texto:
        estado = 'sin_certificar'
    elif re.search(r'[oó]ptima certificada', texto):
        estado = 'optimo'
    elif 'error relativo certificado' in texto:
        estado = 'brecha_1pct'
    else:
        estado = 'revisar_log'
    fila = dict(estado=estado, codigo=codigo, pared_s=time.perf_counter()-inicio)
    for clave, patron in {
        'interno_s': r'Tiempo total:\s*([0-9.]+)',
        'z': r'Congesti[oó]n m[aá]xima:\s*([0-9.eE+\-]+)',
        'gap_pct': r'^Gap certificado(?: actual)?:\s*([0-9.eE+\-]+|inf)%',
        'iteraciones': r'Iteraciones:\s*(\d+)',
        'columnas': r'Columnas:\s*(\d+)',
    }.items():
        m = re.findall(patron, texto, re.MULTILINE)
        fila[clave] = m[-1] if m else ''
    diagnostico = carpeta / 'diagnostico.json'
    if diagnostico.exists() and fila['z']:
        cota = json.loads(diagnostico.read_text()).get('cota_puentes', 0)
        fila['cota_puentes'] = cota
        fila['cota_puentes_sobre_z'] = cota / float(fila['z']) if float(fila['z']) else None
    return fila


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--repo', type=Path, default=Path.home()/'Desktop/Repo Capstone')
    ap.add_argument('--casos', nargs='+', choices=CASOS, default=list(CASOS))
    ap.add_argument('--semillas', nargs='+', type=int, default=[42])
    ap.add_argument('--generacion-seg', type=float, default=30)
    ap.add_argument('--limite', type=float, default=120)
    ap.add_argument('--resolver', action='store_true', help='Genera, dibuja y resuelve cada instancia.')
    ap.add_argument('--resolver-carpeta', type=Path, help='Resuelve las instancias ya guardadas, sin regenerar.')
    ap.add_argument('--salida', type=Path, default=Path.cwd())
    a = ap.parse_args()
    repo = a.repo.expanduser().resolve()
    if not (repo / "compat" / 'generador_waxman.py').exists():
        ap.error('No se encuentra generador_waxman.py en --repo.')
    if a.resolver_carpeta:
        for instancia in sorted(a.resolver_carpeta.expanduser().resolve().glob('*/instancia.txt')):
            carpeta = instancia.parent
            resultado = resolver(repo, carpeta, a.limite)
            (carpeta/'resultado_solver.json').write_text(json.dumps(resultado, indent=2))
            print(carpeta.name, resultado, flush=True)
        return
    salida = a.salida.expanduser().resolve()/('waxman_exploracion_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
    salida.mkdir(parents=True)
    meta = dict(python=sys.version, plataforma=platform.platform(), repo=str(repo),
                generacion_seg=a.generacion_seg, limite_solver=a.limite)
    meta['sha256'] = {n: hashlib.sha256(archivo_fuente(repo/n).read_bytes()).hexdigest() for n in
                      ['generador_waxman.py', 'solver_columnas_e2_v2.py', 'analisis_red.py']}
    (salida/'entorno.json').write_text(json.dumps(meta, indent=2))
    for caso in a.casos:
        for semilla in a.semillas:
            carpeta = salida/f'{caso}_s{semilla}'
            carpeta.mkdir()
            print(f'Generando {carpeta.name} (tope {a.generacion_seg:g} s)...', flush=True)
            with (carpeta/'generacion.log').open('w') as log:
                try:
                    p = subprocess.run([sys.executable, str(Path(__entry_file__).resolve()),
                        '_worker', str(repo), str(carpeta), caso, str(semilla)],
                        stdout=log, stderr=subprocess.STDOUT, timeout=a.generacion_seg)
                    estado = 'generada' if p.returncode == 0 else 'error_generacion'
                except subprocess.TimeoutExpired:
                    estado = 'timeout_preparacion'
            resultado = dict(estado=estado)
            if estado == 'generada' and a.resolver:
                resultado.update(resolver(repo, carpeta, a.limite))
            (carpeta/'estado.json').write_text(json.dumps(resultado, indent=2))
            print(' ', resultado, flush=True)
    print(f'\nImagenes, instancias y logs: {salida}')


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '_worker':
        worker(Path(sys.argv[2]), Path(sys.argv[3]), sys.argv[4], int(sys.argv[5]))
    else:
        main()
