#!/usr/bin/env python3
"""Paso 4: paquete de figuras para la presentación (zip).

Copia cada figura de analisis_final/figuras/ con un nombre descriptivo, en
PNG (300 ppp), SVG y PDF, agrega un índice LEEME.txt y comprime todo en
analisis_final/Capstone_G22_figuras_presentacion.zip.

Uso, desde la raíz del repositorio:
    python3 analisis_final/codigo/04_paquete_presentacion.py
"""
from __future__ import annotations

import shutil
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from comun import FIGURAS, SALIDA  # noqa: E402

NOMBRE = "Capstone_G22_figuras_presentacion"
CARPETA = SALIDA / NOMBRE
ZIP = SALIDA / f"{NOMBRE}.zip"

# (archivo de origen, nombre en el paquete, uso, qué muestra, mensaje, datos)
FIGS = [
    ("fig01_x3_tiempo_por_grado", "01_X3_densidad_tiempo_por_grado", "PRINCIPAL",
     "Tiempo interno de E3 de cada semilla según el grado de la red (4, 8, 12, 16), con mediana y rango intercuartílico.",
     "Con grado 12–16 el tiempo se dispersa (de 0,2 s a ≥ 300 s) y 2 de 10 corridas no certifican en 300 s; con grado 4–8 la mediana está bajo 1 s (máximo 3,1 s).",
     "X3: 40 corridas, Mulgen 400 nodos, 10.000 productos solicitados, semillas 1–10, límite 300 s."),
    ("fig03_x4_tiempo_vs_tamano", "02_X4_escalabilidad_tiempo_vs_tamano", "PRINCIPAL",
     "Tiempo interno de E3 y de la GC base según el número de nodos (200 a 3.200), con un punto por semilla y la mediana por tamaño.",
     "En redes dispersas E3 resuelve 3.200 nodos con una mediana de 7,5 s; la GC base ya tarda 95 s con 800 nodos (solo se ensayó hasta ahí).",
     "X4: 150 corridas E3 + 90 GC base, grado 4, 25 productos por nodo, semillas 1–30, límite 900 s, todas certificadas."),
    ("fig04_x4_aceleracion_pareada", "03_X4_aceleracion_E3_vs_GC_base", "PRINCIPAL",
     "Aceleración T_GC base / T_E3 de cada semilla (misma instancia) para 200, 400 y 800 nodos, con mediana e IC 95 %.",
     "E3 es 26×, 50× y 124× más rápido que la GC base y ninguna semilla fue más lenta con E3; la ventaja crece con el tamaño.",
     "X4: 30 pares por tamaño; IC por remuestreo de semillas; también se marca la mediana con tiempo de pared (14–64×)."),
    ("fig06_waxman_tiempo_por_familia", "04_Waxman_topologia_tiempo_por_familia", "PRINCIPAL",
     "Tiempo interno de E3 en las cinco familias Waxman (local, intermedia, larga, backbone ×1, backbone ×10) con el mismo tamaño.",
     "La organización de la red cambia el tiempo en dos órdenes de magnitud: de 0,2 s (intermedia/larga) a 4–14 s de mediana (local y backbone ×1).",
     "Waxman: 150 corridas, 400 nodos, 800 enlaces, 10.000 productos, semillas 1001–1030, límite 120 s, todas certificadas."),
    ("fig07_waxman_backbone_x1_vs_x10", "05_Waxman_refuerzo_backbone_x1_vs_x10", "PRINCIPAL",
     "Comparación semilla a semilla de backbone ×1 y ×10 sobre la misma topología: (a) tiempos, (b) cambio de congestión z.",
     "Multiplicar ×10 la capacidad entre hubs nunca sube z (mediana −25 %) y reduce el tiempo en 23 de 30 semillas (mediana 0,29×), no en todas.",
     "Waxman W4 vs W5: 30 pares con mismas posiciones, demandas y enlaces."),
    ("fig00_resumen_visual_presentacion", "06_Sintesis_tres_sensibilidades_16x9", "OPCIONAL (síntesis)",
     "Diapositiva 16:9 con las tres sensibilidades lado a lado y un titular por cada una.",
     "Sirve como cierre o resumen; cada panel también está como figura individual (01, 02 y 04).",
     "Las mismas 430 corridas de X3, X4 y Waxman."),
    ("fig02_x3_esfuerzo_maestro_columnas", "R1_X3_respaldo_esfuerzo_maestro_y_columnas", "RESPALDO",
     "(a) Tiempo frente a columnas generadas; (b) porcentaje del tiempo en el problema maestro por grado.",
     "En redes densas crecen las columnas y el maestro concentra el 71–84 % del tiempo (asociación, no causalidad).",
     "X3: las mismas 40 corridas de la figura 01."),
    ("fig05_x4_descomposicion_iteraciones", "R2_X4_respaldo_composicion_tiempo_e_iteraciones", "RESPALDO",
     "(a) En qué se gasta el tiempo (caminos iniciales, maestro, pricing, resto) por método y tamaño; (b) iteraciones.",
     "E3 itera 3–5 veces; la GC base 11–22 y gasta la mayor parte en pricing por LP y caminos iniciales.",
     "X4: las mismas 240 corridas."),
    ("fig08_waxman_local_vs_backbone", "R3_Waxman_respaldo_local_vs_backbone_x1", "RESPALDO",
     "Comparación semilla a semilla de la red local y local + backbone ×1: (a) tiempos, (b) cambio de z.",
     "Agregar backbone sin capacidad extra baja z en 22 de 30 semillas pero aumenta el tiempo en 22 de 30 (mediana 2,4×).",
     "Waxman W1 vs W4: 30 pares con mismas posiciones y demandas (la topología cambia)."),
    ("fig09_waxman_topologia_s1001", "R4_Waxman_respaldo_dibujo_redes_semilla_1001", "RESPALDO",
     "Dibujo de la red local y de la red con backbone para la semilla 1001, con las mismas posiciones; puentes en rojo y hubs en naranjo.",
     "Ilustra cómo los enlaces obligatorios del backbone desplazan enlaces locales y aumentan los puentes (31 → 51 en esta semilla).",
     "Waxman semilla 1001 (la primera de la muestra, no elegida por su resultado)."),
]

FORMATOS = [("png", "PNG_300ppp"), ("svg", "SVG_vectorial"), ("pdf", "PDF_vectorial")]


def leeme():
    lineas = [
        "CAPSTONE ICS2122 · GRUPO 22 — FIGURAS DE RESULTADOS (E3)",
        "=" * 60,
        "",
        "Cada figura viene por separado y en tres formatos:",
        "  · PNG_300ppp ......... usar este en PowerPoint, Keynote o Google Slides.",
        "  · SVG_vectorial ...... se puede agrandar sin perder calidad (PowerPoint 365 y Keynote lo aceptan).",
        "  · PDF_vectorial ...... para el informe escrito (LaTeX, Word).",
        "",
        "Los nombres empiezan con el orden sugerido:",
        "  01–05 = figuras principales (una idea por diapositiva)",
        "  06    = síntesis opcional (las tres sensibilidades juntas)",
        "  R1–R4 = respaldo, para preguntas",
        "",
        "Cada figura ya trae su título, subtítulo con los datos (n, protocolo) y una nota de fuente.",
        "Ejes en escala logarítmica cuando se indica. Relleno = óptimo certificado; círculo hueco =",
        "brecha ≤ 1 % certificada; × rojo = límite de tiempo sin certificar.",
        "",
        "Advertencias al presentar: la memoria (RAM) no se midió en estas baterías; la GC base",
        "solo llega a 800 nodos; los ajustes log-log describen las redes ensayadas, no la complejidad teórica.",
        "",
        "-" * 60,
    ]
    for _, destino, uso, que, mensaje, datos in FIGS:
        lineas += ["", f"{destino}   [{uso}]",
                   f"  Qué muestra: {que}",
                   f"  Mensaje:     {mensaje}",
                   f"  Datos:       {datos}"]
    lineas += ["", "-" * 60,
               "Generado con analisis_final/codigo/ (ejecutar_todo.sh). Detalle en analisis_final/INFORME_RESULTADOS.md.", ""]
    return "\n".join(lineas)


def main():
    # Se sobrescribe en lugar de borrar (algunas carpetas sincronizadas no permiten borrar).
    archivos = []
    for ext, carpeta in FORMATOS:
        (CARPETA / carpeta).mkdir(parents=True, exist_ok=True)
        for origen, destino, *_ in FIGS:
            dst = CARPETA / carpeta / f"{destino}.{ext}"
            shutil.copyfile(FIGURAS / f"{origen}.{ext}", dst)
            archivos.append(dst)
    (CARPETA / "LEEME.txt").write_text(leeme(), encoding="utf-8")
    archivos.insert(0, CARPETA / "LEEME.txt")
    with zipfile.ZipFile(ZIP, "w", compression=zipfile.ZIP_DEFLATED) as z:   # "w" trunca el zip anterior
        for p in archivos:
            z.write(p, p.relative_to(SALIDA))
    print(f"paquete: {ZIP.relative_to(SALIDA.parent)} ({ZIP.stat().st_size / 1e6:.1f} MB, "
          f"{len(FIGS)} figuras × {len(FORMATOS)} formatos)")


if __name__ == "__main__":
    main()
