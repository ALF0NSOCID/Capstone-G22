#!/usr/bin/env python3
"""
Solución de referencia de la instancia (NO es el solver del proyecto): LP de congestión mínima
con agregación por origen, resuelta con HiGHS vía scipy.

  min z
  s.a.  sum_{a in out(v)} x_{s,a} - sum_{a in in(v)} x_{s,a} = b_{s,v}   para todo origen s, nodo v
        sum_s x_{s,a} <= z * c_a                                           para todo arco a
        x >= 0

Agregar los productos que comparten origen es exacto para este problema (no hay restricciones por
producto), así que el z* que entrega debe coincidir con el de generación de columnas.

Uso:  python3 resolver_referencia.py instancia.txt  [--sin-arcos id1,id2 ...]
Imprime z* y los 10 arcos más cargados.
"""
import sys
import numpy as np
import scipy.sparse as sp
from scipy.optimize import linprog


def leer(path):
    with open(path) as fh:
        n, m, K = map(int, fh.readline().split())
        arcs = []
        for _ in range(m):
            o, d, _, c, _ = fh.readline().split()
            arcs.append((int(o), int(d), float(c)))
        prods = []
        for _ in range(K):
            k1, o, v = fh.readline().split()
            k2, d, w = fh.readline().split()
            prods.append((int(o), int(d), float(v)))
    return n, arcs, prods


def resolver(n, arcs, prods, quitar=frozenset()):
    arcs = [a for i, a in enumerate(arcs) if i not in quitar]
    m = len(arcs)
    srcs = sorted({o for o, _, _ in prods})
    S = len(srcs)
    sidx = {s: i for i, s in enumerate(srcs)}
    b = np.zeros((S, n + 1))
    for o, d, v in prods:
        b[sidx[o], o] += v
        b[sidx[o], d] -= v
    # variables: x[s, a] (S*m) y z (última)
    nv = S * m + 1
    rows, cols, vals = [], [], []
    beq = []
    r = 0
    for s in range(S):
        for v in range(1, n + 1):
            beq.append(b[s, v])
        base = s * m
        for a, (o, d, c) in enumerate(arcs):
            rows += [r + o - 1, r + d - 1]
            cols += [base + a, base + a]
            vals += [1.0, -1.0]
        r += n
    Aeq = sp.csr_matrix((vals, (rows, cols)), shape=(S * n, nv))
    rows, cols, vals = [], [], []
    for a, (o, d, c) in enumerate(arcs):
        for s in range(S):
            rows.append(a); cols.append(s * m + a); vals.append(1.0)
        rows.append(a); cols.append(nv - 1); vals.append(-c)
    Aub = sp.csr_matrix((vals, (rows, cols)), shape=(m, nv))
    cost = np.zeros(nv); cost[-1] = 1.0
    res = linprog(cost, A_ub=Aub, b_ub=np.zeros(m), A_eq=Aeq, b_eq=np.array(beq),
                  bounds=(0, None), method='highs')
    if res.status != 0:
        return None, None, arcs
    x = res.x[:-1].reshape(S, m).sum(axis=0)
    util = x / np.array([c for _, _, c in arcs])
    return res.x[-1], util, arcs


if __name__ == '__main__':
    n, arcs, prods = leer(sys.argv[1])
    z, util, arcs2 = resolver(n, arcs, prods)
    print(f'z* = {z:.6f}')
    for a in np.argsort(-util)[:10]:
        o, d, c = arcs2[a]
        print(f'  arco {o}->{d}  cap {c:g}  utilizacion {util[a]:.4f}')
