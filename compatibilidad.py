"""Conserva rutas y nombres públicos mientras las implementaciones están agrupadas.

Las implementaciones se ejecutan en el módulo original. __file__ mantiene la ruta
pública para que datos, out y subprocesos sigan resolviéndose como antes. El nombre
usado en trazas apunta al código agrupado. No cambia el directorio de trabajo.
"""
from pathlib import Path
import json

RAIZ = Path(__file__).resolve().parent

def archivo_fuente(ruta):
    """Devuelve la implementación real para inspección de texto y huellas."""
    ruta = Path(ruta)
    if ruta.parent.resolve() == RAIZ:
        mapa = json.loads((RAIZ / "docs/entradas_compatibles.json").read_text(encoding="utf-8"))
        if ruta.name in mapa:
            return RAIZ / mapa[ruta.name]
    return ruta

def ejecutar_entrada(espacio, relativa):
    """Carga una implementación conservando nombre, argumentos y ruta pública."""
    fuente = RAIZ / relativa
    espacio["__implementation_file__"] = str(fuente)
    exec(compile(fuente.read_bytes(), str(fuente), "exec"), espacio)
