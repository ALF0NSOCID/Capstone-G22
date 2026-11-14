# Verificaciones de la instancia

Generado por `scripts/verificar.py` a partir de los CSV finales. Todo lo que se reporta aquí se recalcula desde los archivos.

## 1. Conexidad del grafo base

- Grafo base (sin candidatos), no dirigido: **conexo** (1 componente). El grafo dirigido (dos arcos por enlace) es por lo tanto fuertemente conexo.

## 2. Comunas del listado FDT

El documento FDT (Subtel, jul-2019, lámina 4) declara **186 comunas**; la suma de los encabezados por macrozona (4 + 16 + 41 + 46 + 36 + 42) da **185**, y los nombres listados son **184** (la lámina de la Macrozona Centro dice "46 comunas" pero nombra 45). Se verificaron los 184 nombres listados:

- Presentes en la red: **183 de 184** (183 con su cabecera comunal como nodo).
- Casos que no están como cabecera:

| macrozona | region_fdt | comuna | estado | nodo |
|---|---|---|---|---|
| Centro Norte | Valparaíso | El Tabo | FALTA |  |

- Las 1–2 comunas que faltan para llegar a 186 no se pueden identificar con certeza. Candidata más probable: **Hualañé** (Maule), POIIT exigible en el diagrama adjudicado pero ausente del listado. Otras comunas que son POIIT en los diagramas adjudicados y no están en el listado FDT: Chaitén, Chimbarongo, Hualañé, Lampa, Los Vilos, Melipilla, Mulchén, Santo Domingo, Teno, Tiltil, Ñiquén.

## 3. Km FON por región y macrozona vs. Subtel

| region | tramos | km_instancia | tramos_dato | km_adjudicado_subtel | dif_km | dif_pct |
|---|---|---|---|---|---|---|
| Arica y Parinacota | 11 | 662.8 | 11 | 663 | -0.2 | -0.0 |
| Antofagasta | 16 | 1253.6 | 16 | 1253 | 0.6 | 0.0 |
| Atacama | 11 | 596.7 | 11 | 643 | -46.3 | -7.2 |
| Coquimbo | 17 | 836.7 | 17 | 837 | -0.3 | -0.0 |
| Valparaíso | 21 | 574.2 | 21 | 575 | -0.8 | -0.1 |
| Metropolitana | 14 | 425.4 | 14 | 426 | -0.6 | -0.1 |
| O'Higgins | 27 | 611.2 | 27 | 611 | 0.2 | 0.0 |
| Maule | 24 | 693.8 | 24 | 694 | -0.2 | -0.0 |
| Ñuble | 18 | 514.4 | 18 | 514 | 0.4 | 0.1 |
| Biobío | 23 | 811.6 | 23 | 824 | -12.4 | -1.5 |
| Araucanía | 27 | 1039.0 | 0 | 980 | 59.0 | 6.0 |
| Los Ríos | 7 | 334.2 | 0 | 603 | -268.8 | -44.6 |
| Los Lagos | 13 | 666.3 | 0 | 937 | -270.7 | -28.9 |


| macrozona | km_instancia | km_adjudicado | km_FDT_jul2019 | dif_vs_adjudicado_pct | dif_vs_FDT_pct |
|---|---|---|---|---|---|
| Arica y Parinacota | 662.8 | 663 | 672 | -0.0 | -1.4 |
| Norte | 1850.3 | 1896 | 1765 | -2.4 | 4.8 |
| Centro Norte | 1836.3 | 1838 | 1582 | -0.1 | 16.1 |
| Centro | 1305.0 | 1305 | 1264 | 0.0 | 3.2 |
| Centro Sur | 1326.0 | 1338 | 1244 | -0.9 | 6.6 |
| Sur | 2039.5 | 2520 | 1951 | -19.1 | 4.5 |
| TOTAL | 9019.9 | 9560 | 8478 | -5.6 | 6.4 |

En las 10 regiones adjudicadas en 2019 los km de cada TRIOT se transcribieron de los diagramas y la suma calza con el total que declara Subtel para cada región (diferencias < 1 km, por redondeo). En la Macrozona Sur (adjudicada en 2021) los diagramas referenciales no traen km: se estimaron como geodésica × 1.319, factor calibrado con 176 TRIOT con km conocido (mediana; rango intercuartil 1.19–1.49). La diferencia de la Macrozona Sur se explica en buena parte porque el trazado referencial no incluye los POIIT adicionales de la propuesta adjudicada (Los Ríos: 6; Los Lagos: 5) ni el detalle de los tramos submarinos.

Atacama (−46,3 km) y Biobío (−12,4 km) difieren solo por tres POIIT adicionales hoja que no se pudieron ubicar en OpenStreetMap y se excluyeron: Quebrada Seca (31,28 km) y La Marquesa (15,17 km) en Atacama, y El Abanico (13,15 km) en Biobío. Con ellos, ambas regiones calzan con Subtel. Esos nodos no tendrían población asignada (son localidades dentro de comunas cuya cabecera ya es nodo), así que no cambian la demanda ni el ruteo.

FOA: la troncal submarina se escaló a 2.800 km (cifra de Huawei Marine/Capacity Media; la presentación de NIC Chile habla de "casi 3.000 km"). Los tramos terrestres estimados suman 1.038 km entre POIIT exigibles y 923 km hacia POIIT adicionales. Subtel declara 3.953 km para todo el proyecto (lámina 3 de la presentación FOA de 2017): submarino + terrestre exigible = 3.838 km (-2.9 %).

Tramos con razón km/geodésica fuera de [0,95; 3,0] (revisados):

| region | triot | origen | destino | km | geo_km | ratio |
|---|---|---|---|---|---|---|
| Arica y Parinacota | AYP15-07 | Socoroma | Putre | 27.5 | 8.75 | 3.14 |
| Arica y Parinacota | AYP15-02 | Codpa | Camarones | 83.8 | 23.16 | 3.62 |
| Arica y Parinacota | AYP15-10 | Cuya | Caleta Camarones | 10.28 | 12.27 | 0.84 |
| Valparaíso | CTN05-15 | Algarrobo | Guallelemu | 2.92 | 6.43 | 0.45 |
| O'Higgins | CTO06-26 | Peralillo | Población | 6.0 | 7.01 | 0.86 |

## 4. Coordenadas dentro de su región

- Cada coordenada (OpenStreetMap) se consultó contra los polígonos comunales del INE (servicio ArcGIS del Censo 2024) con una consulta de punto en polígono. Los 285 nodos caen en una comuna de la región esperada; la búsqueda se restringió al área de esa región en OSM y luego se comprobó con el polígono del INE. Comuna y región en `nodos.csv` = resultado de esa consulta (consistente).
- 228 nodos se buscaron como cabecera comunal y cayeron en la comuna esperada; 57 son localidades de paso (POIIT que no son capital comunal) verificadas por región.
- Nombres repetidos resueltos con este método: Río Negro (comuna de Los Lagos, prov. de Osorno) frente a "Río Negro (Hornopirén)" de la FOA, que se llama Hornopirén en la instancia; San Pedro (RM) frente a San Pedro de Atacama; Tres Pinos (Los Álamos, Biobío) frente a otro Tres Pinos en Curanilahue; El Manzano (Hualaihué) frente a El Manzano en Chaitén; Placilla (O’Higgins) frente a Placilla de Peñuelas (Valparaíso).

## 5. Enlaces de más de 300 km (para revisión; se excluyen tramos submarinos FOA)

| id | origen_nombre | destino_nombre | capa | km |
|---|---|---|---|---|
| 232 | Pozo Almonte | Antofagasta | TRONCAL | 503.7 |
| 233 | Antofagasta | Copiapó | TRONCAL | 545.8 |
| 234 | Copiapó | La Serena | TRONCAL | 390.4 |
| 235 | La Serena | La Calera | TRONCAL | 423.4 |
| 305 | Coyhaique | Villa Santa Lucía | CANDIDATO | 318.1 |

Los tramos troncales largos del norte son esperables: la troncal unificada no tiene nodos de tráfico intermedios entre capitales (los pueblos intermedios son POIIT de ramales FON, que por regla solo se conectan en el PIX). En la realidad hay sitios de regeneración/amplificación que no cambian la topología lógica.

## 6. Nodos duplicados

- Mismo objeto OSM en dos nodos: 0. Coordenadas repetidas (3 decimales): 0. Nombres repetidos: 0.
- Pares de nodos a menos de 3 km: 3: Totoral–Guallelemu (1.8 km); Hernán Brañas–Coelemu (2.37 km); Santa Bárbara–Quilaco (2.27 km). Son localidades distintas que Subtel lista como POIIT separados, no duplicados.
- Una sola cabecera por comuna: verificado en la construcción (el script se detiene si una comuna tiene dos).

## 7. Estadísticas

| indicador | valor |
|---|---|
| |V| nodos | 285 |
| |E| enlaces físicos (base) | 285 |
|   de ellos TRONCAL / FON / FOA | 21 / 229 / 35 |
| |A| = 2|E| arcos dirigidos | 570 |
| grado medio d = |A|/|V| | 2.0 |
| puentes | 269 de 285 (94 %) |
| enlaces candidatos (fuera de la base) | 20 |
| nodos con población (generan demanda) | 229 |
| población representada (Censo 2024) | 8.850.246 |
| productos (pares O-D) | 10000 |
| demanda total (Gbps) | 6931.0 |
| fracción del tráfico total conservada en el top-10.000 | 97.83 % |

## 8. Solución de referencia (LP con agregación por origen, HiGHS)

No es el solver del proyecto: sirve para contrastar el z* que entregue la generación de columnas.

| caso | z_ref | arco_critico |
|---|---|---|
| escenario base | 0.4898 | San Bernardo → Calera de Tango (800 Gbps) |
| escenario uniforme_+25 | 0.6123 | San Bernardo → Calera de Tango (800 Gbps) |
| escenario uniforme_+50 | 0.7347 | San Bernardo → Calera de Tango (800 Gbps) |
| escenario uniforme_+100 | 0.9796 | San Bernardo → Calera de Tango (800 Gbps) |
| escenario hotspot_antofagasta_+200 | 0.4898 | San Bernardo → Calera de Tango (800 Gbps) |
| escenario hotspot_aysen_+200 | 1.4383 | Caleta Tortel → Los Ñadis (100 Gbps) |
| base + los 20 candidatos | 0.3958 | Chaitén → Villa Santa Lucía (100 Gbps) |
| fallas evaluadas (95) | 0.2525 – 0.4898 | ver fallas.csv |
