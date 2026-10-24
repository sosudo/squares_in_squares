"""Supervised multiscale FQ search over a frozen certified rectangle bank."""
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
import argparse
from collections import Counter, defaultdict
import json
import multiprocessing as mp
import os
from pathlib import Path
import shutil
import signal
import time

import numpy as np

import fq_active_pilot as fq
from fq_variant_campaign import atomic_json, atomic_npz, geometry_sha, load_poses


KICK_OPTIONS = {
    'kick_003': ['--loosen', '1.001', '--kick', '.003', '--outer', '35', '--pit', '80', '--flip-top', '12'],
    'kick_010': ['--loosen', '1.001', '--kick', '.01', '--outer', '35', '--pit', '80', '--flip-top', '12'],
    'kick_030': ['--loosen', '1.001', '--kick', '.03', '--outer', '45', '--pit', '80', '--flip-top', '12'],
    'kick_080': ['--loosen', '1.001', '--kick', '.08', '--outer', '45', '--pit', '80', '--flip-top', '12'],
    'round_005': ['--loosen', '1', '--round-r0', '.05', '--round-compress', '--round-steps', '12',
                  '--round-kick', '.003', '--outer', '35', '--pit', '80', '--flip-top', '12'],
    'round_015': ['--loosen', '1', '--round-r0', '.15', '--round-compress', '--round-steps', '12',
                  '--round-kick', '.01', '--outer', '35', '--pit', '80', '--flip-top', '12'],
}
MODE_SLOTS = ['kick_003', 'kick_010', 'kick_030', 'kick_080',
              'kick_010', 'kick_030', 'kick_003', 'rounded']
FOCUS = {'10_23_14': 5, '20_9_12': 3, '10_23_17': 3, '19_7_13': 3}


def configured_trial(job, options):
    """Register explicit options per call without editing the shared trial API."""
    fq.MODES[job[2]] = list(options)
    record, donor = fq.trial(job)
    return {**record, 'command_options': list(options)}, donor


def diversity_bucket(p):
    """Approximate bucket for choosing starts only; stored identities stay exact."""
    q = np.asarray(p, dtype=float).copy()
    q[:, :2] -= q[:, :2].min(axis=0)
    q[:, :2] = np.round(q[:, :2], 2)
    q[:, 2] = np.round(np.degrees((q[:, 2]+np.pi/4) % (np.pi/2)-np.pi/4), 1)
    q = q[np.lexsort((q[:, 2], q[:, 1], q[:, 0]))]
    return geometry_sha(q)


def campaign(args):
    os.setsid()  # Supervisor can stop this entire worker/subprocess group.
    started = time.monotonic()
    deadline = started+args.seconds-12.
    args.out.mkdir(parents=True, exist_ok=False)
    inputs = args.out/'inputs'; inputs.mkdir()
    trials = args.out/'trials'; trials.mkdir()
    input_manifest = {}
    for category, paths in [('reference', args.reference), ('donor', args.donors),
                            ('priorities', [args.priorities])]:
        for index, source in enumerate(paths):
            label = f'{category}_{index}'
            path = inputs/(label+source.suffix)
            shutil.copyfile(source, path); path.chmod(0o444)
            input_manifest[label] = {'original_path': str(source), 'snapshot': str(path), 'sha256': fq.digest(path)}
    binary = inputs/'fq'; shutil.copyfile(args.binary, binary); binary.chmod(0o500)
    binary_sha = fq.digest(binary)
    priorities = json.loads((inputs/'priorities_0.json').read_text())
    reference = {}
    for index in range(len(args.reference)):
        for key, pose in load_poses(inputs/f'reference_{index}.npz').items():
            if '__' in key:
                raise ValueError('Reference archives must have unadorned type keys')
            w, h, _ = map(int, key.split('_'))
            if key not in reference or fq.bloat(pose, w, h) < fq.bloat(reference[key], w, h):
                reference[key] = pose
    atomic_npz(inputs/'combined_reference.npz', reference)
    (inputs/'combined_reference.npz').chmod(0o444)
    reference_sha = fq.digest(inputs/'combined_reference.npz')
    baseline = {key: fq.bloat(p, *map(int, key.split('_')[:2])) for key, p in reference.items()}
    best = {key: p.copy() for key, p in reference.items()}; best_excess = dict(baseline)
    pools = defaultdict(dict)
    input_pose_records = []
    for index in range(len(args.donors)):
        for name, pose in load_poses(inputs/f'donor_{index}.npz').items():
            key = name.split('__')[0]
            if key not in reference:
                raise ValueError(f'Donor type absent from reference: {key}')
            excess = fq.bloat(pose, *map(int, key.split('_')[:2])); sha = geometry_sha(pose)
            input_pose_records.append({'source_archive': f'donor_{index}', 'source_name': name,
                'key': key, 'geometry_sha256': sha, 'excess': excess})
            if excess > baseline[key]+.005:
                continue
            bucket = diversity_bucket(pose)
            previous = pools[key].get(bucket)
            if previous is None or excess < previous['excess']:
                pools[key][bucket] = {'pose': pose, 'excess': excess, 'geometry_sha256': sha,
                    'source_archive': f'donor_{index}', 'source_name': name, 'bucket': bucket}
    keys = sorted(best, key=lambda key: (-priorities.get(key, 0.), key))
    key_offsets = {key: index for index, key in enumerate(keys)}
    visits = {key: 0 for key in keys}
    weights = {key: FOCUS.get(key, 1) for key in keys}
    atomic_json(inputs/'donor_pose_records.json', input_pose_records)
    (inputs/'donor_pose_records.json').chmod(0o444)
    manifest = {'status': 'configured', 'source_repository': 'https://github.com/evand/square-packing',
        'source_commit': fq.SOURCE_COMMIT, 'source_license': 'MIT', 'inputs': input_manifest,
        'frozen_binary_path': str(binary), 'binary_sha256': binary_sha,
        'trial_module_sha256': fq.digest(Path(fq.__file__)), 'campaign_module_sha256': fq.digest(__file__),
        'reference_sha256': reference_sha, 'reference_excess_by_key': baseline,
        'reference_geometry_sha256_by_key': {key: geometry_sha(p) for key, p in reference.items()},
        'input_pose_records_sha256': fq.digest(inputs/'donor_pose_records.json'),
        'mode_options': KICK_OPTIONS, 'mode_slots': MODE_SLOTS, 'priority_weights': weights,
        'diverse_buckets_by_key': {key: len(value) for key, value in pools.items()},
        'seconds': args.seconds, 'trial_seconds': args.trial_seconds, 'workers': args.workers,
        'seed': args.seed, 'max_trials': args.max_trials,
        'budget_note': 'An external supervisor enforces the entire campaign deadline, including validation and shutdown. FQ binary calls are individually capped at20s; scheduling stops12s before the configured ceiling.',
        'selection_note': 'Approximately one-quarter of starts use diverse archived poses within0.005 excess of the reference. Coarse buckets affect start selection only; all inputs and exact-SHA certified outputs are retained.'}
    atomic_json(args.out/'manifest.json', manifest)
    records, donors, best_records = [], {}, {}
    submitted = 0; checkpoint_count = 0; last_checkpoint = started

    def checkpoint(status):
        nonlocal checkpoint_count, last_checkpoint
        checkpoint_count += 1
        destination = args.out/f'snapshot-{checkpoint_count:05d}'; destination.mkdir()
        atomic_npz(destination/'donors.npz', donors); atomic_npz(destination/'best_bank.npz', best)
        atomic_json(destination/'results.json', records)
        improvements = {key: {'reference_excess': baseline[key], 'best_excess': best_excess[key],
            'gain': baseline[key]-best_excess[key], 'geometry_sha256': geometry_sha(best[key]),
            'record': best_records.get(key)} for key in keys if baseline[key]-best_excess[key] > 5e-9}
        report = {'status': status, 'elapsed_seconds': time.monotonic()-started,
            'trials_submitted': submitted, 'trials_completed': len(records),
            'certified_variants': len(donors), 'improved_types': len(improvements),
            'status_counts': dict(Counter(r['status'] for r in records)),
            'mode_counts': dict(Counter(r['mode'] for r in records)), 'visits': dict(visits),
            'improvements': improvements, 'reference_sha256': reference_sha,
            'manifest_sha256': fq.digest(args.out/'manifest.json'), 'binary_sha256': binary_sha,
            'donors_sha256': fq.digest(destination/'donors.npz'),
            'best_bank_sha256': fq.digest(destination/'best_bank.npz'),
            'results_sha256': fq.digest(destination/'results.json'),
            'note': 'New donors pass official raw and pandas-roundtrip checks. Gains compare to the frozen combined21-type reference. Full competition composition remains a separate step.'}
        atomic_json(destination/'analysis.json', report)
        for path in destination.iterdir(): path.chmod(0o444)
        atomic_json(args.out/'current.json', {'snapshot': str(destination),
            'analysis_sha256': fq.digest(destination/'analysis.json'), 'status': status})
        last_checkpoint = time.monotonic()
        return destination, report

    def next_job():
        nonlocal submitted
        if (time.monotonic() >= deadline-1 or (args.out/'STOP').exists()
                or (args.max_trials and submitted >= args.max_trials)):
            return None
        key = min(keys, key=lambda key: (visits[key]/weights[key], -priorities.get(key, 0.), key))
        visit = visits[key]; visits[key] += 1
        slot = MODE_SLOTS[(visit+key_offsets[key]) % len(MODE_SLOTS)]
        mode = slot if slot != 'rounded' else ('round_015' if (visit//8) % 2 == 0 else 'round_005')
        pool = sorted(pools[key].values(), key=lambda value: (value['excess'], value['geometry_sha256']))
        if visit % 4 == 3 and pool:
            selected = pool[(visit//4) % len(pool)]
            pose = selected['pose'].copy()
            parent = {k: selected[k] for k in ['source_archive', 'source_name', 'geometry_sha256', 'bucket']}
            parent['selection'] = 'diverse_archive'
        else:
            pose = best[key].copy()
            parent = {'source_archive': 'campaign_best', 'source_name': key,
                      'geometry_sha256': geometry_sha(pose), 'selection': 'incumbent'}
        seed = args.seed+submitted; submitted += 1
        parent.update(key=key, mode=mode, seed=seed, trial_id=submitted,
                      parent_excess=fq.bloat(pose, *map(int, key.split('_')[:2])), reference_excess=baseline[key])
        job = (key, pose, mode, str(binary.resolve()), str(trials.resolve()), seed,
               args.trial_seconds, deadline)
        return job, parent

    checkpoint('running')
    with ProcessPoolExecutor(max_workers=args.workers) as executor:
        active = {}
        while True:
            while len(active) < args.workers:
                item = next_job()
                if item is None: break
                job, parent = item
                active[executor.submit(configured_trial, job, KICK_OPTIONS[job[2]])] = parent
            if not active: break
            done, _ = wait(active, timeout=.5, return_when=FIRST_COMPLETED)
            for future in done:
                parent = active.pop(future)
                try:
                    raw, donor = future.result()
                except Exception as error:
                    raw, donor = {'status': 'exception', 'error': repr(error),
                        'key': parent['key'], 'mode': parent['mode'], 'seed': parent['seed'],
                        'command_options': KICK_OPTIONS[parent['mode']]}, None
                record = {**raw, 'trial_id': parent['trial_id'], 'parent': parent,
                          'reference_excess': parent['reference_excess'], 'binary_sha256': binary_sha,
                          'source_commit': fq.SOURCE_COMMIT}
                improved = False
                if donor is not None:
                    _, pose = donor; key = parent['key']; sha = geometry_sha(pose)
                    value = fq.bloat(pose, *map(int, key.split('_')[:2]))
                    if sha != record['geometry_sha256'] or not record['certificate']['valid'] or abs(value-record['after']) > 1e-12:
                        raise ValueError('Certified trial geometry binding failed')
                    name = key+'__fqm_'+sha; donors[name] = pose.copy()
                    record.update(archive_key=name, reference_gain=baseline[key]-value,
                                  strict_reference_improvement=baseline[key]-value > 5e-9)
                    if value < best_excess[key]:
                        improved = best_excess[key]-value > 5e-9
                        best[key], best_excess[key] = pose.copy(), value
                        best_records[key] = {'trial_id': parent['trial_id'], 'archive_key': name,
                            'geometry_sha256': sha, 'mode': parent['mode'], 'command_options': record['command_options'],
                            'parent_geometry_sha256': parent['geometry_sha256']}
                    bucket = diversity_bucket(pose)
                    previous = pools[key].get(bucket)
                    if value <= baseline[key]+.005 and (previous is None or value < previous['excess']):
                        pools[key][bucket] = {'pose': pose.copy(), 'excess': value, 'geometry_sha256': sha,
                            'source_archive': 'campaign_donors', 'source_name': name, 'bucket': bucket}
                records.append(record)
                print(json.dumps({k: v for k, v in record.items() if k not in ['fq', 'certificate']}, allow_nan=False), flush=True)
                if improved or len(records) % 10 == 0 or time.monotonic()-last_checkpoint > 20:
                    checkpoint('running')
    destination, report = checkpoint('stopped_on_request' if (args.out/'STOP').exists() else 'completed')
    atomic_json(args.out/'final.json', {'snapshot': str(destination),
        'analysis_sha256': fq.digest(destination/'analysis.json'), 'status': report['status']})
    print(json.dumps({'stage': 'campaign complete', **report}), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--reference', type=Path, action='append', required=True)
    parser.add_argument('--donors', type=Path, action='append', required=True)
    parser.add_argument('--priorities', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--seconds', type=float, default=900.)
    parser.add_argument('--trial-seconds', type=float, default=20.)
    parser.add_argument('--workers', type=int, default=2)
    parser.add_argument('--max-trials', type=int, default=0)
    parser.add_argument('--seed', type=int, default=981001)
    args = parser.parse_args()
    if (not 15 < args.seconds <= 900 or not 0 < args.trial_seconds <= 20
            or not 1 <= args.workers <= 2 or args.max_trials < 0):
        parser.error('Require 15 < seconds <= 900, 0 < trial-seconds <=20, and1-2 workers')
    if args.out.exists(): parser.error('Output directory already exists')
    started = time.monotonic()
    child = mp.get_context('fork').Process(target=campaign, args=(args,))
    child.start()
    child.join(timeout=max(0., args.seconds-2-(time.monotonic()-started)))
    enforced = child.is_alive()
    if enforced:
        # No work starts outside this child's new session/process group.
        os.killpg(child.pid, signal.SIGKILL)
        child.join(timeout=1)
    record = {'status': 'hard_deadline_enforced' if enforced else 'exited',
        'elapsed_seconds': time.monotonic()-started, 'exitcode': child.exitcode,
        'configured_seconds': args.seconds,
        'note': 'Outer supervisor includes executable copying, solving, official checks, checkpoints and worker shutdown. A forced stop leaves the latest complete immutable current.json snapshot available.'}
    if args.out.exists(): atomic_json(args.out/'supervisor.json', record)
    print(json.dumps({'stage': 'supervisor complete', **record}), flush=True)
    if child.exitcode and not enforced: raise SystemExit(child.exitcode)


if __name__ == '__main__':
    main()
