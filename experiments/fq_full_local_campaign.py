#!/usr/bin/env python3
"""Bounded local aspect continuation across joins in complete unit-square puzzles.

Remote squares stay fixed during the local stage. Every retained intermediate
returns to exactly zero aspect and passes the full independent/official gates
before an unrestricted, bounded contact-LP release. No competition submission.
"""
from __future__ import annotations
import time
ENTRY_STARTED = time.monotonic()
import argparse
from collections import Counter
import hashlib
import json
import math
import multiprocessing as mp
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys

for variable in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[variable] = '1'
import numpy as np
from scipy.spatial import cKDTree
import fq_active_pilot as fq
from compose_gadgets import normalize, read_baseline, side
from fq_capacity_probe import full_certificate
from fq_coherent_clusters import Deadline, alarm, grouped_run, atom_json, atom_npz
from fq_local_soft_campaign import neighborhood

ROOT = Path(__file__).resolve().parents[1]
TARGETS = [813, 871, 931, 807, 815, 924]
SCHEDULE = TARGETS+TARGETS[:3]
RELEASE_OPTIONS = ['--no-alm', '--loosen', '1', '--pit', '20', '--flip-top', '0']
MODES = [(.3, 20, 1.001), (.6, 40, 1.001), (.3, 40, 1.005), (.6, 64, 1.005)]


def geometry_sha(p):
    return hashlib.sha256(np.asarray(p, dtype='<f8').tobytes()).hexdigest()


def local_selection(p, seed, count, visit):
    """Start at the proven opposite-tilt join, then diversify actual joins."""
    _, initial = neighborhood(p, seed, .3)
    center = np.array(initial['center']); kind = initial['center_kind']
    pair = None
    if visit:
        pairs = sorted(contact_edges(p, range(len(p)), tolerance=.035))
        angles = (p[:, 2]+np.pi/4) % (np.pi/2)-np.pi/4
        eligible = []
        for i, j in pairs:
            delta = abs((angles[i]-angles[j]+np.pi/4) % (np.pi/2)-np.pi/4)
            # These are unlike orientations within .035 of actual SAT contact,
            # including tilted/upright boundaries at composition joins.
            if delta > .08:
                eligible.append((i, j))
        if eligible:
            rng = np.random.default_rng(seed)
            pair = eligible[int(rng.integers(len(eligible)))]
            center = p[list(pair), :2].mean(0)
            kind = 'adjacent_unlike_orientation_join'
    free = np.argsort(((p[:, :2]-center)**2).sum(1), kind='stable')[:min(count, len(p))]
    frozen = np.setdiff1d(np.arange(len(p)), free)
    return frozen, dict(center=center.tolist(), center_kind=kind,
        selected_pair=list(pair) if pair else None, free_indices=free.tolist(),
        frozen_indices=frozen.tolist(), requested_free_count=count)


def contact_edges(p, free, tolerance=1e-5):
    """Diagnostic SAT near-contact graph, restricted to edges touching free ids."""
    free = set(map(int, free)); answer = set()
    for i, j in cKDTree(p[:, :2]).query_pairs(1.5):
        if i not in free and j not in free:
            continue
        a, b = p[i, 2], p[j, 2]
        axes = np.array([[math.cos(a), math.sin(a)], [-math.sin(a), math.cos(a)],
                         [math.cos(b), math.sin(b)], [-math.sin(b), math.cos(b)]])
        projections = abs(axes @ (p[j, :2]-p[i, :2]))
        radii = .5*(abs(axes @ axes[0])+abs(axes @ axes[1])+
                     abs(axes @ axes[2])+abs(axes @ axes[3]))
        gap = float(max(projections-radii))
        if abs(gap) <= tolerance:
            answer.add((min(i, j), max(i, j)))
    return answer


def displacement(p, q, selection):
    free = np.array(selection['free_indices'], dtype=int)
    frozen = np.array(selection['frozen_indices'], dtype=int)
    difference = q[:, :2]-p[:, :2]
    offset = np.median(difference[frozen], axis=0) if len(frozen) else np.zeros(2)
    lengths = np.linalg.norm(difference-offset, axis=1)
    angle = (q[:, 2]-p[:, 2]+np.pi/4) % (np.pi/2)-np.pi/4
    before, after = contact_edges(p, free), contact_edges(q, free)
    return dict(translation_offset_removed=offset.tolist(),
        free_position_rms=float(np.sqrt(np.mean(lengths[free]**2))),
        free_position_max=float(max(lengths[free])),
        free_angle_rms_degrees=float(np.degrees(np.sqrt(np.mean(angle[free]**2)))),
        free_angle_max_degrees=float(np.degrees(max(abs(angle[free])))),
        free_positions_changed_gt_1e_5=int(sum(lengths[free] > 1e-5)),
        frozen_position_max=float(max(lengths[frozen])) if len(frozen) else 0.,
        contacts_before=len(before), contacts_after=len(after),
        contacts_lost=[list(x) for x in sorted(before-after)],
        contacts_gained=[list(x) for x in sorted(after-before)],
        contact_tolerance=1e-5, diagnostic_only=True)


def soft_options(amplitude, hold, frozen):
    return ['--loosen', '1', '--soft-compress', '--soft-a0', str(amplitude),
        '--soft-steps', '12' if amplitude < .5 else '16', '--soft-p', '2',
        '--soft-kick', '.004', '--hold-f', str(hold), '--outer', '45',
        '--pit', '100', '--flip-top', '16', '--v', '--kick', '.06' if amplitude < .5 else '.1',
        '--freeze', ','.join(map(str, map(int, frozen)))]


def run_stage(p, original_side, mode, options, seed, binary, directory, cap, deadline):
    started = time.monotonic(); n = len(p); w = math.floor(side(p))
    name = f'n{n}-{mode}-{seed}'
    inp, dst, log = (directory/(name+suffix) for suffix in ('.in', '.out', '.log'))
    record = dict(n=n, mode=mode, seed=seed, parent_geometry_sha256=geometry_sha(p),
                  reference_side=original_side, status='started', whole_stage_cap=cap)
    remaining = min(cap, deadline-started)
    if remaining <= 1:
        return dict(record, status='budget-skipped'), None
    previous = signal.signal(signal.SIGALRM, alarm)
    prior_timer = signal.getitimer(signal.ITIMER_REAL)[0]
    signal.setitimer(signal.ITIMER_REAL, remaining)
    try:
        encoded, offsets = fq.encode(p, w, w)
        if offsets != [0, 0]:
            raise ValueError('Full puzzle requires square container')
        inp.write_text(encoded)
        command = [str(binary), 'quench', '--in', str(inp), '--out', str(dst),
                   '--rect-dx', '0', '--rect-dy', '0', '--seed', str(seed), *options]
        record.update(command=command, input_sha256=fq.digest(inp))
        result = grouped_run(command, timeout=max(.01, remaining-(time.monotonic()-started)), text=True)
        log.write_text(result.stdout+'\n'+result.stderr)
        record.update(returncode=result.returncode, log_sha256=fq.digest(log))
        if result.returncode or not dst.exists():
            return dict(record, status='native-failed'), None
        record['fq'] = json.loads(result.stdout.strip().splitlines()[-1])
        if '--soft-a0' in options:
            values = [float(x) for x in re.findall(r'soft eps ([0-9.eE+-]+) hold', result.stderr)]
            steps = int(options[options.index('--soft-steps')+1])
            amplitude = float(options[options.index('--soft-a0')+1])
            valid = (len(values) == steps and values[-1] == 0. and
                     all(a >= b >= 0. for a, b in zip(values, values[1:])) and
                     record['fq'].get('soft', {}).get('a0') == amplitude)
            record['rigid_return_trace'] = dict(valid=valid, epsilons=values,
                native_source_invariant='At final k=K, eps=0 exactly, aspect variables clear; set_soft(0) precedes rigid finish.')
            if not valid:
                return dict(record, status='failed-rigid-return-trace'), None
        q = fq.decode(dst, n)
        if q is None or side(q) > original_side+.005:
            return dict(record, status='outside-near-best-band'), None
        certificate = full_certificate(q)
        record['certificate'] = certificate
        if not certificate['valid']:
            return dict(record, status='failed-full-certificate'), None
        length = float(certificate['independent_raw']['side_upper'])
        record.update(status='certified', geometry_sha256=geometry_sha(q), side=length,
                      side_gain=original_side-length, score_gain=(original_side-length)/math.sqrt(n))
        return record, q
    except (Deadline, subprocess.TimeoutExpired):
        record['status'] = 'whole-stage-timeout'
        return record, None
    except Exception as error:
        record.update(status='error', error_type=type(error).__name__, error=str(error)[:240])
        return record, None
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)
        if prior_timer:
            signal.setitimer(signal.ITIMER_REAL, max(.001, prior_timer-(time.monotonic()-started)))
        record['elapsed_seconds'] = time.monotonic()-started


def campaign(args):
    signal.signal(signal.SIGTERM, alarm)
    deadline = ENTRY_STARTED+args.seconds-7.
    args.out.mkdir(parents=True, exist_ok=False)
    for name in ('inputs', 'source', 'trials', 'retained'):
        (args.out/name).mkdir()
    report = json.loads(args.official_report.read_text()); baseline_sha = fq.digest(args.baseline)
    if not (report['sha256'] == baseline_sha and report['valid'] and report['puzzles'] == 1000
            and report['metric_sha256'] == fq.OFFICIAL_SHA256):
        raise ValueError('Complete matching official baseline proof required')
    evidence = json.loads(args.control.read_text())
    if not (evidence.get('full_certificate', {}).get('valid') and evidence['elapsed_seconds'] <= 30):
        raise ValueError('Actual full-puzzle local continuation control required')
    base = read_baseline(args.baseline)
    cases = {int(r['n']): r for r in report['results']}
    poses = {n:normalize(base[n]) for n in TARGETS}
    original = {n:float(cases[n]['side']) for n in TARGETS}
    binary = (args.out/'inputs/fq').resolve(); shutil.copy2(args.binary, binary); binary.chmod(0o500)
    if fq.digest(binary) != evidence['binary_sha256']:
        raise ValueError('Binary differs from the actual positive control')
    shutil.copy2(args.control, args.out/'inputs/positive-control.json')
    shutil.copy2(args.official_report, args.out/'inputs/official-report.json')
    atom_npz(args.out/'inputs/poses.npz', {str(n):p for n, p in poses.items()})
    sources = [Path(__file__), ROOT/'experiments/fq_active_pilot.py', ROOT/'experiments/fq_capacity_probe.py',
        ROOT/'experiments/fq_coherent_clusters.py', ROOT/'experiments/fq_local_soft_campaign.py',
        ROOT/'experiments/compose_gadgets.py', ROOT/'scripts/validate_submission.py',
        ROOT/'scripts/score_official.py', ROOT/'research/official_metric_v17.py']
    for path in sources:
        shutil.copy2(path, args.out/'source'/path.name)
    manifest = dict(baseline=str(args.baseline), baseline_sha256=baseline_sha,
        baseline_official_sha256=fq.digest(args.official_report), binary_sha256=fq.digest(binary),
        fq_source_commit=fq.SOURCE_COMMIT, source_license='MIT; Evan Daniel',
        source_hashes={str(p):fq.digest(p) for p in sources}, initial_poses_sha256=fq.digest(args.out/'inputs/poses.npz'),
        initial_geometry={str(n):geometry_sha(p) for n, p in poses.items()}, initial_sides=original,
        actual_control_sha256=fq.digest(args.control), workers=1, seconds=args.seconds,
        whole_trial_seconds=28., local_stage_inclusive_cap=12., global_release=RELEASE_OPTIONS,
        modes=MODES, target_order=SCHEDULE, maximum_trials=args.max_trials,
        retention='Every fully certified local intermediate is immutable before global release; all certified near-best release variants retained.',
        no_submission=True)
    atom_json(args.out/'manifest.json', manifest)
    records, retained, candidates = [], {}, {}
    best = {n:p.copy() for n, p in poses.items()}; best_side = dict(original)
    def checkpoint(status):
        atom_json(args.out/'results.json', records)
        atom_json(args.out/'candidates.json', candidates)
        atom_npz(args.out/'donors.npz', retained)
        summary = dict(status=status, elapsed_seconds=time.monotonic()-ENTRY_STARTED,
            stages=len(records), certified_variants=len(retained), improved_cases=len(candidates),
            score_gain=sum((original[int(n)]-float(v['side']))/math.sqrt(int(n)) for n,v in candidates.items()),
            statuses=dict(Counter(r['status'] for r in records)),
            donors_sha256=fq.digest(args.out/'donors.npz'), candidates_sha256=fq.digest(args.out/'candidates.json'),
            results_sha256=fq.digest(args.out/'results.json'), manifest_sha256=fq.digest(args.out/'manifest.json'))
        atom_json(args.out/'summary.json', summary)
        return summary
    def retain(record, q):
        if q is None:
            return
        n = len(q); identity = f'{math.floor(side(q))}_{math.floor(side(q))}_{n-math.floor(side(q))**2}__full_local_'+geometry_sha(q)
        path = args.out/'retained'/(identity+'.npz')
        if not path.exists():
            atom_npz(path, {identity:q}); atom_json(path.with_suffix('.json'), dict(record,
                archive_sha256=fq.digest(path), manifest_sha256=fq.digest(args.out/'manifest.json')))
            path.chmod(0o444); path.with_suffix('.json').chmod(0o444)
        retained[identity] = q.copy()
        if record['side'] < best_side[n]-1e-8:
            best[n], best_side[n] = q.copy(), record['side']
            candidates[str(n)] = dict(side=record['certificate']['independent_raw']['side_upper'],
                squares=[[format(float(v), '.17g') for v in row] for row in q],
                source='Full-puzzle local aspect continuation and contact release',
                certificate=record['certificate'], provenance=dict(record_path=str(path.with_suffix('.json')),
                    record_sha256=fq.digest(path.with_suffix('.json')), geometry_sha256=geometry_sha(q)))
    checkpoint('configured')
    visits = Counter(); cooperative_stop = False
    for trial in range(args.max_trials):
        if (args.out/'STOP').exists():
            cooperative_stop = True
            break
        if time.monotonic() >= deadline-3:
            break
        n = SCHEDULE[trial % len(SCHEDULE)]; visit = visits[n]; visits[n] += 1
        amplitude, count, hold = MODES[visit % len(MODES)]
        seed = 9278200+trial; p = best[n].copy()
        frozen, selection = local_selection(p, seed, count, visit)
        trial_deadline = min(deadline, time.monotonic()+28.)
        previous = signal.signal(signal.SIGALRM, alarm)
        signal.setitimer(signal.ITIMER_REAL, max(.001, trial_deadline-time.monotonic()))
        try:
            record, q = run_stage(p, original[n], 'local', soft_options(amplitude, hold, frozen), seed,
                binary, (args.out/'trials').resolve(), 12., trial_deadline)
            record.update(trial=trial, selection=selection, amplitude=amplitude, hold=hold)
            if q is not None:
                record['geometry_change'] = displacement(p, q, selection)
            records.append(record); retain(record, q); checkpoint('running')
            print(json.dumps({k:record[k] for k in ('n','mode','status','trial','elapsed_seconds') if k in record}), flush=True)
            if (args.out/'STOP').exists():
                cooperative_stop = True
                break
            if q is not None and time.monotonic() < trial_deadline-1:
                released, final = run_stage(q, original[n], 'release', RELEASE_OPTIONS, seed, binary,
                    (args.out/'trials').resolve(), trial_deadline-time.monotonic(), trial_deadline)
                released.update(trial=trial, source_local_geometry_sha256=geometry_sha(q), selection=selection)
                if final is not None:
                    released['geometry_change'] = displacement(p, final, selection)
                records.append(released); retain(released, final); checkpoint('running')
                print(json.dumps({k:released[k] for k in ('n','mode','status','trial','elapsed_seconds') if k in released}), flush=True)
        except Deadline:
            records.append(dict(n=n, trial=trial, mode='composite', status='whole-trial-timeout'))
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, previous)
        checkpoint('running')
    if fq.digest(args.baseline) != baseline_sha or fq.digest(binary) != manifest['binary_sha256']:
        raise ValueError('Frozen source changed during search')
    print(json.dumps(checkpoint('cooperatively_stopped' if cooperative_stop else 'complete')), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--official-report', type=Path, required=True)
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--control', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--seconds', type=float, default=590.)
    parser.add_argument('--max-trials', type=int, default=72)
    args = parser.parse_args()
    if args.out.exists() or not 20 <= args.seconds <= 595 or not 1 <= args.max_trials <= 72:
        parser.error('New output directory, 20–595s and 1–72 trials required')
    process = mp.get_context('fork').Process(target=campaign, args=(args,)); process.start()
    process.join(max(0., args.seconds-(time.monotonic()-ENTRY_STARTED)))
    enforced = process.is_alive()
    if enforced:
        process.terminate(); process.join(1.)
        if process.is_alive():
            process.kill(); process.join(.5)
    receipt = dict(elapsed_seconds=time.monotonic()-ENTRY_STARTED, exitcode=process.exitcode,
                   hard_deadline_enforced=enforced, workers=1)
    if args.out.exists():
        atom_json(args.out/'supervisor.json', receipt)
    print(json.dumps(receipt), flush=True)
    if process.exitcode:
        raise SystemExit(process.exitcode)


if __name__ == '__main__':
    main()
