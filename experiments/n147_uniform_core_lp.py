#!/usr/bin/env python3
"""One-minute fixed-separator LP screen of the canonical n147 diamond.

All 147 centers are independent; only the 64 prescribed core angles change.
One separating branch for every pair is selected from exact source decimal
coordinates at 80 digits and frozen. Results concern this finite branch/trust
model, not unrestricted square packing. Dominated LP poses are unvalidated.
"""
from __future__ import annotations

import time
STARTED = time.monotonic()
import argparse
import csv
import hashlib
import json
import math
import multiprocessing as mp
import os
from pathlib import Path
import shutil
import signal
import sys
import warnings

for variable in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[variable] = '1'

import mpmath
import numpy as np
import scipy
from scipy.optimize import linprog
from scipy.sparse import coo_matrix

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'experiments'), str(ROOT/'scripts')]
from compose_gadgets import normalize, side, legalize
from fq_capacity_probe import full_certificate, geometry_sha, atomic_json, digest
from period5_branch_lp import data


def choose_branches(decimal_rows):
    """Keep the original owner/edge/sign, not a world-space fixed normal."""
    with mpmath.workdps(80):
        xy = [(mpmath.mpf(r['x']), mpmath.mpf(r['y'])) for r in decimal_rows]
        angles = [mpmath.mpf(r['angle']) for r in decimal_rows]
        trig = {a: (mpmath.cos(a), mpmath.sin(a)) for a in set(angles)}
        radii = {(a,b): (1+abs(mpmath.cos(a-b))+abs(mpmath.sin(a-b)))/2
                 for a in set(angles) for b in set(angles)}
        pairs, branches, signs, gaps = [], [], [], []
        for i in range(len(xy)):
            for j in range(i+1, len(xy)):
                dx, dy = xy[j][0]-xy[i][0], xy[j][1]-xy[i][1]
                projections = []
                for k in (i,j):
                    c,s = trig[angles[k]]
                    projections.extend((dx*c+dy*s, -dx*s+dy*c))
                k = max(range(4), key=lambda a: abs(projections[a]))
                gap = abs(projections[k])-radii[angles[i],angles[j]]
                if gap < 0:
                    raise ValueError(f'Original exact decimal pair has no valid branch: {i},{j}')
                pairs.append((i,j)); branches.append(k)
                signs.append(1 if projections[k] >= 0 else -1)
                gaps.append(gap)
        evidence = {'precision_decimal_digits':80,
                    'minimum_selected_gap':str(min(gaps)),
                    'all_original_selected_gaps_nonnegative':True,
                    'pair_count':len(pairs)}
    return np.asarray(pairs),np.asarray(branches),np.asarray(signs),evidence


def solve(original, core, pairs, branches, signs, degrees, dilation, deadline):
    n = len(original)
    warm = original.copy(); warm[:,:2] *= dilation
    angles = original[:,2].copy(); angles[core] += math.radians(degrees)
    prescribed = np.column_stack((warm[:,:2],angles))
    ux,uy,_,_,radii = data(prescribed,pairs)
    k = np.arange(len(pairs)); vx = signs*ux[k,branches]; vy = signs*uy[k,branches]
    i,j = pairs.T
    rows = np.repeat(k,4).tolist()
    cols = np.column_stack((2*i,2*i+1,2*j,2*j+1)).ravel().tolist()
    values = np.column_stack((vx,vy,-vx,-vy)).ravel().tolist()
    rhs = (-radii).tolist()
    extent = .5*(abs(np.cos(angles))+abs(np.sin(angles)))
    for square in range(n):
        for dim in (0,1):
            r = len(rhs); rows.append(r); cols.append(2*square+dim)
            values.append(-1.); rhs.append(-extent[square])
            r = len(rhs); rows.extend((r,r)); cols.extend((2*square+dim,2*n))
            values.extend((1.,-1.)); rhs.append(-extent[square])
    A = coo_matrix((values,(rows,cols)),shape=(len(rhs),2*n+1)).tocsr()
    rhs = np.asarray(rhs)
    objective = np.r_[np.zeros(2*n),1.]
    bounds = [(v-.5,v+.5) for v in warm[:,:2].ravel()]+[(math.sqrt(n),None)]
    begin = time.monotonic()
    with warnings.catch_warnings():
        warnings.filterwarnings('ignore',message='Unrecognized options detected')
        fit = linprog(objective,A_ub=A,b_ub=rhs,bounds=bounds,method='highs',
                      options={'threads':1,'time_limit':min(3.,max(.01,deadline-begin)),
                               'primal_feasibility_tolerance':1e-9,
                               'dual_feasibility_tolerance':1e-9})
    info = {'degrees':degrees,'center_dilation':dilation,'status':int(fit.status),
            'message':fit.message,'success':bool(fit.success),
            'elapsed_seconds':time.monotonic()-begin,'iterations':int(fit.nit)}
    if not fit.success:
        return None,info
    q = np.column_stack((fit.x[:-1].reshape(n,2),angles))
    _,_,_,gaps,_ = data(q,pairs)
    info.update(lp_box_side=float(fit.x[-1]),physical_side=side(q),
                maximum_constraint_violation=float(np.max(A@fit.x-rhs)),
                minimum_all_pair_sat_gap=float(gaps.max(axis=1).min()),
                maximum_center_coordinate_motion=float(abs(q[:,:2]-warm[:,:2]).max()),
                geometry_sha256=geometry_sha(q),status_label='exploratory_unvalidated')
    return q,info


def worker(args):
    os.setsid()
    deadline = STARTED+57.
    out = args.out
    pointer = json.loads(args.pointer.read_text())
    raw = Path(pointer['raw']['path']); report_path = Path(pointer['raw']['official_report'])
    if digest(raw)!=pointer['raw']['sha256'] or digest(report_path)!=pointer['raw']['official_report_sha256']:
        raise ValueError('Canonical input identity mismatch')
    report = json.loads(report_path.read_text())
    if not report['valid'] or report['sha256']!=digest(raw):
        raise ValueError('Canonical official report is not bound to input')
    base = next(r for r in report['results'] if r['n']==147)
    canonical_side = float(base['side'])
    with raw.open() as handle:
        decimal_rows = [r for r in csv.DictReader(handle) if r['n']=='147']
    decimal_rows.sort(key=lambda r:int(r['square_id']))
    if [int(r['square_id'])for r in decimal_rows]!=list(range(147)):
        raise ValueError('n147 identity/count mismatch')
    original = np.array([[float(r[k])for k in ('x','y','angle')]for r in decimal_rows])
    core = np.flatnonzero(abs(original[:,2])>.01)
    outer = np.setdiff1d(np.arange(147),core)
    if len(core)!=64 or len(outer)!=83 or np.any(original[outer,2]!=0.) or not np.allclose(original[core,2],np.pi/4,atol=1e-15,rtol=0):
        raise ValueError('Expected exact 64-square diamond plus 83 upright squares')
    atomic_json(out/'original-rows.json',decimal_rows)
    sources = out/'source'; sources.mkdir()
    source_hashes = {}
    for path in (Path(__file__),ROOT/'experiments/period5_branch_lp.py',ROOT/'experiments/compose_gadgets.py',
                 ROOT/'experiments/fq_capacity_probe.py',ROOT/'experiments/fq_active_pilot.py',
                 ROOT/'scripts/score_official.py',ROOT/'scripts/validate_submission.py',ROOT/'research/official_metric_v17.py'):
        target = sources/path.name; shutil.copyfile(path,target); source_hashes[str(path.relative_to(ROOT))]=digest(target)
    pairs,branches,signs,branch_evidence = choose_branches(decimal_rows)
    normalized = normalize(original)
    np.savez_compressed(out/'inputs-and-branches.npz',original=original,normalized=normalized,
                        core=core,outer=outer,pairs=pairs,branches=branches,signs=signs)
    manifest = {'kind':'n147_uniform_core_angle_fixed_separator_lp','raw_path':str(raw),
                'raw_sha256':digest(raw),'raw_official_report_sha256':digest(report_path),
                'canonical_side_decimal':base['side'],'source_hashes':source_hashes,
                'inputs_sha256':digest(out/'inputs-and-branches.npz'),
                'decimal_rows_sha256':digest(out/'original-rows.json'),
                'original_geometry_sha256':geometry_sha(original),'branch_selection':branch_evidence,
                'independent_center_variables':294,'trust_per_center_coordinate':.5,
                'core_count':64,'upright_count':83,'threads':1,'outer_seconds':60,
                'linprog_seconds_per_call':3,'scipy_version':scipy.__version__,
                'numpy_version':np.__version__,'mpmath_version':mpmath.__version__,
                'scope':'One frozen branch per pair and bounded centers; no unrestricted optimality claim.',
                'variant_degrees':[-.25,.25,-.5,.5,-1.,1.,-2.,2.,-4.,4.]}
    atomic_json(out/'manifest.json',manifest)
    specs = [('control_original',0.,1.),('control_dilated',0.,1.01)]
    specs += [(f'offset_{d:+g}',d,1.)for d in manifest['variant_degrees']]
    records,raw_poses,certified = [],{},{}
    for label,degrees,dilation in specs:
        if deadline-time.monotonic()<3:
            break
        q,record = solve(normalized,core,pairs,branches,signs,degrees,dilation,deadline)
        record['label']=label
        if q is not None:
            raw_poses[label]=q
            record['raw_side_minus_canonical']=record['physical_side']-canonical_side
            control = label.startswith('control_')
            if control and abs(record['lp_box_side']-canonical_side)>1e-7:
                raise ValueError('Positive LP control did not recover canonical side')
            if control or record['physical_side'] < canonical_side-5e-9:
                fixed=legalize(q)
                if fixed is None:
                    raise ValueError('LP output required more than rounding repair')
                certificate=full_certificate(fixed)
                record['certification']=certificate
                record['certified_geometry_sha256']=geometry_sha(fixed)
                record['certified_physical_side']=side(fixed)
                record['true_improvement']=bool(certificate['valid'] and
                    float(certificate['ordinary_pandas_official_side'])<canonical_side-1e-10 and side(fixed)<canonical_side-1e-10)
                if not certificate['valid']:
                    raise ValueError('LP control/improvement failed full official/independent gates')
                if control and abs(side(fixed)-canonical_side)>1e-7:
                    raise ValueError('Legalized control did not recover canonical side')
                certified[label]=fixed
                record['status_label']='fully_certified_control' if control else 'fully_certified_candidate'
        elif label.startswith('control_'):
            raise ValueError('Positive LP control did not solve')
        records.append(record)
        np.savez_compressed(out/'raw-lp-poses.npz',**raw_poses)
        np.savez_compressed(out/'certified-poses.npz',**certified)
        atomic_json(out/'results.json',records)
    summary={'complete':len(records)==len(specs),'requested_trials':len(specs),'completed_trials':len(records),
             'optimal_lp_count':sum(r['success']for r in records),
             'fully_certified_count':len(certified),'true_improvements':sum(r.get('true_improvement',False)for r in records),
             'elapsed_seconds':time.monotonic()-STARTED,'results_sha256':digest(out/'results.json'),
             'raw_lp_sha256':digest(out/'raw-lp-poses.npz'),'certified_sha256':digest(out/'certified-poses.npz'),
             'claim':'Finite prescribed-angle, fixed-separator, trust-bounded LP screen only.'}
    atomic_json(out/'summary.json',summary)
    print(json.dumps(summary),flush=True)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--pointer',type=Path,default=ROOT/'artifacts/current-best-portfolio.json')
    args=parser.parse_args();args.out.mkdir(parents=True,exist_ok=False)
    process=mp.get_context('fork').Process(target=worker,args=(args,));process.start()
    process.join(max(0.,59.-(time.monotonic()-STARTED)))
    killed=process.is_alive()
    if killed:
        try:os.killpg(process.pid,signal.SIGKILL)
        except ProcessLookupError:pass
        process.join(timeout=max(0.,60.-(time.monotonic()-STARTED)))
    atomic_json(args.out/'supervisor.json',{'exitcode':process.exitcode,'forced_kill':killed,
                'elapsed_seconds':time.monotonic()-STARTED,'outer_seconds':60,'workers':1})
    if killed or process.exitcode!=0:raise SystemExit(1)


if __name__=='__main__':main()
