"""Comprueba diseño y reanudación sin generar redes ni resolver LP."""
import csv
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]


class PlanesTest(unittest.TestCase):
    def ejecutar(self, script, carpeta, *args):
        return subprocess.run([sys.executable, str(RAIZ/script), 'plan',
                               '--salida', str(carpeta), *args],
                              cwd=RAIZ, capture_output=True, text=True)

    def test_planes_formales_no_generan_archivos(self):
        for script, fragmento in [('experimento_x3.py', '40 corridas en el plan, 40 pendientes'),
                                  ('experimento_x4.py', '240 corridas pendientes'),
                                  ('experimento_waxman.py', '150 corridas, 150 pendientes')]:
            with self.subTest(script=script), tempfile.TemporaryDirectory() as tmp:
                destino = Path(tmp)/'sin_crear'
                r = self.ejecutar(script, destino)
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertIn(fragmento, r.stdout)
                self.assertFalse(destino.exists())
                if 'x3' in script:
                    self.assertIn('Límite 300 s', r.stdout)
                    self.assertIn('productos/nodo: [25]', r.stdout)
                if 'x4' in script:
                    self.assertIn('3200', r.stdout)
                if 'waxman' in script:
                    self.assertIn('60%/15%', r.stdout)

    def test_x4_seleccion_de_semillas_y_metodos(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = self.ejecutar('experimento_x4.py', Path(tmp)/'salida',
                              '--semillas', '101', '102', '--sin-base')
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn('10 corridas pendientes', r.stdout)

    def test_x3_reanudacion_y_rejilla_explicita(self):
        with tempfile.TemporaryDirectory() as tmp:
            carpeta = Path(tmp)
            with (carpeta/'corridas.csv').open('w', newline='') as f:
                w = csv.writer(f); w.writerow(['instancia']); w.writerow(['x3_g04_p25_s01'])
            r = self.ejecutar('experimento_x3.py', carpeta)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn('40 corridas en el plan, 39 pendientes', r.stdout)
            r = self.ejecutar('experimento_x3.py', carpeta, '--semillas', '101',
                              '--productos-por-nodo', '10', '25', '50')
            self.assertIn('12 corridas en el plan, 12 pendientes', r.stdout)

    def test_rechaza_semillas_duplicadas(self):
        with tempfile.TemporaryDirectory() as tmp:
            for script in ['experimento_x3.py', 'experimento_x4.py', 'experimento_waxman.py']:
                r = self.ejecutar(script, Path(tmp), '--semillas', '1', '1')
                self.assertNotEqual(r.returncode, 0)

    def test_formal_no_modifica_exploracion(self):
        import explorar_waxman
        originales = {c: dict(p) for c, p in explorar_waxman.CASOS.items()}
        import experimento_waxman
        self.assertEqual(explorar_waxman.CASOS, originales)
        for c in ['local_backbone', 'local_backbone_x10']:
            self.assertEqual(experimento_waxman.CASOS[c]['prob_acceso_backbone'], 0.6)
            self.assertEqual(experimento_waxman.CASOS[c]['prob_segundo_hub'], 0.15)
            self.assertEqual(originales[c]['prob_acceso_backbone'], 0.8)
            self.assertEqual(originales[c]['prob_segundo_hub'], 0.25)


if __name__ == '__main__':
    unittest.main()
