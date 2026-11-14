# Instancia "Red inspirada en la infraestructura chilena de fibra óptica"

Capstone ICS2122 – Grupo 22. Flujo multiproducto de congestión mínima.

## Archivos

| Archivo | Contenido |
|---|---|
| `nodos.csv` | 285 nodos numerados 1..n de norte a sur: tipo, capas, región, macrozona, comuna (polígono INE), lat/lon (OSM), población Censo 2024, cabecera comunal, fuente y clasificación. |
| `enlaces.csv` | 305 enlaces (285 base + 20 candidatos): capa, km y su origen, capacidad por sentido, fuente, clasificación, `es_puente`, `revisar_km_gt_300` y demanda desconectada si falla. |
| `demandas_base.csv` | 10.000 productos (origen, destino, demanda en Gbps), ordenados de mayor a menor. |
| `instancia_base.txt` | Instancia base en el formato del grupo (`n m K`, arcos `o d 1 cap 0`, dos líneas por producto). Solo enlaces base. |
| `escenarios/` | `demandas_*.csv` e `instancia_*.txt` para base, +25 %, +50 %, +100 %, hotspot Antofagasta y hotspot Aysén; `resumen_escenarios.csv`. |
| `fallas.csv` | 95 tramos para análisis de fallas (21 troncales, 35 FOA, 39 FON) con demanda desconectada (Gbps y %) y z* de referencia sobre la demanda que sigue conectada. |
| `supuestos.md` | Tabla de supuestos, justificación, fuente e impacto; inconsistencias entre fuentes y valor elegido. |
| `fuentes.md` | Solo fuentes abiertas y verificadas, con URL. |
| `verificaciones.md` | Resultado de las verificaciones obligatorias y estadísticas. |
| `resumen.md` | Resumen de una página: DATO / ESTIMADO / SUPUESTO y limitaciones. |
| `mapa_control.html`, `mapa_control.png` | Mapa de control coloreado por capa. |
| `datos_crudos/` | Insumos transcritos: tramos FON de los diagramas, población INE, coordenadas OSM, listado FDT, chequeo de comunas, z* de referencia por candidato. |
| `scripts/` | Código para regenerar todo. |

## Regenerar

```bash
python3 scripts/construir_instancia.py   # nodos, enlaces, demanda, instancia base, fallas
python3 scripts/generar_escenarios.py    # escenarios (opcional: --hotspot Biobío 2.0)
python3 scripts/referencias.py           # z* de referencia (LP agregado por origen, HiGHS vía scipy)
python3 scripts/verificar.py             # verificaciones.md
python3 scripts/generar_mapa.py          # mapa_control.html y .png
```

Requiere Python 3 con pandas, numpy, networkx, scipy y matplotlib. Los parámetros (capacidades, factor punta, fracción de salida internacional, γ, máximo de productos) están en `PARAMS` dentro de `construir_instancia.py`.

## Notas para usar la instancia

- Unidades: demanda y capacidad en Gbps por sentido; cada enlace físico aparece como dos arcos con la misma capacidad, independientes.
- Santiago (nodo 87) concentra la salida internacional/CDN: es origen o destino de los 456 productos más grandes.
- Para evaluar inversiones, agregar a la instancia los dos arcos de cada enlace con `capa == CANDIDATO`.
- Para fallas: quitar los dos arcos del enlace, descartar los productos cuyo origen y destino quedan en componentes distintas (`demanda_desconectada_*`) y resolver sobre el resto.
- `scripts/resolver_referencia.py` resuelve cualquier archivo de instancia en ~1 s; sirve para validar el z* de la generación de columnas.
