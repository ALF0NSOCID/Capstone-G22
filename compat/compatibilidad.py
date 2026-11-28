"""Conserva rutas y nombres públicos mientras las implementaciones están agrupadas.

Las implementaciones se ejecutan en el módulo original. __file__ mantiene la ruta
pública para que datos, out y subprocesos sigan resolviéndose como antes. El nombre
usado en trazas apunta al código agrupado. No cambia el directorio de trabajo.
"""
from pathlib import Path
import json
import sys

RAIZ = Path(__file__).resolve().parents[1]
if sys.pycache_prefix is None:
    sys.pycache_prefix = str(RAIZ / "trabajo" / "pycache")
# Los accesos se ejecutan desde compat/ y las implementaciones conservan
# __file__ lógico en la raíz para no alterar sus rutas de datos.
import sys
for carpeta in (RAIZ, RAIZ / "compat", RAIZ / "src" / "nativo"):
    if str(carpeta) not in sys.path:
        sys.path.insert(0, str(carpeta))

def archivo_fuente(ruta):
    """Devuelve la implementación real para inspección de texto y huellas."""
    ruta = Path(ruta)
    if ruta.parent.resolve() in (RAIZ, RAIZ / "compat"):
        mapa = json.loads((RAIZ / "docs/entradas_compatibles.json").read_text(encoding="utf-8"))
        if ruta.name in mapa:
            return RAIZ / mapa[ruta.name]
    return ruta

def ejecutar_entrada(espacio, relativa):
    """Carga una implementación conservando nombre, argumentos y ruta pública."""
    fuente = RAIZ / relativa
    espacio["__entry_file__"] = str(Path(espacio["__file__"]).resolve())
    espacio["__file__"] = str(RAIZ / Path(espacio["__file__"]).name)
    espacio["__implementation_file__"] = str(fuente)
    exec(compile(fuente.read_bytes(), str(fuente), "exec"), espacio)
