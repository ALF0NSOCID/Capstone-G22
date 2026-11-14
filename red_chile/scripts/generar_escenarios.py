#!/usr/bin/env python3
"""
Escenarios de demanda a partir de demandas_base.csv.

  python3 generar_escenarios.py                       # genera los escenarios estándar
  python3 generar_escenarios.py --hotspot Biobío 2.0  # agrega un hotspot (+200 % = factor 3) hacia otra región

Escenarios estándar:
  base, uniforme_+25, uniforme_+50, uniforme_+100,
  hotspot_antofagasta_+200: +200 % (×3) en todos los productos cuyo DESTINO está en la Región de Antofagasta.
  hotspot_aysen_+200:       ídem para la Región de Aysén (depende solo de la FOA).

Nota: en congestión mínima un crecimiento uniforme multiplica z* por el mismo factor (el ruteo óptimo no cambia).
Los escenarios uniformes sirven como prueba de consistencia del solver; el hotspot sí cambia la estructura.
"""
import os, sys
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ESC = os.path.join(ROOT, 'escenarios')


def write_instance(path, nodos, enl, dem):
    base = enl[enl.capa != 'CANDIDATO']
    arcs = []
    for r in base.itertuples():
        arcs += [(r.origen, r.destino, r.capacidad_gbps_por_sentido), (r.destino, r.origen, r.capacidad_gbps_por_sentido)]
    with open(path, 'w') as fh:
        fh.write(f'{len(nodos)} {len(arcs)} {len(dem)}\n')
        for o, d, c in arcs:
            fh.write(f'{o} {d} 1 {c:g} 0\n')
        for k, r in enumerate(dem.itertuples(), start=1):
            fh.write(f'{k} {r.origen} {r.demanda:.6f}\n{k} {r.destino} {-r.demanda:.6f}\n')


def main(extra=None):
    os.makedirs(ESC, exist_ok=True)
    nodos = pd.read_csv(os.path.join(ROOT, 'nodos.csv'), dtype={'cut': str})
    enl = pd.read_csv(os.path.join(ROOT, 'enlaces.csv'))
    dem = pd.read_csv(os.path.join(ROOT, 'demandas_base.csv'))
    reg = dict(zip(nodos.id, nodos.region))
    escenarios = {'base': lambda d: d.demanda,
                  'uniforme_+25': lambda d: d.demanda * 1.25,
                  'uniforme_+50': lambda d: d.demanda * 1.50,
                  'uniforme_+100': lambda d: d.demanda * 2.00,
                  'hotspot_antofagasta_+200': lambda d: d.demanda * d.destino.map(lambda v: 3.0 if reg[v] == 'Antofagasta' else 1.0),
                  'hotspot_aysen_+200': lambda d: d.demanda * d.destino.map(lambda v: 3.0 if reg[v] == 'Aysén' else 1.0)}
    if extra:
        region, g = extra
        escenarios[f'hotspot_{region.lower()}_+{int(round(g * 100))}'] = \
            lambda d: d.demanda * d.destino.map(lambda v: 1 + g if reg[v] == region else 1.0)
    resumen = []
    for name, fn in escenarios.items():
        d = dem.copy()
        d['demanda'] = fn(d).round(6)
        d[['id_producto', 'origen', 'destino', 'demanda']].to_csv(os.path.join(ESC, f'demandas_{name}.csv'), index=False)
        write_instance(os.path.join(ESC, f'instancia_{name}.txt'), nodos, enl, d)
        resumen.append((name, len(d), round(d.demanda.sum(), 2)))
    pd.DataFrame(resumen, columns=['escenario', 'productos', 'demanda_total_gbps']).to_csv(os.path.join(ESC, 'resumen_escenarios.csv'), index=False)
    for r in resumen:
        print(*r)


if __name__ == '__main__':
    extra = None
    if '--hotspot' in sys.argv:
        i = sys.argv.index('--hotspot')
        extra = (sys.argv[i + 1], float(sys.argv[i + 2]))
    main(extra)
