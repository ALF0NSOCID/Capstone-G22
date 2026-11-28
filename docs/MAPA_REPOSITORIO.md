# Mapa del repositorio

La raíz contiene la entrada `capstone.py`, el README y las dependencias.
Las carpetas de datos y resultados científicos conservan sus ubicaciones.

| Carpeta | Contenido |
| --- | --- |
| `src/solvers/` | Implementaciones activas; E3 es `solver_columnas_e2_v2.py` |
| `src/lectores/` | Canad y adaptación SNDlib |
| `src/generadores/` | Generación Waxman |
| `src/ejecucion/` | Ejecutores, carpetas por corrida y registro |
| `src/diagnosticos/` | Análisis, visualización y perfiles |
| `src/nativo/` | Código C++ y módulo compilado local |
| `tools/` | Configuración de compilación |
| `compat/` | Accesos de comandos y módulos anteriores |
| `experimentos/scripts/` | X3, X4, Waxman, validación, eta y memoria |
| `historico/solvers/` y `historico/experimentos/` | Variantes previas |
| `historico/archivos/` | ZIP E2 y manifiesto de escalabilidad anteriores |
| `historico/copias/` | Copia antigua del benchmark local |
| `trabajo/` | Instancia compartida de baterías, compilación y temporales locales |
| `ejecuciones/` | Corridas individuales nuevas, aisladas |

## Ejecutar y editar

Usar `python3 capstone.py --help` para empezar. Los nombres anteriores están
en `compat/`: `python3 compat/ejecutar.py a1 E3`.
Editar la implementación indicada en [entradas_compatibles.json](entradas_compatibles.json),
no el wrapper.

Los wrappers conservan un `__file__` lógico en la raíz para que las rutas de datos
sigan apuntando al repositorio. `__entry_file__` identifica el acceso físico en
`compat/` y `__implementation_file__` el archivo con el código.
`archivo_fuente` permite localizar este último para inspección y huellas.

## Procedencia

Se conserva `huellas_antes_reorganizacion.json` como registro histórico.
`huellas_codigo_actual.json` comprueba las implementaciones actuales.
`migracion_raiz.json` identifica nuevas ubicaciones; no reemplaza protocolos de corridas.
Los hashes de logs/CSV históricos no se reescriben.

Las rutas nuevas pueden cambiar las huellas de scripts. Consultar corridas previas
no requiere repetirlas. Para correr otra serie, usar una salida nueva y conservar
su protocolo.

Consultar [ejecuciones](EJECUCIONES.md), [datos](../datos/README.md),
[resultados](RESULTADOS.md) e [histórico](../historico/README.md).
