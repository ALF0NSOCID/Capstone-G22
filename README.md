# Capstone G22 — Congestión en redes multiproducto

Solver de congestión mínima con generación de columnas. La versión final se llama
**E3** en el informe y mantiene el nombre `solver_columnas_e2_v2.py` en el código.

## Por dónde empezar

| Quiero… | Consultar |
| --- | --- |
| Instalar, compilar y ejecutar | [Guía de ejecución](docs/GUIA_EJECUCION.md) |
| Entender carpetas, código y accesos compatibles | [Mapa del repositorio](docs/MAPA_REPOSITORIO.md) |
| Ejecutar las baterías de cierre | [Experimentos](experimentos/README.md) |
| Localizar entradas y conocer sus supuestos | [Catálogo de datos](datos/README.md) |
| Encontrar resultados y distinguir series | [Guía de resultados](docs/RESULTADOS.md) |
| Revisar el caso aplicado chileno | [Red Chile](red_chile/README.md) |
| Revisar variantes anteriores | [Histórico y alternativas](historico/README.md) |

## Ejecutar las baterías oficiales

Desde la raíz del repositorio, con las dependencias y licencia instaladas:

```bash
# Ver planes sin generar instancias ni resolver.
python3 experimento_x3.py plan
python3 experimento_x4.py plan
python3 experimento_waxman.py plan

# Ejecutar secuencialmente. Cada script reanuda su carpeta de salida.
python3 experimento_x3.py correr
python3 experimento_x4.py correr
python3 experimento_waxman.py correr
```

| Batería | Diseño predeterminado | Salida nueva |
| --- | --- | --- |
| X3: densidad | 400 nodos, 10.000 productos solicitados; grados 4/8/12/16; 10 semillas; 300 s; **40 corridas** | `experimentos/x3_formal/` |
| X4: tamaño | 200–3.200 nodos; 30 semillas; **150 E3 + 90 GC base** hasta 800 nodos | `experimentos/x4_formal/` |
| Waxman: topología | Cinco familias; 30 semillas nuevas; backbone **60 % / 15 %**; **150 corridas** | `experimentos/waxman_formal/` |

Se conserva la comparación existente con generación de columnas base; estas
baterías no agregan un LP completo ni HiGHS. En Mulgen se registran los productos
efectivos después del filtro de conectividad.

## Estructura

```text
src/                     Implementaciones de solvers, generador, lectores y diagnóstico
experimentos/scripts/    Implementaciones de las baterías oficiales y del explorador
historico/               Métodos anteriores, alternativas y experimentos históricos
datos/README.md          Catálogo de entradas; las carpetas físicas conservan sus rutas
docs/                    Ejecución, organización y ubicación de resultados
tests/                   Pruebas de generación, planes y compatibilidad
Canad/                   Fuentes y parámetros Mulgen (ruta original)
sndlib/                  XML de referencia (ruta original)
red_chile/               Caso aplicado, fuentes, escenarios, scripts y resultados
```

Los `.py` pequeños de la raíz son **entradas compatibles** a las implementaciones
agrupadas. Se conservan sus nombres, importaciones y comandos. Para editar un
algoritmo, abrir su implementación en `src/`, `experimentos/scripts/` o
`historico/`; consultar el mapa, no duplicar cambios en la entrada compatible.
Los ejecutores `ejecutar*.py` y la compilación C++ permanecen en la raíz.

Los archivos `out`, binarios, compilaciones, entornos y resultados no son código
fuente. Sus rutas se mantienen para preservar los ejecutores y las series previas.
No ejecutar X3 y X4 simultáneamente en la misma copia: comparten `out` y Mulgen.
Para comenzar de cero en otro computador, usar carpetas de salida nuevas.

## Verificar la instalación

```bash
python3 -m unittest discover -s tests -v
```

Las pruebas no sustituyen una licencia Gurobi ni la compilación de `pricing_cpp`.
Las instrucciones completas y los comandos históricos están en la guía de ejecución.
