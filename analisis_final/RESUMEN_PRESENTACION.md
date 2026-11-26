# Resumen visual para la presentación (15 min)

Una conclusión principal por sensibilidad, sostenida por una o dos figuras. El resto queda como respaldo. Todas las figuras están en `figuras/` (PNG para diapositivas; SVG o PDF si hay que editarlas).

## Diapositiva de síntesis
**`fig00_resumen_visual_presentacion`**, en formato 16:9.

> E3 certifica 426 de 430 corridas. Es rápido y escala bien en redes dispersas; la densidad y la organización de la red determinan cuándo se vuelve difícil.

---

## 1. Densidad (X3)
**Figura:** `fig01_x3_tiempo_por_grado`

**Mensaje:** *Con grado 12–16, el tiempo de E3 se dispersa en tres órdenes de magnitud y 2 de cada 10 corridas no certifican en 300 s; con grado 4–8 la mediana está bajo 1 s (máximo 3,1 s).*

- Grados 4 y 8: 10/10 certificadas, medianas de 0,36 s y 0,25 s.
- Grados 12 y 16: 8/10 certificadas, medianas de 21 s y 127 s (con las corridas en el límite contadas como ≥ 300 s).
- La causa visible es el maestro: concentra el 71–84 % del tiempo y se generan 3–4 columnas por producto.
- **Decir en voz alta:**
  - Los 300 s de las corridas en el límite no son tiempos de solución.
  - Las redes más densas tienen menos congestión, y aun así son más difíciles.

## 2. Escalabilidad (X4)
**Figuras:** `fig03_x4_tiempo_vs_tamano` y `fig04_x4_aceleracion_pareada`

**Mensaje:** *En redes dispersas, E3 resuelve 3.200 nodos (≈ 77 mil productos) con una mediana de 7,5 s, y es 26×, 50× y 124× más rápido que la GC base a 200, 400 y 800 nodos.*

- Las 240 corridas certifican.
- La aceleración es pareada por semilla, y ninguna semilla fue más lenta con E3. Con tiempo de pared es 14–64×.
- La ventaja se mantiene en las semillas donde E3 llegó al óptimo exacto, así que no viene de detenerse al 1 %.
- **Decir en voz alta:**
  - El caso base solo se ensayó hasta 800 nodos.
  - El ajuste log-log (β ≈ 0,72 frente a 1,20) describe esta familia; no es complejidad teórica.
  - K·|A| ≈ 10⁹ es una dimensión equivalente: E3 no construye esas variables.

## 3. Topología (Waxman)
**Figuras:** `fig06_waxman_tiempo_por_familia` (y `fig07_waxman_backbone_x1_vs_x10` si hay tiempo)

**Mensaje:** *A igual tamaño, la organización de la red cambia el tiempo de E3 en dos órdenes de magnitud. Reforzar el backbone nunca empeora z y casi siempre acelera, pero agregar backbone sin capacidad extra suele frenar.*

- Local frente a intermedia: unas 19× más lenta (pareado, 29/30 semillas).
- Backbone ×1 frente a local: z −20 %, pero 2,4× más lento en 22/30 semillas, porque los enlaces obligatorios consumen el presupuesto fijo.
- Backbone ×10 frente a ×1, sobre la misma red: z −25 % (nunca sube) y 0,29× el tiempo en 23/30 semillas.
- **Decir en voz alta:**
  - z ≈ 18–35 indica que la capacidad es insuficiente para la demanda modelada; no es una falla del algoritmo.
  - Las familias espaciales cambian α y β a la vez, y el efecto de α solo no se detecta.

---

## Respaldo (no proyectar salvo preguntas)

| Figura | Responde a |
|---|---|
| `fig02_x3_esfuerzo_maestro_columnas` | ¿Por qué cuesta la densidad? (columnas, peso del maestro) |
| `fig05_x4_descomposicion_iteraciones` | ¿Dónde se va el tiempo de cada método? (iteraciones, composición) |
| `fig08_waxman_local_vs_backbone` | Detalle por semilla de backbone ×1 frente a local |
| `fig09_waxman_topologia_s1001` | Cómo se ven las redes local y backbone con las mismas posiciones (semilla 1001) |

## Advertencias para preguntas

- **Memoria:** no fue medida en las baterías formales. Hay que decirlo explícitamente o medirla antes de la entrega.
- **Comparación con FPTAS u otros métodos:** no forma parte de estas baterías.
- **Calidad:** E3 entrega z con brecha certificada ≤ 1 % (óptimo exacto en 140/150 corridas de Waxman y 117/150 de X4). En X4 se validó contra el óptimo del caso base en las 90 semillas.
