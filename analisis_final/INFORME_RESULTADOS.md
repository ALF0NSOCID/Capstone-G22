# Análisis final de resultados — Capstone ICS2122, Grupo 22

**Objeto:** baterías formales de E3 (`solver_columnas_e2_v2.py`) para las sensibilidades de densidad (X3), escalabilidad (X4) y organización topológica (Waxman).
**Fecha del análisis:** 24-nov-2026. **Fuentes:** `experimentos/x3_formal/`, `experimentos/x4_formal/` y `experimentos/waxman_formal/`. Se leyeron sin modificarlos.
**Reproducción:** `bash analisis_final/codigo/ejecutar_todo.sh` desde la raíz (numpy, pandas y matplotlib; no hace falta scipy ni networkx).

---

## 0. Resumen ejecutivo

1. **Las tres baterías están completas y son íntegras.** Hay 430 de 430 corridas: X3 40/40, X4 240/240 y Waxman 150/150. Los CSV coinciden con los logs, no hay duplicados ni errores, y todas las corridas se ejecutaron en una sola sesión secuencial y sin solapes. El código no se modificó durante las corridas.
2. **La calidad certificada se cumple, con una excepción acotada.** Certificaron 426 de 430 corridas. Las 4 restantes son de X3 (grados 12 y 16) y llegaron al límite interno de 300 s. En X4, el z óptimo de GC base cae dentro del intervalo [cota inferior, z] de E3 en las 90 semillas comparables.
3. **X3, densidad.** Con grado 4 u 8, E3 certifica 10/10 con medianas bajo 1 s (máximo 3,1 s). Con grado 12 o 16, la mediana sube a 21 s y 127 s, 2 de 10 corridas no certifican en 300 s y los tiempos abarcan tres órdenes de magnitud. En esas corridas el maestro concentra el 71–84 % del tiempo.
4. **X4, escalabilidad.** En redes dispersas E3 resuelve 3.200 nodos (77 mil productos efectivos; K·|A| ≈ 10⁹) con una mediana de 7,5 s y un máximo de 30,5 s. Frente a GC base, la aceleración pareada crece con el tamaño: 26× con 200 nodos, 50× con 400 y 124× con 800 (tiempo interno). Ninguna semilla fue más lenta con E3. La ventaja se mantiene en las semillas donde E3 llegó al óptimo exacto.
5. **Waxman, topología.** Con el mismo tamaño, la organización mueve el tiempo en dos órdenes de magnitud. La red local es unas 19× más lenta que la intermedia (comparación pareada). Agregar backbone con capacidad ×1 baja z en 22 de 30 semillas, pero suele ser más lento. Reforzar ×10 los enlaces entre hubs nunca sube z y reduce el tiempo en 23 de 30 semillas (mediana 0,29×).
6. **Falta la memoria.** Ninguna batería formal registró RAM, así que ese KPI no se puede presentar con estos datos (ver `INCIDENCIAS.md`).

---

## 1. Material, protocolo y convenciones

### 1.1 Estado real de las baterías

| Batería | Diseño | Esperadas | Presentes | Certificadas | Límite interno | Timeout externo / error |
|---|---|---:|---:|---:|---:|---:|
| X3 densidad | Mulgen, 400 nodos, 10.000 productos solicitados, grados 4/8/12/16, semillas 1–10, 300 s | 40 | 40 | 36 (33 óptimo + 3 brecha ≤ 1 %) | 4 | 0 / 0 |
| X4 E3 | Grado 4, 25 productos/nodo, 200–3.200 nodos, semillas 1–30, 900 s | 150 | 150 | 150 (117 + 33) | 0 | 0 / 0 |
| X4 GC base | Mismas instancias, 200–800 nodos | 90 | 90 | 90 (óptimo por costo reducido) | 0 | 0 / 0 |
| Waxman | 5 familias, 400 nodos, 800 enlaces, 10.000 productos, semillas 1001–1030, 120 s | 150 | 150 | 150 (140 + 10) | 0 | 0 / 0 |

- **Semillas.** X3 no se amplió más allá de las semillas 1–10. Waxman no contiene el piloto 42/43 ni carpetas ajenas al diseño. Las 150 corridas Waxman tienen `estado.json` y su CSV está al día.
- **Estado anterior.** El estado descrito en la revisión previa (X4 125/240, Waxman sin empezar) ya no es el actual. Todas las corridas formales que hay hoy en disco llevan marcas del 24-nov-2026 entre 21:14 y 23:54 UTC (18:14–20:54 hora de Chile), en una única secuencia: X3, luego X4, luego Waxman.
- **Entorno.** Las tres baterías parecen venir del mismo equipo. Waxman registra macOS 26.6.2 arm64 y Python 3.9.6, y sus hashes coinciden con los archivos actuales. X3 y X4 no registran entorno, pero comparten la licencia Gurobi 2855691 y forman una secuencia continua; los solvers y scripts son anteriores a la primera corrida. No se mezclan equipos.
- **Series excluidas.** No se mezclan `experimentos/x3/` ni `experimentos/x4/` (históricos, con otro protocolo), `explorar_waxman.py` (80 %/25 %), el piloto 42/43 ni los logs con memoria del ciclo E2 (`resultados E2/`, otros solvers).

### 1.2 Métricas

- **Tiempo interno.** Es el que informa el solver ("Tiempo total"). En E3 el reloj parte después de leer la instancia y de construir el motor C++; en GC base parte antes de construir sus LP de pricing. Esa diferencia favorece levemente a E3, por eso también se informa el **tiempo de pared** del subproceso, que es la medida conservadora.
- **Memoria.** No se registró (ver §6). Las columnas e iteraciones se usan solo como medidas explicativas, no como RAM.
- **Estados.**
  - Óptimo: brecha ≤ 1e-6 contra la cota inferior en E3; costo reducido ≥ −1e-7 en GC base.
  - Brecha ≤ 1 %: E3 con cota inferior.
  - Límite interno: E3 no certificó dentro del límite.
  - No hubo timeouts externos ni errores. Un código de salida 0 no se tomó como certificado.

### 1.3 Estadística

- Se informa n, mediana, RIC, máximo y tasa de certificación.
- **Censura.** Las corridas que llegaron al límite cuentan como "≥ límite": entran en la mediana de *todas las corridas* como valores superiores y nunca como tiempos de solución. La mediana calculada solo con corridas certificadas se rotula como tal, porque subestima el tiempo típico.
- **Aceleraciones.** Se calcula T_base/T_E3 por semilla sobre la misma instancia y se resumen esas razones (mediana, RIC, media geométrica). No se usa el cociente de medianas.
- **IC 95 %.** Percentil de remuestreo de semillas (B = 10.000; 2.000 en los ajustes), pareado cuando la comparación es pareada.
- No se aplican pruebas de hipótesis: con 30 pares por comparación, los intervalos bastan.

---

## 2. Requisito de validez: calidad certificada

- **Tasas.** X4 y Waxman certifican el 100 %. X3 certifica el 90 % (36/40), y las 4 corridas restantes llegaron al límite interno (§3).
- **Validación cruzada en X4.** GC base resuelve hasta optimalidad por costo reducido; E3 entrega el intervalo [cota inferior, z].
  - En las 90 semillas comparables, el z de GC base cae dentro del intervalo de E3 (`tablas/x4_validacion_cruzada_z.csv`).
  - Cuando E3 declara óptimo, los dos z coinciden exactamente.
  - Cuando E3 se detiene con brecha ≤ 1 %, su z supera al óptimo en a lo más un 0,90 %.
  - E3 y GC base resolvieron las mismas instancias: coinciden productos efectivos y arcos (90/90).
- **Cota independiente en Waxman.** La cota de congestión obligatoria por puentes nunca supera el z de E3 (150/150), lo que es consistente con que z sea factible y óptimo o casi óptimo.
- **Corridas de X3 en el límite.** Quedaron con brechas de 587 % a 2.354 %, porque la cota inferior es débil mientras el maestro no converge. Sus cotas superiores (0,033–0,050) están en el extremo bajo de los z de su grado. No deben presentarse como soluciones de calidad conocida.

---

## 3. X3 — ¿Cómo cambia el desempeño al aumentar las conexiones, manteniendo nodos y productos solicitados?

Figuras: `fig01_x3_tiempo_por_grado` (principal) y `fig02_x3_esfuerzo_maestro_columnas` (respaldo). Tabla: `tablas/x3_resumen_por_grado.csv`.

| Grado | Arcos | K efectivo (mediana) | Certificadas | Mediana, todas (s) [IC 95 %] | RIC (s) | Máx. | Mediana solo certificadas | Iteraciones | Columnas | % maestro | z mediana |
|---:|---:|---:|---:|---|---|---|---:|---:|---:|---:|---:|
| 4 | 1.600 | 9.671 | 10/10 | 0,36 [0,21–0,64] | 0,21–0,61 | 0,82 | 0,36 | 6 | 9.954 | 6 % | 0,559 |
| 8 | 3.200 | 10.000 | 10/10 | 0,25 [0,18–1,04] | 0,18–0,86 | 3,10 | 0,25 | 2,5 | 10.012 | 6 % | 0,270 |
| 12 | 4.800 | 10.000 | 8/10 | 21,4 [2,0 – ≥ 300] | 2,6–240 | ≥ 300 | 9,9 | 116,5 | 28.563 | 71 % | 0,066 |
| 16 | 6.400 | 10.000 | 8/10 | 126,7 [10,8 – ≥ 300] | 12,7–231 | ≥ 300 | 43,0 | 196,5 | 43.489 | 84 % | 0,041 |

**Lectura**

- **El cambio es un salto, no una tendencia suave.** Con grado 4 u 8 todas las corridas certifican en 3,1 s o menos. Con grado 12 o 16 aparecen corridas de cientos de segundos y 2 de 10 no certifican en 300 s, mientras otras semillas del mismo grado resuelven en 0,23 s. **La densidad aumenta sobre todo la dispersión y la cola.**
- **Las medianas solo de certificadas engañan.** Dan 9,9 s y 43,0 s en grados 12 y 16, frente a 21,4 s y 126,7 s con todas las corridas. El `resumen.csv` original usa la primera versión sin rotularla (ver `INCIDENCIAS.md`).
- **El maestro explica la dificultad.** En grados 12–16 se generan 2,9–4,3 columnas por producto, hay 100–200 iteraciones y el maestro concentra el 71–84 % del tiempo (73–94 % en las corridas que llegaron al límite). En grados 4–8 basta casi una columna por producto. Es una asociación descriptiva.
- **No hay monotonía entre grado 4 y 8.** Grado 8 no es más lento que 4 y los IC se traslapan. El grado 4 además tiene menos productos efectivos (9.478–9.795), porque el filtro de conectividad elimina pares sin camino.
- **Congestión y dificultad se oponen.** z baja fuertemente con el grado (0,56 → 0,04), ya que hay más capacidad para la misma demanda. Dentro de cada grado, las instancias con menor z tardan más (Spearman entre −0,77 y −0,99; agrupado dentro de grado, −0,90). La hipótesis es que un z alto dominado por un cuello de botella aislado se certifica en pocas iteraciones, mientras que una congestión difusa exige muchas columnas. **Alta congestión no implica problema difícil.**
- **Protocolo.** El límite de 300 s no es comparable con las tasas históricas de `experimentos/x3/`, obtenidas con 900 s.

**Respuesta.** Con 400 nodos y 10.000 productos, pasar de grado 8 a grado 12–16 vuelve muy variable el desempeño de E3: tiempos de 0,2 s a ≥ 300 s, el 20 % sin certificar en 300 s y el maestro como cuello de botella. Con grados bajos, la mediana de E3 está bajo 1 s y el máximo es 3,1 s.

---

## 4. X4 — ¿Cómo crece el esfuerzo en redes dispersas y cuánto mejora E3 frente al caso base?

Figuras: `fig03_x4_tiempo_vs_tamano` y `fig04_x4_aceleracion_pareada` (principales), `fig05_x4_descomposicion_iteraciones` (respaldo). Tablas: `x4_resumen_por_tamano.csv`, `x4_aceleracion_por_semilla.csv`, `x4_aceleracion_resumen.csv` y `x4_crecimiento_empirico.csv`.

| N | K efectivo | K·\|A\| | E3 mediana (s) [RIC] | E3 máx. | E3 pared | GC base mediana (s) [RIC] | GC base máx. | Aceleración interna, mediana [IC 95 %] | Mín. | Aceleración de pared |
|---:|---:|---:|---|---:|---:|---|---:|---|---:|---:|
| 200 | 4.816 | 3,9 M | 0,13 [0,09–0,22] | 1,8 | 0,25 | 3,9 [2,4–4,6] | 6,5 | 26× [23–27] | 3,6× | 14× |
| 400 | 9.660 | 15 M | 0,28 [0,20–0,59] | 1,9 | 0,52 | 15,6 [12,2–25,5] | 34,2 | 50× [46–58] | 18× | 29× |
| 800 | 19.265 | 62 M | 0,62 [0,51–2,01] | 4,7 | 1,22 | 95,5 [71,6–139,7] | 190,7 | 124× [97–136] | 41× | 64× |
| 1.600 | 38.437 | 246 M | 2,0 [1,4–4,3] | 19,9 | 3,9 | — | — | — | — | — |
| 3.200 | 76.867 | 984 M | 7,5 [4,2–12,8] | 30,5 | 13,6 | — | — | — | — | — |

K·|A| es el número equivalente de variables de flujo del LP por arcos con K efectivo. **E3 no construye esas variables**; la columna solo da escala.

**Lectura**

- **Escalabilidad.** Las 240 corridas certifican y ninguna se acercó a 900 s. E3 resuelve 3.200 nodos con una mediana de 7,5 s.
- **Aceleración.** La mediana de las razones por semilla sube de 26× a 50× y luego a 124×, con IC que no se traslapan. **Ninguna semilla fue más lenta con E3.** Con tiempo de pared las razones son la mitad (14×, 29×, 64×), porque el arranque de Python, la lectura y la licencia pesan más en E3, que es mucho más rápido.
- **La ventaja no viene de detenerse al 1 %.** En las semillas donde E3 llegó al óptimo exacto, la aceleración es 27× (n = 26), 54× (n = 25) y 127× (n = 24). En las semillas detenidas con brecha ≤ 1 % es algo menor (22×, 40×, 92×; n = 4–6), porque son las instancias más difíciles para E3.
- **Crecimiento empírico.** Esto vale para la familia Mulgen de grado 4 y 25 productos por nodo:

| Medida | E3 | GC base |
|---|---|---|
| β global, log t vs log K·\|A\| | 0,72 [0,66–0,78], R² = 0,78 | 1,20 [1,13–1,27], R² = 0,92 |
| β por tramo | 0,58 → 0,57 → 0,87 → 0,94 (IC amplios) | 0,99 → 1,31 |
| Factor de tiempo por cada duplicación de N | 2,2 → 2,2 → 3,3 → 3,7 | 4,0 → 6,1 |

  Un exponente único subestima el crecimiento de E3 en los tamaños mayores. **Esto describe la familia ensayada; no demuestra complejidad teórica ni autoriza a extrapolar más allá de 3.200 nodos.**
- **Por qué es más rápido (descriptivo).** E3 itera 3–5 veces y genera 1,01–1,04 columnas por producto: la partida congestion-aware deja casi el conjunto final. GC base itera 11–22 veces (1,12–1,22 columnas por producto) y gasta el 48–56 % del tiempo en pricing por LP y el 21–28 % en caminos iniciales; su maestro es despreciable. Con 3.200 nodos, E3 gasta el 74 % en "pricing y columnas", que incluye costos reducidos y alta de columnas en Python. **Estas baterías no separan el aporte de cada mejora** (C++, partida, normalización, criterio de parada).

**Respuesta.** En redes dispersas, el tiempo de E3 crece de forma sub-lineal a casi lineal en K·|A| dentro del rango ensayado, con una curvatura creciente. Frente al caso base, E3 es 26–124× más rápido según el tamaño (14–64× en tiempo de pared), y la ventaja aumenta con N.

---

## 5. Waxman — ¿Cómo cambia el desempeño con la organización topológica a tamaño fijo?

Figuras: `fig06_waxman_tiempo_por_familia` y `fig07_waxman_backbone_x1_vs_x10` (principales); `fig08_waxman_local_vs_backbone` y `fig09_waxman_topologia_s1001` (respaldo). Tablas: `waxman_resumen_por_familia.csv`, `waxman_comparaciones_pareadas.csv`, `waxman_comparaciones_por_semilla.csv`, `waxman_estructura_y_puentes_por_familia.csv` y `waxman_tiempo_segun_puente.csv`.

### 5.1 Familias

| Familia | Certificadas (óptimo + brecha) | Mediana (s) [IC 95 %] | RIC (s) | Máx. (s) | Iteraciones | Columnas | % maestro | z mediana | Puentes | Puente explica z |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| W1 local (α 0,04; β 1) | 30 (26 + 4) | 4,1 [2,1–10,5] | 1,4–18,1 | 55,1 | 33,5 | 47.471 | 57 % | 35,2 | 32 | 8/30 |
| W2 intermedia (0,20; 0,40) | 30 (30 + 0) | 0,21 [0,17–0,23] | 0,17–0,25 | 0,54 | 2 | 10.042 | 6 % | 18,3 | 28,5 | 25/30 |
| W3 larga (0,70; 0,40) | 30 (30 + 0) | 0,21 [0,17–0,27] | 0,17–0,36 | 1,51 | 2 | 10.043 | 6 % | 18,4 | 23 | 25/30 |
| W4 backbone ×1 | 30 (26 + 4) | 14,2 [9,0–20,4] | 7,2–23,3 | 112,7 | 41,5 | 71.158 | 83 % | 30,3 | 45,5 | 3/30 |
| W5 backbone, hubs ×10 | 30 (28 + 2) | 4,0 [1,6–10,3] | 0,9–18,9 | 57,8 | 16,5 | 42.766 | 74 % | 21,4 | 45,5 | 19/30 |

La brecha máxima entre las corridas detenidas al 1 % fue 0,24 %. El máximo de W4 (112,7 s) quedó cerca del límite de 120 s: con un límite menor habría habido censura.

### 5.2 Comparaciones pareadas por semilla

Las posiciones y demandas son las mismas para cada semilla.

| Id | Comparación | Razón de tiempos B/A: mediana [IC 95 %] | Media geom. [IC 95 %] | Semillas con B más lento | Cambio de z: mediana [IC 95 %] | z baja / sube / no distinguible (certificado) |
|---|---|---|---|---:|---|---|
| C1 | W1 local / W2 intermedia (cambian α y β) | 19,4 [11,3–31,8] | 17,4 [9,7–30,5] | 29/30 | +87 % [+73; +106] | 1 / 29 / 0 |
| C2 | W1 local / W3 larga (cambian α y β) | 15,5 [8,3–38,1] | 14,5 [8,0–25,5] | 29/30 | +92 % [+63; +130] | 1 / 29 / 0 |
| C3 | W3 larga / W2 intermedia (solo α; β = 0,40) | 1,00 [0,85–1,43] | 1,20 [0,96–1,53] | 13/30 | −3 % [−12; +7] | 16 / 14 / 0 |
| C4 | W4 backbone ×1 / W1 local | 2,43 [1,58–7,01] | 3,08 [1,43–6,60] | 22/30 | −20 % [−23; −4] | 22 / 8 / 0 |
| C5 | W5 ×10 / W4 ×1 (misma topología y demandas) | 0,29 [0,17–0,35] | 0,28 [0,17–0,47] | 7/30 | −25 % [−33; −17] | 27 / 0 / 3 |

Un cambio de z es "certificado" cuando los intervalos [cota inferior, z] de las dos corridas no se traslapan.

**Lectura**

- **Local frente a intermedia y larga.** La red local es unas 15–19× más lenta en 29 de 30 semillas, y también más congestionada (z +87–92 %). C1 y C2 cambian α y β a la vez, así que el efecto no se atribuye solo a α. Entre larga e intermedia, donde solo cambia α (0,2 → 0,7 con β = 0,4), **no se detecta efecto en el tiempo** (IC de la razón 0,85–1,43). La propiedad que acompaña a la lentitud es la localidad extrema: enlaces cortos (longitud media 0,10 frente a 0,33–0,46), más clustering y más iteraciones (×10–15).
- **Backbone ×1 frente a local (C4).** No es una comparación de "solo agregar hubs". Los enlaces obligatorios —24–29 hub–hub y los accesos— consumen el presupuesto fijo de 800 enlaces: W1 y W4 comparten solo 290–380 enlaces, los puentes suben de 32 a 45,5 y el grado de los nodos normales baja de 4,0 a 3,3. El resultado es una z menor en 22 de 30 semillas (mediana −20 %) **y más tiempo en 22 de 30** (mediana 2,4×). **Un backbone no siempre acelera.**
- **Refuerzo ×10 (C5), el efecto aislado.** La topología y las demandas son idénticas y solo cambia la capacidad de 24–29 enlaces hub–hub (verificado en las 30 semillas). z nunca sube: baja en 27 semillas (mediana −25 %) y queda igual en 3. **Las 3 semillas sin cambio ya tenían z determinado por un puente,** donde reforzar el backbone no puede bajar z. Esto es coherente con la teoría y sirve como chequeo lógico. El tiempo baja en 23 de 30 (mediana 0,29×), pero **sube en 7: más capacidad no siempre reduce el tiempo.** Tras el refuerzo, el puente pasa a explicar z en 19 de 30 semillas (antes, 3 de 30).
- **Puentes.** En W2 y W3 la cota de tráfico obligatorio por un puente coincide con z en 25 de 30 semillas; esas corridas certifican en 2 iteraciones y unos 0,2 s. En todas las familias, las corridas donde un puente explica z son más rápidas que las demás (W1: 0,54 s frente a 8,0 s; W4: 0,92 s frente a 16,3 s; W5: 1,8 s frente a 21,5 s). Que la cota no coincida **no demuestra** muchas rutas competitivas: pueden intervenir otros cortes.
- **Cobertura del backbone.** El acceso obligatorio alcanza al 60,7 % de los nodos normales (rango 54–65 %), cerca de la probabilidad nominal del 60 %. Pero el 65,1 % (60–69 %) tiene algún hub vecino, porque parte de los enlaces Waxman naturales también llegan a hubs. **Una probabilidad de acceso del 60 % no equivale a un 60 % de cobertura final.** El doble acceso obligatorio llega al 9,2 % (5,5–13,2 %), cerca del 0,6 × 0,15 = 9 % esperado. Los hubs tienen grado 17 frente a 3,3 de los normales.
- **Congestión muy alta.** z ≈ 18–35 significa que la capacidad modelada (50–150 por enlace) es insuficiente para la demanda (unos 300 mil en total). No es una falla del algoritmo, y por eso las comparaciones de z son relativas. Una z alta no implica dificultad: W2, con z ≈ 18, se resuelve en 0,2 s.

**Respuesta.** A tamaño fijo, la organización topológica cambia el tiempo de E3 en unos dos órdenes de magnitud: de 0,2 s en redes intermedias o largas a 4–14 s de mediana en redes locales o con backbone ×1, con máximos de hasta 113 s. Reforzar el backbone sobre la misma estructura reduce z de forma consistente y reduce el tiempo en la mayoría de las semillas, no en todas.

---

## 6. KPIs

| KPI | Estado | Evidencia |
|---|---|---|
| Tiempo | ✔ Medido (interno y pared) | Las tres baterías |
| Escalabilidad | ✔ Medida | X4, 200–3.200 nodos; comparación pareada con GC base hasta 800 |
| Memoria | ✘ **No registrada** | Ninguna batería formal la mide. Solo hay mediciones históricas de otros solvers (ciclo E2), que no corresponden a E3 |
| Calidad (requisito) | ✔ 426/430 certificadas | Validación cruzada con GC base y cota por puentes |

**Sobre la memoria.** Si se presenta, hace falta una medición nueva: por ejemplo, reutilizar `vigilar_memoria` de `src/utilidades/metricas_ejecucion.py` en una submuestra de X4. Mientras no exista, el informe debe decir que la memoria no fue medida en las baterías formales. No puede inferirse a partir de columnas o iteraciones.

---

## 7. Conclusiones

Ver `CONCLUSIONES_CLASIFICADAS.md`, que las separa en respaldadas, hipótesis y no demostradas. Las incidencias y los problemas de código están en `INCIDENCIAS.md`. La selección de figuras para los 15 minutos está en `RESUMEN_PRESENTACION.md`.

## 8. Índice de figuras (`figuras/`, cada una en PNG 200 ppp, SVG y PDF)

| Archivo | Uso |
|---|---|
| `fig00_resumen_visual_presentacion` | Diapositiva de síntesis: un mensaje por sensibilidad |
| `fig01_x3_tiempo_por_grado` | **Principal X3** |
| `fig02_x3_esfuerzo_maestro_columnas` | Respaldo X3 (columnas y peso del maestro) |
| `fig03_x4_tiempo_vs_tamano` | **Principal X4** (escalabilidad) |
| `fig04_x4_aceleracion_pareada` | **Principal X4** (frente a GC base) |
| `fig05_x4_descomposicion_iteraciones` | Respaldo X4 (dónde se va el tiempo) |
| `fig06_waxman_tiempo_por_familia` | **Principal Waxman** |
| `fig07_waxman_backbone_x1_vs_x10` | **Principal Waxman** (efecto aislado de la capacidad) |
| `fig08_waxman_local_vs_backbone` | Respaldo Waxman |
| `fig09_waxman_topologia_s1001` | Ilustración topológica (semilla 1001, la primera de la muestra) |
