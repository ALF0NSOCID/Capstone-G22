"""Contratos de compatibilidad de la reorganización, sin ejecutar baterías."""
import _rutas

import hashlib
import importlib
import json
from pathlib import Path
import unittest

import compatibilidad

RAIZ = Path(__file__).resolve().parents[1]


class OrganizacionTest(unittest.TestCase):
    def test_todas_las_entradas_tienen_implementacion(self):
        mapa = json.loads((RAIZ/'docs/entradas_compatibles.json').read_text())
        for entrada, relativa in mapa.items():
            with self.subTest(entrada=entrada):
                self.assertTrue((RAIZ/relativa).is_file())
                self.assertIn('ejecutar_entrada', (RAIZ/"compat"/entrada).read_text())
                self.assertEqual(compatibilidad.archivo_fuente(RAIZ/"compat"/entrada), RAIZ/relativa)

    def test_solucionadores_y_bibliotecas_no_cambiaron(self):
        mapa = json.loads((RAIZ/'docs/entradas_compatibles.json').read_text())
        hashes = json.loads((RAIZ/'docs/huellas_codigo_actual.json').read_text())
        adaptados = {'experimento_conclusiones.py', 'explorar_waxman.py', 'experimento_waxman.py'}
        for nombre, relativa in mapa.items():
            if nombre not in adaptados:
                with self.subTest(nombre=nombre):
                    self.assertEqual(hashlib.sha256((RAIZ/relativa).read_bytes()).hexdigest(), hashes[nombre])

    def test_importaciones_conservan_identidad_y_rutas_publicas(self):
        for nombre in ['generador_waxman', 'lector_sndlib', 'analisis_red', 'metricas_ejecucion',
                       'experimento_x3', 'experimento_x4', 'experimento_waxman']:
            with self.subTest(nombre=nombre):
                modulo = importlib.import_module(nombre)
                self.assertEqual(modulo.__name__, nombre)
                self.assertEqual(Path(modulo.__file__), RAIZ/(nombre+'.py'))
                self.assertTrue(Path(modulo.__implementation_file__).is_file())

    def test_inspeccion_de_fuente_historica(self):
        modulo = importlib.import_module('experimento_conclusiones')
        parametros = modulo.configuracion_solver()
        self.assertEqual(parametros['eta'], 25)
        self.assertEqual(parametros['limite_tiempo'], 120)


if __name__ == '__main__':
    unittest.main()
