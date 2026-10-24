"""Rigidly rotate packings to minimize their square envelopes.

This preserves the geometry in exact arithmetic. The exported result receives
a small outward margin and must pass the independent interval validator.
"""
import argparse
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.spatial import ConvexHull


def bounds(q):
    h = (np.abs(np.cos(q[:, 2])) + np.abs(np.sin(q[:, 2]))) / 2
    lo = (q[:, :2] - h[:, None]).min(axis=0)
    hi = (q[:, :2] + h[:, None]).max(axis=0)
    return float((hi - lo).max())


def best_rotation(q):
    t = q[:, 2]
    u = np.column_stack((np.cos(t), np.sin(t))) / 2
    v = np.column_stack((-np.sin(t), np.cos(t))) / 2
    corners = np.concatenate([q[:, :2] + a*u + b*v for a,b in [(1,1),(1,-1),(-1,1),(-1,-1)]])
    p = corners[ConvexHull(corners).vertices]
    edges = np.roll(p, -1, axis=0) - p
    events = np.unique(np.r_[0, math.pi/2, (-np.arctan2(edges[:, 1], edges[:, 0])) % (math.pi/2)])
    candidates = list(events)
    for left, right in zip(events[:-1], events[1:]):
        mid = (left + right)/2
        co, si = np.cos(mid), np.sin(mid)
        xx, yy = p[:, 0]*co-p[:, 1]*si, p[:, 0]*si+p[:, 1]*co
        dx = p[xx.argmax()] - p[xx.argmin()]
        dy = p[yy.argmax()] - p[yy.argmin()]
        # width-height = (dx.x-dy.y)*cos(t) + (-dx.y-dy.x)*sin(t)
        a, b = dx[0]-dy[1], -dx[1]-dy[0]
        root = math.atan2(-a, b)
        for k in range(-2, 3):
            angle = root + k*math.pi
            if left < angle < right:
                candidates.append(angle)
    best = (bounds(q), 0.0)
    for angle in candidates:
        co, si = math.cos(angle), math.sin(angle)
        side = max(np.ptp(p[:, 0]*co-p[:, 1]*si), np.ptp(p[:, 0]*si+p[:, 1]*co))
        if side < best[0]:
            best = (float(side), float(angle))
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('input')
    ap.add_argument('output')
    args = ap.parse_args()
    df = pd.read_csv(args.input)
    result = {}
    gain = 0.0
    for n,g in df.groupby('n', sort=True):
        q = g.sort_values('square_id')[['x','y','angle']].to_numpy(float)
        old = bounds(q)
        side, angle = best_rotation(q)
        if side < old - 1e-8:
            co,si = math.cos(angle),math.sin(angle)
            q[:, :2] = q[:, :2] @ np.array([[co,si],[-si,co]])
            q[:, 2] += angle
            q[:, :2] *= 1+1e-10
            new = bounds(q)
            if new < old - 1e-9:
                gain += (old-new)/math.sqrt(n)
                result[str(n)] = {'side':new,'squares':q.tolist(),'source':'rigid-envelope-search'}
                print(f'n={n} {old:.12f} -> {new:.12f}; cumulative gain {gain:.12g}',flush=True)
    Path(args.output).parent.mkdir(parents=True,exist_ok=True)
    Path(args.output).write_text(json.dumps(result))
    print(f'{len(result)} improved envelopes; estimated score gain {gain:.12g}')


if __name__ == '__main__':
    main()
