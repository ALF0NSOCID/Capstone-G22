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

# Solver final E2: partida congestion-aware, pricing C++ y gap certificado al 1%.
python3 ejecutar.py a10 solver_columnas_e2

# Generación de columnas con estabilización dual.
python3 ejecutar.py a10 solver_columnas_estabilizado
```

Antes de usar el solver C++ o E2, compilar su módulo una vez:

```bash
python3 -m pip install pybind11
python3 setup_pricing_cpp.py build_ext --inplace
```
Las instancias principales se encuentran en `Canad/Data`, por ejemplo
`a10.par`, y contienen los parámetros necesarios para reproducirlas.

## Redes Waxman

`ejecutar_waxman.py` genera una red espacial Waxman y luego ejecuta el solver
seleccionado. La red se genera conexa y cada enlace no dirigido se transforma
en dos arcos dirigidos con la misma capacidad. Todos los escenarios son
reproducibles mediante `--semilla`.

Dependencias del generador y del visualizador:

```bash
python3 -m pip install networkx matplotlib
```

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
- `arcos` fija el número exacto de arcos dirigidos y debe ser par. Si se
  omite, se conserva la densidad natural de la red Waxman.
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

Los hubs forman un backbone local conectado, no un clique completo. Esto
mantiene la estructura geográfica sin consumir una cantidad excesiva de
arcos.

### Waxman con demanda y capacidades estructuradas

El generador nuevo permite combinar tres elementos:

- **Demanda gravitacional:** asigna una masa lognormal a cada nodo. Los pares
  origen-destino y sus demandas dependen del producto de sus masas.
- **Capacidades escalonadas:** clasifica los enlaces por centralidad
  `betweenness` y asigna mayor capacidad a los enlaces más centrales.
- **Backbone de hubs:** conecta hubs geográficamente cercanos y multiplica la
  capacidad de esos enlaces.

Escenario reproducible usado para las pruebas de 400 nodos, 1600 arcos y
10000 productos:

```bash
python3 ejecutar_waxman.py solver_columnas_cpp \
  --nodos 400 \
  --arcos 1600 \
  --productos 10000 \
  --alpha 0.2 \
  --beta 0.4 \
  --porcentaje-hubs 0.05 \
  --vecinos-hub 3 \
  --multiplicador-hubs 5 \
  --demanda-gravedad \
  --demanda-media 30 \
  --sigma-masa 0.15 \
  --capacidad-escalones \
  --capacidad-min 800 \
  --factores-escalon 1 1.5 2.5 4 \
  --cuantiles-escalon 0.40 0.75 0.93 \
  --semilla 42 \
  --nombre waxman_normal_s42 \
  --analizar-red
```

- `demanda-media` fija la demanda media objetivo.
- `sigma-masa` controla la heterogeneidad de las masas nodales; valores
  mayores concentran más demanda en pocos nodos.
- `capacidad-min` es la capacidad base de los escalones.
- `factores-escalon` multiplica la capacidad base en cada nivel de
  centralidad.
- `cuantiles-escalon` separa los niveles; debe existir un cuantil menos que
  factores.
- `nombre` fija el identificador usado en el archivo de resultados.

Para resolver el mismo escenario con el solver combinado de la Entrega 2,
se puede reemplazar `solver_columnas_cpp` por `solver_columnas_e2`.

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
  --multiplicador-hubs 5 \
  --demanda-gravedad \
  --demanda-media 30 \
  --sigma-masa 0.15 \
  --capacidad-escalones \
  --capacidad-min 800 \
  --capacidad-max 800 \
  --factores-escalon 1 1.5 2.5 4 \
  --cuantiles-escalon 0.40 0.75 0.93 \
  --semilla 42 \
  --salida resultados/visualizaciones/waxman_normal_s42.png \
  --mostrar
```

Las imágenes se guardan en `resultados/visualizaciones/`. Los hubs aparecen
como estrellas rojas, el backbone en color naranja, el tamaño de los nodos
representa su demanda OD y el ancho de los enlaces representa su capacidad.

## Archivos principales

- `ejecutar.py`: genera instancias Mulgen, ejecuta un solver y guarda sus KPI.
- `ejecutar_waxman.py`: genera y resuelve instancias Waxman.
- `generador_waxman.py`: construye redes Waxman normales o con hubs.
- `visualizar_waxman.py`: crea una imagen de la topología espacial.
- `analisis_red.py`: calcula conectividad, grados, capacidades y demandas.
- `lector.py`: lee la instancia activa en el formato Canad.
- `metricas_ejecucion.py`: calcula tiempos, memoria y resumen de ejecución.
- `pricing_cpp.cpp`: implementa los caminos mínimos del pricing en C++.

## Preparación y ejecución en cada sistema

Ejecutar los comandos desde la raíz del repositorio (la carpeta que contiene
este README). Usar el mismo intérprete y entorno Python para instalar paquetes,
compilar y resolver. Los comandos siguientes usan `python3`; en Windows,
reemplazarlo por `python` y escribir los ejemplos en una sola línea: la
continuación `\` de los ejemplos anteriores corresponde a bash/zsh, no a
PowerShell ni a CMD.

Dependencias de los solvers Gurobi y de las redes Waxman:

```bash
python3 -m pip install gurobipy networkx matplotlib
```

`gurobipy` requiere una licencia Gurobi válida y suficiente para el tamaño del
modelo; instalar el paquete no garantiza poder resolver las instancias grandes.
El conversor SNDlib y su opción `--listar` usan solo la biblioteca estándar.
No se necesita Fortran para SNDlib ni Waxman.

- **MULGEN:** tener `gfortran` en el PATH y conservar los fuentes de
  `Canad/Mulgen/`. `ejecutar.py` compila automáticamente si falta el ejecutable
  o hay fuentes más recientes. En Windows el `ejecutar_windows.py` ya existente
  agrega `-static` al enlace para evitar dependencias de DLL de Fortran; requiere
  una distribución de gfortran con bibliotecas estáticas. En macOS/Linux usar
  `ejecutar.py`. No reutilizar binarios de otro sistema o arquitectura.
- **Pricing C++:** `solver_columnas_cpp` y `solver_columnas_e2` requieren
  `pricing_cpp`, `setuptools`, `pybind11` y un compilador C++17 (por ejemplo,
  Clang en macOS o GCC en Linux). Desde la raíz:

  ```bash
  python3 -m pip install setuptools pybind11
  python3 setup_pricing_cpp.py build_ext --inplace
  python3 -c "from pricing_cpp import MotorCaminos; print('pricing_cpp disponible')"
  ```

  El módulo debe compilarse para el Python, sistema y arquitectura usados;
  el `.so` CPython 3.9/macOS incluido no sirve para cualquier otro entorno.
  El setup actual fija `-O3` y `-DNDEBUG`, opciones de GCC/Clang: no se garantiza
  su compilación con MSVC en Windows tal como está. Una alternativa para los
  comandos de esta guía es `solver_columnas`, que no requiere el módulo C++;
  para compilarlo en un entorno Linux bajo WSL, instalar allí también Python,
  dependencias y licencia, y usar los comandos Linux.
- **Métricas:** el monitor de memoria usa `ps` de macOS/Linux. En Windows la
  memoria puede figurar como «no disponible» y los tiempos CPU de procesos
  hijos no deben asumirse comparables entre plataformas.

Estructura mínima de entradas y archivos generados:

```text
Repo Capstone/
├── README.md
├── ejecutar.py / ejecutar_windows.py / ejecutar_sndlib.py / ejecutar_waxman.py
├── lector.py / lector_sndlib.py / solver*.py
├── setup_pricing_cpp.py / pricing_cpp.cpp
├── Canad/
│   ├── Data/a10.par                   # parámetros MULGEN (y otros .par)
│   └── Mulgen/                        # fuentes .f, dim.par, mulgen.cmn
├── sndlib/
│   ├── germany50.xml                  # redes XML estáticas
│   ├── fon-raw.xml                    # red chilena incorporada al repositorio
│   └── temporales/<red>/<serie>/      # opcional: matrices XML, XML.GZ o TGZ
├── red_chile/                        # instancia y documentación chilena original
├── out                               # instancia activa, se sobrescribe
└── resultados/                       # logs/KPI y metadatos SNDlib
```

Los scripts escriben `resultados/` en minúscula. La carpeta existente
`Resultados/` puede ser la misma en sistemas que no distinguen mayúsculas;
en sistemas que sí las distinguen son carpetas distintas.

## Redes SNDlib

`ejecutar_sndlib.py` convierte el XML a `out` y reutiliza los solvers y KPI de
`ejecutar.py`, sin compilar ni ejecutar MULGEN. El nombre de red es el nombre
del archivo sin extensión (también acepta `.xml`); el solver acepta nombre
con o sin `.py`.

```bash
# Consultar las redes estáticas disponibles sin generar ni resolver.
python3 ejecutar_sndlib.py all --listar

# Resolver una red y mostrar su diagnóstico estructural.
python3 ejecutar_sndlib.py germany50 solver_columnas --analizar-red

# Usar E2 después de compilar pricing_cpp para el entorno activo.
python3 ejecutar_sndlib.py germany50 solver_columnas_e2

# Convertir únicamente: sobrescribe out, sin usar Gurobi.
python3 ejecutar_sndlib.py germany50 --solo-generar

# Procesar todos los XML de la carpeta y omitir los ya completados.
python3 ejecutar_sndlib.py all solver_columnas --reanudar
```

Por defecto busca primero `sndlib/` junto al script. Para otra ubicación,
agregar `--carpeta-redes "ruta/a/sndlib"`. `all` incluye **todos** sus XML,
también `fon-raw.xml`; no se admite con `--solo-generar` ni con `--serie`.
Un error interrumpe el lote. `--reanudar` consulta el log y el JSON con estado
`ok` y rutas coincidentes; no verifica cambios en el contenido del XML o del
solver. Para recalcular tras cambios, omitir esa opción.

### Matrices temporales opcionales

Los XML estáticos no contienen una serie temporal. Solo usar estos comandos
cuando existan matrices separadas en `sndlib/temporales/germany50/5min/`:

```bash
python3 ejecutar_sndlib.py germany50 --serie 5min --listar
python3 ejecutar_sndlib.py germany50 solver_columnas --serie 5min --t 3
python3 ejecutar_sndlib.py germany50 solver_columnas --serie 5min --desde 1 --hasta 50 --cada 10 --reanudar
python3 ejecutar_sndlib.py germany50 solver_columnas --serie 5min --todas --reanudar
```

Los índices empiezan en 1 y siguen el orden natural de los nombres de archivo;
el ejemplo de rango requiere al menos 50 matrices. Sin selección se usa la
primera. `--carpeta-temporales "ruta/base"` busca dentro de
`ruta/base/<red>/<serie>/`. Los TGZ se extraen a disco y pueden ocupar mucho
espacio. El lector necesita una sección XML `<demands>` reconocible, con
`source`, `target` y `demandValue`; rechaza otros formatos.

### Convenciones y límites del lector SNDlib

- Cada enlace XML se convierte en dos arcos con capacidades independientes por
  sentido. No modela capacidad compartida. Arcos paralelos se fusionan sumando
  capacidades; si el XML ya trae enlaces A→B y B→A separados, ambos suman en
  cada sentido. Revisar `colisiones_arcos_fusionados` en el JSON.
- `--capacidad preinstalada_o_minima` (predeterminado) elige la preinstalada
  positiva o, en su ausencia, el módulo positivo mínimo. `minima` y `maxima`
  eligen el módulo respectivo y usan la preinstalada si no hay módulos.
  No se suman todos los módulos ni se optimiza la instalación de capacidad.
- `--factor-capacidad 2` multiplica solo las capacidades. Debe ser positivo.
  Capacidades y demandas se escalan juntas a enteros, automáticamente, con
  una potencia de diez. `--escala-fija` permite una escala común entre tiempos;
  debe ser un entero positivo que represente exactamente todos los valores.
  Un factor insuficiente produce error, sin redondeo. Escalas grandes pueden
  empeorar el comportamiento numérico del solver.
- Omite demandas nulas o con origen igual a destino; rechaza demandas negativas,
  nodos desconocidos, lazos y enlaces sin capacidad positiva. Los costos del
  XML no se usan como costos fijos: el conversor escribe cero en ese campo.
  No implementa las restricciones de diseño/enrutamiento del problema SNDlib
  original: se resuelve la adaptación de congestión del proyecto.
- `lector.py` filtra productos sin camino dirigido conservando los arcos.
  Revisar el mensaje de conectividad: el número de productos del KPI de `out`
  y del JSON de conversión puede superar el efectivamente resuelto.

## Red chilena de fibra óptica

El archivo real es **`sndlib/fon-raw.xml`**. Se ejecuta mediante el mismo lector
SNDlib; no requiere un ejecutor distinto ni parámetros MULGEN:

```bash
python3 ejecutar_sndlib.py fon-raw --listar
python3 ejecutar_sndlib.py fon-raw --solo-generar --analizar-red
python3 ejecutar_sndlib.py fon-raw solver_columnas --analizar-red
python3 ejecutar_sndlib.py fon-raw solver_columnas_e2 --analizar-red
```

La conversión del XML presente produce 285 nodos, 570 arcos dirigidos y
10.000 productos, con escala automática 1.000.000 y sin colisiones de arcos.
Es una red **inspirada en infraestructura chilena**; consultar
[`red_chile/README.md`](red_chile/README.md), sus fuentes y supuestos para
interpretarla. Las políticas de capacidad y escalado anteriores también se
aplican a este XML.

`red_chile/instancia_base.txt` y `red_chile/escenarios/instancia_*.txt` son
entradas de otro flujo, ya en formato de instancia; no son XML para
`ejecutar_sndlib.py`. Su lector de referencia admite valores decimales,
mientras que `lector.py` exige enteros. Para validar directamente la instancia
base con el programa de referencia existente (HiGHS vía SciPy):

```bash
python3 -m pip install numpy scipy
python3 red_chile/scripts/resolver_referencia.py red_chile/instancia_base.txt
```

Este último imprime el resultado en consola, sin el log/KPI del ejecutor
principal. Regenerar los datos y mapas tiene dependencias adicionales indicadas
en el README de `red_chile/`.

## Comprobación rápida, resultados y límites de ejecución

Para una prueba Waxman pequeña, con parámetros de conectividad adecuados:

```bash
python3 ejecutar_waxman.py solver_columnas --nodos 20 --arcos 60 --productos 30 --alpha 0.8 --beta 0.8 --semilla 42 --nombre waxman_prueba --analizar-red
```

En Waxman, `--arcos` debe ser par y estar entre `2*(nodos-1)` y
`nodos*(nodos-1)`; el backbone puede exigir un mínimo mayor. Con parámetros
poco densos puede fallar tras 10.000 intentos de obtener conectividad; aumentar
`alpha` o `beta`. MULGEN tiene límites compilados en `Canad/Mulgen/dim.par`:
3.200 nodos, 12.800 arcos y 85.200 productos. Estos límites pertenecen al
generador Fortran y no al conversor SNDlib ni al generador Waxman.

Los resultados de los ejemplos se escriben, respectivamente, en:

- MULGEN: `resultados/a10_solver_columnas.txt`.
- Waxman pequeño: `resultados/waxman_prueba_solver_columnas.txt`.
- SNDlib: `resultados/sndlib_germany50_base_preinstalada_o_minima_solver_columnas.txt`.
- Chile: `resultados/sndlib_fon-raw_base_preinstalada_o_minima_solver_columnas.txt`.

SNDlib guarda además un JSON con el mismo nombre base: rutas, escala,
convenciones y estado. Las series usan, por ejemplo, `5min_t000003` en lugar
de `base`; cambiar capacidad, factor o escala modifica el identificador.
`--solo-generar` solo deja `out`: no guarda ese log ni JSON.

**No ejecutar familias en paralelo en la misma copia:** todas sobrescriben el
`out` de la raíz. Repetir el mismo identificador y solver sobrescribe su log
(y su JSON si corresponde). `--analizar-red` imprime el diagnóstico antes
del solver; el archivo de resultados captura la salida del solver y su KPI,
no toda la consola del ejecutor.

Los límites están fijados dentro de cada solver, no son argumentos de estos
ejecutores: `solver.py` configura 900 s para Gurobi; `solver_columnas.py`
configura 900 s y 1.000 iteraciones; `solver_columnas_e2.py`, 120 s,
1.000 iteraciones y gap objetivo del 1 %. Alcanzar un límite o terminar con
código cero no certifica por sí solo el óptimo ni el gap objetivo: revisar
estado, cotas y gap reportados. La formulación por arcos puede consumir mucha
memoria en redes con muchos productos.

Los argumentos se contrastaron con los scripts y sus ayudas; se comprobó la
conversión de `germany50.xml` y `fon-raw.xml` en archivos temporales y la
generación Waxman de 20 nodos del ejemplo. Esto no constituye una ejecución
completa de los solvers ni una prueba de compilación en los tres sistemas.
