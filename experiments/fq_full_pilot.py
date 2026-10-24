#!/usr/bin/env python3
"""Bounded contact-branch fq polishing of complete competition packings.

Keep the exact input count using w=h=floor(sqrt(n)), d=n-w*h. Search results
are separate from the immutable baseline. Full-puzzle exports must improve
the baseline's official side and pass both official and independent checks.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import json
import math
import os
from pathlib import Path
import signal
import shutil
import sys
import time

for variable in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[variable] = '1'

import numpy as np
import pandas as pd

from fq_active_pilot import trial, digest, bloat, SOURCE_COMMIT, MODES
from compose_gadgets import normalize

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from validate_submission import Square, validate_puzzle

REQUIRED_CASES = (646, 650, 599, 813, 799, 925, 991, 995)


class TrialDeadline(BaseException):
    # The official metric deliberately catches Exception and returns a failed
    # case. A hard worker deadline must escape that adapter to reach our outer
    # handler, so validation cannot consume another unbounded interval.
    pass


def _alarm(signum, frame):
    raise TrialDeadline('Whole trial wall-time budget')


def checked_trial(payload):
    job, baseline_side = payload[:2]
    mode_arguments = payload[2] if len(payload) > 2 else None
    start = time.monotonic()
    remaining = job[-1] - start
    if remaining <= 1:
        return {'key': job[0], 'mode': job[2], 'seed': job[5],
                'status': 'budget-skipped'}, None
    previous_handler = signal.getsignal(signal.SIGALRM)
    previous_arguments = MODES.get(job[2])
    if mode_arguments is not None:
        MODES[job[2]] = list(mode_arguments)
    w, h, _ = map(int, job[0].split('_'))
    name = f'{job[0]}-{job[2]}-{job[5]}'
    command = [job[3], 'quench', '--in', str(Path(job[4])/(name+'.in')),
               '--out', str(Path(job[4])/(name+'.out')),
               '--rect-dx', str(w-min(w,h)), '--rect-dy', str(h-min(w,h)),
               '--seed', str(job[5])] + list(MODES[job[2]])
    signal.signal(signal.SIGALRM, _alarm)
    signal.setitimer(signal.ITIMER_REAL, min(job[-2], remaining))
    try:
        record, donor = trial(job)
        record['command'] = command
        if donor is not None:
            name, q = donor
            side = float(record['certificate']['raw_side'])
            record['official_side_gain'] = baseline_side - side
            if record['official_side_gain'] <= 1e-10:
                donor = None
                record['full_improvement'] = False
            else:
                squares = [Square(*(format(float(v), '.17g') for v in row)) for row in q]
                certificate = validate_puzzle(len(q), squares)
                record['independent_certificate'] = certificate
                record['full_improvement'] = bool(certificate['valid'])
                if not certificate['valid']:
                    donor = None
                    record['status'] = 'failed-independent'
        return record, donor
    except TrialDeadline:
        return {'key': job[0], 'mode': job[2], 'seed': job[5],
                'status': 'whole-trial-timeout', 'seconds': time.monotonic()-start,
                'command': command}, None
    except Exception as exc:
        return {'key': job[0], 'mode': job[2], 'seed': job[5], 'status': 'error',
                'error_type': type(exc).__name__, 'error': str(exc)[:300],
                'command': command}, None
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)
        if mode_arguments is not None:
            if previous_arguments is None:
                MODES.pop(job[2], None)
            else:
                MODES[job[2]] = previous_arguments


def describe_case(n, p, official):
    folded = (p[:, 2]+math.pi/4) % (math.pi/2)-math.pi/4
    tilted = abs(folded) > .018
    w = math.isqrt(n)
    return {'n': n, 'key': f'{w}_{w}_{n-w*w}',
            'side': float(official[n]['side']), 'score': official[n]['score'],
            'bloat': bloat(p, w, w), 'tilted': int(tilted.sum()),
            'angle_classes': len(np.unique(np.round(folded[tilted], 3)))}


def select_cases(poses, official, count):
    metadata = {}
    for n, p in poses.items():
        if n < 100 or math.isqrt(n)**2 == n:
            continue
        item = describe_case(n, p, official)
        if not item['tilted']:
            continue
        metadata[n] = item
    selected = list(REQUIRED_CASES)
    if any(n not in metadata for n in selected):
        raise ValueError('A required complete non-grid case is unavailable')
    bands = {band: sorted((n for n in metadata if n//100 == band and n not in selected),
                         key=lambda n: -metadata[n]['score']) for band in range(1, 10)}
    while len(selected) < count and any(bands.values()):
        for band in bands:
            if bands[band] and len(selected) < count:
                selected.append(bands[band].pop(0))
    return selected, [metadata[n] for n in selected]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--baseline', type=Path, default=ROOT/'artifacts/submission-public-refresh-v1-safe.csv')
    ap.add_argument('--official-report', type=Path, default=ROOT/'artifacts/submission-public-refresh-v1-safe-official.json')
    ap.add_argument('--binary', type=Path, default=Path('/tmp/squares-fq-portable-target/release/fq'))
    ap.add_argument('--out', type=Path, default=ROOT/'artifacts/fq-full-pilot-v1')
    ap.add_argument('--cases', type=int, default=24)
    ap.add_argument('--seconds', type=float, default=500)
    ap.add_argument('--trial-seconds', type=float, default=30)
    ap.add_argument('--workers', type=int, default=2)
    ap.add_argument('--case-list', type=Path,
                    help='JSON integer list or transport summary with case_score_changes')
    ap.add_argument('--profile', choices=('standard', 'composition-polish'), default='standard')
    ap.add_argument('--light-seconds', type=float, default=8)
    args = ap.parse_args()
    if not (len(REQUIRED_CASES) <= args.cases <= 1000 and 0 < args.seconds <= 600
            and 0 < args.trial_seconds <= 30 and args.workers == 2):
        ap.error('Use 2 workers, <=600s total, <=30s/trial, and enough cases for required seeds')
    if not 0 < args.light_seconds <= 8:
        ap.error('Light pass must have a positive budget no larger than 8s')
    args.out.mkdir(parents=True, exist_ok=False)
    start = time.monotonic()
    deadline = start + args.seconds
    baseline_sha = digest(args.baseline)
    report = json.loads(args.official_report.read_text())
    if report['sha256'] != baseline_sha or not report['valid'] or report['puzzles'] != 1000:
        raise ValueError('Complete matching official baseline certificate required')
    official = {r['n']: r for r in report['results']}
    frame = pd.read_csv(args.baseline)
    poses = {int(n): normalize(g.sort_values('square_id')[['x', 'y', 'angle']].to_numpy(float))
             for n, g in frame.groupby('n', sort=True)}
    if set(poses) != set(range(1, 1001)) or any(len(p) != n for n, p in poses.items()):
        raise ValueError('Invalid baseline counts')
    if args.case_list:
        source_cases = json.loads(args.case_list.read_text())
        if isinstance(source_cases, dict):
            source_cases = [r['n'] for r in source_cases['case_score_changes']]
        selected = [int(n) for n in source_cases]
        if (len(selected) != args.cases or len(set(selected)) != len(selected)
                or any(n not in poses for n in selected)):
            raise ValueError('Explicit case list/count mismatch')
        metadata = [describe_case(n, poses[n], official) for n in selected]
    else:
        selected, metadata = select_cases(poses, official, args.cases)
    if args.profile == 'composition-polish':
        phases = [('light_polish', args.light_seconds,
                   ['--no-alm', '--loosen', '1', '--pit', '40', '--flip-top', '0']),
                  ('deep_polish', args.trial_seconds,
                   ['--no-alm', '--loosen', '1', '--pit', '160', '--flip-top', '16'])]
    else:
        phases = [(mode, args.trial_seconds, MODES[mode]) for mode in ('polish', 'kick')]
    binary_snapshot = args.out/'fq-portable'
    binary_sha = digest(args.binary)
    shutil.copy2(args.binary, binary_snapshot)
    if digest(binary_snapshot) != binary_sha or digest(args.binary) != binary_sha:
        raise ValueError('Executable changed while snapshotting')
    (args.out/'source_fq_full_pilot.py').write_bytes(Path(__file__).read_bytes())
    (args.out/'source_fq_active_pilot.py').write_bytes((ROOT/'experiments/fq_active_pilot.py').read_bytes())
    manifest = {'baseline': str(args.baseline), 'baseline_sha256': baseline_sha,
                'baseline_report': str(args.official_report), 'baseline_report_sha256': digest(args.official_report),
                'source_repository': 'https://github.com/evand/square-packing',
                'source_commit': SOURCE_COMMIT, 'source_notice': 'vendor/fq/NOTICE',
                'binary_sha256': binary_sha, 'binary_snapshot': str(binary_snapshot.resolve()),
                'script_sha256': digest(Path(__file__)),
                'shared_adapter_sha256': digest(ROOT/'experiments/fq_active_pilot.py'),
                'selection': metadata, 'seconds': args.seconds, 'trial_seconds': args.trial_seconds,
                'workers': args.workers, 'profile': args.profile,
                'case_list': str(args.case_list) if args.case_list else None,
                'case_list_sha256': digest(args.case_list) if args.case_list else None,
                'modes': {mode: flags for mode, cap, flags in phases},
                'mode_wall_budgets': {mode: cap for mode, cap, flags in phases},
                'deep_phase_only_if_light_improved': args.profile == 'composition-polish'}
    (args.out/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    print(json.dumps({'stage': 'start', 'cases': selected, 'seconds': args.seconds,
                      'trial_seconds': args.trial_seconds, 'workers': args.workers}), flush=True)
    records, candidates, donors = [], {}, {}
    best = {n: poses[n] for n in selected}
    with ProcessPoolExecutor(max_workers=2) as pool:
        for stage, (mode, cap, mode_arguments) in enumerate(phases):
            if time.monotonic() >= deadline-2:
                break
            jobs = []
            phase_cases = selected
            if stage and args.profile == 'composition-polish':
                phase_cases = [n for n in selected if str(n) in candidates]
            for i, n in enumerate(phase_cases):
                w = math.isqrt(n); key = f'{w}_{w}_{n-w*w}'
                job = (key, best[n], mode, str(binary_snapshot.resolve()), str(args.out.resolve()),
                       781001+stage*1000+i, cap, deadline)
                jobs.append((job, float(official[n]['side']), mode_arguments))
            for future in as_completed([pool.submit(checked_trial, j) for j in jobs]):
                record, donor = future.result()
                records.append(record)
                if donor is not None:
                    name, p = donor; n = len(p)
                    side = float(record['certificate']['raw_side'])
                    if str(n) not in candidates or side < candidates[str(n)]['side']:
                        best[n] = p
                        candidates[str(n)] = {'side': side,
                            'squares': [[format(float(v), '.17g') for v in row] for row in p],
                            'source': 'fq full-puzzle contact-branch CPU search',
                            'mode': mode, 'geometry_sha256': record['geometry_sha256'],
                            'official_certificate': record['certificate'],
                            'independent_certificate': record['independent_certificate']}
                    donors[name] = p
                    np.savez_compressed(args.out/'donors.npz', **donors)
                (args.out/'results.json').write_text(json.dumps(records, indent=2)+'\n')
                (args.out/'full_candidates.json').write_text(json.dumps(candidates)+'\n')
                print(json.dumps({k: v for k, v in record.items()
                                  if k not in ('fq', 'certificate', 'independent_certificate', 'command')}), flush=True)
    summary = {'elapsed_seconds': time.monotonic()-start, 'attempted': len(records),
               'cases': selected, 'full_improvements': len(candidates),
               'estimated_full_score_gain': sum((float(official[int(n)]['side'])-c['side'])/math.sqrt(int(n))
                                               for n, c in candidates.items()),
               'candidate_sha256': digest(args.out/'full_candidates.json'),
               'baseline_sha256': baseline_sha, 'results_sha256': digest(args.out/'results.json'),
               'statuses': {status: sum(r['status'] == status for r in records)
                            for status in sorted({r['status'] for r in records})}}
    if digest(args.baseline) != baseline_sha:
        raise ValueError('Baseline changed during pilot')
    if digest(binary_snapshot) != binary_sha:
        raise ValueError('Executable snapshot changed during pilot')
    (args.out/'summary.json').write_text(json.dumps(summary, indent=2)+'\n')
    print(json.dumps({'stage': 'complete', **summary}), flush=True)


if __name__ == '__main__':
    main()
