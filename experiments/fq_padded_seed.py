#!/usr/bin/env python3
"""Make a different full-puzzle seed by exact public square-frame padding."""
import argparse
import csv
import json
import math
import os
from pathlib import Path
import shutil
import time

for variable in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[variable] = '1'
import numpy as np
import fq_active_pilot as fq
import fq_full_basin_pilot as basin
from compose_gadgets import normalize, legalize
from cpu_recipe_replay import public_functions
from fq_capacity_probe import full_certificate
from fq_coherent_clusters import atom_json, atom_npz

ROOT = Path(__file__).resolve().parents[1]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source-n', type=int, required=True)
    ap.add_argument('--target-k', type=int, required=True)
    ap.add_argument('--baseline', type=Path, required=True)
    ap.add_argument('--official-report', type=Path, required=True)
    ap.add_argument('--interval-report', type=Path, required=True)
    ap.add_argument('--binary', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    started = time.monotonic()
    args.out.mkdir(parents=True, exist_ok=False)
    (args.out/'control').mkdir()
    official = json.loads(args.official_report.read_text())
    interval = json.loads(args.interval_report.read_text())
    assert official['valid'] and interval['valid']
    assert official['sha256'] == interval['sha256'] == fq.digest(args.baseline)
    original = {r['n']:r for r in official['results']}
    source_k = math.isqrt(args.source_n)
    d = args.source_n-source_k*source_k
    target_n = args.target_k**2+d
    assert 0 < d and source_k < args.target_k and target_n <= 150
    rows = {args.source_n:[], target_n:[]}
    with args.baseline.open() as stream:
        for row in csv.DictReader(stream):
            n = int(row['n'])
            if n in rows:
                rows[n].append(row)
    for n in rows:
        rows[n].sort(key=lambda r:int(r['square_id']))
        assert len(rows[n]) == n
        atom_json(args.out/f'exact-case-{n}-rows.json', rows[n])
    p = normalize(np.array([[float(r[k]) for k in ('x','y','angle')] for r in rows[args.source_n]]))
    f = math.ceil((fq.bloat(p,source_k,source_k)+3e-8)*1e9)*1e-9
    stitch, _ = public_functions(ROOT/'vendor/lightning_ftmc')
    q, _ = stitch([(0,3)], [dict(w=source_k,h=source_k,dm=d,f=f,donor=0)],
                  [(p,'source-case')], box=(args.target_k,args.target_k))
    q = legalize(q)
    assert q is not None and q.shape == (target_n,3)
    certificate = full_certificate(q)
    assert certificate['valid']
    key = f'{args.target_k}_{args.target_k}_{d}'
    atom_npz(args.out/'reference.npz', {key:q})
    atom_json(args.out/'priorities.json', {key:1.0})
    binary = (args.out/'fq').resolve()
    shutil.copy2(args.binary,binary)
    binary.chmod(0o500)
    proof = dict(source=str(args.baseline), source_sha256=fq.digest(args.baseline), n=target_n, key=key,
        source_n=args.source_n, source_case=original[args.source_n], target_k=args.target_k,
        original_official_case=original[target_n],
        original_interval_case=next(r for r in interval['results'] if r['n']==target_n),
        original_true_target_side=original[target_n]['side'],
        search_reference_side=certificate['independent_raw']['side_upper'],
        reference_excess=fq.bloat(q,args.target_k,args.target_k), certificate=certificate,
        exact_source_rows_sha256=fq.digest(args.out/f'exact-case-{args.source_n}-rows.json'),
        exact_true_target_rows_sha256=fq.digest(args.out/f'exact-case-{target_n}-rows.json'),
        reference_sha256=fq.digest(args.out/'reference.npz'), geometry_sha256=basin.geom_sha(q),
        binary_sha256=fq.digest(binary), source_sha256_this_script=fq.digest(__file__),
        source_dependencies={str(path.relative_to(ROOT)):fq.digest(path) for path in
            (ROOT/'vendor/lightning_ftmc/solver.py',ROOT/'experiments/cpu_recipe_replay.py',
             ROOT/'experiments/fq_active_pilot.py',ROOT/'experiments/fq_full_basin_pilot.py')},
        construction='Public single-block stitch with complete square-frame padding and independent full-case validation.',
        interpretation='Search improvements relative to the worse padded reference are not n50 improvements; final comparisons use original_true_target_side.',
        no_submission=True)
    atom_json(args.out/'input-proof.json', proof)
    basin.MODES['control'] = ['--no-alm','--loosen','1','--pit','20','--flip-top','0']
    record, donor = basin.run_one(q,float(original[target_n]['side']),'control',target_n*10000+37,
        binary,(args.out/'control').resolve(),25,started+30)
    atom_json(args.out/'control/report.json',record)
    if donor is None:
        raise ValueError('Padded complete-case control failed')
    atom_npz(args.out/'control/donor.npz',{key:donor})
    proof.update(control_valid=True,control_report_sha256=fq.digest(args.out/'control/report.json'),
                 control_side_gain_vs_true_target=record['side_gain'],elapsed_seconds=time.monotonic()-started)
    atom_json(args.out/'complete-proof.json',proof)
    (args.out/'source.py').write_bytes(Path(__file__).read_bytes())
    print(json.dumps({k:proof[k] for k in ('n','source_n','source_sha256','original_true_target_side',
        'search_reference_side','reference_excess','reference_sha256','control_valid','control_side_gain_vs_true_target','elapsed_seconds')}))


if __name__ == '__main__':
    main()
