# Fuentes abiertas y verificadas

Solo se listan documentos que se abrieron y de los que se extrajo o comprobó algo. Entre paréntesis, qué se usó de cada uno.

## Subtel – Fibra Óptica Nacional (FON)

1. **Subtel (jul-2019). Proyectos FDT – versión pública.** https://www.subtel.gob.cl/wp-content/uploads/2019/08/PROYECTOS_FDT_VERSION_PUBLICA.pdf
   (Lámina 4: 186 comunas, 8.478 km, 3.246.188 habitantes, km por macrozona. Láminas 6–11: listado de comunas por macrozona. Lámina 15: proyecto Fibra Óptica Tarapacá, no modelado.)
2. **Subtel (2019). Informe resumen de adjudicación FON, código FDT-2019-01.** https://www.subtel.gob.cl/wp-content/uploads/2019/10/Informe_resumen_adjudicacion_fon.pdf
   (Diagramas lineales y tablas por región: PIX, POIIT exigibles y adicionales, km de cada TRIOT, 24 pares de filamentos por cable, km aéreos y soterrados. Págs. 3, 5, 6, 8, 9, 10, 12, 13, 15 y 16. Adjudicatario WOM S.A.; Macrozona Sur desierta.)
3. **Subtel (2020). Proyecto FON Macrozona Sur – Topología de trazados regionales de infraestructura óptica.** https://www.subtel.gob.cl/wp-content/uploads/2020/10/Proyecto_FON_Macrozona_Sur_Topologias.pdf
   (Láminas 5–7: trazado referencial de Araucanía, Los Ríos y Los Lagos, sin km.)
4. **Subtel (2021). Informe resumen de adjudicación FON Macrozona Sur, código FDT-2019-01-SUR.** https://www.subtel.gob.cl/wp-content/uploads/2020/10/Informe_resumen_adjudicacion.pdf
   (Adjudicatario Telefónica Empresas Chile; km por región: Araucanía 980, Los Ríos 603, Los Lagos 937; número de POIIT exigibles y adicionales.)

## Subtel – Fibra Óptica Austral (FOA)

5. **Subtel (2017). Resumen del Proyecto Fibra Óptica Austral.** https://foa.subtel.gob.cl/wp-content/uploads/2017/03/Resumen_Proyecto_FOA_03_2017.pdf
   (POIIT exigibles de la troncal submarina —Puerto Williams, Punta Arenas, Caleta Tortel, Puerto Montt— y POIIT exigibles y adicionales de las troncales terrestres de Los Lagos, Aysén y Magallanes; tasas de canal 10/40/100GbE.)
6. **Subtel (2017). Fibra Óptica Austral: una política pública al servicio de la zona más austral del país (presentación de R. Ramírez).** https://foa.subtel.gob.cl/wp-content/uploads/2017/06/PPT_Rodrigo_Ramirez.pdf
   (Lámina 2: mapa de la ruta y comunas servidas. Lámina 3: 3.953 km y 60 canales ópticos = 6 Tbps. Lámina 5: 40 canales = 4 Tbps por POIIT terrestre. Lámina 10: proyección de tráfico IP mensual de Chile.)
7. **Capacity Media. "Huawei wins order to build Chile's 2,800km southern cable".** https://www.capacitymedia.com/article/29ota593u7c7lklw0fpq8/top-story/huawei-wins-order-to-build-chiles-2-800km-southern-cable
   (Longitud submarina de 2.800 km y capacidad de diseño de 16 Tbps.)
8. **Valenzuela, M. (NIC Chile), 24-ene-2024. Catastro y conectividad digital en Chile (Escuela de Verano AChM).** https://www.achm.cl/wp-content/uploads/2023/12/Chile-Internet-Infraestructura-y-Resiliencia.pdf
   (FOA submarina de casi 3.000 km; contexto FON y Fibra Óptica Tarapacá.)

## Tráfico y demanda

9. **Subtel (mar-2026). Informe del Sector Telecomunicaciones, diciembre 2025.** https://www.subtel.gob.cl/wp-content/uploads/2026/03/Informe_del_Sector_Telecomunicaciones_Dic25.pdf
   (Tráfico 2025: internet fija 36.356,4 miles de TB; internet móvil 7.179,0 miles de TB.)
10. **TeleSemana (15-oct-2019). "Chile dará subsidios por US$ 120,6 millones para el despliegue de 10.000 kilómetros de fibra óptica".** https://www.telesemana.com/blog/2019/10/15/chile-dara-subsidios-por-us-1206-millones-para-el-despliegue-de-10-000-kilometros-de-fibra-optica/
    (Cifra anunciada de 10.000 km.)
11. **Roughan, M., Thorup, M. y Zhang, Y. (2003). Performance of estimated traffic matrices in traffic engineering. ACM SIGMETRICS.** https://www.cs.utexas.edu/~yzhang/papers/ospf-sigm03.pdf
    (Modelo de gravedad simple: el tráfico entre ubicaciones es proporcional a los volúmenes que entran y salen en ellas, con el término de distancia constante → γ = 0.)
12. **Roughan, M. (2005). Simplifying the synthesis of Internet traffic matrices. Computer Communication Review 35(5), 93–96. DOI 10.1145/1096536.1096551.** https://web4.library.adelaide.edu.au/dspace/handle/2440/17847?mode=full
    (Registro y resumen: propone un modelo de gravedad para sintetizar matrices de tráfico. Solo se leyó el resumen; la forma exacta del modelo no se verificó en el texto completo.)

## Población, límites y coordenadas

13. **INE (2025). Censo 2024 – Resultados.** https://censo2024.ine.gob.cl/resultados/
    y su servicio de indicadores comunales usado por el dashboard oficial: https://services5.arcgis.com/hUyD8u3TeZLKPe4T/arcgis/rest/services/CENSO2024_V2_gdb/FeatureServer
    (Capa 0: población censada por comuna, 346 comunas, total 18.480.432, y polígonos comunales usados para la consulta de punto en polígono. Capa 1: límites regionales simplificados para el mapa.)
14. **OpenStreetMap**, consultado con Overpass API (https://overpass-api.de) y Nominatim (https://nominatim.openstreetmap.org). © colaboradores de OpenStreetMap, licencia ODbL.
    (Coordenadas de los 285 nodos; el identificador OSM de cada uno está en `nodos.csv`, columna `osm_id`.)

## Consultadas sin resultado utilizable

- **Subtel / NIC Chile. Mapa Nacional de Infraestructura Digital.** https://www.subtel.gob.cl/mapadigital/ — el índice existe, pero la capa de fibra ("Recorrido Yafün", https://www.subtel.gob.cl/mapadigital/mapa_recorrido_yafun) responde "No encontrado". Por eso la troncal es un supuesto.
- **DPL News. "Conoce el mapa de NIC Chile que muestra la ubicación de la fibra óptica en el país".** https://dplnews.com/?p=37826 — confirma que el mapa existió, sin datos de trazado.

## Citadas en el enunciado y no verificadas aquí

- "Zhang et al. 2003": probablemente Zhang, Roughan, Duffield y Greenberg (SIGMETRICS 2003) sobre tomogravedad. No se abrió; en su lugar se verificó el artículo 11, de los mismos autores y año, que contiene la afirmación sobre la distancia.
