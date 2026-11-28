# Capstone G22 — Congestión en redes multiproducto

Proyecto ICS2122: minimizar la máxima utilización de los enlaces de una red.
El solver final **E3** utiliza generación de columnas, caminos mínimos en C++ y
certificación de optimalidad o brecha relativa de hasta **1 %**.

## Instalar y ejecutar

Requiere Python 3, licencia Gurobi y compilador C++17.
Para generar redes Mulgen también se necesita `gfortran`. Desde la raíz:

```bash
python3 -m pip install -r requirements.txt
python3 capstone.py compilar
python3 capstone.py instancia red_chile/instancias_enteras/base.txt E3
```

`capstone.py` es la entrada principal. Alias: **E3** = `solver_columnas_e2_v2.py`,
**base** = generación de columnas con pricing Gurobi y **LP** = formulación completa
por arcos. Consultar opciones con `python3 capstone.py --help`.

## Comandos habituales

```bash
python3 capstone.py mulgen a1 E3
python3 capstone.py sndlib abilene E3
python3 capstone.py waxman E3 --nodos 400 --arcos 1600 --productos 10000 --semilla 42
```

Cada corrida individual conserva instancia, log y metadatos en `ejecuciones/`.
Para otras opciones, salidas y herramientas de memoria:
[guía de ejecución](docs/EJECUCIONES.md).

## Experimentos y resultados

| Contenido | Ubicación |
| --- | --- |
| X3: densidad, 40 corridas | [`experimentos/x3_formal/`](experimentos/x3_formal/) |
| X4: tamaño, 150 E3 + 90 base | [`experimentos/x4_formal/`](experimentos/x4_formal/) |
| Waxman: cinco familias, 150 corridas | [`experimentos/waxman_formal/`](experimentos/waxman_formal/) |
| Validación HiGHS y SNDlib/Chile | [400 casos pequeños](experimentos/validacion/), [27 casos adaptados](experimentos/sndlib_validacion_v2.csv) |
| Calibración de eta, 84 corridas | [`experimentos/s6/`](experimentos/s6/) |
| Memoria medida | [Serie pequeña](experimentos/memoria_20261125_155019_730765/), [E3 grande](experimentos/memoria_20261125_161531_860231/) |
| Aplicación chilena y fuentes | [`red_chile/`](red_chile/README.md) |
| Tablas y gráficos consolidados | [`analisis_final/`](analisis_final/README.md) |

Para consultar o repetir baterías, seguir [experimentos](experimentos/README.md).
Usar una salida nueva al repetir con el código actual y ejecutar secuencialmente
las baterías que comparten Mulgen o `trabajo/out`.
Regenerar tablas y figuras: `bash analisis_final/codigo/ejecutar_todo.sh`.

## Organización

- `src/`: implementación; `experimentos/scripts/`: programas experimentales.
- `compat/`: accesos anteriores; `historico/`: variantes, archivos y copias antiguas.
- `trabajo/`: temporales y compilación; `ejecuciones/`: corridas individuales locales.
- [Mapa completo](docs/MAPA_REPOSITORIO.md) y [datos de entrada](datos/README.md).

Los comandos antiguos ahora se ejecutan desde `compat/`, por ejemplo:
`python3 compat/ejecutar.py a1 E3`.
Los resultados históricos conservan sus protocolos; completar un proceso no implica
certificar la solución. Chile es una representación con datos públicos y supuestos.
Las cifras de memoria medidas se distinguen de las extrapolaciones.

Pruebas: `python3 -m unittest discover -s tests -v`.
