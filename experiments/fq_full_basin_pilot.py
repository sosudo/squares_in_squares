#!/usr/bin/env python3
"""One-worker aggressive FQ basin changes on newly improved complete puzzles."""
from __future__ import annotations
import time
ENTRY_STARTED = time.monotonic()
import argparse
import hashlib
import json
import math
import multiprocessing as mp
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys

for variable in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[variable] = '1'
import numpy as np
import fq_active_pilot as fq
from compose_gadgets import normalize, read_baseline, side
from fq_coherent_clusters import Deadline, alarm, grouped_run, atom_json, atom_npz
from fq_capacity_probe import full_certificate

ROOT = Path(__file__).resolve().parents[1]
TARGETS = [599, 702, 807, 813, 815, 871, 924, 931]
MODES = {
    'control': ['--no-alm', '--loosen', '1', '--pit', '20', '--flip-top', '0'],
    'kick03': ['--loosen', '1.003', '--kick', '.03', '--outer', '65', '--pit', '100', '--flip-top', '24'],
    'kick08': ['--loosen', '1.006', '--kick', '.08', '--outer', '80', '--pit', '100', '--flip-top', '32'],
    'round15': ['--loosen', '1', '--round-r0', '.15', '--round-compress', '--round-steps', '12',
                '--round-kick', '.03', '--outer', '45', '--pit', '100', '--flip-top', '16'],
}


def geom_sha(p):
    return hashlib.sha256(np.asarray(p, dtype='<f8').tobytes()).hexdigest()


def run_one(p, reference_side, mode, seed, binary, out, cap, deadline):
    start = time.monotonic()
    n = len(p)
    w = math.floor(side(p))
    d = n-w*w
    key = f'{w}_{w}_{d}'
    assert w*w+d == n
    name = f'n{n}-{mode}-{seed}'
    inp, dst = out/(name+'.in'), out/(name+'.out')
    encoded, offsets = fq.encode(p, w, w)
    assert offsets == [0, 0]
    inp.write_text(encoded)
    command = [str(binary), 'quench', '--in', str(inp), '--out', str(dst),
               '--rect-dx', '0', '--rect-dy', '0', '--seed', str(seed), *MODES[mode]]
    record = dict(n=n, key=key, parent_geometry_sha256=geom_sha(p), mode=mode, seed=seed,
                  input_sha256=fq.digest(inp), reference_side=reference_side, command=command)
    remaining = min(cap, deadline-start-2)
    if remaining <= 1:
        return dict(record, status='budget-skipped'), None
    previous = signal.signal(signal.SIGALRM, alarm)
    signal.setitimer(signal.ITIMER_REAL, remaining)
    try:
        result = grouped_run(command, capture_output=True, text=True, timeout=remaining)
        (out/(name+'.log')).write_text(result.stdout+'\n'+result.stderr)
        record['returncode'] = result.returncode
        if result.returncode or not dst.exists():
            record['status'] = 'fq-failed'
            return record, None
        record['fq'] = json.loads(result.stdout.strip().splitlines()[-1])
        q = fq.decode(dst, n)
        if q is None:
            record['status'] = 'failed-clearance'
            return record, None
        record['floating_side'] = side(q)
        record['side_gain'] = reference_side-side(q)
        if mode != 'control' and record['side_gain'] <= 1e-8:
            record['status'] = 'no-material-side-gain'
            return record, None
        certificate = full_certificate(q)
        record['certificate'] = certificate
        if not certificate['valid']:
            record['status'] = 'failed-full-certificate'
            return record, None
        length = float(certificate['independent_raw']['side_upper'])
        record['side_gain'] = reference_side-length
        if mode != 'control' and record['side_gain'] <= 1e-8:
            record['status'] = 'no-certified-side-gain'
            return record, None
        record.update(status='certified', geometry_sha256=geom_sha(q),
                      score_gain=record['side_gain']/math.sqrt(n))
        return record, q
    except (Deadline, subprocess.TimeoutExpired):
        record['status'] = 'whole-trial-timeout'
        return record, None
    except Exception as exc:
        record.update(status='error', error_type=type(exc).__name__, error=str(exc)[:300])
        return record, None
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)
        record['elapsed_seconds'] = time.monotonic()-start


def campaign(args):
    # A supervisor termination must unwind grouped_run and kill its FQ session.
    signal.signal(signal.SIGTERM, alarm)
    deadline = ENTRY_STARTED+args.seconds-5
    args.out.mkdir(parents=True, exist_ok=False)
    for name in ('inputs', 'source', 'trials'):
        (args.out/name).mkdir()
    official = json.loads(args.official_report.read_text())
    assert official['valid'] and official['sha256'] == fq.digest(args.baseline)
    official_cases = {r['n']:r for r in official['results']}
    base = read_baseline(args.baseline)
    poses = {n:normalize(base[n]) for n in TARGETS}
    selected = {n:dict(source=str(args.baseline), source_sha256=official['sha256'],
                       side=float(official_cases[n]['side'])) for n in TARGETS}
    inputs = [dict(path=str(args.baseline), sha256=fq.digest(args.baseline)),
              dict(path=str(args.official_report), sha256=fq.digest(args.official_report))]
    for i, path in enumerate(args.candidates):
        digest = fq.digest(path)
        shutil.copyfile(path, args.out/'inputs'/f'candidates-{i}.json')
        inputs.append(dict(path=str(path), sha256=digest))
        proposals = json.loads(path.read_text())
        for n in TARGETS:
            if str(n) not in proposals:
                continue
            item = proposals[str(n)]
            length = float(item['side'])
            if length < selected[n]['side']:
                p = normalize(np.array(item['squares'], dtype=float))
                assert p.shape == (n, 3) and np.isfinite(p).all()
                poses[n] = p
                selected[n] = dict(source=str(path), source_sha256=digest, side=length)
    for n, p in poses.items():
        selected[n]['geometry_sha256'] = geom_sha(p)
        selected[n]['key'] = f'{math.floor(side(p))}_{math.floor(side(p))}_{n-math.floor(side(p))**2}'
    atom_npz(args.out/'inputs/selected-poses.npz', {str(n):p for n,p in poses.items()})
    binary = (args.out/'inputs/fq').resolve()
    shutil.copy2(args.binary, binary)
    binary.chmod(0o500)
    assert fq.digest(binary) == fq.digest(args.binary)
    sources = [Path(__file__), ROOT/'experiments/fq_active_pilot.py', ROOT/'experiments/fq_coherent_clusters.py',
               ROOT/'experiments/fq_capacity_probe.py', ROOT/'experiments/compose_gadgets.py',
               ROOT/'scripts/validate_submission.py', ROOT/'scripts/score_official.py', ROOT/'research/official_metric_v17.py']
    for path in sources:
        shutil.copy2(path, args.out/'source'/path.name)
    manifest = dict(inputs=inputs, selected=selected, selected_poses_sha256=fq.digest(args.out/'inputs/selected-poses.npz'),
        binary_sha256=fq.digest(binary), source_commit=fq.SOURCE_COMMIT,
        source_hashes={str(p):fq.digest(p) for p in sources}, modes=MODES, workers=1,
        seconds=args.seconds, trial_seconds=args.trial_seconds, maximum_search_trials=24,
        command=[sys.executable, str(Path(__file__).resolve()), *sys.argv[1:]],
        container='w=h=floor(current bounding side), d=n-w*w; encoded s is bounding side, not score',
        no_submission=True)
    atom_json(args.out/'manifest.json', manifest)
    control, control_pose = run_one(poses[702], selected[702]['side'], 'control', 9147000,
                                   binary, (args.out/'trials').resolve(), args.trial_seconds, deadline)
    atom_json(args.out/'positive-control.json', control)
    if control_pose is None:
        raise ValueError('New complete-puzzle FQ/transport positive control failed')
    records, candidates, donors = [], {}, {}
    best = {n:p.copy() for n,p in poses.items()}
    best_side = {n:selected[n]['side'] for n in TARGETS}
    def checkpoint(status):
        atom_json(args.out/'results.json', records)
        atom_json(args.out/'candidates.json', candidates)
        atom_npz(args.out/'donors.npz', donors)
        summary = dict(status=status, elapsed_seconds=time.monotonic()-ENTRY_STARTED, trials=len(records),
            improved_cases=len(candidates), total_score_gain=sum((selected[int(n)]['side']-float(c['side']))/math.sqrt(int(n)) for n,c in candidates.items()),
            statuses={s:sum(r['status']==s for r in records) for s in sorted({r['status'] for r in records})},
            candidates_sha256=fq.digest(args.out/'candidates.json'), donors_sha256=fq.digest(args.out/'donors.npz'),
            results_sha256=fq.digest(args.out/'results.json'), manifest_sha256=fq.digest(args.out/'manifest.json'))
        atom_json(args.out/'summary.json', summary)
        return summary
    print(json.dumps(dict(stage='control-passed', selected=selected)), flush=True)
    # Phase ordering gives every target a moderate kick before stronger changes.
    for index, (mode, n) in enumerate((mode,n) for mode in ('kick03','round15','kick08') for n in TARGETS):
        if time.monotonic() >= deadline-2:
            break
        record, p = run_one(best[n], best_side[n], mode, 9147100+index, binary,
                            (args.out/'trials').resolve(), args.trial_seconds, deadline)
        records.append(record)
        if p is not None:
            length = record['certificate']['independent_raw']['side_upper']
            key = record['key']+'__full_basin_'+record['geometry_sha256']
            donors[key] = p
            best[n], best_side[n] = p, float(length)
            candidates[str(n)] = dict(side=length, squares=[[f'{v:.17g}' for v in row] for row in p],
                source='Aggressive full-puzzle FQ basin search', certificate=record['certificate'],
                provenance=dict(manifest_sha256=fq.digest(args.out/'manifest.json'), trial=index,
                                parent_geometry_sha256=record['parent_geometry_sha256']))
        checkpoint('running')
        print(json.dumps({k:v for k,v in record.items() if k not in ('fq','certificate','command')}), flush=True)
    for entry in inputs:
        assert fq.digest(entry['path']) == entry['sha256']
    assert fq.digest(binary) == manifest['binary_sha256']
    print(json.dumps(checkpoint('complete')), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--official-report', type=Path, required=True)
    parser.add_argument('--candidates', type=Path, action='append', required=True)
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--seconds', type=float, default=290)
    parser.add_argument('--trial-seconds', type=float, default=18)
    args = parser.parse_args()
    if args.out.exists() or not 20 <= args.seconds <= 295 or not 15 <= args.trial_seconds <= 20:
        parser.error('New output directory, one worker, <=295s total and 15–20s per complete trial required')
    process = mp.get_context('fork').Process(target=campaign, args=(args,))
    process.start()
    process.join(max(0, args.seconds-(time.monotonic()-ENTRY_STARTED)))
    enforced = process.is_alive()
    if enforced:
        process.terminate()
        process.join(1)
        if process.is_alive():
            process.kill()
            process.join(.5)
    receipt = dict(elapsed_seconds=time.monotonic()-ENTRY_STARTED, exitcode=process.exitcode,
                   hard_deadline_enforced=enforced, workers=1)
    if args.out.exists():
        atom_json(args.out/'supervisor.json', receipt)
    print(json.dumps(receipt), flush=True)
    if process.exitcode:
        raise SystemExit(process.exitcode)


if __name__ == '__main__':
    main()
