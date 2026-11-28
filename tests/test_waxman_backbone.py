import unittest
import _rutas

import networkx as nx

from generador_waxman import generar_instancia
from analisis_red import analizar_estructura_extendida


class BackboneTest(unittest.TestCase):
    def generar(self, **cambios):
        parametros = dict(nodos=40, productos=120, arcos_objetivo=160,
                          alpha=0.7, beta=1, semilla=42,
                          porcentaje_hubs=0.1, conexiones_por_hub=2,
                          prob_acceso_backbone=0.8, prob_segundo_hub=0.25,
                          secuencias_independientes=True,
                          multiplicador_capacidad_hubs=1)
        parametros.update(cambios)
        return generar_instancia(**parametros)

    def test_presupuesto_conectividad_y_accesos(self):
        g, arcos, ds = self.generar(prob_acceso_backbone=1, prob_segundo_hub=1)
        self.assertEqual(len(arcos), 160)
        self.assertEqual(g.number_of_edges(), 80)
        self.assertTrue(nx.is_connected(g))
        hubs = {u for u in g if g.nodes[u]['es_hub']}
        for u in set(g) - hubs:
            obligatorios = [v for v in g[u] if g.edges[u, v]['acceso_obligatorio']]
            self.assertEqual(len(obligatorios), 2)
            self.assertTrue(set(obligatorios) <= hubs)
        d = analizar_estructura_extendida(g, arcos, ds)
        self.assertEqual(d['normales_doble_acceso_obligatorio'], 36)
        self.assertEqual(d['cobertura_backbone_pct'], 100)

    def test_cero_acceso_no_impone_enlaces(self):
        g, _, _ = self.generar(prob_acceso_backbone=0, prob_segundo_hub=1)
        self.assertFalse(any(d['acceso_obligatorio'] for _, _, d in g.edges(data=True)))

    def test_capacidad_reforzada_sin_cambiar_topologia_o_demanda(self):
        g1, a1, d1 = self.generar()
        g2, a2, d2 = self.generar(multiplicador_capacidad_hubs=10)
        self.assertEqual(set(g1.edges), set(g2.edges))
        self.assertEqual(d1, d2)
        for a, b in zip(a1, a2):
            factor = 10 if g1.edges[a['origen'], a['destino']]['es_backbone'] else 1
            self.assertEqual(b['capacidad'], factor * a['capacidad'])

    def test_posiciones_demanda_y_capacidades_compartidas(self):
        g1, a1, d1 = self.generar(porcentaje_hubs=0, prob_acceso_backbone=0,
                                  prob_segundo_hub=0, alpha=0.3)
        g2, a2, d2 = self.generar(alpha=0.8)
        self.assertEqual(nx.get_node_attributes(g1, 'pos'), nx.get_node_attributes(g2, 'pos'))
        self.assertEqual(d1, d2)
        caps = {(a['origen'], a['destino']): a['capacidad'] for a in a1}
        for a in a2:
            key = a['origen'], a['destino']
            if key in caps:
                self.assertEqual(caps[key], a['capacidad'])

    def test_reproducibilidad(self):
        g1, a1, d1 = self.generar()
        g2, a2, d2 = self.generar()
        self.assertEqual(a1, a2)
        self.assertEqual(d1, d2)
        self.assertEqual(list(g1.edges(data=True)), list(g2.edges(data=True)))

    def test_presupuesto_insuficiente_y_parametros_invalidos(self):
        for cambios in [dict(arcos_objetivo=78, prob_acceso_backbone=1, prob_segundo_hub=1),
                        dict(prob_acceso_backbone=-0.1), dict(prob_segundo_hub=1.1),
                        dict(porcentaje_hubs=0)]:
            with self.subTest(cambios=cambios), self.assertRaises(ValueError):
                self.generar(**cambios)

    def test_cota_puente_demanda_dirigida(self):
        g = nx.Graph([(1, 2), (2, 3), (3, 1), (3, 4)])
        arcos = [dict(origen=u, destino=v, capacidad=5)
                 for a, b in g.edges for u, v in [(a, b), (b, a)]]
        ds = [dict(origen=1, destino=4, demanda=10),
              dict(origen=2, destino=4, demanda=5),
              dict(origen=4, destino=1, demanda=20)]
        d = analizar_estructura_extendida(g, arcos, ds)
        self.assertEqual(d['puentes'], 1)
        self.assertEqual(d['cota_puentes'], 4)
        self.assertEqual(d['puente_critico'], [4, 3])


if __name__ == '__main__':
    unittest.main()
