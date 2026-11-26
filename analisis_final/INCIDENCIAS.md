# Corridas faltantes, errores, inconsistencias y problemas de código

La verificación automática completa está en `tablas/verificaciones.csv`: 55 chequeos, de los cuales 54 dan OK o INFO y 1 da ALERTA (memoria no registrada). Aquí se resume lo que importa para el informe. **No se corrigió código ni se relanzó ninguna batería.**

## 1. Corridas faltantes

**Ninguna.**

| Batería | Esperadas | Presentes | Faltantes |
|---|---:|---:|---:|
| X3 (grados 4/8/12/16 × semillas 1–10) | 40 | 40 | 0 |
| X4 (E3 en 200–3.200 × 30; GC base en 200–800 × 30) | 240 | 240 | 0 |
| Waxman (5 familias × semillas 1001–1030) | 150 | 150 | 0 |

- El estado de la revisión previa (X4 125/240, Waxman sin empezar) quedó superado. Todo lo que hay hoy en disco se ejecutó el 24-nov-2026 entre 21:14 y 23:54 UTC.
- No hay semillas fuera del diseño, logs huérfanos ni carpetas ajenas en `waxman_formal/`; el piloto 42/43 no está ahí. Los 150 `estado.json` están consolidados en `corridas.csv`.

## 2. Corridas no certificadas y errores

- **Errores: 0.** Todos los códigos de salida son 0, no hay trazas de error y todos los logs terminan con la línea de tiempo total.
- **Timeouts externos: 0.** En Waxman no hubo timeouts de preparación.
- **Límites internos: 4**, todos en X3 y todos por tiempo: no se alcanzaron las 1.000 iteraciones y el tiempo final fue de 300,0 s.

| Instancia | Grado | Semilla | Iteraciones | Columnas | Cota superior | Cota inferior | Brecha final | % maestro |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| x3_g12_p25_s08 | 12 | 8 | 121 | 68.969 | 0,05044 | 0,00734 | 587 % | 73 % |
| x3_g12_p25_s09 | 12 | 9 | 132 | 66.981 | 0,04962 | 0,00716 | 593 % | 94 % |
| x3_g16_p25_s05 | 16 | 5 | 211 | 60.695 | 0,03426 | 0,00155 | 2.107 % | 79 % |
| x3_g16_p25_s09 | 16 | 9 | 212 | 60.978 | 0,03348 | 0,00136 | 2.354 % | 90 % |

Estas corridas se conservan como resultado. En las tablas consolidadas cuentan como "≥ 300 s" y no se reemplazaron.

## 3. Inconsistencias de datos

- **CSV ↔ logs (X3, X4):** 0 discrepancias en estado, z, tiempo, iteraciones, columnas, productos efectivos, arcos, nodos y límite.
- **CSV ↔ `estado.json` ↔ `solver.log` ↔ `parametros.json` ↔ `instancia.txt` (Waxman):** 0 discrepancias. Detalle de lo verificado:
  - Las familias W4 y W5 usan acceso 60 %/15 % en las 30 semillas.
  - Las demandas son idénticas entre las 5 variantes de cada semilla.
  - Las posiciones son idénticas: se reconstruyeron con la secuencia del generador y reproducen la longitud media del diagnóstico en las 150 corridas.
  - W4 y W5 tienen la misma topología y solo cambian los enlaces hub–hub, exactamente ×10.
  - La capacidad depende de la identidad del enlace: coincide entre W1 y W4 en los enlaces comunes.
  - El orden de ejecución sigue la aleatorización por semilla en las 30 semillas.
  - Los hashes SHA-256 del protocolo coinciden con los archivos actuales.
- **Validación cruzada X4:** el z de GC base cae dentro de [cota inferior, z] de E3 en 90/90 semillas, sobre las mismas instancias.

### Observaciones (no son errores, pero afectan la lectura)

1. **`experimentos/x3_formal/resumen.csv` informa la mediana solo de corridas certificadas** en la columna `mediana_tiempo_s`, sin rotularla. Da 9,92 s y 43,01 s en grados 12 y 16; con todas las corridas tratadas como censuradas la mediana es 21,4 s y 126,7 s.
   - Código: `experimentos/scripts/experimento_x3.py:136-137`.
   - Usar `analisis_final/tablas/x3_resumen_por_grado.csv`. Lo mismo ocurre en `experimento_x4.py:170` y `experimento_waxman.py:60-63`, pero ahí no tiene efecto porque todo certificó.
2. **El z queda vacío en el CSV de las corridas de X3 que llegaron al límite.** En la rama de límite, el solver imprime "Cota superior" pero no "Congestión máxima" (`src/solvers/solver_columnas_e2_v2.py:353-361`), y el script extrae z solo de esa línea (`experimento_x3.py:83`). Las tablas consolidadas recuperan la cota superior desde el log.
3. **La resolución temporal es de 0,01 s** (los logs imprimen 2 decimales). Con 200 nodos, E3 tarda 0,07–0,5 s, así que las razones con tamaños pequeños tienen un error de redondeo de hasta ~7 %. No cambia ninguna conclusión.

## 4. Problemas de código

No se corrigió nada. Ninguno alteró los resultados de estas baterías, pero conviene saberlo antes de reutilizar los scripts.

| # | Archivo:línea | Problema | Efecto en estas baterías |
|---|---|---|---|
| C1 | `src/solvers/solver_columnas_pricing_gurobi.py:30` (y `experimento_x4.py:66`) | GC base fija `LIMITE_TIEMPO = 900` en el código e ignora `E2_LIMITE_TIEMPO`. Un `--limite` distinto no se aplicaría al caso base. | Ninguno: el protocolo usa 900 s. |
| C2 | `experimento_x4.py:76-87` frente a `solver_columnas_pricing_gurobi.py:402` | Si GC base no certifica, imprime "No se certificó el óptimo", que no coincide con "No se alcanz", y el script la clasificaría como `error (0)` en lugar de límite. | Ninguno: 0 casos. |
| C3 | `experimento_x4.py:91` | `k_por_arcos` usa los arcos solicitados (4N), no los generados. | Ninguno: coinciden en 240/240 corridas (verificado). |
| C4 | `experimentos/scripts/explorar_waxman.py:99-100` | El estado `sin_certificar` agrupa el límite interno y la falta de certificación numérica ("SIN CERTIFICAR"); hay que leer el log para distinguirlos. | Ninguno: 0 casos. |
| C5 | `experimento_x3.py:65-66`, `experimento_x4.py:72-73` | Ante un timeout externo, `TimeoutExpired.stdout` llega en bytes y el script guarda un log vacío, con lo que se pierde la salida parcial. | Ninguno: 0 timeouts. |
| C6 | `src/solvers/solver_columnas_e2_v2.py:60-67` y `:100`, frente a `solver_columnas_pricing_gurobi.py:209` y `:264-270` | El reloj interno de E3 parte después de construir el motor C++; el de GC base incluye la construcción de sus LP de pricing. Ambos excluyen la lectura de la instancia. Esto favorece levemente a E3 en la razón de tiempos internos. | Acotado: se informa también la razón con tiempo de pared (14–64×), que es conservadora. |
| C7 | `src/solvers/solver_columnas_e2_v2.py:199-203, 170, 240` | El límite de tiempo de E3 se revisa al inicio de cada iteración y se aplica al maestro, pero no a la partida ni al pricing. Puede excederse levemente. | Mínimo: máximo 300,02 s en X3. |
| C8 | Scripts formales frente a `src/utilidades/metricas_ejecucion.py:60` | `vigilar_memoria` existe y la usa `ejecutar.py:257-260`, pero no X3, X4 ni Waxman. **La memoria no se registró.** | El KPI de memoria no está disponible. |
| C9 | `experimento_x3.py:7`, `experimento_x4.py:7` | Los docstrings mencionan `experimentos/x3/` y `x4/` como salida, cuando el destino real es `*_formal/`. | Solo documentación. |

## 5. Brechas de registro

- **Memoria:** no registrada en ninguna batería formal. Las únicas mediciones existentes (952 logs en `resultados E2/` y `Resultados/`) son de solvers del ciclo E2 y no representan a E3. No se mezclan.
- **Entorno en X3 y X4:** no se guardaron la versión de Python, la plataforma ni los hashes. El mismo equipo y la misma configuración se infieren de la licencia Gurobi 2855691, constante en los 280 logs, de la secuencia temporal continua con Waxman (que sí registra macOS 26.6.2 arm64 y Python 3.9.6) y de que solvers y scripts son anteriores a la primera corrida.
- **Preparación en Waxman:** solo se cronometra la generación (máximo 0,22 s). El diagnóstico y el dibujo no se miden por separado; ninguna corrida superó el tope de 60 s.
- **Versión de Gurobi:** no figura en los logs (`OutputFlag = 0`).

## 6. Series no mezcladas

| Serie | Motivo |
|---|---|
| `experimentos/x3/`, `experimentos/x4/` | Históricas: otras semillas y límites (900 s en X3) |
| `explorar_waxman.py`, `waxman_exploracion_*` | Exploración con acceso 80 %/25 % (no hay carpetas `waxman_exploracion_*` dentro del repositorio) |
| Piloto con semillas 42/43 | Fuera de la muestra formal 1001–1030 |
| `benchmark_local_*`, `resultados E2/`, `Resultados/` | Otros equipos, solvers o protocolos |
