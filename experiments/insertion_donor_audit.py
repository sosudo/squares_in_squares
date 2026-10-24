#!/usr/bin/env python3
"""Compare frozen insertion donors with a current portfolio and same-box banks.

Capacity dominance concerns only count and bounding excess. It deliberately
does not discard a pose: different separator profiles can still compose better.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import time

for variable in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[variable] = '1'

import numpy as np
from compose_gadgets import extents, legalize, read_baseline, side
from cpu_recipe_replay import public_functions
from extract_broad_active_frontier import orient, geometry_sha
from fq_capacity_probe import full_certificate

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def entries(path):
    result = []
    with np.load(path, allow_pickle=False) as archive:
        for key in archive.files:
            w, h, d = map(int, key.split('__')[0].split('_'))
            p = np.asarray(archive[key], dtype=float)
            assert p.shape == (w*h+d, 3) and np.isfinite(p).all()
            q = orient(p, w > h, 1, 1)
            w, h = min(w, h), max(w, h)
            lo, hi = extents(q)
            f = float(max(hi.max(0)-lo.min(0)-[w, h]))
            result.append(dict(w=w, h=h, d=d, excess=f, pose=q,
                               archive=str(path), key=key,
                               geometry_sha256=geometry_sha(q)))
    return result


def metadata(entry):
    return {k: v for k, v in entry.items() if k != 'pose'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--donors', type=Path, required=True)
    parser.add_argument('--bank', action='append', type=Path, required=True)
    parser.add_argument('--portfolio', type=Path, required=True)
    parser.add_argument('--portfolio-report', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    start = time.monotonic()
    args.out.mkdir(parents=True, exist_ok=False)
    report = json.loads(args.portfolio_report.read_text())
    assert report['valid'] and report['sha256'] == digest(args.portfolio)
    base = read_baseline(args.portfolio)
    best_side = {n: side(p) for n, p in base.items()}
    donors = entries(args.donors)
    references = [entry for bank in args.bank for entry in entries(bank)]
    stitch, _ = public_functions(ROOT/'vendor/lightning_ftmc')
    candidates, audits = {}, []
    containers = 0
    for donor in donors:
        w, h, d = donor['w'], donor['h'], donor['d']
        matched = [r for r in references if (r['w'], r['h'], r['d']) == (w, h, d)]
        dominators = [r for r in references if (r['w'], r['h']) == (w, h)
                      and r['d'] >= d and r['excess'] <= donor['excess'] + 1e-10]
        audit = metadata(donor)
        audit['matching_type_best_excess'] = min((r['excess'] for r in matched), default=None)
        audit['same_box_capacity_dominators'] = [metadata(r) for r in dominators]
        audit['standalone_screen'] = []
        # Public filler pads one rectangular motif to k by k, retaining surplus d.
        f = math.ceil((donor['excess']+3e-8)*1e9)*1e-9
        for k in range(h, 32):
            n = k*k+d
            if n > 1000:
                continue
            containers += 1
            gain = (best_side[n]-(k+f))/math.sqrt(n)
            entry = dict(k=k, n=n, predicted_side=k+f, incumbent_side=best_side[n],
                         screened_score_gain=gain)
            audit['standalone_screen'].append(entry)
            if gain <= 1e-9:
                continue
            gadgets = [dict(w=w, h=h, dm=d, f=f, donor=0)]
            q, _ = stitch([(0, 3)], gadgets, [(donor['pose'], 'insertion')], box=(k, k))
            assert len(q) == n
            q = legalize(q)
            if q is None or side(q) >= best_side[n]-1e-9:
                entry['status'] = 'no_valid_side_gain'
                continue
            certificate = full_certificate(q)
            entry['certificate'] = certificate
            if not certificate['valid']:
                entry['status'] = 'certificate_failed'
                continue
            length = certificate['independent_raw']['side_upper']
            entry['status'] = 'certified_improvement'
            entry['certified_score_gain'] = (side(base[n])-float(length))/math.sqrt(n)
            candidates[str(n)] = dict(side=length, squares=[[f'{v:.17g}' for v in row] for row in q],
                source='Standalone square padding of a certified insertion donor',
                provenance=dict(donor=metadata(donor), k=k, certificate=certificate))
            best_side[n] = float(length)
        audits.append(audit)
    result = dict(elapsed_seconds=time.monotonic()-start, donors=len(donors), containers_screened=containers,
        same_box_capacity_dominated=sum(bool(a['same_box_capacity_dominators']) for a in audits),
        matching_type_improved=sum(a['matching_type_best_excess'] is not None and
            a['matching_type_best_excess']-a['excess'] > 1e-7 for a in audits),
        standalone_certified_improvements=len(candidates), audits=audits,
        inputs={str(p):digest(p) for p in [args.donors, *args.bank, args.portfolio, args.portfolio_report]},
        source_sha256=digest(__file__), command=[sys.executable, str(Path(__file__).resolve()), *sys.argv[1:]],
        interpretation='Same-box count/excess dominance does not imply separator-profile dominance; all donors retained.',
        no_submission=True)
    (args.out/'audit.json').write_text(json.dumps(result, indent=2)+'\n')
    (args.out/'candidates.json').write_text(json.dumps(candidates, indent=2)+'\n')
    (args.out/'source.py').write_text(Path(__file__).read_text())
    print(json.dumps({k:v for k,v in result.items() if k not in ('audits','inputs','command')}))


if __name__ == '__main__':
    main()
