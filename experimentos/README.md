# Experimentos

Las implementaciones están en `scripts/`; los comandos públicos se ejecutan desde
la raíz del repositorio. E3 corresponde a `solver_columnas_e2_v2.py`.

## Baterías oficiales de cierre

| Comando | Diseño y número de corridas | Salida |
| --- | --- | --- |
| `python3 compat/experimento_x3.py correr` | Cuatro grados, 10 semillas, 10.000 productos solicitados, 300 s: 40 | `x3_formal/` |
| `python3 compat/experimento_x4.py correr` | Cinco tamaños, 30 semillas, 900 s: 150 E3 y 90 GC base | `x4_formal/` |
| `python3 compat/experimento_waxman.py correr` | Cinco familias, semillas 1001–1030, acceso 60 % / 15 %, 120 s: 150 | `waxman_formal/` |

Cada uno acepta `plan`, `correr`, `resumen`, `--semillas` y `--salida`.
`plan` no genera ni resuelve. Las entradas ya registradas se saltan; revisar los
fallos guardados antes de reanudar. No transferir una carpeta formal con datos si
se pretende repetir toda la batería desde cero en otro computador.

X3 formal mantiene solo 25 productos por nodo. Para pedir explícitamente la
rejilla histórica usar `--productos-por-nodo 10 25 50`. X4 incluye 3.200 por
defecto; admite `--sin-3200` y `--sin-base`.

## Exploración y antecedentes

- `explorar_waxman.py` conserva 80 % / 25 % como exploración anterior; la batería
  formal es `experimento_waxman.py`, con 60 % / 15 %.
- `x3/` contiene la serie histórica factorial, cinco semillas por celda y límite
  900 s. No mezclar su tasa de certificación con el protocolo formal de 300 s.
- `x4/` contiene la serie histórica de cinco semillas por tamaño.
- `sndlib_validacion_v2.csv` conserva su nombre de procedencia; contiene la
  validación de E3 frente a la referencia LP.
- Experimentos históricos adicionales: `historico/experimentos/`.

Las salidas conservan semillas, estados y límites. Los resultados de las baterías
nuevas se crean al ejecutarlas; una carpeta todavía inexistente no implica fallo.
Los protocolos y supuestos detallados están en [la guía](../docs/GUIA_EJECUCION.md).
