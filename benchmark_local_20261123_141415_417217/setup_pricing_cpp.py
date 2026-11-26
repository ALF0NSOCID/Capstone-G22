import sys
from pathlib import Path

from setuptools import setup

try:
    from pybind11.setup_helpers import Pybind11Extension, build_ext
except ImportError as error:
    raise SystemExit(
        "Falta pybind11. Instálalo con: "
        "python3 -m pip install --user pybind11"
    ) from error


RAIZ = Path(__file__).resolve().parent

# MSVC (Windows) no reconoce las opciones de GCC/Clang; en macOS/Linux se
# mantienen exactamente las de antes.
if sys.platform == "win32":
    OPCIONES = ["/O2", "/DNDEBUG", "/EHsc"]
else:
    OPCIONES = ["-O3", "-DNDEBUG"]


setup(
    name="pricing_cpp",
    version="1.0.0",
    description="Motor C++ de caminos mínimos para generación de columnas",
    ext_modules=[
        Pybind11Extension(
            "pricing_cpp",
            [str(RAIZ / "pricing_cpp.cpp")],
            cxx_std=17,
            extra_compile_args=OPCIONES,
        )
    ],
    cmdclass={"build_ext": build_ext},
)
