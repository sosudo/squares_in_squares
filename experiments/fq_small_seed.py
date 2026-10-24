#!/usr/bin/env python3
"""Freeze an exact complete-case source and certify a 20-step FQ control."""
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
from compose_gadgets import normalize
from fq_capacity_probe import full_certificate
from fq_coherent_clusters import atom_json, atom_npz


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--n', type=int, required=True)
    ap.add_argument('--baseline', type=Path, required=True)
    ap.add_argument('--official-report', type=Path, required=True)
    ap.add_argument('--interval-report', type=Path, required=True)
    ap.add_argument('--binary', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    started = time.monotonic()
    assert 1 < args.n <= 150
    args.out.mkdir(parents=True, exist_ok=False)
    (args.out/'control').mkdir()
    official = json.loads(args.official_report.read_text())
    interval = json.loads(args.interval_report.read_text())
    source_sha = fq.digest(args.baseline)
    assert official['valid'] and interval['valid'] and official['sha256'] == interval['sha256'] == source_sha
    with args.baseline.open() as stream:
        rows = [r for r in csv.DictReader(stream) if int(r['n']) == args.n]
    rows.sort(key=lambda r:int(r['square_id']))
    assert len(rows) == args.n and len({r['square_id'] for r in rows}) == args.n
    atom_json(args.out/'exact-source-rows.json', rows)
    pose = normalize(np.array([[float(r[k]) for k in ('x','y','angle')] for r in rows]))
    certificate = full_certificate(pose)
    assert certificate['valid'], 'Numeric source needs explicit repair before it can become a certified seed'
    source_case = next(r for r in official['results'] if r['n'] == args.n)
    interval_case = next(r for r in interval['results'] if r['n'] == args.n)
    w = math.floor(float(source_case['side']))
    key = f'{w}_{w}_{args.n-w*w}'
    atom_npz(args.out/'reference.npz', {key:pose})
    atom_json(args.out/'priorities.json', {key:1.0})
    binary = (args.out/'fq').resolve()
    shutil.copy2(args.binary, binary)
    binary.chmod(0o500)
    assert fq.digest(binary) == fq.digest(args.binary)
    folded = (pose[:,2]+np.pi/4)%(np.pi/2)-np.pi/4
    angles, counts = np.unique(np.round(np.degrees(folded[abs(folded)>1e-5]), 6), return_counts=True)
    proof = dict(source=str(args.baseline), source_sha256=source_sha,
        official_report_sha256=fq.digest(args.official_report), interval_report_sha256=fq.digest(args.interval_report),
        exact_source_rows_sha256=fq.digest(args.out/'exact-source-rows.json'), n=args.n, key=key,
        original_official_case=source_case, original_interval_case=interval_case,
        optimizer_seed_conversion='Original decimal strings preserved separately; binary64 values normalized by common translation.',
        optimizer_seed_geometry_sha256=basin.geom_sha(pose), reference_sha256=fq.digest(args.out/'reference.npz'),
        reference_excess=fq.bloat(pose,w,w), certificate=certificate,
        tilted_angle_counts_degrees=list(zip(angles.tolist(),counts.tolist())), binary_sha256=fq.digest(binary),
        source_sha256_this_script=fq.digest(__file__), no_submission=True)
    atom_json(args.out/'input-proof.json', proof)
    basin.MODES['control'] = ['--no-alm','--loosen','1','--pit','20','--flip-top','0']
    record, donor = basin.run_one(pose, float(source_case['side']), 'control', args.n*10000+1,
        binary, (args.out/'control').resolve(), 25, started+30)
    atom_json(args.out/'control/report.json', record)
    if donor is None:
        raise ValueError('Small full-case control failed')
    atom_npz(args.out/'control/donor.npz', {key:donor})
    proof.update(control_valid=True, control_report_sha256=fq.digest(args.out/'control/report.json'),
                 control_geometry_sha256=basin.geom_sha(donor), elapsed_seconds=time.monotonic()-started)
    atom_json(args.out/'complete-proof.json', proof)
    (args.out/'source.py').write_bytes(Path(__file__).read_bytes())
    print(json.dumps(dict(n=args.n, key=key, source_sha256=source_sha, source_side=source_case['side'],
        control_valid=True, control_side_gain=record.get('side_gain'), control_score_gain=record.get('score_gain'),
        control_seconds=record['elapsed_seconds'], elapsed_seconds=proof['elapsed_seconds'],
        reference_sha256=proof['reference_sha256'], complete_proof_sha256=fq.digest(args.out/'complete-proof.json'))))


if __name__ == '__main__':
    main()
