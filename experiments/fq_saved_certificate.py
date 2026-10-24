#!/usr/bin/env python3
"""Certify a frozen FQ output after an earlier trial exhausted its time limit."""
from __future__ import annotations
import argparse
import json
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
    ap.add_argument('--directory', type=Path, required=True)
    ap.add_argument('--seconds', type=float, default=40)
    args = ap.parse_args()
    if not 1 <= args.seconds <= 60 or (args.directory/'recovery.json').exists():
        ap.error('Unprocessed recovery directory and 1–60s budget required')
    started = time.monotonic()
    proof = json.loads((args.directory/'input-proof.json').read_text())
    original = json.loads((args.directory/'original-trial.json').read_text())
    path = args.directory/'frozen-fq.out'
    assert fq.digest(path) == proof['output_sha256']
    assert original['status'] == 'whole-trial-timeout'
    record = dict(status='pending', original_status=original['status'], original_n=original['n'],
        input_proof_sha256=fq.digest(args.directory/'input-proof.json'),
        original_trial_sha256=fq.digest(args.directory/'original-trial.json'),
        output_sha256=fq.digest(path), seconds=args.seconds, source_sha256=fq.digest(__file__),
        source_helpers={name:fq.digest(Path(__file__).parent/name) for name in
            ('fq_active_pilot.py', 'fq_coherent_clusters.py', 'fq_capacity_probe.py', 'fq_full_basin_pilot.py')},
        optimization_repeated=False, no_submission=True)
    previous = signal.signal(signal.SIGALRM, alarm)
    signal.setitimer(signal.ITIMER_REAL, args.seconds)
    candidates, donors = {}, {}
    try:
        p = fq.decode(path, original['n'])
        if p is None:
            record['status'] = 'failed-clearance'
        else:
            certificate = full_certificate(p)
            record['certificate'] = certificate
            if certificate['valid']:
                length = certificate['independent_raw']['side_upper']
                gain = original['reference_side']-float(length)
                record.update(side_gain=gain, score_gain=gain/len(p)**.5, geometry_sha256=geom_sha(p))
                if gain > 1e-8:
                    record['status'] = 'recovered-after-trial-timeout'
                    candidates[str(len(p))] = dict(side=length, squares=[[f'{v:.17g}' for v in row] for row in p],
                        source='Separately certified saved FQ output after whole-trial timeout', certificate=certificate,
                        provenance=dict(input_proof_sha256=record['input_proof_sha256'],
                            original_trial_sha256=record['original_trial_sha256'], geometry_sha256=record['geometry_sha256']))
                    donors[original['key']+'__recovered_'+record['geometry_sha256']] = p
                else:
                    record['status'] = 'valid-no-improvement'
            else:
                record['status'] = 'failed-full-certificate'
    except Deadline:
        record['status'] = 'separate-certification-timeout'
    except Exception as exc:
        record.update(status='error', error_type=type(exc).__name__, error=str(exc)[:300])
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)
    atom_json(args.directory/'candidates.json', candidates)
    atom_npz(args.directory/'donors.npz', donors)
    record.update(elapsed_seconds=time.monotonic()-started,
        candidates_sha256=fq.digest(args.directory/'candidates.json'), donors_sha256=fq.digest(args.directory/'donors.npz'))
    atom_json(args.directory/'recovery.json', record)
    (args.directory/'source.py').write_bytes(Path(__file__).read_bytes())
    print(json.dumps({k:v for k,v in record.items() if k != 'certificate'}))


if __name__ == '__main__':
    main()
