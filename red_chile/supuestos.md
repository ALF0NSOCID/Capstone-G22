# Supuestos, inconsistencias y decisiones

Red inspirada en la infraestructura chilena de fibra óptica (Capstone ICS2122). Cada fila indica qué se supuso, por qué, en qué fuente se apoya (si existe) y qué pasaría si estuviera equivocado. Los parámetros numéricos están en `scripts/construir_instancia.py` (diccionario `PARAMS`) y se pueden cambiar y regenerar todo.

## 1. Topología

| # | Supuesto | Justificación | Fuente | Impacto si está equivocado |
|---|---|---|---|---|
| T1 | La troncal privada se modela como **una sola troncal unificada** de 21 tramos a lo largo de la Ruta 5 (Arica–Pozo Almonte–Antofagasta–Copiapó–La Serena–La Calera–Santiago–San Bernardo–…–Osorno–Puerto Montt) más accesos a Iquique, Valparaíso, Concepción y Valdivia. | El trazado real de los operadores no es público. El Mapa Nacional de Infraestructura Digital (NIC Chile/Subtel) ya no está disponible: la página del "Recorrido Yafün" en subtel.gob.cl/mapadigital responde "No encontrado". Sin evidencia no se incluyeron rutas paralelas ni costeras. | Ninguna verificable para el trazado (SUPUESTO). | Es el supuesto de mayor impacto. La red real tiene rutas paralelas de varios operadores y salidas por Argentina; aquí **todos los tramos troncales son puentes**, así que cada falla troncal desconecta demanda. Las métricas de falla son una cota pesimista. |
| T2 | Nodos troncales sin PIX: Iquique (capital sin FON), Pozo Almonte (empalme Ruta 5/Ruta 16), La Calera, Santiago, San Fernando, Curicó, Linares, Los Ángeles y Osorno. | Ciudades de la Ruta 5 con población relevante que no son POIIT; permiten que la troncal tenga nodos de tráfico. | SUPUESTO. | Cambia dónde entra la demanda de esas comunas; no altera la estructura radial. |
| T3 | La troncal pasa por Valdivia (Temuco–Valdivia–Osorno) en vez de seguir la Ruta 5 por Lanco y Los Lagos. | Valdivia es PIX y capital regional; un desvío de ~40 km no cambia la topología lógica. | SUPUESTO. | Solo cambia km. |
| T4 | Los ramales FON se conectan a la troncal **solo en el PIX** de su región, aunque pasen por pueblos que están sobre la Ruta 5 (Cuya, Chañaral, Vallenar, Los Vilos, Teno, etc.). | Regla del enunciado. | Enunciado del grupo. | Las conexiones reales en esos pueblos crearían anillos; están propuestas como enlaces candidatos. |
| T5 | Ramales FON de las 10 regiones adjudicadas en 2019: topología y km **tal como aparecen en los diagramas lineales** de la propuesta adjudicada (WOM). | Es la fuente pública más detallada. La suma de los km transcritos coincide con el total regional que declara Subtel (diferencias < 1 km). | Subtel, Informe resumen de adjudicación FON (2019), págs. 3, 5, 6, 8, 9, 10, 12, 13, 15 y 16. | Bajo. Es la red comprometida, no necesariamente la construida. |
| T6 | Macrozona Sur (Araucanía, Los Ríos, Los Lagos): topología del **trazado referencial de las bases** (2020), no de la propuesta adjudicada a Telefónica (2021), cuyo diagrama no es público. | Única topología publicada para el Sur. | Subtel, Proyecto FON Macrozona Sur – Topologías (2020), láminas 5 a 7. | Medio en Los Ríos y Los Lagos: la propuesta adjudicada tiene 6 y 5 POIIT adicionales que no están aquí (ver verificaciones, sección 3). |
| T7 | En el Sur, los tramos dibujados con línea punto-raya (Niebla–Corral, Pargua–Curaco de Vélez, Quinchao–Puqueldón, Puqueldón–Chaitén) se incluyen como enlaces fijos. | Las bases dejan a la proponente libre de conectar esos POIIT a cualquier PIX o POIIT; se toma la conexión dibujada. | Subtel (2020), láminas 6 y 7. | Bajo; podrían conectarse distinto. |
| T8 | FOA terrestre: los tramos siguen el **orden en que las bases listan los POIIT** de cada troncal y la red vial (Carretera Austral, Ruta 9, rutas de Tierra del Fuego). Puelo Alto–Contao, Hornopirén–Chaitén (Ruta 7 con cruces de fiordo) y Punta Arenas–Porvenir (cruce del Estrecho) son los tramos más dudosos. | Las bases listan POIIT pero no tramos. | Subtel FOA, Resumen del proyecto (2017), sección de troncales terrestres. | Medio en Los Lagos: el tramo Hornopirén–Chaitén cierra el único anillo de la red base (Puerto Montt–Hornopirén–Chaitén–Chiloé–Pargua–Puerto Montt). |
| T9 | FOA: se incluyen todos los POIIT exigibles y solo los adicionales que son capital comunal o empalme necesario (Chaitén, Villa Santa Lucía, Futaleufú, Palena, Villa O'Higgins, Puerto Ingeniero Ibáñez, Onaisín, Cameron, Puerto Natales). Se omiten El Límite, Valle California, El Azul, Hualaihué (Puerto), Puerto Sánchez, Balmaceda y San Sebastián. | Prioridad a trazabilidad; los omitidos son localidades sin comuna propia. | Subtel FOA (2017) y lámina 2 de la presentación FOA (mapa con las comunas servidas). | Bajo: serían hojas sin población asignada. |
| T10 | Se excluyen tres POIIT adicionales hoja que no aparecen en OpenStreetMap: Quebrada Seca y La Marquesa (Atacama) y El Abanico (Biobío). | No se pudo verificar su ubicación; no tendrían población (su comuna ya tiene cabecera en la red). | — | Ninguno sobre demanda ni ruteo; explica −46 km en Atacama y −12 km en Biobío. |
| T11 | Enlaces candidatos: 20 tramos que hoy no existen, con capacidad de ramal FON y km = geodésica × factor de ruta. | Cierran anillos entre ramales vecinos, crean rutas costeras paralelas a la troncal o dan una segunda vía a Aysén. | Propuesta del grupo (justificación por enlace en `enlaces.csv`, columna `nota`). | Son opciones de inversión, no forman parte de la red base. |

## 2. Distancias

| # | Supuesto | Justificación | Fuente | Impacto si está equivocado |
|---|---|---|---|---|
| D1 | Km no publicados = distancia geodésica × **1,319**. | Mediana de km_declarado / geodésica en 176 TRIOT con km conocido (rango intercuartil 1,19–1,49). Se excluyeron tramos de menos de 5 km de geodésica. | Calibración propia con los diagramas de Subtel 2019. | Los km no entran en la función objetivo (no hay costos); solo afectan la comparación con Subtel y la evaluación de candidatos por longitud. |
| D2 | Troncal submarina FOA: km de cada tramo proporcional a su geodésica, escalado para sumar **2.800 km**. | Cifra de longitud del cable submarino reportada por Huawei Marine. | Capacity Media (nota sobre el contrato de Huawei Marine). | La presentación de NIC Chile dice "casi 3.000 km"; la diferencia (7 %) no afecta el ruteo. |

## 3. Nodos y población

| # | Supuesto | Justificación | Fuente | Impacto si está equivocado |
|---|---|---|---|---|
| N1 | Toda la población de la comuna (Censo 2024) se asigna a **un solo nodo**: su cabecera comunal. Los demás POIIT de la misma comuna son nodos de paso con población 0. | El Censo por comuna es oficial y está completo; repartir por localidad requeriría datos por entidad que no se usaron. | INE, Censo 2024 (servicio de indicadores comunales). | Bajo para el ruteo en un ramal en árbol (la demanda pasa por los mismos tramos). |
| N2 | El Quisco no tiene su cabecera como POIIT; su población se asigna al POIIT "Guallelemu", que en OpenStreetMap figura como Huallilemu (comuna de El Quisco). | El diagrama de Valparaíso lista Guallelemu y Totoral (ambos en El Quisco) en lugar de El Quisco y El Tabo. | Subtel 2019, pág. 9; OSM; polígono comunal INE. | Bajo. |
| N3 | Santiago se representa con la población de la **comuna de Santiago** (438.856), no del Gran Santiago, y es además el nodo de salida internacional/CDN. | Regla del enunciado (población de la comuna del nodo). El resto del Gran Santiago no está en la red y su tráfico es mayoritariamente local. | INE. | Subestima el tráfico doméstico Santiago–regiones; ese tráfico queda absorbido en los flujos de la salida internacional/CDN. |
| N4 | La demanda de cada comuna POIIT viaja **completa** por esta red (no hay otros backhaul). | Es la única red modelada. En la realidad muchas comunas tienen otras rutas privadas, por eso el ramal de la RM aparece como el más cargado. | SUPUESTO. | Sobrestima la carga de los ramales FON que llegan a comunas grandes (Lampa, Melipilla, Padre Hurtado). |
| N5 | Coordenadas con clasificación ESTIMADO: Icalma (objeto OSM "Icalma" en la orilla de la laguna, sin nodo de localidad) y El Manzano (OSM: Caleta Manzano, Hualaihué). | No hay nodo `place` con ese nombre exacto. | OpenStreetMap. | Bajo (nodos de paso). |
| N6 | Hualañé es la candidata más probable a la comuna 186 que el listado FDT no nombra. | Es POIIT exigible en el diagrama adjudicado del Maule y no aparece en la lista; no hay forma de confirmarlo. | Subtel 2019, pág. 13. | Solo afecta el conteo de verificación. |

## 4. Capacidades (Gbps por sentido)

Regla: escalones estándar de equipos ópticos {100, 400, 800, 2.000, 4.000, 8.000} Gbps; por capa se usa **el menor escalón uniforme que deja la red base bajo 70 % de utilización en hora punta**, que es una holgura operativa habitual. Ninguna fuente pública da la capacidad iluminada por tramo, así que todo esto es SUPUESTO; las cifras declaradas por Subtel se reportan solo como cota superior.

| Tipo de tramo | Capacidad | Interpretación | Cifras de referencia verificadas |
|---|---|---|---|
| Troncal entre capitales | 8.000 | 80 canales de 100G, agregado de todos los operadores | — |
| Ramal FON | 800 | 8 × 100G sobre uno de los 24 pares de filamentos por cable | 24 pares por cable y 1 cable por TRIOT (tablas de cada región, Subtel 2019) |
| FOA submarina | 400 | 4 canales de 100G iluminados | 60 canales ópticos = 6 Tbps (Subtel, presentación FOA 2017, lámina 3); 16 Tbps de diseño (Capacity Media) |
| FOA terrestre | 100 | 1 canal óptico 100GbE | 40 canales = 4 Tbps por POIIT (Subtel 2017, lámina 5); las bases admiten 10/40/100GbE |
| Candidato | 800 | igual que un ramal FON | — |

Impacto: el z* escala con 1/capacidad del tramo que lo determina. Con el escalón inferior para FON (400 Gbps) el z* base subiría a 0,98 y lo fijaría el ramal de la RM. La red base queda equilibrada: el ramal FON San Bernardo–Calera de Tango (0,49), la FOA terrestre de Aysén (0,48) y la troncal Santiago–San Bernardo (0,47) están casi igual de cargados.

## 5. Demanda

| # | Supuesto | Valor | Justificación | Fuente | Impacto si está equivocado |
|---|---|---|---|---|---|
| M1 | Tráfico nacional de referencia | 36.356,4 + 7.179,0 miles de TB en 2025 (fijo + móvil) | Dato oficial más reciente encontrado | Subtel, Informe del Sector Telecomunicaciones dic-2025 (DATO) | — |
| M2 | Factor hora punta / promedio | 1,6 | Tráfico residencial con máximo nocturno; no se encontró dato chileno | SUPUESTO | z* es lineal en este factor: 1,4 daría z* ×0,875. |
| M3 | Tráfico por habitante en hora punta | 0,956 Mbps | 43.535 PB/año → 11,0 Tbps promedio → 17,7 Tbps punta ÷ 18.480.432 hab. | ESTIMADO (Subtel + INE) | Lineal en z*. |
| M4 | Fracción del tráfico hacia/desde Internet global y CDN en Santiago (f) | 0,75 | La mayor parte del tráfico de usuarios es contenido servido desde cachés y salidas internacionales concentradas en Santiago | SUPUESTO (no se encontró cifra pública verificable) | Mayor f concentra más carga en la troncal desde Santiago y menos en tráfico entre regiones. |
| M5 | De lo que va a la salida, fracción en sentido Santiago → nodo | 0,85 | Asimetría bajada/subida típica del tráfico residencial | SUPUESTO | Cambia la carga relativa de los dos sentidos de cada enlace. |
| M6 | Exponente de distancia γ | 0 | En tráfico IP el modelo de gravedad simple trata la distancia como constante | Roughan, Thorup y Zhang (SIGMETRICS 2003) lo dicen explícitamente; Roughan (CCR 2005) usa gravedad para sintetizar matrices | Con γ > 0 se reforzaría el tráfico entre nodos vecinos y bajaría la carga de la troncal. |
| M7 | Normalización de k | Tráfico doméstico total = (1 − f)·τ·ΣP / 2 → k = 1,375·10⁻¹¹ Gbps/hab² | Cada unidad de tráfico doméstico se cuenta en origen y destino | ESTIMADO | — |
| M8 | Selección de productos | Se conservan siempre los 456 pares con Santiago (salida); el resto son los pares domésticos de mayor demanda hasta completar 10.000 | Así ningún nodo con población queda sin demanda | — | El top-10.000 conserva 97,83 % del tráfico (52.212 pares posibles). |
| M9 | Una sola salida internacional (Santiago) | — | No se abrió una fuente que confirme puntos de aterrizaje de cables; una segunda salida (p. ej., Valparaíso o Arica) queda como variante | SUPUESTO | Una segunda salida en el norte aliviaría la troncal norte. |
| M10 | Población 2024 con tráfico 2025 | — | Censo más reciente y tráfico más reciente | — | Desfase de un año, despreciable frente a M2–M4. |

## 6. Escenarios y fallas

| # | Supuesto | Justificación |
|---|---|---|
| E1 | Crecimiento uniforme +25 %, +50 %, +100 %. | Pedido en el enunciado. En congestión mínima z* escala exactamente con el factor (el ruteo óptimo no cambia), así que sirven como prueba de consistencia del solver. |
| E2 | Hotspot: ×3 (+200 %) sobre los productos cuyo **destino** está en la región. Se entregan Antofagasta (minería y centros de datos) y Aysén (depende solo de la FOA). | Antofagasta no cambia z* (su ramal más cargado queda bajo el cuello de botella de la RM); Aysén sí: lleva z* a 1,44 por la FOA terrestre de 100 Gbps. El script acepta cualquier región y factor. |
| E3 | Lista de fallas: los 21 tramos troncales, los 35 FOA y una muestra de 39 tramos FON (por región: el de mayor demanda aguas abajo, uno intermedio y el del extremo). | Pedido en el enunciado; la muestra cubre los tres tipos de posición en un ramal. |

## 7. Inconsistencias entre fuentes y valor elegido

| Dato | Valores encontrados | Elegido y por qué |
|---|---|---|
| Km totales FON | 8.478 km (FDT, jul-2019, lámina 4); 9.560 km (suma de las propuestas adjudicadas: 2019 + Macrozona Sur 2021); 10.000 km (anuncio del subsidio, TeleSemana, 15-oct-2019) | Se usan los km por tramo de los diagramas adjudicados; la comparación se hace contra las cifras adjudicadas porque vienen del mismo documento que la topología. Los 8.478 km del FDT eran una estimación de planificación previa a las propuestas. |
| Número de comunas FON | 186 (portada FDT); 185 (suma de encabezados por macrozona); 184 (nombres listados) | Se verifican los 184 nombres; 183 están en la red (falta El Tabo, sin POIIT en el diagrama de Valparaíso). |
| Km Arica y Parinacota | 680 km (texto del informe) vs 656 aéreos + 7 soterrados = 663 km (tabla) | 663 km: coincide con la suma de los 11 TRIOT (662,84 km). |
| Capacidad FOA | 6 Tbps / 60 canales submarinos y 4 Tbps / 40 canales terrestres (Subtel 2017) vs 16 Tbps de diseño (Huawei Marine vía Capacity Media) | Ninguna se usa directamente: son capacidades potenciales. Se modela capacidad iluminada (400 y 100 Gbps) y las cifras declaradas quedan como cota superior. |
| Longitud FOA submarina | 2.800 km (Capacity Media) vs "casi 3.000 km" (presentación NIC Chile, 2024) | 2.800 km; con ella, submarino + terrestre exigible queda a −2,9 % de los 3.953 km totales que declara Subtel. |
| Región de San Pablo | El listado FDT lo nombra junto a las comunas de Los Ríos | Los Lagos (INE; además está en el diagrama de Los Lagos de Subtel 2020). |
| TRIOT 18 y 19 del Maule | La extracción de texto los desordena | Diagrama: Licantén–Vichuquén 15,63 km y Licantén–Hualañé 18,50 km. |
| Nombres | "Empredrado", "Paiguano", "Treguaco" (FDT); "Guallelemu" (diagrama de Valparaíso); "Puerto Bernard" (bases FOA) | Empedrado, Paihuano y Trehuaco (INE); Huallilemu (OSM); Puerto Bertrand. |
