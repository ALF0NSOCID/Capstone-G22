# Experimentos de realismo sobre la red chilena (referencia HiGHS)

Generados con `scripts/experimentos_chile.py` (LP agregado por origen, HiGHS vía scipy; NO es el solver del proyecto).
Base: z* = 0,4898. Sirven como referencia para validar E2 y para decidir qué corridas hacer con el solver propio.

- `estructura.csv`: % de enlaces que son puentes (base 94,4 %; con los 20 candidatos 32,8 %).
- `candidatos_greedy.csv`: agregado secuencial de candidatos (mejor z en cada paso; en empate, el más corto).
  Cuatro enlaces (451,8 km) alcanzan toda la mejora de los 20 (19,19 %); desde el paso 5 z no baja.
- `fallas_con_sin.csv`: las 95 fallas de `fallas.csv`, con y sin los 20 candidatos. Columnas `servida_*_pct` (demanda
  que sigue conectada) y `z_*` (z sobre esa demanda) van separadas a propósito: z baja solo porque se desconecta demanda.
- `_parciales/`: archivos intermedios de la corrida por partes; se pueden borrar.

Uso: `python3 scripts/experimentos_chile.py estructura | greedy 8 | fallas_parte i 4 (i=1..4) | unir`.
Supuestos: los de `supuestos.md` (troncal única, capacidades por capa, candidatos de 800 Gbps).
