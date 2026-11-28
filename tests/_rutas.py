"""Rutas de importación de los accesos compatibles durante las pruebas."""
import sys
from pathlib import Path
R = Path(__file__).resolve().parents[1]
if sys.pycache_prefix is None: sys.pycache_prefix = str(R / "trabajo/pycache")
for p in (R, R / "compat", R / "src/nativo"):
    if str(p) not in sys.path: sys.path.insert(0, str(p))
