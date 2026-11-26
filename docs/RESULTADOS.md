# Dónde están los resultados

| Ubicación desde la raíz | Contenido |
| --- | --- |
| `experimentos/x3/` | Serie histórica de densidad y productos: cinco semillas por celda, 900 s |
| `experimentos/x4/` | Serie histórica de escalabilidad: cinco semillas por tamaño |
| `experimentos/x3_formal/` | Nueva batería de densidad, creada al ejecutar |
| `experimentos/x4_formal/` | Nueva batería de tamaño, creada al ejecutar |
| `experimentos/waxman_formal/` | Nueva batería topológica 60 % / 15 %, creada al ejecutar |
| `red_chile/experimentos/` | Aplicación Chile: candidatos, fallas, referencias y figuras |
| `resultados E2/` | Mejoras y comparaciones del ciclo anterior |
| `Resultados/` / `resultados/` | Logs de los ejecutores tradicionales |
| `benchmark_local_*/` | Copias independientes y comparación de equipo |
| `waxman_exploracion_*/` | Exploraciones independientes, si se guardaron dentro del repo |

En sistemas sin distinción de mayúsculas `Resultados/` y `resultados/` pueden
ser la misma carpeta; en otros son diferentes. La reorganización no las fusiona
ni cambia la procedencia de ningún registro.

La mediana de corridas certificadas debe identificarse como tal y acompañarse
con el número de certificadas y límites de tiempo. Una terminación con código
cero no es, por sí sola, un certificado. Conservar protocolo y equipo por serie.
