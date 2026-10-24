#!/usr/bin/env python3
"""Independently certify a frozen small-square campaign and report actual gains."""
import argparse
import json
import math
import os
from pathlib import Path
import signal
import time

for variable in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[variable] = '1'
import numpy as np
import fq_active_pilot as fq
from fq_coherent_clusters import Deadline, alarm, atom_json, atom_npz
from fq_capacity_probe import full_certificate
from fq_full_basin_pilot import geom_sha


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--campaign', type=Path, required=True)
    ap.add_argument('--seed-proof', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--seconds', type=float, default=60)
    args = ap.parse_args()
    started = time.monotonic()
    args.out.mkdir(parents=True, exist_ok=False)
    final = json.loads((args.campaign/'final.json').read_text())
    snapshot = Path(final['snapshot'])
    assert fq.digest(snapshot/'analysis.json') == final['analysis_sha256']
    analysis = json.loads((snapshot/'analysis.json').read_text())
    manifest = json.loads((args.campaign/'manifest.json').read_text())
    seed = json.loads(args.seed_proof.read_text())
    assert analysis['status'] == 'completed' and analysis['manifest_sha256'] == fq.digest(args.campaign/'manifest.json')
    assert fq.digest(snapshot/'donors.npz') == analysis['donors_sha256']
    assert fq.digest(snapshot/'results.json') == analysis['results_sha256']
    assert fq.digest(manifest['frozen_binary_path']) == manifest['binary_sha256']
    for entry in manifest['inputs'].values():
        assert fq.digest(entry['snapshot']) == entry['sha256']
    source_dir = args.campaign.with_name(args.campaign.name+'-source')
    source_manifest = json.loads((source_dir/'manifest.json').read_text())
    for name, digest in source_manifest['files'].items():
        assert fq.digest(source_dir/name) == digest
    records = json.loads((snapshot/'results.json').read_text())
    by_key = {r['archive_key']:r for r in records if 'archive_key' in r}
    valid, candidates, checks = {}, {}, []
    original_side = float(seed['original_official_case']['side'])
    previous = signal.signal(signal.SIGALRM, alarm)
    signal.setitimer(signal.ITIMER_REAL, args.seconds)
    status = 'complete'
    try:
        with np.load(snapshot/'donors.npz') as archive:
            for key in archive.files:
                p = archive[key]
                record = by_key[key]
                assert geom_sha(p) == record['geometry_sha256']
                assert len(p) == seed['n']
                if 'soft' in record['mode']:
                    assert record['rigid_return_trace']['valid']
                certificate = full_certificate(p)
                check = dict(key=key, geometry_sha256=geom_sha(p), certificate=certificate)
                if certificate['valid']:
                    valid[key] = p
                    length = certificate['independent_raw']['side_upper']
                    gain = original_side-float(length)
                    check.update(side=length, side_gain=gain, direct_score_gain=gain/math.sqrt(len(p)))
                    if gain > 1e-8:
                        if str(len(p)) not in candidates or float(length) < float(candidates[str(len(p))]['side']):
                            candidates[str(len(p))] = dict(side=length, squares=[[f'{v:.17g}' for v in row] for row in p],
                                source='FQ small-square multi-basin campaign', certificate=certificate,
                                provenance=dict(snapshot_analysis_sha256=final['analysis_sha256'], array_key=key,
                                                geometry_sha256=check['geometry_sha256']))
                checks.append(check)
    except Deadline:
        status = 'bounded-partial'
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)
    atom_json(args.out/'candidates.json', candidates)
    atom_npz(args.out/'all-strict.npz', valid)
    report = dict(status=status, elapsed_seconds=time.monotonic()-started, original_n=seed['n'],
        original_side=seed['original_official_case']['side'], original_case_score=seed['original_official_case']['score'],
        campaign_final=final, campaign_analysis=analysis, seed_proof_sha256=fq.digest(args.seed_proof),
        source_manifest_sha256=fq.digest(source_dir/'manifest.json'), source_sha256=fq.digest(__file__),
        variants_checked=len(checks), strictly_valid_variants=len(valid), invalid_variants=len(checks)-len(valid),
        improved_full_cases=len(candidates), best_direct_score_gain=max([0.]+[c.get('direct_score_gain',0.) for c in checks]),
        best_valid_side=min((float(c['side']) for c in checks if 'side' in c), default=None),
        candidates_sha256=fq.digest(args.out/'candidates.json'), all_strict_sha256=fq.digest(args.out/'all-strict.npz'),
        checks=checks, no_submission=True)
    atom_json(args.out/'report.json', report)
    (args.out/'source.py').write_bytes(Path(__file__).read_bytes())
    print(json.dumps({k:v for k,v in report.items() if k not in ('checks','campaign_final','campaign_analysis')}))


if __name__ == '__main__':
    main()
