#!/usr/bin/env python3
"""
Construcción de la instancia "Red inspirada en la infraestructura de fibra óptica chilena"
Capstone ICS2122 – flujo multiproducto de congestión mínima.

Entradas (carpeta datos_crudos/):
  - fon_triot_diagramas.csv     tramos FON leídos de los diagramas lineales de Subtel
  - censo2024_comunas_ine.csv   población Censo 2024 por comuna (servicio ArcGIS del INE)
  - coordenadas_osm.csv         coordenadas OpenStreetMap + comuna INE por punto-en-polígono
  - fdt_186_comunas.csv         listado de comunas FON del documento FDT (jul-2019)

Salidas (carpeta raíz):
  nodos.csv, enlaces.csv, demandas_base.csv, instancia_base.txt, escenarios/, fallas.csv,
  verificaciones.md (resultados de los chequeos) y datos para el mapa.

Todo parámetro que no viene de una fuente está marcado como SUPUESTO en PARAMS y en supuestos.md.
"""
import csv, json, math, os, unicodedata
from collections import defaultdict
import numpy as np
import pandas as pd
import networkx as nx

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, 'datos_crudos')
OUT = ROOT

# ----------------------------------------------------------------------------------------
# Parámetros (cada uno documentado en supuestos.md)
# ----------------------------------------------------------------------------------------
PARAMS = dict(
    # Tráfico nacional 2025 (Subtel, Informe del Sector Telecomunicaciones dic-2025):
    trafico_fijo_2025_milesTB=36356.4,     # DATO
    trafico_movil_2025_milesTB=7179.0,     # DATO
    poblacion_nacional_2024=18480432,      # DATO (INE, Censo 2024)
    factor_hora_punta=1.6,                 # SUPUESTO: punta / promedio
    fraccion_salida_internacional=0.75,    # SUPUESTO f: tráfico hacia/desde Internet global + CDN en Santiago
    fraccion_bajada=0.85,                  # SUPUESTO: de lo que va a la salida, fracción en sentido Santiago→nodo
    gamma=0.0,                             # SUPUESTO justificado (Zhang et al. 2003; Roughan 2005)
    max_productos=10000,
    # Capacidades iluminadas (Gbps por sentido)
    # Regla: escalones estándar {100, 400, 800, 2000, 4000, 8000}; por capa, el menor escalón uniforme que deja
    # la red base bajo 70 % de utilización en hora punta (holgura operativa). Ver supuestos.md.
    cap_troncal=8000,                      # SUPUESTO: 80 × 100G (p. ej. 2 pares × 40 canales DWDM), agregado de operadores
    cap_fon=800,                           # SUPUESTO: 8 × 100G sobre los 24 pares por cable declarados en las bases
    cap_foa_submarino=400,                 # SUPUESTO: 4 de los 60 canales ópticos (100G) declarados por Subtel
    cap_foa_terrestre=100,                 # SUPUESTO: 1 canal óptico 100GbE (de 40 declarados por POIIT)
    cap_candidato=800,                     # SUPUESTO: misma tecnología que un ramal FON
    # Longitudes
    km_foa_submarino_total=2800,           # DATO secundario (Capacity Media / Huawei Marine)
    umbral_km_revision=300,
)
REG_EXIT = 'Santiago'  # nodo con la salida internacional / CDN

REGION = {'15': 'Arica y Parinacota', '01': 'Tarapacá', '02': 'Antofagasta', '03': 'Atacama',
          '04': 'Coquimbo', '05': 'Valparaíso', '13': 'Metropolitana', '06': "O'Higgins",
          '07': 'Maule', '16': 'Ñuble', '08': 'Biobío', '09': 'Araucanía', '14': 'Los Ríos',
          '10': 'Los Lagos', '11': 'Aysén', '12': 'Magallanes'}
MACRO = {'15': 'Arica y Parinacota', '01': 'Fuera de FON (Tarapacá)', '02': 'Norte', '03': 'Norte',
         '04': 'Centro Norte', '05': 'Centro Norte', '13': 'Centro Norte', '06': 'Centro', '07': 'Centro',
         '16': 'Centro Sur', '08': 'Centro Sur', '09': 'Sur', '14': 'Sur', '10': 'Sur',
         '11': 'Austral (FOA)', '12': 'Austral (FOA)'}

PIX = ['Arica', 'Antofagasta', 'Copiapó', 'La Serena', 'Valparaíso', 'San Bernardo', 'Rancagua',
       'Talca', 'Chillán', 'Concepción', 'Temuco', 'Valdivia', 'Puerto Montt']

SRC_ADJ19 = 'Subtel, Informe_resumen_adjudicacion_fon.pdf (2019)'
SRC_SUR20 = 'Subtel, Proyecto_FON_Macrozona_Sur_Topologias.pdf (2020)'
SRC_FOA17 = 'Subtel FOA, Resumen_Proyecto_FOA_03_2017.pdf (POIIT por troncal)'
SRC_FOAPPT = 'Subtel FOA, PPT_Rodrigo_Ramirez.pdf (2017), lámina 2'

# Troncal unificada (SUPUESTO de topología: Ruta 5 + accesos a capitales fuera del eje)
TRONCAL = [
    ('Arica', 'Pozo Almonte'), ('Pozo Almonte', 'Iquique'), ('Pozo Almonte', 'Antofagasta'),
    ('Antofagasta', 'Copiapó'), ('Copiapó', 'La Serena'), ('La Serena', 'La Calera'),
    ('La Calera', 'Santiago'), ('Santiago', 'Valparaíso'), ('Santiago', 'San Bernardo'),
    ('San Bernardo', 'Rancagua'), ('Rancagua', 'San Fernando'), ('San Fernando', 'Curicó'),
    ('Curicó', 'Talca'), ('Talca', 'Linares'), ('Linares', 'Chillán'), ('Chillán', 'Concepción'),
    ('Chillán', 'Los Ángeles'), ('Los Ángeles', 'Temuco'), ('Temuco', 'Valdivia'),
    ('Valdivia', 'Osorno'), ('Osorno', 'Puerto Montt'),
]

# FOA. (origen, destino, subtipo, tipo_poiit, clasificacion_topologia, nota)
FOA = [
    ('Puerto Montt', 'Caleta Tortel', 'SUBMARINO', 'exigible', 'DATO', 'Troncal submarina: POIIT exigibles Puerto Montt, Tortel, Punta Arenas, Puerto Williams'),
    ('Caleta Tortel', 'Punta Arenas', 'SUBMARINO', 'exigible', 'DATO', ''),
    ('Punta Arenas', 'Puerto Williams', 'SUBMARINO', 'exigible', 'DATO', ''),
    # Troncal terrestre Los Lagos (orden de POIIT de las bases; tramos = SUPUESTO por red vial)
    ('Puerto Montt', 'Alerce', 'TERRESTRE', 'exigible', 'SUPUESTO', ''),
    ('Alerce', 'Ensenada', 'TERRESTRE', 'exigible', 'SUPUESTO', ''),
    ('Ensenada', 'Ralún', 'TERRESTRE', 'exigible', 'SUPUESTO', ''),
    ('Ralún', 'Cochamó', 'TERRESTRE', 'exigible', 'SUPUESTO', ''),
    ('Cochamó', 'Puelo Alto', 'TERRESTRE', 'exigible', 'SUPUESTO', ''),
    ('Puelo Alto', 'Contao', 'TERRESTRE', 'exigible', 'SUPUESTO', 'continuidad vial no verificada'),
    ('Contao', 'El Manzano', 'TERRESTRE', 'exigible', 'SUPUESTO', ''),
    ('El Manzano', 'Pichicolo', 'TERRESTRE', 'exigible', 'SUPUESTO', ''),
    ('Pichicolo', 'Hornopirén', 'TERRESTRE', 'exigible', 'SUPUESTO', 'POIIT "Río Negro (Hornopirén)", comuna Hualaihué'),
    ('Hornopirén', 'Chaitén', 'TERRESTRE', 'adicional', 'SUPUESTO', 'Ruta 7 con cruces de fiordo'),
    ('Chaitén', 'Villa Santa Lucía', 'TERRESTRE', 'adicional', 'SUPUESTO', ''),
    ('Villa Santa Lucía', 'Futaleufú', 'TERRESTRE', 'adicional', 'SUPUESTO', ''),
    ('Villa Santa Lucía', 'Palena', 'TERRESTRE', 'adicional', 'SUPUESTO', ''),
    # Troncal terrestre Aysén
    ('Caleta Tortel', 'Los Ñadis', 'TERRESTRE', 'exigible', 'SUPUESTO', ''),
    ('Los Ñadis', 'Cochrane', 'TERRESTRE', 'exigible', 'SUPUESTO', ''),
    ('Cochrane', 'Puerto Bertrand', 'TERRESTRE', 'exigible', 'SUPUESTO', ''),
    ('Puerto Bertrand', 'Puerto Guadal', 'TERRESTRE', 'exigible', 'SUPUESTO', ''),
    ('Puerto Guadal', 'Mallín Grande', 'TERRESTRE', 'exigible', 'SUPUESTO', ''),
    ('Mallín Grande', 'Chile Chico', 'TERRESTRE', 'exigible', 'SUPUESTO', ''),
    ('Puerto Bertrand', 'Puerto Río Tranquilo', 'TERRESTRE', 'exigible', 'SUPUESTO', ''),
    ('Puerto Río Tranquilo', 'Bahía Murta', 'TERRESTRE', 'exigible', 'SUPUESTO', ''),
    ('Bahía Murta', 'Cerro Castillo', 'TERRESTRE', 'exigible', 'SUPUESTO', ''),
    ('Cerro Castillo', 'El Blanco', 'TERRESTRE', 'exigible', 'SUPUESTO', ''),
    ('El Blanco', 'Coyhaique', 'TERRESTRE', 'exigible', 'SUPUESTO', ''),
    ('Caleta Tortel', "Villa O'Higgins", 'TERRESTRE', 'adicional', 'SUPUESTO', ''),
    ('Cerro Castillo', 'Puerto Ingeniero Ibáñez', 'TERRESTRE', 'adicional', 'SUPUESTO', ''),
    # Troncal terrestre Magallanes
    ('Punta Arenas', 'Porvenir', 'TERRESTRE', 'exigible', 'SUPUESTO', 'cruce del Estrecho de Magallanes'),
    ('Porvenir', 'Onaisín', 'TERRESTRE', 'adicional', 'SUPUESTO', ''),
    ('Onaisín', 'Cerro Sombrero', 'TERRESTRE', 'exigible', 'SUPUESTO', ''),
    ('Onaisín', 'Cameron', 'TERRESTRE', 'adicional', 'SUPUESTO', ''),
    ('Cameron', 'Pampa Guanaco', 'TERRESTRE', 'exigible', 'SUPUESTO', ''),
    ('Punta Arenas', 'Puerto Natales', 'TERRESTRE', 'adicional', 'SUPUESTO', ''),
]

# Enlaces candidatos (no existen hoy). (origen, destino, justificación)
CANDIDATOS = [
    ('Cuya', 'Pozo Almonte', 'Cierra anillo Arica–Cuya–Pozo Almonte paralelo a la troncal (Ruta 5); quita el puente Arica–Pozo Almonte.'),
    ('Tocopilla', 'Iquique', 'Ruta costera (Ruta 1): une el ramal costero de Antofagasta con Tarapacá; segunda vía para Iquique.'),
    ('Taltal', 'Chañaral', 'Une los extremos de los ramales de Antofagasta y Atacama por la costa; anillo alternativo a la troncal Antofagasta–Copiapó.'),
    ('Vallenar', 'La Higuera', 'Une ramales de Atacama y Coquimbo por la Ruta 5; respaldo al tramo troncal Copiapó–La Serena.'),
    ('Los Vilos', 'La Ligua', 'Une ramales de Coquimbo y Valparaíso por la Ruta 5 costera; respaldo al tramo La Serena–La Calera.'),
    ('Catemu', 'Tiltil', 'Une ramales de Valparaíso y Metropolitana; segunda entrada a Santiago desde el valle del Aconcagua.'),
    ('Santo Domingo', 'San Pedro', 'Une los ramales costeros de Valparaíso y Metropolitana (litoral central).'),
    ('Alhué', 'Las Cabras', 'Une ramales de Metropolitana y O’Higgins; anillo alternativo al tramo troncal San Bernardo–Rancagua.'),
    ('Navidad', 'Santo Domingo', 'Une ramales costeros de O’Higgins y Valparaíso (desembocadura del Rapel).'),
    ('Paredones', 'Vichuquén', 'Une ramales costeros de O’Higgins y Maule.'),
    ('Chimbarongo', 'Teno', 'Une ramales de O’Higgins y Maule por la Ruta 5; respaldo al tramo San Fernando–Curicó.'),
    ('Cauquenes', 'Quirihue', 'Une ramales del secano costero de Maule y Ñuble.'),
    ('Coelemu', 'Concepción', 'Une el ramal costero de Ñuble con el PIX Concepción; respaldo al tramo troncal Chillán–Concepción.'),
    ('Yungay', 'Tucapel', 'Une ramales de Ñuble y Biobío (Yungay–Huépil); respaldo al tramo Chillán–Los Ángeles.'),
    ('Renaico', 'Negrete', 'Une ramales de Araucanía y Biobío; respaldo al tramo Los Ángeles–Temuco.'),
    ('Tirúa', 'Saavedra', 'Ruta costera entre los ramales de Biobío y Araucanía.'),
    ('Toltén', 'San José de la Mariquina', 'Ruta costera entre los ramales de Araucanía y Los Ríos; respaldo al tramo Temuco–Valdivia.'),
    ('Pucón', 'Panguipulli', 'Une ramales lacustres de Araucanía y Los Ríos.'),
    ('Río Bueno', 'San Pablo', 'Une ramales de Los Ríos y Los Lagos; respaldo al tramo Valdivia–Osorno.'),
    ('Coyhaique', 'Villa Santa Lucía', 'Carretera Austral: une las troncales terrestres FOA de Aysén y Los Lagos; elimina la dependencia de la troncal submarina para Aysén.'),
]

# Comunas con nodos en la red pero sin su cabecera comunal como nodo: se asigna la población a un nodo (SUPUESTO)
ASIGNACION_POBLACION_EXTRA = {'Guallelemu': '05604'}   # El Quisco → POIIT Huallilemu ("Guallelemu" en el diagrama)
# POIIT adicionales hoja que no se pudieron ubicar en OSM: se excluyen (sin población asignable, no afectan el ruteo)
EXCLUIR_POIIT = {'Quebrada Seca', 'La Marquesa', 'El Abanico'}


def strip(s):
    return unicodedata.normalize('NFD', s).encode('ascii', 'ignore').decode().lower().strip()


def hav(a, b):
    R = 6371.0088
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))


def main():
    os.makedirs(os.path.join(OUT, 'escenarios'), exist_ok=True)
    report = []   # líneas para verificaciones.md

    coords = pd.read_csv(os.path.join(RAW, 'coordenadas_osm.csv'), dtype={'cut_ine': str})
    coords = coords.set_index('nodo')
    censo = pd.read_csv(os.path.join(RAW, 'censo2024_comunas_ine.csv'), dtype={'cut': str}).set_index('cut')
    fon = pd.read_csv(os.path.join(RAW, 'fon_triot_diagramas.csv'))
    excl = fon[fon.origen.isin(EXCLUIR_POIIT) | fon.destino.isin(EXCLUIR_POIIT)]
    fon = fon.drop(excl.index).reset_index(drop=True)

    # ------------------------------------------------------------------ nodos
    fon_nodes = set(fon.origen) | set(fon.destino)
    foa_nodes = {n for e in FOA for n in e[:2]}
    tro_nodes = {n for e in TRONCAL for n in e}
    cand_nodes = {n for e in CANDIDATOS for n in e[:2]}
    all_nodes = fon_nodes | foa_nodes | tro_nodes
    missing = sorted((all_nodes | cand_nodes) - set(coords.index))
    if missing:
        raise SystemExit(f'Faltan coordenadas para: {missing}')

    def capas(n):
        c = []
        if n in tro_nodes: c.append('TRONCAL')
        if n in fon_nodes: c.append('FON')
        if n in foa_nodes: c.append('FOA')
        return '|'.join(c)

    def tipo(n):
        if n in PIX: return 'CAPITAL_PIX'
        if n in fon_nodes: return 'POIIT'
        if n in foa_nodes: return 'FOA'
        return 'NODO_TRONCAL'

    # orden: de norte a sur (latitud descendente), PIX primero dentro de cada región no es necesario
    order = sorted(all_nodes, key=lambda n: -coords.loc[n, 'lat'])
    nid = {n: i + 1 for i, n in enumerate(order)}

    # cabeceras: nodos cuyo punto OSM se buscó como capital comunal y cayó en la comuna esperada
    cabecera = {n: (coords.loc[n, 'metodo'] == 'cut') for n in order}
    for n, cut in ASIGNACION_POBLACION_EXTRA.items():
        cabecera[n] = True
    # control: una cabecera por comuna
    cab_por_comuna = defaultdict(list)
    for n in order:
        if cabecera[n]:
            cab_por_comuna[coords.loc[n, 'cut_ine']].append(n)
    dup_cab = {k: v for k, v in cab_por_comuna.items() if len(v) > 1}
    if dup_cab:
        raise SystemExit(f'Más de una cabecera por comuna: {dup_cab}')

    rows = []
    for n in order:
        c = coords.loc[n]
        cut = c['cut_ine']
        reg = cut[:2]
        pop = int(censo.loc[cut, 'poblacion_2024']) if cabecera[n] else 0
        if n in PIX:
            fuente = f'{SRC_ADJ19 if reg not in ("09","14","10") else SRC_SUR20} (PIX)'
        elif n in fon_nodes:
            fr = fon[(fon.origen == n) | (fon.destino == n)].iloc[0]
            fuente = f"Subtel, {fr['fuente']}, p. {fr['pagina']} (POIIT)"
        elif n in foa_nodes:
            fuente = SRC_FOA17 + ('; ' + SRC_FOAPPT if n in ('Puerto Montt','Caleta Tortel','Punta Arenas','Puerto Williams') else '')
        else:
            fuente = 'Nodo troncal elegido por el grupo (ciudad en la Ruta 5 o capital sin PIX)'
        clas = 'SUPUESTO' if tipo(n) == 'NODO_TRONCAL' else ('ESTIMADO' if c['clasificacion_coord'] == 'ESTIMADO' else 'DATO')
        rows.append(dict(
            id=nid[n], nombre=n, tipo=tipo(n), capas=capas(n), region=REGION[reg], macrozona=MACRO[reg],
            comuna=censo.loc[cut, 'comuna'].title(), cut=cut, lat=round(float(c['lat']), 5), lon=round(float(c['lon']), 5),
            poblacion_comuna=pop, anio_poblacion=2024, cabecera_comunal=int(cabecera[n]),
            nombre_osm=c['osm_name'], osm_id=c['osm_id'], osm_place=c['osm_place'],
            fuente=fuente + f"; coord: OpenStreetMap {c['osm_id']}; comuna: polígono INE (punto en polígono); población: INE Censo 2024",
            clasificacion=clas,
        ))
    nodos = pd.DataFrame(rows)
    nodos.to_csv(os.path.join(OUT, 'nodos.csv'), index=False)
    P = dict(zip(nodos.nombre, nodos.poblacion_comuna))
    LL = {n: (float(coords.loc[n, 'lat']), float(coords.loc[n, 'lon'])) for n in all_nodes | cand_nodes}

    # ------------------------------------------------------------------ factor de ruta
    fon['geo_km'] = [hav(LL[o], LL[d]) for o, d in zip(fon.origen, fon.destino)]
    cal = fon[fon.km.notna() & (fon.geo_km >= 5)].copy()
    cal['ratio'] = cal.km / cal.geo_km
    f_med = float(cal.ratio.median())
    q1, q3 = cal.ratio.quantile([.25, .75])
    calib = dict(n=len(cal), mediana=f_med, q1=float(q1), q3=float(q3), media=float(cal.ratio.mean()))
    # tramos con ratio sospechoso (posible error de geocodificación o de lectura)
    sospechosos = cal[(cal.ratio < 0.95) | (cal.ratio > 3.0)][['region', 'triot', 'origen', 'destino', 'km', 'geo_km', 'ratio']]

    # ------------------------------------------------------------------ enlaces
    E = []

    def add(o, d, capa, subtipo, km, km_fuente, cap, fuente, clas, nota=''):
        E.append(dict(origen=nid.get(o, -1), destino=nid.get(d, -1), origen_nombre=o, destino_nombre=d, capa=capa,
                      subtipo=subtipo, km=round(km, 2), km_fuente=km_fuente, capacidad_gbps_por_sentido=cap,
                      fuente=fuente, clasificacion=clas, nota=nota))

    for _, r in fon.iterrows():
        if pd.notna(r.km):
            add(r.origen, r.destino, 'FON', f"TRIOT-{r.triot} ({r.tipo_poiit_destino})", float(r.km), 'DATO (km del TRIOT en el diagrama Subtel)',
                PARAMS['cap_fon'], f"Subtel, {r.fuente}, p. {r.pagina}", 'DATO')
        else:
            flex = 'flex' in str(r.triot)
            add(r.origen, r.destino, 'FON', 'referencial' + (' (conexión flexible, submarina/subacuática)' if flex else ''),
                r.geo_km * f_med, f'ESTIMADO (geodésica × factor de ruta {f_med:.3f})', PARAMS['cap_fon'],
                f"Subtel, {r.fuente}, p. {r.pagina}", 'ESTIMADO',
                'Topología del trazado referencial de las bases; km estimado (el diagrama no trae km)')
    for o, d in TRONCAL:
        add(o, d, 'TRONCAL', 'troncal entre capitales/ciudades', hav(LL[o], LL[d]) * f_med,
            f'ESTIMADO (geodésica × factor de ruta {f_med:.3f})', PARAMS['cap_troncal'],
            'Topología: SUPUESTO del grupo (eje Ruta 5); sin fuente pública verificable del trazado', 'SUPUESTO')
    sub = [e for e in FOA if e[2] == 'SUBMARINO']
    geo_sub = sum(hav(LL[o], LL[d]) for o, d, *_ in sub)
    f_sub = PARAMS['km_foa_submarino_total'] / geo_sub
    for o, d, st, tp, clt, nota in FOA:
        g = hav(LL[o], LL[d])
        if st == 'SUBMARINO':
            add(o, d, 'FOA', 'submarino', g * f_sub,
                f'ESTIMADO (geodésica × {f_sub:.3f}, escalado a {PARAMS["km_foa_submarino_total"]} km totales)',
                PARAMS['cap_foa_submarino'], SRC_FOA17 + '; ' + SRC_FOAPPT, 'ESTIMADO', nota)
        else:
            add(o, d, 'FOA', f'terrestre ({tp})', g * f_med, f'ESTIMADO (geodésica × factor de ruta {f_med:.3f})',
                PARAMS['cap_foa_terrestre'], SRC_FOA17, clt, nota)
    for o, d, just in CANDIDATOS:
        add(o, d, 'CANDIDATO', 'inversión candidata', hav(LL[o], LL[d]) * f_med,
            f'ESTIMADO (geodésica × factor de ruta {f_med:.3f})', PARAMS['cap_candidato'],
            'Propuesta del grupo', 'SUPUESTO', just)
    enl = pd.DataFrame(E)
    enl.insert(0, 'id', range(1, len(enl) + 1))

    # puentes (grafo base no dirigido, sin candidatos)
    base = enl[enl.capa != 'CANDIDATO']
    G = nx.Graph()
    G.add_nodes_from(nodos.id)
    for _, r in base.iterrows():
        G.add_edge(r.origen, r.destino, id=r.id)
    bridges = {frozenset(b) for b in nx.bridges(G)}
    enl['es_puente'] = [int(r.capa != 'CANDIDATO' and frozenset((r.origen, r.destino)) in bridges) for _, r in enl.iterrows()]
    enl['revisar_km_gt_300'] = [int(r.km > PARAMS['umbral_km_revision'] and r.subtipo != 'submarino') for _, r in enl.iterrows()]

    # ------------------------------------------------------------------ demanda
    tot_bytes = (PARAMS['trafico_fijo_2025_milesTB'] + PARAMS['trafico_movil_2025_milesTB']) * 1e15
    avg_gbps = tot_bytes * 8 / (365.25 * 86400) / 1e9
    peak_gbps = avg_gbps * PARAMS['factor_hora_punta']
    tau = peak_gbps / PARAMS['poblacion_nacional_2024']          # Gbps por habitante en hora punta
    f = PARAMS['fraccion_salida_internacional']; dl = PARAMS['fraccion_bajada']
    popn = [n for n in order if P[n] > 0]
    Ptot = sum(P[n] for n in popn)
    Psq = sum(P[n] ** 2 for n in popn)
    D_dom = (1 - f) * tau * Ptot / 2
    k = D_dom / (Ptot ** 2 - Psq)
    dem = defaultdict(float)
    for i in popn:
        for j in popn:
            if i == j: continue
            dist = hav(LL[i], LL[j])
            dem[(i, j)] += k * P[i] * P[j] / (dist ** PARAMS['gamma'] if PARAMS['gamma'] else 1.0)
    exit_pairs = set()
    for i in popn:
        if i == REG_EXIT: continue
        dem[(REG_EXIT, i)] += f * dl * tau * P[i]
        dem[(i, REG_EXIT)] += f * (1 - dl) * tau * P[i]
        exit_pairs |= {(REG_EXIT, i), (i, REG_EXIT)}
    total_dem = sum(dem.values())
    # se conservan siempre los pares con la salida internacional (para que ningún nodo quede sin demanda)
    forced = sorted(exit_pairs, key=lambda p: -dem[p])
    rest = sorted((p for p in dem if p not in exit_pairs), key=lambda p: -dem[p])
    keep = forced + rest[:max(0, PARAMS['max_productos'] - len(forced))]
    kept_dem = sum(dem[p] for p in keep)
    dbase = pd.DataFrame([(nid[o], nid[d], round(dem[(o, d)], 6), o, d) for o, d in keep],
                         columns=['origen', 'destino', 'demanda', 'origen_nombre', 'destino_nombre'])
    dbase = dbase.sort_values('demanda', ascending=False).reset_index(drop=True)
    dbase.insert(0, 'id_producto', range(1, len(dbase) + 1))
    dbase.to_csv(os.path.join(OUT, 'demandas_base.csv'), index=False)
    demand_info = dict(trafico_anual_PB=tot_bytes / 1e15, promedio_gbps=avg_gbps, punta_gbps=peak_gbps,
                       tau_mbps_hab=tau * 1e3, poblacion_en_red=Ptot, nodos_con_poblacion=len(popn), k=k,
                       pares_total=len(dem), pares_conservados=len(keep), demanda_total_gbps=total_dem,
                       demanda_conservada_gbps=kept_dem, fraccion_conservada=kept_dem / total_dem,
                       pares_salida=len(exit_pairs))

    # ------------------------------------------------------------------ fallas: demanda desconectada
    dem_by_pair = {(r.origen, r.destino): r.demanda for r in dbase.itertuples()}
    tot_kept = dbase.demanda.sum()

    def disconnected_after(edge_id):
        H = G.copy()
        r = enl.loc[enl.id == edge_id].iloc[0]
        H.remove_edge(r.origen, r.destino)
        comp = {}
        for ci, cc in enumerate(nx.connected_components(H)):
            for v in cc: comp[v] = ci
        lost = sum(v for (o, d), v in dem_by_pair.items() if comp[o] != comp[d])
        return lost

    fallas = []
    for r in enl[enl.capa.isin(['TRONCAL', 'FOA'])].itertuples():
        fallas.append((r.id, r.capa, r.subtipo, r.origen_nombre, r.destino_nombre, r.es_puente))
    # muestra FON: por región, el tramo que sale del PIX con más demanda aguas abajo + uno intermedio + uno extremo
    fon_e = enl[enl.capa == 'FON'].copy()
    fon_e['lost'] = [disconnected_after(i) if p else 0.0 for i, p in zip(fon_e.id, fon_e.es_puente)]
    reg_of = dict(zip(nodos.id, nodos.region))
    fon_e['region'] = [reg_of[o] for o in fon_e.origen]
    sample = []
    for reg, g in fon_e.groupby('region'):
        g = g.sort_values('lost', ascending=False)
        pick = [g.iloc[0]]
        if len(g) > 2: pick.append(g.iloc[len(g) // 2])
        if len(g) > 1: pick.append(g.iloc[-1])
        sample += [p.id for p in pick]
    for r in enl[enl.id.isin(sample)].itertuples():
        fallas.append((r.id, r.capa, r.subtipo, r.origen_nombre, r.destino_nombre, r.es_puente))
    fl = pd.DataFrame(fallas, columns=['id_enlace', 'capa', 'subtipo', 'origen', 'destino', 'es_puente'])
    fl['demanda_desconectada_gbps'] = [round(disconnected_after(i), 4) if p else 0.0 for i, p in zip(fl.id_enlace, fl.es_puente)]
    fl['demanda_desconectada_pct'] = (100 * fl.demanda_desconectada_gbps / tot_kept).round(3)
    fl.to_csv(os.path.join(OUT, 'fallas.csv'), index=False)
    enl['demanda_desconectada_si_falla_gbps'] = [round(disconnected_after(i), 4) if p else 0.0 for i, p in zip(enl.id, enl.es_puente)]
    enl.to_csv(os.path.join(OUT, 'enlaces.csv'), index=False)

    # ------------------------------------------------------------------ instancia base (formato del grupo)
    def write_instance(path, edges_df, prods):
        arcs = []
        for r in edges_df.itertuples():
            arcs.append((r.origen, r.destino, r.capacidad_gbps_por_sentido))
            arcs.append((r.destino, r.origen, r.capacidad_gbps_por_sentido))
        with open(path, 'w') as fh:
            fh.write(f'{len(nodos)} {len(arcs)} {len(prods)}\n')
            for o, d, c in arcs:
                fh.write(f'{o} {d} 1 {c:g} 0\n')
            for k_, (o, d, v) in enumerate(prods, start=1):
                fh.write(f'{k_} {o} {v:.6f}\n{k_} {d} {-v:.6f}\n')
        return len(arcs)

    prods = list(zip(dbase.origen, dbase.destino, dbase.demanda))
    n_arcs = write_instance(os.path.join(OUT, 'instancia_base.txt'), base, prods)

    json.dump(dict(params=PARAMS, calib=calib, f_sub=f_sub, demand=demand_info, n_arcs=n_arcs,
                   sospechosos=sospechosos.to_dict('records'), cab_por_comuna={k: v for k, v in cab_por_comuna.items()}),
              open(os.path.join(OUT, 'datos_crudos', '_build_info.json'), 'w'), ensure_ascii=False, indent=1, default=str)
    print(json.dumps(dict(calib=calib, f_sub=f_sub, demand=demand_info, n_nodos=len(nodos), n_enlaces_base=len(base),
                          n_arcos=n_arcs, puentes=int(enl.es_puente.sum())), ensure_ascii=False, indent=1, default=str))
    if len(sospechosos):
        print('TRAMOS SOSPECHOSOS:\n', sospechosos.to_string())


if __name__ == '__main__':
    main()
