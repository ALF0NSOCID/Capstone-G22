# analisis_final/

Análisis de las baterías formales de E3 (X3, X4 y Waxman). Solo lee `experimentos/*_formal/`; no modifica scripts, entradas ni resultados originales.

## Contenido

| Archivo / carpeta | Qué es |
|---|---|
| `INFORME_RESULTADOS.md` | Informe de resultados e interpretación por pregunta (validez, X3, X4, Waxman, KPI) |
| `RESUMEN_PRESENTACION.md` | Una conclusión por sensibilidad, figuras principales y de respaldo para 15 min |
| `CONCLUSIONES_CLASIFICADAS.md` | Conclusiones respaldadas, hipótesis y no demostradas |
| `INCIDENCIAS.md` | Corridas faltantes, no certificadas, inconsistencias, problemas de código (archivo:línea) |
| `tablas/` | Tablas consolidadas con procedencia (`origen_*`) y resúmenes estadísticos |
| `figuras/` | 10 figuras en PNG (300 ppp), SVG y PDF |
| `Capstone_G22_figuras_presentacion.zip` | Las figuras por separado, con nombres descriptivos y un `LEEME.txt` que explica cada una |
| `codigo/` | Código para regenerar todo |

### Tablas principales

- `verificaciones.csv`: los 55 chequeos de integridad y su resultado.
- `procedencia_archivos_originales.csv`: SHA-256 y fecha de los CSV y JSON originales usados.
- `x3_corridas_consolidadas.csv`, `x4_corridas_consolidadas.csv`, `waxman_corridas_consolidadas.csv`: una fila por corrida. Incluyen estado normalizado, censura, métricas extraídas del log (cota superior en los límites, tiempo de maestro y pricing, caminos iniciales), diagnóstico topológico y ruta del archivo de origen.
- `x3_resumen_por_grado.csv`, `x3_corridas_en_limite.csv`.
- `x4_resumen_por_tamano.csv`, `x4_aceleracion_por_semilla.csv`, `x4_aceleracion_resumen.csv`, `x4_crecimiento_empirico.csv`, `x4_validacion_cruzada_z.csv`.
- `waxman_resumen_por_familia.csv`, `waxman_comparaciones_pareadas.csv`, `waxman_comparaciones_por_semilla.csv`, `waxman_backbone_x1_vs_x10_por_semilla.csv`, `waxman_local_vs_backbone_por_semilla.csv`, `waxman_estructura_y_puentes_por_familia.csv`, `waxman_tiempo_segun_puente.csv`, `waxman_verificacion_instancias.csv`.
- `cifras_clave.json`: cifras usadas en el informe.

## Reproducir

Desde la raíz del repositorio:

```bash
bash analisis_final/codigo/ejecutar_todo.sh
```

Requiere Python 3 con numpy, pandas y matplotlib (no scipy ni networkx). Tarda unos 10 s. El remuestreo usa una semilla fija (2122), por lo que los IC se reproducen exactamente.

1. `01_consolidar.py`: inventario, verificaciones y tablas por corrida.
2. `02_estadisticas.py`: resúmenes, razones pareadas, IC por remuestreo de semillas y crecimiento empírico.
3. `03_figuras.py`: figuras.
4. `04_paquete_presentacion.py`: zip para la presentación.

## Convenciones

- E3 = `solver_columnas_e2_v2.py` (etiqueta CSV `e2_v2`). GC base = `solver_columnas_pricing_gurobi.py`.
- **Tiempo** = tiempo interno del solver, salvo cuando se indica "pared".
- Las corridas en el límite se tratan como "≥ límite"; nunca se usan como tiempo de solución.
- La "mediana solo certificadas" siempre se rotula como tal.
- **Aceleración** = T_base / T_E3 por semilla sobre la misma instancia; se resume la distribución de esas razones.
- Números con coma decimal y punto de miles.
