# Red inspirada en la infraestructura chilena de fibra óptica — resumen

Instancia de flujo multiproducto de congestión mínima para el Capstone ICS2122 (Grupo 22). Es una red plausible y trazable, **no la red real de Chile**.

**Tamaño:** 285 nodos, 285 enlaces físicos (21 troncales, 229 FON, 35 FOA), 570 arcos dirigidos, grado medio 2,0, 269 puentes (94 %), 20 enlaces candidatos fuera de la base. 10.000 productos con 6.931 Gbps en hora punta (97,8 % del tráfico de los 52.212 pares posibles). 229 nodos con población, que suman 8.850.246 habitantes (48 % del país).

**z\* de referencia** (LP agregado por origen, solo para contrastar): base 0,490; +25 % → 0,612; +50 % → 0,735; +100 % → 0,980; hotspot Antofagasta → 0,490; hotspot Aysén → 1,438; base + los 20 candidatos → 0,396.

## Qué es DATO (sale de una fuente)

- POIIT y PIX de las 13 regiones FON y topología de los ramales: diagramas de Subtel (adjudicación 2019 y trazado referencial del Sur 2020).
- Km de 182 tramos FON (10 regiones): km de cada TRIOT en los diagramas; por región suman lo que declara Subtel.
- POIIT de la FOA (submarina y terrestre) según las bases de 2017.
- Población comunal: Censo 2024 del INE (346 comunas, 18.480.432 hab.).
- Coordenadas: OpenStreetMap, verificadas contra polígonos comunales del INE (285 de 285 en su región).
- Tráfico nacional 2025: Subtel (43.535 PB/año entre fijo y móvil).

## Qué es ESTIMADO (calculado a partir de fuentes)

- Km de 47 tramos FON del Sur, de la troncal, de la FOA terrestre y de los candidatos: geodésica × 1,319 (factor calibrado con 176 TRIOT con km conocido).
- Km de la FOA submarina: proporcional a la geodésica, escalado a 2.800 km.
- Tráfico por habitante en hora punta: 0,956 Mbps (Subtel ÷ INE × factor punta) y la constante k del modelo de gravedad.
- Coordenadas de Icalma y El Manzano (sin nodo de localidad exacto en OSM).

## Qué es SUPUESTO (decisión del grupo, justificada en supuestos.md)

- Trazado de la troncal: una sola troncal unificada por la Ruta 5 y sus nodos intermedios.
- Tramos de la FOA terrestre (las bases listan POIIT, no tramos).
- Capacidades iluminadas: troncal 8.000, FON 800, FOA submarina 400, FOA terrestre 100, candidatos 800 Gbps por sentido (menor escalón uniforme por capa que deja la base bajo 70 %).
- Factor hora punta 1,6; 75 % del tráfico hacia/desde la salida internacional y CDN en Santiago; 85 % de ese tráfico en sentido de bajada; γ = 0.
- Toda la población comunal en la cabecera; los POIIT de paso no generan demanda.
- Los 20 enlaces candidatos y los dos hotspots (Antofagasta y Aysén).

## Principales limitaciones

1. **La troncal es radial.** Sin el mapa de NIC Chile (ya no disponible) no se incluyeron rutas paralelas, así que todo tramo troncal es puente: cortar Santiago–San Bernardo desconecta 66 % de la demanda. Es una cota pesimista de la resiliencia real.
2. **Casi toda la red es un árbol.** El único anillo de la base está en Los Lagos. Sin candidatos el ruteo está casi forzado y z\* es simplemente el tramo más cargado; la optimización se vuelve interesante al agregar candidatos.
3. **Cada comuna depende solo de esta red.** En la realidad hay otros backhaul; por eso el ramal FON de la RM (Lampa, Melipilla, Padre Hurtado) resulta el cuello de botella.
4. **Macrozona Sur con trazado referencial.** Faltan 6 POIIT adicionales en Los Ríos y 5 en Los Lagos respecto de la propuesta adjudicada (−45 % y −29 % de km).
5. **Capacidades y parámetros de demanda sin dato público.** z\* es lineal en el factor punta y en la escala de capacidades; conviene presentar resultados como sensibilidades, no como valores absolutos.
6. **Fuera del alcance:** Fibra Óptica Tarapacá, salidas por Argentina, cables submarinos internacionales y una segunda salida internacional.
