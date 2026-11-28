# Ejecutar el proyecto

Desde la raíz, tras instalar dependencias y compilar el motor C++ según el README.
`capstone.py` reúne los comandos; las entradas anteriores siguen disponibles.

## Resolver una red

```bash
# Instancia existente; no requiere generar otra red.
python3 capstone.py instancia red_chile/instancias_enteras/base.txt E3

# Generar Mulgen desde Canad/Data/a1.par y resolver.
python3 capstone.py mulgen a1 E3

# Generar Waxman y resolver.
python3 capstone.py waxman E3 --nodos 400 --arcos 1600 --productos 10000 --semilla 42

# Adaptar una red SNDlib y resolver.
python3 capstone.py sndlib abilene E3
```

Alias: **E3** = `solver_columnas_e2_v2.py`; **base** =
`solver_columnas_pricing_gurobi.py`; **LP** = `solver.py`.
También se aceptan los nombres de archivo anteriores.
El LP completo puede exigir muchos recursos; usar instancias pequeñas al probarlo.

Añadir `--analizar-red` para el diagnóstico y `--salida RUTA` para elegir la
carpeta base. Sin esa opción se utiliza `ejecuciones/`.
Consultar opciones con `python3 capstone.py COMANDO --help`.
Las rutas relativas de la entrada principal se interpretan desde la raíz del repo.

## Qué se guarda

Cada llamada individual crea una carpeta única:

```text
ejecuciones/fecha_nombre_identificador/
    instancia.txt       Entrada realmente utilizada
    solver.log          Salida del solver y resumen
    ejecucion.json      Estado del proceso, tiempos, certificado y huellas
```

Mulgen conserva además parámetros, fuentes y log de generación en esa carpeta;
compila allí, sin modificar las fuentes compartidas. Waxman guarda parámetros y,
si se solicita, diagnóstico. SNDlib conserva sus metadatos de conversión.
Las corridas fallidas/interrumpidas conservan lo producido. **Ctrl+C** detiene
el solver de la ejecución individual y registra la interrupción.
Completar el proceso no significa necesariamente certificar la solución: consultar
el certificado dentro de `resultado` en `ejecucion.json`.

La RAM del ejecutor es RSS muestreada, si el sistema permite medirla. No se debe
mezclar con el benchmark dedicado que utiliza `ru_maxrss`.

En SNDlib, `--reanudar` busca registros completados de la misma configuración
en la salida elegida y en los resultados compatibles anteriores.

## Baterías formales

```bash
# Consultar planes sin ejecutar.
python3 capstone.py x3 plan
python3 capstone.py x4 plan
python3 capstone.py topologia plan
```

Para ejecutarlas, usar `correr` en lugar de `plan` y consultar
[el protocolo de experimentos](../experimentos/README.md).
`validacion` y `eta` también delegan a sus scripts existentes.
Estos comandos conservan sus diseños, salidas y reanudación; **no incorporan
el aislamiento nuevo de las ejecuciones individuales**.
No lanzar simultáneamente baterías que usan `trabajo/out` o el generador compartido.
Para repetir en otro equipo, utilizar las opciones de salida nuevas de cada batería.

Los resultados científicos anteriores permanecen en `experimentos/`,
`red_chile/`, `resultados E2/` y `analisis_final/`. La carpeta `ejecuciones/`
es local e ignorada por Git; se puede compartir una corrida concreta si hace falta.

## Compilación, memoria y perfiles

Compilar el motor con python3 capstone.py compilar. El módulo se genera en
src/nativo/ y los objetos en trabajo/build/, sin ensuciar la raíz.
python3 capstone.py memoria --help ofrece el benchmark dedicado de RAM (macOS/Linux).
python3 capstone.py perfil-waxman --help permite consultar tres casos seleccionados.
Estos scripts están en el repositorio y no dependen de la carpeta personal de Codex.
Si un mensaje histórico indica compilar setup_pricing_cpp.py en la raíz,
utilizar en su lugar capstone.py compilar.
