"""Extracción y presentación de métricas de las ejecuciones de solvers."""

import re
import subprocess


def extraer_ultimo(texto, patrones, conversion=float):
    for patron in patrones:
        coincidencias = re.findall(patron, texto, flags=re.IGNORECASE)
        if coincidencias:
            return conversion(coincidencias[-1])
    return None


def resumir_salida(texto):
    return {
        "objetivo": extraer_ultimo(texto, [
            r"Optimal objective\s+([0-9.eE+\-]+)",
            r"Congesti[oó]n m[aá]xima(?: aproximada)?:\s*([0-9.eE+\-]+)",
        ]),
        "cota_superior": extraer_ultimo(
            texto, [r"Cota superior[^:]*:\s*([0-9.eE+\-]+)"]
        ),
        "cota_inferior": extraer_ultimo(
            texto, [r"Cota inferior[^:]*:\s*([0-9.eE+\-]+)"]
        ),
        "gap": extraer_ultimo(texto, [r"Gap[^:]*:\s*([0-9.eE+\-]+)%"]),
        "rondas": extraer_ultimo(texto, [r"Rondas realizadas:\s*(\d+)"], int),
        "fases": extraer_ultimo(texto, [r"Fases realizadas:\s*(\d+)"], int),
        "aumentos": extraer_ultimo(texto, [r"Aumentos de camino:\s*(\d+)"], int),
        "iteraciones": extraer_ultimo(texto, [r"Iteraciones:\s*(\d+)"], int),
        "columnas": extraer_ultimo(texto, [r"Columnas:\s*(\d+)"], int),
        "tiempo_algoritmo": extraer_ultimo(
            texto, [r"Tiempo total:\s*([0-9.eE+\-]+)\s*segundos"]
        ),
    }


def vigilar_memoria(pid, detener, maximo_kb):
    """Muestrea la memoria residente del solver en macOS y Linux."""
    while not detener.is_set():
        try:
            salida = subprocess.check_output(
                ["ps", "-o", "rss=", "-p", str(pid)],
                text=True,
                stderr=subprocess.DEVNULL,
            ).strip()
            if salida:
                maximo_kb[0] = max(maximo_kb[0], int(salida.split()[0]))
        except (OSError, ValueError, subprocess.SubprocessError):
            break
        detener.wait(0.1)


def construir_resumen_kpi(
    nombre_instancia,
    archivo_solver,
    codigo_salida,
    tiempo_pared,
    tiempo_cpu,
    memoria_maxima_kb,
    texto_salida,
    archivo_resultado,
    ruta_instancia,
):
    with open(ruta_instancia, "r", encoding="utf-8") as archivo:
        n, m, k = map(int, archivo.readline().split())

    datos = resumir_salida(texto_salida)
    uso_cpu = 100 * tiempo_cpu / tiempo_pared if tiempo_pared > 0 else 0
    estado = "completado" if codigo_salida == 0 else f"error ({codigo_salida})"
    lineas = [
        "",
        "=" * 58,
        "RESUMEN DE EJECUCION — KPI",
        "=" * 58,
        f"Instancia: {nombre_instancia} ({n} nodos, {m} arcos, {k} productos)",
        f"Solver: {archivo_solver.name}",
        f"Estado: {estado}",
        f"Tiempo de pared del proceso: {tiempo_pared:.2f} s",
        f"Tiempo de CPU acumulado: {tiempo_cpu:.2f} s",
        f"Uso medio aproximado de CPU: {uso_cpu:.1f}%",
    ]

    if maximo_kb := memoria_maxima_kb[0]:
        lineas.append(f"Memoria residente maxima observada: {maximo_kb / 1024:.2f} MB")
    else:
        lineas.append("Memoria residente maxima observada: no disponible")

    etiquetas = [
        ("Tiempo interno del algoritmo", "tiempo_algoritmo", " s"),
        ("Objetivo/congestion", "objetivo", ""),
        ("Cota superior", "cota_superior", ""),
        ("Cota inferior", "cota_inferior", ""),
        ("Gap certificado", "gap", "%"),
        ("Rondas", "rondas", ""),
        ("Fases", "fases", ""),
        ("Aumentos de camino", "aumentos", ""),
        ("Iteraciones", "iteraciones", ""),
        ("Columnas finales", "columnas", ""),
    ]
    for etiqueta, clave, sufijo in etiquetas:
        if datos[clave] is not None:
            lineas.append(f"{etiqueta}: {datos[clave]}{sufijo}")

    lineas.extend([
        f"Resultado guardado en: {archivo_resultado}",
        "=" * 58,
    ])
    return "\n".join(lineas) + "\n"
