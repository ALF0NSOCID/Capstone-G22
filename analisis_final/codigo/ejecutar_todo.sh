#!/usr/bin/env bash
# Regenera tablas y figuras de analisis_final/ desde los resultados originales.
# Uso (desde la raíz del repositorio): bash analisis_final/codigo/ejecutar_todo.sh
set -euo pipefail
cd "$(dirname "$0")/../.."
PY="${PYTHON:-python3}"
"$PY" analisis_final/codigo/01_consolidar.py
"$PY" analisis_final/codigo/02_estadisticas.py > /dev/null
"$PY" analisis_final/codigo/03_figuras.py
"$PY" analisis_final/codigo/04_paquete_presentacion.py
echo "Listo: analisis_final/tablas, analisis_final/figuras y el zip de presentación"
