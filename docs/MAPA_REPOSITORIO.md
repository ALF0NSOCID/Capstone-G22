# Mapa del repositorio

## Organización y compatibilidad

El código de 30 módulos está agrupado por responsabilidad. Cada entrada pública
original en la raíz ejecuta su implementación en el mismo espacio de nombres;
conserva `__name__`, `__file__`, argumentos y directorio de trabajo para resolver
las rutas anteriores. Las trazas identifican el archivo de implementación.

`compatibilidad.py` carga esas entradas. `archivo_fuente(ruta)` devuelve el
archivo real para experimentos que inspeccionan o calculan huellas del código.
Las rutas físicas de entradas, salidas, compilación y caso Chile se mantienen.
No se usan enlaces simbólicos ni se duplican implementaciones.

## Código agrupado

| Entrada pública original | Implementación para editar |
| --- | --- |
| `analisis_red.py` | [`src/diagnosticos/analisis_red.py`](../src/diagnosticos/analisis_red.py) |
| `bateria_sndlib.py` | [`historico/experimentos/bateria_sndlib.py`](../historico/experimentos/bateria_sndlib.py) |
| `corrector_conectividad.py` | [`src/diagnosticos/corrector_conectividad.py`](../src/diagnosticos/corrector_conectividad.py) |
| `ejecutar_benchmark_escalabilidad.py` | [`historico/experimentos/ejecutar_benchmark_escalabilidad.py`](../historico/experimentos/ejecutar_benchmark_escalabilidad.py) |
| `experimento_conclusiones.py` | [`historico/experimentos/experimento_conclusiones.py`](../historico/experimentos/experimento_conclusiones.py) |
| `experimento_waxman.py` | [`experimentos/scripts/experimento_waxman.py`](../experimentos/scripts/experimento_waxman.py) |
| `experimento_x3.py` | [`experimentos/scripts/experimento_x3.py`](../experimentos/scripts/experimento_x3.py) |
| `experimento_x4.py` | [`experimentos/scripts/experimento_x4.py`](../experimentos/scripts/experimento_x4.py) |
| `explorar_waxman.py` | [`experimentos/scripts/explorar_waxman.py`](../experimentos/scripts/explorar_waxman.py) |
| `generador_waxman.py` | [`src/generadores/generador_waxman.py`](../src/generadores/generador_waxman.py) |
| `generar_benchmark_escalabilidad.py` | [`historico/experimentos/generar_benchmark_escalabilidad.py`](../historico/experimentos/generar_benchmark_escalabilidad.py) |
| `lector.py` | [`src/lectores/lector.py`](../src/lectores/lector.py) |
| `lector_sndlib.py` | [`src/lectores/lector_sndlib.py`](../src/lectores/lector_sndlib.py) |
| `metricas_ejecucion.py` | [`src/utilidades/metricas_ejecucion.py`](../src/utilidades/metricas_ejecucion.py) |
| `solver.py` | [`src/solvers/solver.py`](../src/solvers/solver.py) |
| `solver_columnas.py` | [`src/solvers/solver_columnas.py`](../src/solvers/solver_columnas.py) |
| `solver_columnas_combinado.py` | [`historico/solvers/solver_columnas_combinado.py`](../historico/solvers/solver_columnas_combinado.py) |
| `solver_columnas_cpp.py` | [`src/solvers/solver_columnas_cpp.py`](../src/solvers/solver_columnas_cpp.py) |
| `solver_columnas_e2.py` | [`historico/solvers/solver_columnas_e2.py`](../historico/solvers/solver_columnas_e2.py) |
| `solver_columnas_e2_escalado.py` | [`historico/solvers/solver_columnas_e2_escalado.py`](../historico/solvers/solver_columnas_e2_escalado.py) |
| `solver_columnas_e2_v2.py` | [`src/solvers/solver_columnas_e2_v2.py`](../src/solvers/solver_columnas_e2_v2.py) |
| `solver_columnas_eliminacion.py` | [`historico/solvers/solver_columnas_eliminacion.py`](../historico/solvers/solver_columnas_eliminacion.py) |
| `solver_columnas_estabilizado.py` | [`historico/solvers/solver_columnas_estabilizado.py`](../historico/solvers/solver_columnas_estabilizado.py) |
| `solver_columnas_gap_1pct.py` | [`src/solvers/solver_columnas_gap_1pct.py`](../src/solvers/solver_columnas_gap_1pct.py) |
| `solver_columnas_limitado.py` | [`historico/solvers/solver_columnas_limitado.py`](../historico/solvers/solver_columnas_limitado.py) |
| `solver_columnas_partida_ca.py` | [`src/solvers/solver_columnas_partida_ca.py`](../src/solvers/solver_columnas_partida_ca.py) |
| `solver_columnas_pricing_gurobi.py` | [`src/solvers/solver_columnas_pricing_gurobi.py`](../src/solvers/solver_columnas_pricing_gurobi.py) |
| `solver_garg_konemann.py` | [`historico/solvers/solver_garg_konemann.py`](../historico/solvers/solver_garg_konemann.py) |
| `solver_karakostas_implicito.py` | [`historico/solvers/solver_karakostas_implicito.py`](../historico/solvers/solver_karakostas_implicito.py) |
| `solver_karakostas_implicito_rapido.py` | [`historico/solvers/solver_karakostas_implicito_rapido.py`](../historico/solvers/solver_karakostas_implicito_rapido.py) |

## Entradas de ejecución y compilación

`ejecutar.py`, `ejecutar_windows.py`, `ejecutar_sndlib.py`,
`ejecutar_waxman.py` y `ejecutar_instancia.py` siguen en la raíz.
`visualizar_waxman.py` conserva su comando mediante una entrada compatible.
`setup_pricing_cpp.py`, `pricing_cpp.cpp` y el módulo compilado conservan sus
rutas para que la compilación y las importaciones sigan funcionando.

Los archivos pequeños de compatibilidad no contienen el algoritmo. Editar solo
las implementaciones indicadas. Los archivos de datos y resultados permanecen
intactos; las nuevas carpetas de código no son nuevas baterías ejecutadas.

## Documentación

- [Instalación y ejecución detalladas](GUIA_EJECUCION.md)
- [Catálogo de datos](../datos/README.md)
- [Baterías oficiales](../experimentos/README.md)
- [Resultados](RESULTADOS.md)
- [Métodos anteriores y alternativas](../historico/README.md)

`entradas_compatibles.json` es el índice usado por la carga y la inspección de
fuentes. `huellas_antes_reorganizacion.json` registra las huellas de las
implementaciones previas. Los únicos cambios de código durante el traslado son
adaptaciones en tres experimentos para inspeccionar las implementaciones reales.
Las fórmulas y parámetros de solvers y generadores no fueron modificados.

## Verificación

Desde la raíz: `python3 -m unittest discover -s tests -v`.
Para inspeccionar baterías sin ejecutar: los tres `experimento_*.py plan`.
Para un equipo nuevo: instalar dependencias, licencia y compilar C++; usar salidas
nuevas para no saltar por reanudación las corridas que se quieren repetir.
