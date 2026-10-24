"""Bounded two-CPU FQ polishing of frozen gentle and FQ donor variants.

Polish every distinct input before using remaining time for randomized small
kicks of the current best bank. Gains always use the frozen FQ best bank as
their reference, independently of whether a trial improved its own parent.
"""
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
import argparse
from collections import Counter, defaultdict, deque
import hashlib
import json
import os
from pathlib import Path
import shutil
import time

import numpy as np

from fq_active_pilot import SOURCE_COMMIT, MODES, bloat, digest, trial


def geometry_sha(p):
    return hashlib.sha256(np.asarray(p, dtype='<f8').tobytes()).hexdigest()


def atomic_json(path, value):
    temporary = path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')
    temporary.replace(path)


def atomic_npz(path, values):
    temporary = path.with_suffix(path.suffix+'.tmp')
    with temporary.open('wb') as stream:
        np.savez_compressed(stream, **values)
    temporary.replace(path)


def load_poses(path):
    poses = {}
    with np.load(path, allow_pickle=False) as archive:
        for name in archive.files:
            key = name.split('__')[0]
            w, h, d = map(int, key.split('_'))
            p = np.asarray(archive[name], dtype=np.float64)
            if p.shape != (w*h+d, 3) or not np.isfinite(p).all():
                raise ValueError(f'Invalid source pose: {path}:{name}')
            poses[name] = p.copy()
    return poses


def interleave_sources(sources, priorities):
    groups = defaultdict(list)
    for source in sources:
        groups[source['key']].append(source)
    queues = {key: deque(sorted(values, key=lambda s: (s['parent_excess'], s['geometry_sha256'])))
              for key, values in groups.items()}
    keys = sorted(queues, key=lambda key: (-priorities.get(key, 0.), key))
    pending = deque()
    while any(queues.values()):
        for key in keys:
            if queues[key]:
                pending.append(queues[key].popleft())
    return pending


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--binary', type=Path, required=True)
    ap.add_argument('--reference', type=Path, required=True)
    ap.add_argument('--gentle', type=Path, required=True)
    ap.add_argument('--fq-donors', type=Path, required=True)
    ap.add_argument('--priorities', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--seconds', type=float, default=590.)
    ap.add_argument('--trial-seconds', type=float, default=20.)
    ap.add_argument('--workers', type=int, default=2)
    ap.add_argument('--max-trials', type=int, default=0, help='Optional smoke-test limit; zero uses time budget')
    ap.add_argument('--seed', type=int, default=761001)
    args = ap.parse_args()
    if (not 5 < args.seconds <= 600 or not 0 < args.trial_seconds <= 20
            or not 1 <= args.workers <= 2 or args.max_trials < 0):
        ap.error('Require 5 < seconds <= 600, 0 < trial-seconds <= 20, and 1-2 workers')
    started = time.monotonic()
    deadline = started+args.seconds-3.  # Retain a small final checkpoint allowance.
    args.out.mkdir(parents=True, exist_ok=False)
    inputs = args.out/'inputs'
    inputs.mkdir()
    trials = args.out/'trials'
    trials.mkdir()
    paths = {'reference': args.reference, 'gentle': args.gentle,
             'fq_donors': args.fq_donors, 'priorities': args.priorities}
    input_manifest = {}
    for label, path in paths.items():
        destination = inputs/(label+path.suffix)
        shutil.copyfile(path, destination)
        input_manifest[label] = {'original_path': str(path), 'snapshot': str(destination),
                                 'sha256': digest(destination)}
        destination.chmod(0o444)
    priorities = json.loads((inputs/'priorities.json').read_text())
    reference = load_poses(inputs/'reference.npz')
    if any('__' in key for key in reference):
        raise ValueError('Reference bank must have one unadorned key per rectangle type')
    reference_excess = {key: bloat(p, *map(int, key.split('_')[:2])) for key, p in reference.items()}
    best = {key: p.copy() for key, p in reference.items()}
    best_excess = dict(reference_excess)
    sources, input_counts, source_poses = [], {}, {}
    for label in ['gentle', 'fq_donors']:
        variants = load_poses(inputs/(label+'.npz'))
        input_counts[label] = len(variants)
        for name, p in variants.items():
            key = name.split('__')[0]
            if key not in reference:
                raise ValueError(f'Source type is absent from frozen reference: {key}')
            sha = geometry_sha(p)
            identity = key+'__'+sha
            if identity in source_poses:
                continue
            source_poses[identity] = p
            sources.append({'key': key, 'source_archive': label, 'source_name': name,
                'geometry_sha256': sha, 'source_identity': identity,
                'parent_excess': bloat(p, *map(int, key.split('_')[:2]))})
    pending = interleave_sources(sources, priorities)
    all_keys = sorted(best, key=lambda key: (-priorities.get(key, 0.), key))
    manifest = {'status': 'running', 'source_repository': 'https://github.com/evand/square-packing',
        'source_commit': SOURCE_COMMIT, 'license': 'MIT', 'inputs': input_manifest,
        'binary_sha256': digest(args.binary), 'trial_module_sha256': digest(Path(__file__).with_name('fq_active_pilot.py')),
        'campaign_module_sha256': digest(__file__), 'input_counts': input_counts,
        'distinct_polish_inputs': len(sources), 'source_records': sources,
        'reference_excess_by_key': reference_excess, 'seconds': args.seconds,
        'trial_seconds': args.trial_seconds, 'workers': args.workers, 'seed': args.seed,
        'max_trials': args.max_trials, 'modes': {key: MODES[key] for key in ['polish', 'kick']},
        'budget_note': 'Binary calls share a monotonic deadline and are capped at 20 seconds. No more than two calls run concurrently. Final checkpoint allowance is three seconds.',
        'scoring_note': 'Component excess improvements only; no full competition score claim.'}
    atomic_json(args.out/'manifest.json', manifest)
    records, donors, best_records = [], {}, {}
    snapshot_number, submitted, kicks = 0, 0, 0
    last_checkpoint = started

    def checkpoint(status):
        nonlocal snapshot_number, last_checkpoint
        snapshot_number += 1
        directory = args.out/f'snapshot-{snapshot_number:05d}'
        directory.mkdir()
        atomic_npz(directory/'donors.npz', donors)
        atomic_npz(directory/'best_bank.npz', best)
        atomic_json(directory/'results.json', records)
        improvements = {key: {'reference_excess': reference_excess[key], 'best_excess': best_excess[key],
            'gain': reference_excess[key]-best_excess[key], 'geometry_sha256': geometry_sha(best[key]),
            'record': best_records.get(key)} for key in best if reference_excess[key]-best_excess[key] > 5e-9}
        report = {'status': status, 'elapsed_seconds': time.monotonic()-started,
            'trials_submitted': submitted, 'trials_completed': len(records),
            'status_counts': dict(Counter(r['status'] for r in records)),
            'mode_counts': dict(Counter(r['mode'] for r in records)),
            'certified_variants': len(donors), 'strict_improving_types': len(improvements),
            'improvements': improvements, 'polish_inputs_remaining': len(pending),
            'frozen_reference_sha256': input_manifest['reference']['sha256'],
            'manifest_sha256': digest(args.out/'manifest.json'),
            'donors_sha256': digest(directory/'donors.npz'),
            'best_bank_sha256': digest(directory/'best_bank.npz'),
            'results_sha256': digest(directory/'results.json'),
            'note': 'Every new donor has official raw and pandas-roundtrip certification. Gains compare to the immutable FQ best bank; full composition has not been scored.'}
        atomic_json(directory/'analysis.json', report)
        for path in directory.iterdir():
            path.chmod(0o444)
        atomic_json(args.out/'current.json', {'snapshot': str(directory),
            'analysis_sha256': digest(directory/'analysis.json'), 'status': status})
        last_checkpoint = time.monotonic()
        return report

    def next_job():
        nonlocal submitted, kicks
        if time.monotonic() >= deadline-1 or (args.max_trials and submitted >= args.max_trials):
            return None
        # Drain all polish inputs before spending remaining time on kicks.
        if pending:
            parent = pending.popleft()
            pose = source_poses[parent['source_identity']]
            mode = 'polish'
        else:
            key = all_keys[kicks % len(all_keys)]
            kicks += 1
            pose = best[key].copy()
            parent = {'key': key, 'source_archive': 'campaign_best', 'source_name': key,
                'geometry_sha256': geometry_sha(pose), 'parent_excess': best_excess[key]}
            mode = 'kick'
        seed = args.seed+submitted
        submitted += 1
        metadata = {**parent, 'trial_id': submitted, 'seed': seed, 'mode': mode,
                    'reference_excess': reference_excess[parent['key']]}
        job = (parent['key'], pose, mode, str(args.binary.resolve()), str(trials.resolve()),
               seed, args.trial_seconds, deadline)
        return job, metadata

    checkpoint('running')
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        active = {}
        while True:
            while len(active) < args.workers:
                item = next_job()
                if item is None:
                    break
                job, metadata = item
                active[pool.submit(trial, job)] = metadata
            if not active:
                break
            done, _ = wait(active, timeout=.5, return_when=FIRST_COMPLETED)
            for future in done:
                parent = active.pop(future)
                try:
                    raw_record, donor = future.result()
                except Exception as error:
                    raw_record, donor = {'key': parent['key'], 'mode': parent['mode'],
                        'seed': parent['seed'], 'status': 'exception', 'error': repr(error)}, None
                record = {**raw_record, 'trial_id': parent['trial_id'],
                    'parent_geometry_sha256': parent['geometry_sha256'],
                    'parent_source_archive': parent['source_archive'], 'parent_source_name': parent['source_name'],
                    'reference_excess': parent['reference_excess']}
                improvement = False
                if donor is not None:
                    _, q = donor
                    sha = geometry_sha(q)
                    key = record['key']
                    after = bloat(q, *map(int, key.split('_')[:2]))
                    if (sha != record['geometry_sha256'] or not record['certificate']['valid']
                            or abs(after-record['after']) > 1e-12):
                        raise ValueError('Trial result does not match its certified geometry record')
                    identity = key+'__fqv_'+sha
                    donors[identity] = q.copy()
                    gain = reference_excess[key]-after
                    record.update(archive_key=identity, reference_gain=gain,
                                  strict_reference_improvement=gain > 5e-9)
                    if after < best_excess[key]:
                        improvement = best_excess[key]-after > 5e-9
                        best[key], best_excess[key] = q.copy(), after
                        best_records[key] = {'trial_id': record['trial_id'], 'archive_key': identity,
                            'geometry_sha256': sha, 'reference_gain': gain,
                            'parent_geometry_sha256': parent['geometry_sha256'], 'mode': record['mode']}
                records.append(record)
                print(json.dumps({key: value for key, value in record.items()
                    if key not in ('fq', 'certificate')}, allow_nan=False), flush=True)
                if improvement or len(records) % 10 == 0 or time.monotonic()-last_checkpoint > 20:
                    checkpoint('running')
    report = checkpoint('completed')
    # Convenience outputs are atomic copies; current.json names the immutable bundle.
    final_directory = args.out/f'snapshot-{snapshot_number:05d}'
    for name in ['donors.npz', 'best_bank.npz', 'results.json', 'analysis.json']:
        temporary = args.out/(name+'.tmp')
        shutil.copyfile(final_directory/name, temporary)
        os.replace(temporary, args.out/name)
    print(json.dumps({'stage': 'campaign complete', **report}), flush=True)


if __name__ == '__main__':
    main()
