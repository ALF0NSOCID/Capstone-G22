"""Contratos de aislamiento y conservación de fallos, sin licencia ni baterías."""
import _rutas

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from src.ejecucion import gestion


class EjecucionesTest(unittest.TestCase):
    def test_raiz_solo_expone_entrada_principal(self):
        raiz = Path(__file__).resolve().parents[1]
        self.assertEqual({p.name for p in raiz.glob("*.py")}, {"capstone.py"})
        import capstone
        for script in capstone.COMANDOS.values():
            self.assertTrue((raiz / "compat" / script).is_file(), script)

    def test_nombres_repetidos_no_sobrescriben(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = gestion.crear_corrida("../mismo nombre", tmp)
            b = gestion.crear_corrida("../mismo nombre", tmp)
            self.assertNotEqual(a, b)
            self.assertEqual(a.parent, Path(tmp).resolve())

    def test_instancia_y_fallo_se_conservan(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            origen = p / "red.txt"
            origen.write_text("2 2 1\n")
            solver = p / "fallo.py"
            solver.write_text("import sys; print('fallo controlado', flush=True); sys.exit(7)")
            carpeta = gestion.crear_corrida("error", p)
            with patch.object(gestion, "vigilar_memoria", lambda *args: None):
                with self.assertRaises(RuntimeError):
                    gestion.ejecutar_solver("error", solver, origen, carpeta)
            datos = json.loads((carpeta / "ejecucion.json").read_text())
            self.assertEqual(datos["estado"], "error")
            self.assertEqual(datos["codigo_salida"], 7)
            self.assertEqual((carpeta / "instancia.txt").read_text(), origen.read_text())
            self.assertIn("fallo controlado", (carpeta / "solver.log").read_text())

    def test_entrada_explicita_y_log_no_reutilizable(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            origen = p / "red.txt"
            origen.write_text("2 2 1\n")
            solver = p / "solver_prueba.py"
            solver.write_text(
                "import os\nfrom pathlib import Path\n"
                "assert Path(os.environ['ARCHIVO_INSTANCIA']).read_text() == '2 2 1\\n'\n"
                "print('Congestión máxima: 5.0')\n"
            )
            carpeta = gestion.crear_corrida("ok", p)
            with patch.object(gestion, "vigilar_memoria", lambda *args: None):
                gestion.ejecutar_solver("ok", solver, origen, carpeta)
            datos = json.loads((carpeta / "ejecucion.json").read_text())
            self.assertEqual(datos["estado"], "completada")
            self.assertEqual(datos["resultado"]["objetivo"], 5)
            self.assertIsNone(datos["ram_muestreada_kib"])
            with self.assertRaises(FileExistsError):
                gestion.ejecutar_solver("ok", solver, origen, carpeta)

    def test_interrupcion_detiene_hijo_y_registra_estado(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            origen = p / "red.txt"
            origen.write_text("2 2 1\n")
            solver = p / "esperar.py"
            solver.write_text("import time; time.sleep(30)")
            carpeta = gestion.crear_corrida("interrupcion", p)
            class SalidaInterrumpida:
                def __iter__(self):
                    raise KeyboardInterrupt
                def close(self):
                    pass
            popen = subprocess.Popen
            hijos = []
            def iniciar(*args, **kwargs):
                child = popen(*args, **kwargs)
                original = child.stdout
                child.stdout = SalidaInterrumpida()
                hijos.append((child, original))
                return child
            with patch.object(gestion.subprocess, "Popen", iniciar), \
                    patch.object(gestion, "vigilar_memoria", lambda *args: None):
                with self.assertRaises(KeyboardInterrupt):
                    gestion.ejecutar_solver("interrupcion", solver, origen, carpeta)
            for child, stream in hijos:
                stream.close()
                self.assertIsNotNone(child.poll())
            self.assertEqual(json.loads((carpeta / "ejecucion.json").read_text())["estado"],
                             "interrumpida")

    def test_ayuda_no_crea_salidas_ni_lee_instancias(self):
        raiz = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            for cmd in [
                ["capstone.py", "--help"],
                ["capstone.py", "instancia", "--help"],
                ["ejecutar.py", "--help"],
                ["ejecutar_windows.py", "--help"],
                ["ejecutar_instancia.py", "--help"],
                ["ejecutar_waxman.py", "--help"],
                ["ejecutar_sndlib.py", "--help"],
                ["capstone.py", "memoria", "--help"],
                ["capstone.py", "perfil-waxman", "--help"],
                ["capstone.py", "topologia", "--help"],
            ]:
                with self.subTest(cmd=cmd):
                    result = subprocess.run([sys.executable, str((raiz if cmd[0] == "capstone.py" else raiz / "compat") / cmd[0]), *cmd[1:]],
                                            cwd=tmp, capture_output=True, text=True)
                    self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(list(Path(tmp).iterdir()), [])


if __name__ == "__main__":
    unittest.main()
