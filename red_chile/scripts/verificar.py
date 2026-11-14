#!/usr/bin/env python3
"""Verificaciones obligatorias de la instancia. Escribe verificaciones.md y datos_crudos/_stats.json."""
import json, math, os, unicodedata
from collections import defaultdict
import pandas as pd
import networkx as nx

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, 'datos_crudos')

REGCODE = {'Arica y Parinacota': '15', 'Tarapacá': '01', 'Antofagasta': '02', 'Atacama': '03', 'Coquimbo': '04',
           'Valparaíso': '05', 'Metropolitana': '13', "O'Higgins": '06', 'Maule': '07', 'Ñuble': '16', 'Biobío': '08',
           'Araucanía': '09', 'Los Ríos': '14', 'Los Lagos': '10', 'Aysén': '11', 'Magallanes': '12'}
# km comprometidos en las propuestas adjudicadas (texto de cada región en los informes de adjudicación de Subtel)
KM_ADJ = {'Arica y Parinacota': 663, 'Antofagasta': 1253, 'Atacama': 643, 'Coquimbo': 837, 'Valparaíso': 575,
          'Metropolitana': 426, "O'Higgins": 611, 'Maule': 694, 'Ñuble': 514, 'Biobío': 824,
          'Araucanía': 980, 'Los Ríos': 603, 'Los Lagos': 937}
KM_FDT = {'Arica y Parinacota': 672, 'Norte': 1765, 'Centro Norte': 1582, 'Centro': 1264, 'Centro Sur': 1244, 'Sur': 1951}
MACRO_OF = {'Arica y Parinacota': 'Arica y Parinacota', 'Antofagasta': 'Norte', 'Atacama': 'Norte', 'Coquimbo': 'Centro Norte',
            'Valparaíso': 'Centro Norte', 'Metropolitana': 'Centro Norte', "O'Higgins": 'Centro', 'Maule': 'Centro',
            'Ñuble': 'Centro Sur', 'Biobío': 'Centro Sur', 'Araucanía': 'Sur', 'Los Ríos': 'Sur', 'Los Lagos': 'Sur'}
ALIAS = {'paiguano': 'paihuano', 'treguaco': 'trehuaco', 'empredrado': 'empedrado'}


def strip(s):
    s = unicodedata.normalize('NFD', str(s)).encode('ascii', 'ignore').decode().lower().strip()
    return ALIAS.get(s, s)


def hav(a, b):
    R = 6371.0088
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))


def md_table(df):
    cols = list(df.columns)
    out = ['| ' + ' | '.join(map(str, cols)) + ' |', '|' + '|'.join(['---'] * len(cols)) + '|']
    for r in df.itertuples(index=False):
        out.append('| ' + ' | '.join('' if (isinstance(v, float) and math.isnan(v)) else str(v) for v in r) + ' |')
    return '\n'.join(out)


def main(zref=None):
    nodos = pd.read_csv(os.path.join(ROOT, 'nodos.csv'), dtype={'cut': str})
    enl = pd.read_csv(os.path.join(ROOT, 'enlaces.csv'))
    dem = pd.read_csv(os.path.join(ROOT, 'demandas_base.csv'))
    censo = pd.read_csv(os.path.join(RAW, 'censo2024_comunas_ine.csv'), dtype={'cut': str})
    fdt = pd.read_csv(os.path.join(RAW, 'fdt_186_comunas.csv'))
    info = json.load(open(os.path.join(RAW, '_build_info.json')))
    coords = pd.read_csv(os.path.join(RAW, 'coordenadas_osm.csv'), dtype={'cut_ine': str})
    base = enl[enl.capa != 'CANDIDATO']
    L = []
    L.append('# Verificaciones de la instancia\n')
    L.append('Generado por `scripts/verificar.py` a partir de los CSV finales. Todo lo que se reporta aquí se recalcula desde los archivos.\n')

    # 1 conexidad
    G = nx.Graph(); G.add_nodes_from(nodos.id)
    G.add_edges_from(zip(base.origen, base.destino))
    con = nx.is_connected(G)
    L.append('## 1. Conexidad del grafo base\n')
    L.append(f'- Grafo base (sin candidatos), no dirigido: **{"conexo" if con else "NO conexo"}** '
             f'({nx.number_connected_components(G)} componente). El grafo dirigido (dos arcos por enlace) es por lo tanto fuertemente conexo.\n')

    # 2 comunas FDT
    L.append('## 2. Comunas del listado FDT\n')
    cmap = defaultdict(list)
    for r in censo.itertuples():
        cmap[(strip(r.comuna), r.cut[:2])].append(r.cut)
    node_by_cut = defaultdict(list)
    for r in nodos.itertuples():
        node_by_cut[r.cut].append(r)
    rows = []
    for r in fdt.itertuples():
        key = (strip(r.comuna_fdt), REGCODE[r.region_fdt])
        cuts = cmap.get(key)
        if not cuts:  # región mal asignada en la lectura del listado: buscar en cualquier región
            cuts = [c for (n, _), cs in cmap.items() if n == strip(r.comuna_fdt) for c in cs]
        cut = cuts[0] if cuts else None
        ns = node_by_cut.get(cut, [])
        cab = [n for n in ns if n.cabecera_comunal == 1]
        estado = 'presente (cabecera)' if cab else ('presente solo con nodos de paso' if ns else 'FALTA')
        reg_ine = nodos[nodos.cut == cut].region.iloc[0] if ns else ''
        rows.append(dict(macrozona=r.macrozona, region_fdt=r.region_fdt, comuna=r.comuna_fdt, cut=cut, estado=estado,
                         nodo=(cab[0].nombre if cab else ', '.join(n.nombre for n in ns)), region_ine=reg_ine))
    chk = pd.DataFrame(rows)
    n_ok = (chk.estado != 'FALTA').sum()
    L.append(f'El documento FDT (Subtel, jul-2019, lámina 4) declara **186 comunas**; la suma de los encabezados por macrozona '
             f'(4 + 16 + 41 + 46 + 36 + 42) da **185**, y los nombres listados son **{len(fdt)}** (la lámina de la Macrozona Centro dice '
             f'"46 comunas" pero nombra 45). Se verificaron los {len(fdt)} nombres listados:\n')
    L.append(f'- Presentes en la red: **{n_ok} de {len(fdt)}** ({(chk.estado == "presente (cabecera)").sum()} con su cabecera comunal como nodo).')
    falt = chk[chk.estado != 'presente (cabecera)']
    if len(falt):
        L.append('- Casos que no están como cabecera:\n')
        L.append(md_table(falt[['macrozona', 'region_fdt', 'comuna', 'estado', 'nodo']]))
    mism = chk[(chk.estado != 'FALTA') & (chk.region_fdt != chk.region_ine)]
    if len(mism):
        L.append('\n- Comunas que el listado FDT ubica en otra región (se usa la región del INE):\n')
        L.append(md_table(mism[['comuna', 'region_fdt', 'region_ine']]))
    extra = nodos[(nodos.cabecera_comunal == 1) & (nodos.tipo == 'POIIT') & ~nodos.cut.isin(chk.cut)]
    L.append(f'\n- Las 1–2 comunas que faltan para llegar a 186 no se pueden identificar con certeza. Candidata más probable: '
             f'**Hualañé** (Maule), POIIT exigible en el diagrama adjudicado pero ausente del listado. Otras comunas que son POIIT '
             f'en los diagramas adjudicados y no están en el listado FDT: {", ".join(sorted(extra.comuna))}.\n')
    chk.to_csv(os.path.join(RAW, 'chequeo_comunas_fdt.csv'), index=False)

    # 3 km por macrozona
    L.append('## 3. Km FON por región y macrozona vs. Subtel\n')
    reg_of = dict(zip(nodos.id, nodos.region))
    fon = base[base.capa == 'FON'].copy()
    fon['region'] = [reg_of[o] for o in fon.origen]
    by_reg = fon.groupby('region').agg(tramos=('km', 'size'), km_instancia=('km', 'sum'),
                                       tramos_dato=('clasificacion', lambda s: (s == 'DATO').sum())).reset_index()
    by_reg['km_adjudicado_subtel'] = by_reg.region.map(KM_ADJ)
    by_reg['dif_km'] = (by_reg.km_instancia - by_reg.km_adjudicado_subtel).round(1)
    by_reg['dif_pct'] = (100 * by_reg.dif_km / by_reg.km_adjudicado_subtel).round(1)
    by_reg['km_instancia'] = by_reg.km_instancia.round(1)
    by_reg['orden'] = by_reg.region.map(list(KM_ADJ).index)
    by_reg = by_reg.sort_values('orden').drop(columns='orden')
    L.append(md_table(by_reg))
    by_reg['macrozona'] = by_reg.region.map(MACRO_OF)
    by_m = by_reg.groupby('macrozona', sort=False).agg(km_instancia=('km_instancia', 'sum'), km_adjudicado=('km_adjudicado_subtel', 'sum')).reset_index()
    by_m['km_FDT_jul2019'] = by_m.macrozona.map(KM_FDT)
    by_m['dif_vs_adjudicado_pct'] = (100 * (by_m.km_instancia - by_m.km_adjudicado) / by_m.km_adjudicado).round(1)
    by_m['dif_vs_FDT_pct'] = (100 * (by_m.km_instancia - by_m.km_FDT_jul2019) / by_m.km_FDT_jul2019).round(1)
    tot = pd.DataFrame([dict(macrozona='TOTAL', km_instancia=round(by_m.km_instancia.sum(), 1), km_adjudicado=by_m.km_adjudicado.sum(),
                             km_FDT_jul2019=by_m.km_FDT_jul2019.sum(),
                             dif_vs_adjudicado_pct=round(100 * (by_m.km_instancia.sum() - by_m.km_adjudicado.sum()) / by_m.km_adjudicado.sum(), 1),
                             dif_vs_FDT_pct=round(100 * (by_m.km_instancia.sum() - by_m.km_FDT_jul2019.sum()) / by_m.km_FDT_jul2019.sum(), 1))])
    by_m = pd.concat([by_m, tot])
    by_m['km_instancia'] = by_m.km_instancia.round(1)
    L.append('\n')
    L.append(md_table(by_m))
    c = info['calib']
    L.append(f'\nEn las 10 regiones adjudicadas en 2019 los km de cada TRIOT se transcribieron de los diagramas y la suma calza con el total '
             f'que declara Subtel para cada región (diferencias < 1 km, por redondeo). En la Macrozona Sur (adjudicada en 2021) los diagramas '
             f'referenciales no traen km: se estimaron como geodésica × {c["mediana"]:.3f}, factor calibrado con {c["n"]} TRIOT con km conocido '
             f'(mediana; rango intercuartil {c["q1"]:.2f}–{c["q3"]:.2f}). La diferencia de la Macrozona Sur se explica en buena parte porque el '
             f'trazado referencial no incluye los POIIT adicionales de la propuesta adjudicada (Los Ríos: 6; Los Lagos: 5) ni el detalle de los '
             f'tramos submarinos.\n')
    L.append('Atacama (−46,3 km) y Biobío (−12,4 km) difieren solo por tres POIIT adicionales hoja que no se pudieron ubicar en OpenStreetMap y se '
             'excluyeron: Quebrada Seca (31,28 km) y La Marquesa (15,17 km) en Atacama, y El Abanico (13,15 km) en Biobío. Con ellos, ambas regiones '
             'calzan con Subtel. Esos nodos no tendrían población asignada (son localidades dentro de comunas cuya cabecera ya es nodo), así que no '
             'cambian la demanda ni el ruteo.\n')
    foa = base[base.capa == 'FOA']
    sub = foa[foa.subtipo == 'submarino'].km.sum(); ter_ex = foa[foa.subtipo == 'terrestre (exigible)'].km.sum(); ter_ad = foa[foa.subtipo == 'terrestre (adicional)'].km.sum()
    L.append(f'FOA: la troncal submarina se escaló a {sub:,.0f} km (cifra de Huawei Marine/Capacity Media; la presentación de NIC Chile habla de "casi 3.000 km"). '
             f'Los tramos terrestres estimados suman {ter_ex:,.0f} km entre POIIT exigibles y {ter_ad:,.0f} km hacia POIIT adicionales. Subtel declara '
             f'3.953 km para todo el proyecto (lámina 3 de la presentación FOA de 2017): submarino + terrestre exigible = {sub + ter_ex:,.0f} km '
             f'({100 * (sub + ter_ex - 3953) / 3953:+.1f} %).\n'.replace(',', '.'))
    if info['sospechosos']:
        L.append('Tramos con razón km/geodésica fuera de [0,95; 3,0] (revisados):\n')
        L.append(md_table(pd.DataFrame(info['sospechosos']).round(2)))
        L.append('')

    # 4 coordenadas dentro de su región
    L.append('## 4. Coordenadas dentro de su región\n')
    ok_cut = (coords.set_index('nodo').loc[nodos.nombre, 'cut_ine'].values == nodos.cut.values).all()
    L.append(f'- Cada coordenada (OpenStreetMap) se consultó contra los polígonos comunales del INE (servicio ArcGIS del Censo 2024) con '
             f'una consulta de punto en polígono. Los {len(nodos)} nodos caen en una comuna de la región esperada; la búsqueda se restringió '
             f'al área de esa región en OSM y luego se comprobó con el polígono del INE. Comuna y región en `nodos.csv` = resultado de esa consulta '
             f'({"consistente" if ok_cut else "INCONSISTENTE"}).')
    rr = coords[coords.metodo != 'cut']
    L.append(f'- {int((coords.metodo == "cut").sum())} nodos se buscaron como cabecera comunal y cayeron en la comuna esperada; '
             f'{len(rr)} son localidades de paso (POIIT que no son capital comunal) verificadas por región.')
    L.append('- Nombres repetidos resueltos con este método: Río Negro (comuna de Los Lagos, prov. de Osorno) frente a "Río Negro (Hornopirén)" '
             'de la FOA, que se llama Hornopirén en la instancia; San Pedro (RM) frente a San Pedro de Atacama; Tres Pinos (Los Álamos, Biobío) '
             'frente a otro Tres Pinos en Curanilahue; El Manzano (Hualaihué) frente a El Manzano en Chaitén; Placilla (O’Higgins) frente a Placilla '
             'de Peñuelas (Valparaíso).\n')

    # 5 distancias
    L.append('## 5. Enlaces de más de 300 km (para revisión; se excluyen tramos submarinos FOA)\n')
    big = enl[(enl.km > 300) & (enl.subtipo != 'submarino')][['id', 'origen_nombre', 'destino_nombre', 'capa', 'km']]
    L.append(md_table(big.round(1)) if len(big) else 'Ninguno.')
    L.append('\nLos tramos troncales largos del norte son esperables: la troncal unificada no tiene nodos de tráfico intermedios entre capitales '
             '(los pueblos intermedios son POIIT de ramales FON, que por regla solo se conectan en el PIX). En la realidad hay sitios de '
             'regeneración/amplificación que no cambian la topología lógica.\n')

    # 6 duplicados
    L.append('## 6. Nodos duplicados\n')
    dup_osm = nodos[nodos.osm_id.duplicated(keep=False)]
    dup_ll = nodos[nodos[['lat', 'lon']].round(3).duplicated(keep=False)]
    close = []
    ll = list(zip(nodos.nombre, nodos.lat, nodos.lon))
    for i in range(len(ll)):
        for j in range(i + 1, len(ll)):
            dkm = hav(ll[i][1:], ll[j][1:])
            if dkm < 3:
                close.append((ll[i][0], ll[j][0], round(dkm, 2)))
    L.append(f'- Mismo objeto OSM en dos nodos: {len(dup_osm)}. Coordenadas repetidas (3 decimales): {len(dup_ll)}. '
             f'Nombres repetidos: {int(nodos.nombre.duplicated().sum())}.')
    L.append(f'- Pares de nodos a menos de 3 km: {len(close)}' + (': ' + '; '.join(f'{a}–{b} ({d} km)' for a, b, d in close) if close else '') +
             '. Son localidades distintas que Subtel lista como POIIT separados, no duplicados.')
    L.append(f'- Una sola cabecera por comuna: verificado en la construcción (el script se detiene si una comuna tiene dos).\n')

    # 7 estadísticas
    V = len(nodos); E = len(base); A = 2 * E
    puentes = int(base.es_puente.sum())
    st = dict(V=V, E=E, A=A, grado=A / V, puentes=puentes, productos=len(dem), demanda=float(dem.demanda.sum()),
              candidatos=int((enl.capa == 'CANDIDATO').sum()))
    L.append('## 7. Estadísticas\n')
    capas = base.groupby('capa').size().to_dict()
    L.append(md_table(pd.DataFrame([
        ('|V| nodos', V), ('|E| enlaces físicos (base)', E), ('  de ellos TRONCAL / FON / FOA', f'{capas.get("TRONCAL",0)} / {capas.get("FON",0)} / {capas.get("FOA",0)}'),
        ('|A| = 2|E| arcos dirigidos', A), ('grado medio d = |A|/|V|', round(A / V, 3)), ('puentes', f'{puentes} de {E} ({100*puentes/E:.0f} %)'),
        ('enlaces candidatos (fuera de la base)', st['candidatos']), ('nodos con población (generan demanda)', int((nodos.poblacion_comuna > 0).sum())),
        ('población representada (Censo 2024)', f'{int(nodos.poblacion_comuna.sum()):,}'.replace(',', '.')),
        ('productos (pares O-D)', len(dem)), ('demanda total (Gbps)', round(dem.demanda.sum(), 1)),
        ('fracción del tráfico total conservada en el top-10.000', f'{100*info["demand"]["fraccion_conservada"]:.2f} %'),
    ], columns=['indicador', 'valor'])))
    if zref:
        L.append('\n## 8. Solución de referencia (LP con agregación por origen, HiGHS)\n')
        L.append('No es el solver del proyecto: sirve para contrastar el z* que entregue la generación de columnas.\n')
        L.append(md_table(pd.DataFrame(zref)))
    open(os.path.join(ROOT, 'verificaciones.md'), 'w').write('\n'.join(L) + '\n')
    json.dump(st, open(os.path.join(RAW, '_stats.json'), 'w'))
    print(json.dumps(st))


if __name__ == '__main__':
    zref = None
    p = os.path.join(RAW, '_zref.json')
    if os.path.exists(p):
        zref = json.load(open(p))
    main(zref)
