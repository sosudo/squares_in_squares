"""Import stronger public exact square-packing witnesses with their provenance.

This script does not download code, submit to Kaggle, or alter the baseline. It
reads a separately inspected checkout of franciscouzo/square-packing and calls
its documented high-precision catalogue reader. Coordinates are rendered as
75-digit decimal strings after tiny centre dilation; preserve these strings
when merging into a submission. The official metric must validate the result.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib
import json
import math
from pathlib import Path
import subprocess
import sys

import mpmath as mp
import numpy as np
from scipy.spatial import cKDTree

sys.set_int_max_str_digits(0)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def baseline_sides(path: Path) -> dict[int, float]:
    bounds = {}
    with path.open() as f:
        for row in csv.DictReader(f):
            n = int(row['n'])
            x, y, a = map(float, (row['x'], row['y'], row['angle']))
            h = (abs(math.cos(a)) + abs(math.sin(a))) / 2
            box = (x-h, y-h, x+h, y+h)
            if n not in bounds:
                bounds[n] = list(box)
            else:
                b = bounds[n]
                b[0], b[1] = min(b[0],box[0]), min(b[1],box[1])
                b[2], b[3] = max(b[2],box[2]), max(b[3],box[3])
    return {n:max(b[2]-b[0],b[3]-b[1]) for n,b in bounds.items()}


def measure(rows):
    xmin = ymin = mp.inf
    xmax = ymax = -mp.inf
    for x,y,a in rows:
        h = (abs(mp.cos(a))+abs(mp.sin(a)))/2
        xmin, ymin = min(xmin,x-h), min(ymin,y-h)
        xmax, ymax = max(xmax,x+h), max(ymax,y+h)
    return max(xmax-xmin,ymax-ymin)


def float_sanity(rows, tolerance=2e-12):
    """Catch material overlap; high precision official certification follows."""
    q = np.asarray([[float(v) for v in row] for row in rows])
    pairs = cKDTree(q[:,:2]).query_pairs(math.sqrt(2)+1e-10, output_type='ndarray')
    if not len(pairs):
        return math.inf
    i,j = pairs.T
    c,s = np.cos(q[:,2]),np.sin(q[:,2])
    u,v = np.stack((c,s),axis=-1),np.stack((-s,c),axis=-1)
    axes = np.stack((u[i],v[i],u[j],v[j]),axis=1)
    d = q[j,:2]-q[i,:2]
    projection = np.abs(np.einsum('pi,pai->pa',d,axes))
    da = q[i,2]-q[j,2]
    radii = .5*(1+np.abs(np.cos(da))+np.abs(np.sin(da)))
    gap = float(np.min(np.max(projection-radii[:,None],axis=1)))
    if gap < -tolerance:
        raise ValueError(f'Material overlap: minimum SAT separation {gap}')
    return gap


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--catalogue',type=Path,default=Path('/tmp/squares-research/couzo'))
    ap.add_argument('--baseline',type=Path,default=Path('artifacts/baseline.csv'))
    ap.add_argument('--output',type=Path,default=Path('artifacts/candidates/records.json'))
    ap.add_argument('--min-score-gain',type=float,default=1e-9)
    ap.add_argument('--cases',type=int,nargs='*')
    args = ap.parse_args()
    root = args.catalogue.resolve()
    sys.path.insert(0,str(root))
    exporter = importlib.import_module('prepare_kaggle')
    catalogue = exporter.Packings(root)
    baseline = baseline_sides(args.baseline)
    commit = subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
    provenance = {'repository':'https://github.com/franciscouzo/square-packing',
                  'commit':commit,'upper_bounds_sha256':sha256(root/'upper_bounds.json'),
                  'baseline_sha256':sha256(args.baseline)}
    chosen = args.cases or sorted(baseline)
    result = {}
    gain = 0.
    with mp.workdps(100):
        dilation = 1+mp.mpf('1e-40')
        for n in chosen:
            expected = exporter.exact_value(catalogue.upper[str(n)]['verified'])
            approx = float(expected.p)+float(expected.q)*math.sqrt(2)
            if (baseline[n]-approx)/math.sqrt(n) <= args.min_score_gain:
                continue
            rows,info = catalogue.rows(n)
            if len(rows) != n:
                raise ValueError(f'n={n}: expected {n} squares, got {len(rows)}')
            rows = [(x*dilation,y*dilation,a) for x,y,a in rows]
            side = measure(rows)
            score_gain = (baseline[n]-float(side))/math.sqrt(n)
            if score_gain <= args.min_score_gain:
                continue
            gap = float_sanity(rows)
            render = lambda x:mp.nstr(x,75,strip_zeros=False)
            result[str(n)] = {'side':render(side),
                              'squares':[[render(v) for v in row] for row in rows],
                              'source':f"public exact catalogue {commit[:12]}",
                              'provenance':{**provenance,**info},
                              'estimated_score_gain':score_gain,
                              'float_minimum_sat_gap':gap,
                              'centre_dilation':'1+1e-40',
                              'validation':'float sanity passed; official interval certification required'}
            gain += score_gain
            if len(result)%20 == 0:
                print(f'Imported {len(result)} improved cases; estimated gain {gain:.12f}',flush=True)
                args.output.parent.mkdir(parents=True,exist_ok=True)
                args.output.write_text(json.dumps(result))
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result))
    summary = {'count':len(result),'estimated_score_gain':gain,'provenance':provenance,
               'cases':[{k:v for k,v in {'n':int(n),'side':r['side'],'estimated_score_gain':r['estimated_score_gain']}.items()}
                        for n,r in sorted(result.items(),key=lambda item:-item[1]['estimated_score_gain'])]}
    args.output.with_suffix('.summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps({'output':str(args.output),'count':len(result),'estimated_score_gain':gain}))


if __name__ == '__main__':
    main()
