# Capstone G22 — Flujo multicommodity

Este repositorio compara distintos métodos para minimizar la congestión máxima
en redes multicommodity. Los resultados de cada ejecución se guardan en
`resultados/`.

## Instancias Mulgen

Ejecución básica con una instancia de `Canad/Data/`:

```bash
python3 ejecutar.py a10 solver_columnas
```
Caso Windows:
```bash
python ejecutar_windows.py a10 solver_columnas
```

El primer argumento selecciona el archivo de parámetros, por ejemplo `a10`
usa `Canad/Data/a10.par`. El segundo argumento selecciona el solver.

Para imprimir primero un diagnóstico estructural de la red:

```bash
python3 ejecutar.py a10 solver_columnas --analizar-red
```

### Solvers principales

```bash
# Formulación completa por arcos en Gurobi.
python3 ejecutar.py a10 solver

# Generación de columnas base con pricing Dijkstra en Python.
python3 ejecutar.py a10 solver_columnas

# Generación de columnas con detención certificada al 1%.
python3 ejecutar.py a10 solver_columnas_gap_1pct

# Partida congestion-aware para mejorar las columnas iniciales.
python3 ejecutar.py a10 solver_columnas_partida_ca

# Pricing y caminos mínimos implementados en C++.
python3 ejecutar.py a10 solver_columnas_cpp

# Generación de columnas con estabilización dual.
python3 ejecutar.py a10 solver_columnas_estabilizado
```

Antes de usar el solver C++, compilar su módulo una vez:

```bash
python3 -m pip install pybind11
python3 setup_pricing_cpp.py build_ext --inplace
```
Instancias principales pueden ser encontradas en Canad/Data. Se ecnuentra como a10.par y contienen los parámetros para reproducir cada instancia.

## Redes Waxman

`ejecutar_waxman.py` genera una red espacial Waxman y luego ejecuta el solver
seleccionado.

### Waxman normal

```bash
python3 ejecutar_waxman.py solver_columnas \
  --nodos 400 \
  --arcos 1600 \
  --productos 10000 \
  --alpha 0.2 \
  --beta 0.4 \
  --semilla 42 \
  --analizar-red
```

- `alpha` controla cuánto se penalizan geográficamente los enlaces largos.
- `beta` controla la probabilidad general de conexión.
- `semilla` permite reproducir exactamente la instancia.

### Waxman con hubs

```bash
python3 ejecutar_waxman.py solver_columnas \
  --nodos 400 \
  --arcos 1600 \
  --productos 10000 \
  --alpha 0.2 \
  --beta 0.4 \
  --porcentaje-hubs 0.05 \
  --vecinos-hub 3 \
  --multiplicador-hubs 10 \
  --semilla 42 \
  --analizar-red
```

- `porcentaje-hubs 0.05` convierte aproximadamente 5% de los nodos en hubs.
- `vecinos-hub 3` conecta cada hub con sus tres hubs geográficos más cercanos.
- `multiplicador-hubs 10` multiplica por diez la capacidad del backbone.

### Visualizar una red Waxman

```bash
python3 visualizar_waxman.py \
  --nodos 400 \
  --arcos 1600 \
  --productos 10000 \
  --alpha 0.2 \
  --beta 0.4 \
  --porcentaje-hubs 0.05 \
  --vecinos-hub 3 \
  --multiplicador-hubs 10 \
  --semilla 42 \
  --mostrar
```

Las imágenes se guardan en `resultados/visualizaciones/`. Los hubs aparecen
como estrellas rojas y sus conexiones como enlaces naranjas.

## Archivos principales

- `ejecutar.py`: genera instancias Mulgen, ejecuta un solver y guarda sus KPI.
- `ejecutar_waxman.py`: genera y resuelve instancias Waxman.
- `generador_waxman.py`: construye redes Waxman normales o con hubs.
- `visualizar_waxman.py`: crea una imagen de la topología espacial.
- `analisis_red.py`: calcula conectividad, grados, capacidades y demandas.
- `lector.py`: lee la instancia activa en el formato Canad.
- `metricas_ejecucion.py`: calcula tiempos, memoria y resumen de ejecución.
- `pricing_cpp.cpp`: implementa los caminos mínimos del pricing en C++.

