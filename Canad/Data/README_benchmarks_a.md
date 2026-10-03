# Benchmarks A

Esta familia usa Mulgen con topologia dirigida aleatoria (`grdarc 0`) y la
reparacion local determinista activada en `lector.py`. Los archivos conservan
los parametros numericos del ejemplo entregado por el profesor y escalan hasta
la instancia objetivo de 400 nodos, 1600 arcos y 10000 productos.

| Instancia | Nodos | Arcos | Productos | Variables explicitas aproximadas |
|---|---:|---:|---:|---:|
| a1 | 20 | 80 | 50 | 4,000 |
| a2 | 30 | 120 | 100 | 12,000 |
| a3 | 40 | 160 | 250 | 40,000 |
| a4 | 60 | 240 | 500 | 120,000 |
| a5 | 80 | 320 | 1,000 | 320,000 |
| a6 | 100 | 400 | 2,000 | 800,000 |
| a7 | 150 | 600 | 3,500 | 2,100,000 |
| a8 | 200 | 800 | 5,000 | 4,000,000 |
| a9 | 300 | 1,200 | 7,500 | 9,000,000 |
| a10 | 400 | 1,600 | 10,000 | 16,000,000 |

La ultima columna corresponde a `arcos * productos`, es decir, al numero de
variables de flujo del modelo explicito antes de sumar la variable de
congestion. En generacion de columnas solo se crean las rutas necesarias.

Todos los niveles usan la semilla 101, `ctight 60.0`, `fixvar 0.01`, una fuente
y un destino por producto, y cuatro arcos aleatorios por nodo. La reparacion de
conectividad no forma parte del generador Canad original; por eso los resultados
deben identificarse como benchmarks Canad aleatorios reparados.
