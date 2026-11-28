"""Carpetas independientes, generación aislada y registro de ejecuciones."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
import uuid

from compatibilidad import archivo_fuente
from metricas_ejecucion import construir_resumen_kpi, resumir_salida, vigilar_memoria

RAIZ = Path(__file__).resolve().parents[2]
FUENTES_MULGEN = (
    "main.f", "mulgen.f", "ran2.f", "outdat.f", "mps.f", "lp.f",
    "append.f", "traitenom.f", "int2char.f",
)


def nombre_seguro(nombre):
    return re.sub(r"[^a-zA-Z0-9_.-]+", "_", str(nombre)).strip("._")[:100] or "corrida"


def huella(ruta):
    h = hashlib.sha256()
    with Path(ruta).open("rb") as f:
        for bloque in iter(lambda: f.read(1024 * 1024), b""):
            h.update(bloque)
    return h.hexdigest()


def guardar_json(ruta, datos):
    ruta = Path(ruta)
    temporal = ruta.with_suffix(ruta.suffix + ".tmp")
    temporal.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
    temporal.replace(ruta)


def crear_corrida(nombre, salida=None):
    base = Path(salida).resolve() if salida else RAIZ / "ejecuciones"
    marca = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    carpeta = base / f"{marca}_{nombre_seguro(nombre)}_{uuid.uuid4().hex[:8]}"
    carpeta.mkdir(parents=True, exist_ok=False)
    print(f"Carpeta de ejecución: {carpeta}", flush=True)
    return carpeta


def preparar_archivo(origen, carpeta):
    origen = Path(origen).resolve()
    if not origen.is_file():
        raise FileNotFoundError(f"No existe la instancia: {origen}")
    destino = Path(carpeta) / "instancia.txt"
    shutil.copy2(origen, destino)
    guardar_json(Path(carpeta) / "entrada.json", {
        "origen": str(origen), "sha256": huella(destino),
    })
    return destino


def generar_mulgen_aislado(nombre, carpeta):
    """Usa los mismos parámetros/fuentes sin escribir out ni compilar en Canad."""
    nombre = Path(nombre).name
    if not nombre.endswith(".par"):
        nombre += ".par"
    parametro = RAIZ / "Canad" / "Data" / nombre
    if not parametro.is_file():
        raise FileNotFoundError(f"No existe el parámetro: {parametro}")
    carpeta = Path(carpeta)
    trabajo = carpeta / "generador"
    trabajo.mkdir()
    origen = RAIZ / "Canad" / "Mulgen"
    for p in origen.iterdir():
        if p.suffix.lower() in (".f", ".cmn") or p.name == "dim.par":
            shutil.copy2(p, trabajo / p.name)
    texto = parametro.read_text(encoding="utf-8-sig")
    # El nombre de salida cambia; los parámetros de generación se conservan.
    texto, cambios = re.subn(r"(?im)^\s*outfil\s+\S+.*$", "outfil out", texto)
    if cambios != 1:
        raise ValueError("Se esperaba exactamente una directiva outfil en el .par")
    (trabajo / "parametros.par").write_text(texto, encoding="utf-8")
    ejecutable = trabajo / ("mulgen.exe" if os.name == "nt" else "mulgen")
    compilacion = ["gfortran", "-std=legacy", "-ffixed-line-length-none",
                   "-fno-stack-protector", *FUENTES_MULGEN, "-o", ejecutable.name]
    with (carpeta / "generacion.log").open("w", encoding="utf-8") as log:
        for comando in (compilacion, [str(ejecutable), "parametros.par"]):
            p = subprocess.run(comando, cwd=trabajo, stdout=log,
                               stderr=subprocess.STDOUT, text=True)
            if p.returncode:
                raise RuntimeError(f"Falló Mulgen; revisar {log.name}")
    if "EXECUTION ABORTED" in (carpeta / "generacion.log").read_text():
        raise RuntimeError("Mulgen rechazó parámetros; revisar generacion.log")
    destino = carpeta / "instancia.txt"
    shutil.copy2(trabajo / "out", destino)
    guardar_json(carpeta / "entrada.json", {
        "parametro": str(parametro), "sha256_parametro": huella(parametro),
        "sha256_instancia": huella(destino),
        "fuentes_mulgen": {p.name: huella(p) for p in trabajo.iterdir()
                           if p.suffix.lower() in (".f", ".cmn") or p.name == "dim.par"},
    })
    return destino


def _detener(proceso):
    if proceso.poll() is not None:
        return
    if os.name == "posix":
        os.killpg(proceso.pid, signal.SIGTERM)
    else:
        proceso.terminate()
    try:
        proceso.wait(timeout=3)
    except subprocess.TimeoutExpired:
        if os.name == "posix":
            os.killpg(proceso.pid, signal.SIGKILL)
        else:
            proceso.kill()
        proceso.wait()


def ejecutar_solver(nombre, solver, instancia, carpeta=None, salida=None):
    """Ejecuta el solver sobre una copia persistente; conserva fallos e interrupciones."""
    solver = Path(solver).resolve()
    origen = Path(instancia).resolve()
    carpeta = Path(carpeta).resolve() if carpeta else crear_corrida(nombre, salida)
    destino = carpeta / "instancia.txt"
    if origen != destino:
        preparar_archivo(origen, carpeta)
    log = carpeta / "solver.log"
    if log.exists():
        raise FileExistsError(f"La corrida ya tiene log: {log}")
    env = dict(os.environ, ARCHIVO_INSTANCIA=str(destino))
    fuente = archivo_fuente(solver)
    datos = {
        "instancia": nombre, "archivo_instancia": str(destino),
        "sha256_instancia": huella(destino), "solver": solver.name,
        "fuente_solver": str(fuente), "sha256_solver": huella(fuente),
        "inicio_utc": datetime.now(timezone.utc).isoformat(),
        "python": sys.version, "ejecutable_python": sys.executable,
        "plataforma": platform.platform(), "estado": "en ejecución",
        "parametros_entorno": {k: v for k, v in env.items() if k.startswith("E2_")},
        "medida_ram": "RSS muestreada con ps; no equivale al benchmark ru_maxrss",
    }
    guardar_json(carpeta / "ejecucion.json", datos)
    inicio = time.perf_counter()
    cpu_antes = os.times()
    proceso = None
    detener = threading.Event()
    memoria = [0]
    monitor = None
    lineas = []
    interrumpida = False
    error = None
    try:
        with log.open("x", encoding="utf-8") as f:
            print(f"Solver: {solver.name}\nResultado: {log}", flush=True)
            proceso = subprocess.Popen(
                [sys.executable, "-u", str(solver)], cwd=RAIZ, env=env,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                bufsize=1, start_new_session=(os.name == "posix"),
            )
            monitor = threading.Thread(target=vigilar_memoria,
                                       args=(proceso.pid, detener, memoria), daemon=True)
            monitor.start()
            try:
                for linea in proceso.stdout:
                    print(linea, end="")
                    f.write(linea)
                    f.flush()
                    lineas.append(linea)
                proceso.wait()
            except BaseException:
                _detener(proceso)
                raise
            finally:
                proceso.stdout.close()
    except KeyboardInterrupt:
        interrumpida = True
        raise
    except Exception as exc:
        error = str(exc)
        raise
    finally:
        detener.set()
        if monitor:
            monitor.join(timeout=2)
        pared = time.perf_counter() - inicio
        cpu_despues = os.times()
        cpu = (cpu_despues.children_user + cpu_despues.children_system
               - cpu_antes.children_user - cpu_antes.children_system)
        codigo = proceso.returncode if proceso else None
        datos.update(estado=("interrumpida" if interrumpida else
                             "completada" if codigo == 0 and not error else "error"),
                     codigo_salida=codigo, error=error, tiempo_proceso_s=pared,
                     ram_muestreada_kib=memoria[0] or None,
                     fin_utc=datetime.now(timezone.utc).isoformat(),
                     resultado=resumir_salida("".join(lineas)))
        guardar_json(carpeta / "ejecucion.json", datos)
        if proceso and not interrumpida and not error:
            resumen = construir_resumen_kpi(
                nombre, solver, codigo, pared, cpu, memoria,
                "".join(lineas), log, destino)
            with log.open("a", encoding="utf-8") as f:
                f.write(resumen)
            print(resumen, end="")
    if proceso.returncode:
        raise RuntimeError(f"{solver.name} terminó con código {proceso.returncode}; revisar {log}")
    return log
