# Conclusiones clasificadas

Criterio de clasificación:

- **Respaldada:** se sigue directamente de los datos de las baterías formales, con el diseño adecuado (pareado cuando corresponde) y sin depender de supuestos no verificados.
- **Hipótesis:** hay una asociación consistente, pero el diseño no permite atribuir causa; requiere un experimento dirigido.
- **No demostrada:** no debe afirmarse con estos datos.

Todas las cifras provienen de `tablas/`.

---

## A. Respaldadas

### Validez

1. **Las tres baterías están completas e íntegras.** Hay 430/430 corridas del diseño, sin duplicados ni filas truncadas, con coincidencia total entre CSV, logs y `estado.json`. Se ejecutaron en una única sesión secuencial sin solapes y con el código sin cambios. Ver `tablas/verificaciones.csv`.
2. **E3 entrega soluciones certificadas en 426/430 corridas.** Las 4 restantes son de X3 (grados 12 y 16) y llegaron al límite de 300 s. En X4, el óptimo de GC base cae dentro de [cota inferior, z] de E3 en 90/90 semillas, con un exceso máximo de z del 0,90 % cuando E3 se detiene al 1 %. En Waxman, la cota por puentes nunca supera z (150/150).

### X3 — densidad

3. **Con 400 nodos y 10.000 productos solicitados, pasar a grado 12–16 aumenta fuertemente la dispersión y la cola del tiempo de E3.**
   - Grados 4–8: 20/20 certificadas, todas en ≤ 3,1 s; medianas de 0,36 s y 0,25 s.
   - Grados 12–16: 16/20 certificadas, medianas de 21,4 s y 126,7 s, tiempos de 0,23 s a ≥ 300 s.
4. **En grados 12–16 el problema maestro concentra el tiempo** (mediana del 71–84 % frente al 6 % en grados 4–8), con 2,9–4,3 columnas por producto y 100–200 iteraciones.
5. **La mediana calculada solo con certificadas subestima el tiempo típico** (9,9 s frente a 21,4 s en grado 12; 43,0 s frente a 126,7 s en grado 16).

### X4 — escalabilidad y caso base

6. **E3 resuelve y certifica todas las instancias dispersas de 200 a 3.200 nodos.** La mediana con 3.200 nodos es 7,5 s y el máximo 30,5 s, lejos del límite de 900 s.
7. **E3 es más rápido que GC base en cada una de las 90 semillas comparables, y la ventaja crece con el tamaño.**
   - Tiempo interno: mediana 26× [23–27] con 200 nodos, 50× [46–58] con 400 y 124× [97–136] con 800.
   - Tiempo de pared: 14×, 29× y 64×.
8. **La ventaja no proviene del criterio de parada al 1 %.** En las semillas donde E3 alcanzó el óptimo exacto, la aceleración es 27×, 54× y 127×.
9. **En la familia ensayada, el tiempo de E3 crece más lento que el de GC base.**
   - β frente a K·|A|: 0,72 [0,66–0,78] para E3 y 1,20 [1,13–1,27] para GC base.
   - El exponente local de E3 aumenta con el tamaño (≈ 0,6 → 0,9).
   - Es una descripción empírica para Mulgen de grado 4 entre 200 y 3.200 nodos.
10. **E3 converge en 3–5 iteraciones con 1,01–1,04 columnas por producto; GC base necesita 11–22 iteraciones.**

### Waxman — topología

11. **A tamaño fijo, la organización topológica cambia el tiempo de E3 en unos dos órdenes de magnitud.** Las medianas van de 0,21 s (intermedia y larga) a 4,1 s (local) y 14,2 s (backbone ×1).
12. **La red local es más lenta que la intermedia y que la larga en 29 de 30 semillas** (razón pareada mediana 19× y 16×).
13. **Con β = 0,40, pasar de α = 0,20 a 0,70 no produce una diferencia detectable de tiempo** (razón 1,00 [0,85–1,43]).
14. **Agregar backbone con capacidad ×1 sobre la estructura local baja z en 22 de 30 semillas (mediana −20 %), pero aumenta el tiempo en 22 de 30 (mediana 2,4×).** Un backbone no siempre acelera.
15. **Sobre la misma topología y demandas, multiplicar ×10 la capacidad hub–hub nunca aumenta z:** baja en 27 de 30 semillas (mediana −25 %) y queda igual en 3. **El tiempo baja en 23 de 30 (mediana 0,29×) y sube en 7.** Más capacidad no siempre reduce el tiempo.
16. **Las 3 semillas donde ×10 no cambia z son exactamente semillas con z determinado por un puente.** Esto es consistente con la teoría: reforzar otros enlaces no puede bajar una cota de corte obligatoria.
17. **Una probabilidad de acceso del 60 % no equivale a un 60 % de cobertura.** El acceso obligatorio alcanza al 60,7 % de los nodos normales (54–65 %) y la cobertura total al 65,1 % (60–69 %). El doble acceso obligatorio es del 9,2 %.
18. **Con el presupuesto fijo de 800 enlaces, el backbone desplaza enlaces locales.** W1 y W4 comparten solo 290–380 enlaces, y los puentes suben de 32 a 45,5 (medianas).

### General

19. **Alta congestión no implica problema difícil, y z > 1 no implica falla del algoritmo.** En Waxman, z ≈ 18–35 en todas las familias y W2 se resuelve en 0,2 s. En X3, dentro de cada grado, las instancias de mayor z son las más rápidas.

---

## B. Hipótesis (asociación consistente; no causal)

H1. **Cuando un cuello aislado determina z, E3 certifica en pocas iteraciones.** Puede ser un puente con tráfico obligatorio o un corte dominante.
- Evidencia: en Waxman, las corridas donde la cota por puentes coincide con z son más rápidas en todas las familias (W4: 0,9 s frente a 16 s; W5: 1,8 s frente a 21,5 s). En X3, la correlación de rangos entre z y tiempo dentro de grado es −0,90.
- Prueba sugerida: instancias construidas con y sin cuello dominante a igual tamaño.

H2. **La dificultad en redes densas o locales proviene de una congestión difusa que exige muchas columnas y un maestro grande.**
- Evidencia: correlación entre columnas, peso del maestro y tiempo (fig02).
- Que la cota por puentes no coincida con z no demuestra que existan muchas rutas competitivas, porque pueden intervenir otros cortes.

H3. **El refuerzo ×10 acelera porque traslada el cuello de botella a puentes de acceso.**
- Evidencia: el puente explica z en 19/30 semillas con ×10 frente a 3/30 con ×1, y 16 semillas cambian de "no coincide" a "coincide".
- Las 7 semillas más lentas con ×10 muestran que el mecanismo no es universal.

H4. **La lentitud de la familia local se asocia a enlaces cortos, más clustering y mayor congestión.** No se puede atribuir solo a α, porque W1 cambia α y β a la vez y C3 no muestra efecto de α con β = 0,40.

H5. **El crecimiento de E3 en X4 se acerca a lineal en K·|A| para tamaños mayores.** Los exponentes locales suben de 0,58 a 0,94, pero sus IC son amplios (0,2–1,3). Confirmarlo requiere tamaños mayores.

H6. **La aceleración frente a GC base combina pricing en C++, partida congestion-aware y normalización.** La descomposición (fig05) sugiere que pesan el pricing por LP y los caminos iniciales del caso base. Estas baterías no tienen ablaciones, así que no separan los aportes.

---

## C. No demostradas (no afirmar)

- **Complejidad teórica de E3**, o que E3 sea "lineal" u "O(·)". El ajuste log-log solo describe la familia ensayada.
- **Superioridad sobre un FPTAS** u otros métodos no ensayados (Garg–Könemann, Karakostas). Las baterías formales comparan solo con GC base.
- **Ventaja frente a GC base por encima de 800 nodos.** La serie base se detiene en 800 y no debe extrapolarse.
- **Memoria (RAM) de E3 o de GC base.** No se registró. Columnas e iteraciones no son memoria.
- **Que un backbone siempre acelere** (es falso en 22/30 semillas con ×1) **o que más capacidad siempre reduzca el tiempo** (es falso en 7/30 con ×10).
- **Que α cause por sí solo los cambios entre familias espaciales.**
- **El tiempo real de solución de las 4 corridas de X3 en el límite,** ni la mediana exacta en grados 12–16. Solo se sabe que son ≥ 300 s y que el IC superior no está acotado.
- **Comparabilidad de la tasa de certificación de X3 formal (300 s) con la serie histórica (900 s).**
- **Generalización a otras familias de redes, otros equipos u otras versiones de Gurobi y Python.** Todas las corridas son de un único equipo y una única sesión.
- **Calidad de las soluciones de las 4 corridas no certificadas.** Sus brechas finales van de 587 % a 2.354 %.
