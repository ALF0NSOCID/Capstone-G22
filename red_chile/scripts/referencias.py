#!/usr/bin/env python3
"""z* de referencia (LP agregado por origen) para escenarios, fallas y candidatos. Escribe datos_crudos/_zref.json
y agrega a fallas.csv la columna z_ref_demanda_restante. Solo para contrastar con el solver del proyecto."""
import json, os, sys
import numpy as np, pandas as pd, networkx as nx
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from resolver_referencia import leer, resolver
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

nodos = pd.read_csv(os.path.join(ROOT, 'nodos.csv'), dtype={'cut': str}); nm = dict(zip(nodos.id, nodos.nombre))
enl = pd.read_csv(os.path.join(ROOT, 'enlaces.csv'))
base = enl[enl.capa != 'CANDIDATO']
N, arcs, prods = leer(os.path.join(ROOT, 'instancia_base.txt'))

def top(z, u, a2):
    i = int(np.argmax(u)); o, d, c = a2[i]
    return f'{nm[o]} → {nm[d]} ({c:g} Gbps)'

out = []
for esc in ['base', 'uniforme_+25', 'uniforme_+50', 'uniforme_+100', 'hotspot_antofagasta_+200', 'hotspot_aysen_+200']:
    n_, a_, p_ = leer(os.path.join(ROOT, 'escenarios', f'instancia_{esc}.txt'))
    z, u, a2 = resolver(n_, a_, p_)
    out.append(dict(caso=f'escenario {esc}', z_ref=round(z, 4), arco_critico=top(z, u, a2)))

# con candidatos
def arcs_for(df):
    a = []
    for r in df.itertuples():
        a += [(r.origen, r.destino, float(r.capacidad_gbps_por_sentido)), (r.destino, r.origen, float(r.capacidad_gbps_por_sentido))]
    return a
z0, u0, a0 = resolver(N, arcs_for(base), prods)
zall, uall, aall = resolver(N, arcs_for(enl), prods)
out.append(dict(caso='base + los 20 candidatos', z_ref=round(zall, 4), arco_critico=top(zall, uall, aall)))
cand_rows = []
for r in enl[enl.capa == 'CANDIDATO'].itertuples():
    z, u, a2 = resolver(N, arcs_for(pd.concat([base, enl[enl.id == r.id]])), prods)
    cand_rows.append(dict(id_enlace=r.id, candidato=f'{r.origen_nombre} – {r.destino_nombre}', km=round(r.km, 1), z_ref_base_mas_candidato=round(z, 4),
                          mejora_pct=round(100 * (z0 - z) / z0, 2)))
pd.DataFrame(cand_rows).to_csv(os.path.join(ROOT, 'datos_crudos', 'referencia_candidatos.csv'), index=False)

# fallas: z* sobre la demanda que sigue conectada
fl = pd.read_csv(os.path.join(ROOT, 'fallas.csv'))
zs = []
for r in fl.itertuples():
    e = enl[enl.id == r.id_enlace].iloc[0]
    keep = base[base.id != r.id_enlace]
    G = nx.Graph(); G.add_nodes_from(nodos.id); G.add_edges_from(zip(keep.origen, keep.destino))
    comp = {v: i for i, cc in enumerate(nx.connected_components(G)) for v in cc}
    p2 = [(o, d, v) for o, d, v in prods if comp[o] == comp[d]]
    z, u, a2 = resolver(N, arcs_for(keep), p2)
    zs.append(round(z, 4))
fl['z_ref_demanda_restante'] = zs
fl.to_csv(os.path.join(ROOT, 'fallas.csv'), index=False)
out.append(dict(caso=f'fallas evaluadas ({len(fl)})', z_ref=f'{min(zs):.4f} – {max(zs):.4f}', arco_critico='ver fallas.csv'))
json.dump(out, open(os.path.join(ROOT, 'datos_crudos', '_zref.json'), 'w'), ensure_ascii=False, indent=1)
print(pd.DataFrame(out).to_string(index=False))
print(pd.DataFrame(cand_rows).sort_values('mejora_pct', ascending=False).to_string(index=False))
print(fl.sort_values('demanda_desconectada_pct', ascending=False).head(12).to_string(index=False))
