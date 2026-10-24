"""Independent sequential-LP square packing compaction.

The separating axes are selected from the incumbent. All four vertices of the
other square are constrained against each selected edge, avoiding the derivative
ambiguity at equal angles. Each step is checked with the exact floating-point SAT
formula and legalized by center expansion before acceptance.
"""
from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import time

os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
import numpy as np
from scipy.optimize import linprog
from scipy.sparse import coo_matrix
from scipy.spatial import cKDTree


SIGNS = np.array([[-1, -1], [-1, 1], [1, -1], [1, 1]]) / 2


def vertices(p):
    c, s = np.cos(p[:, 2]), np.sin(p[:, 2])
    v = np.empty((len(p), 4, 2))
    v[:, :, 0] = c[:, None] * SIGNS[:, 0] - s[:, None] * SIGNS[:, 1]
    v[:, :, 1] = s[:, None] * SIGNS[:, 0] + c[:, None] * SIGNS[:, 1]
    return v


def side(p):
    v = vertices(p) + p[:, None, :2]
    return float(np.max(np.max(v, axis=(0, 1)) - np.min(v, axis=(0, 1))))


def normalize(p):
    p = np.array(p, copy=True)
    v = vertices(p) + p[:, None, :2]
    p[:, :2] -= np.min(v, axis=(0, 1))
    return p


def pairdata(p, distance=1.6):
    pairs = cKDTree(p[:, :2]).query_pairs(distance, output_type="ndarray")
    if not len(pairs):
        return pairs, np.empty((0, 4)), np.empty(0), np.empty((0, 4, 2))
    i, j = pairs.T
    c, s = np.cos(p[:, 2]), np.sin(p[:, 2])
    u, v = np.stack([c, s], -1), np.stack([-s, c], -1)
    axes = np.stack([u[i], v[i], u[j], v[j]], axis=1)
    d = p[j, :2] - p[i, :2]
    proj = np.abs(np.einsum("pi,pai->pa", d, axes))
    delta = p[i, 2] - p[j, 2]
    radius = .5 * (1 + np.abs(np.cos(delta)) + np.abs(np.sin(delta)))
    return pairs, proj, radius, axes


def legalize(p, margin=2e-12):
    p = normalize(p)
    pairs, proj, radius, axes = pairdata(p)
    if len(pairs):
        need = np.min((radius[:, None] + margin) / np.maximum(proj, 1e-200), axis=1)
        scale = max(1.0, float(np.max(need)))
        p[:, :2] *= scale
    return normalize(p)


def min_gap(p):
    pairs, proj, radius, axes = pairdata(p)
    return float(np.min(np.max(proj - radius[:, None], axis=1))) if len(pairs) else math.inf


def linear_step(p, trust=.03, angle_trust=.01, rng=None):
    n = len(p)
    v = vertices(p)
    vp = np.stack([-v[:, :, 1], v[:, :, 0]], axis=-1)
    pairs, projections, radius, axes = pairdata(p, math.sqrt(2) + 4 * trust)
    rows, cols, vals, rhs = [], [], [], []

    def row(indices, values, value):
        r = len(rhs)
        rows.extend([r] * len(indices)); cols.extend(indices)
        vals.extend(values); rhs.append(value)

    L = side(p)
    for i in range(n):
        for k in range(4):
            for dim in range(2):
                # -(p_i + rotated vertex) <= 0, upper vertex <= L.
                row([3*i+dim, 3*i+2], [-1, -vp[i,k,dim]], p[i,dim]+v[i,k,dim])
                row([3*i+dim, 3*i+2, 3*n], [1, vp[i,k,dim], -1], L-p[i,dim]-v[i,k,dim])
    selected = np.argmax(projections, axis=1)
    for ij, k, ax in zip(pairs, selected, axes[np.arange(len(pairs)), selected]):
        a, b = (int(ij[0]), int(ij[1])) if k < 2 else (int(ij[1]), int(ij[0]))
        d = p[b,:2]-p[a,:2]
        ax = ax * (1 if d@ax >= 0 else -1)
        ap = np.array([-ax[1],ax[0]])
        for corner in range(4):
            dv = d+v[b,corner]
            gap = dv@ax - .5
            ga, gb = dv@ap, vp[b,corner]@ax
            # Linearized gap >= 1e-12.
            row([3*a,3*a+1,3*b,3*b+1,3*a+2,3*b+2],
                [ax[0],ax[1],-ax[0],-ax[1],-ga,-gb],gap-1e-12)
    A = coo_matrix((vals,(rows,cols)),shape=(len(rhs),3*n+1)).tocsr()
    c = np.zeros(3*n+1); c[-1]=1
    if rng is not None:
        c[:-1] = rng.normal(size=3*n)*1e-7/n
    bounds = [(-trust,trust),(-trust,trust),(-angle_trust,angle_trust)]*n+[(-trust,trust)]
    result = linprog(c, A_ub=A,b_ub=np.array(rhs),bounds=bounds,method="highs", options={"dual_feasibility_tolerance":1e-9,"primal_feasibility_tolerance":1e-9,"threads":1})
    if not result.success:
        return None, result.message
    return result.x[:-1].reshape(n,3), float(result.x[-1])


def compact(p, seconds=60, seed=0):
    p = normalize(p)
    rng = np.random.default_rng(seed)
    original = best = side(p)
    end = time.monotonic()+seconds
    trust, angle_trust = .03, .01
    iterations=0
    while time.monotonic()<end and trust>1e-6:
        step, pred = linear_step(p,trust,angle_trust,rng)
        iterations+=1
        if step is None:
            trust/=3;angle_trust/=3
            continue
        winner=None
        for alpha in (1.,.5,.25,.1):
            q=legalize(p+alpha*step)
            L=side(q)
            if L<best-1e-10 and (winner is None or L<winner[0]):
                winner=L,q
        if winner:
            best,p=winner
            if best<original-1e-6:
                print(f"n={len(p)} iter={iterations} side={best:.12f} gain={original-best:.8g} trust={trust:.3g}",flush=True)
        else:
            trust/=3;angle_trust/=3
    return p,{"original_side":original,"side":best,"iterations":iterations,"min_gap":min_gap(p)}


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--source',default='/tmp/squares-research/shubin/data/kaggle')
    ap.add_argument('--ns',default='29,37,39,41,54,55,68,69,70,71,84,87,88,102,105,106,107,108,110')
    ap.add_argument('--seconds',type=float,default=30)
    ap.add_argument('--seed',type=int,default=0)
    ap.add_argument('--out',default='artifacts/candidates/slp.json')
    a=ap.parse_args(); source=Path(a.source)
    out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True)
    saved=json.loads(out.read_text()) if out.exists() else {}
    ns=sorted(int(x.stem) for x in source.glob('*.bin')) if a.ns=='all' else [int(x) for x in a.ns.split(',')]
    for n in ns:
        p=np.fromfile(source/f'{n}.bin',dtype='<f8').reshape(-1,3)
        q,info=compact(p,a.seconds,a.seed+n)
        print(json.dumps({'n':n,**info}),flush=True)
        if info['side']<info['original_side']-1e-9 and info['min_gap']>0:
            if str(n) not in saved or info['side']<saved[str(n)]['side']:
                saved[str(n)]={'side':info['side'],'squares':q.tolist(),'search':info}
                tmp=out.with_suffix('.tmp'); tmp.write_text(json.dumps(saved));tmp.replace(out)


if __name__=='__main__':
    main()
