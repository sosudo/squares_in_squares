"""Matched LP20 versus proven ALM release on exact saved winning intermediates."""
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import json
import multiprocessing as mp
import os
from pathlib import Path
import shutil
import signal
import sys
import time

import numpy as np

import fq_active_pilot as fq
from fq_capacity_probe import full_certificate
from fq_variant_campaign import atomic_json, atomic_npz, geometry_sha

OPTIONS = {
    'release_lp20': ['--no-alm', '--loosen', '1', '--pit', '20', '--flip-top', '0'],
    'release_alm45': ['--loosen', '1', '--outer', '45', '--pit', '100', '--flip-top', '16'],
}


def release_trial(job, current_minimum):
    key, pose, mode, _, _, _, _, _ = job
    fq.MODES[mode] = list(OPTIONS[mode])
    record, donor = fq.trial(job)
    record.update(source_geometry_sha256=geometry_sha(pose), command_options=OPTIONS[mode],
                  current_reference_excess=current_minimum)
    if donor is not None:
        _, q = donor
        certificate = full_certificate(q)
        record['full_certificate'] = certificate
        if not certificate['valid']:
            return {**record, 'status': 'failed-full-certificate'}, None
        record['current_reference_gain'] = current_minimum-record['after']
        record['strict_current_reference_improvement'] = record['current_reference_gain'] > 5e-9
    return record, donor


def control(args):
    os.setsid()
    started = time.monotonic(); deadline = started+args.seconds-5
    args.out.mkdir(parents=True)
    inputs = args.out/'inputs'; inputs.mkdir()
    trials = args.out/'trials'; trials.mkdir()
    sources = args.out/'source'; sources.mkdir()
    binary = inputs/'fq'; shutil.copyfile(args.binary, binary); binary.chmod(0o500)
    source_paths = [Path(__file__), Path(fq.__file__),
        Path(sys.modules['fq_capacity_probe'].__file__), Path(sys.modules['fq_variant_campaign'].__file__),
        Path(sys.modules['compose_gadgets'].__file__), Path(sys.modules['score_official'].__file__),
        Path(sys.modules['validate_submission'].__file__), fq.ROOT/'research/official_metric_v17.py']
    source_hashes = {}
    for index, src in enumerate(source_paths):
        dst = sources/f'{index:02d}-{src.name}'; shutil.copyfile(src, dst); dst.chmod(0o444)
        source_hashes[str(src)] = {'snapshot': str(dst), 'sha256': fq.digest(dst)}
    snapshot = Path(json.loads((args.previous_run/'final.json').read_text())['snapshot'])
    previous = json.loads((snapshot/'results.json').read_text())
    reference_path = inputs/'current_reference.npz'
    shutil.copyfile(args.reference, reference_path); reference_path.chmod(0o444)
    with np.load(reference_path, allow_pickle=False) as archive:
        references = {key: fq.bloat(archive[key], *map(int, key.split('_')[:2])) for key in archive.files}
    poses, input_records, jobs = {}, [], []
    for trial_id in [19, 200]:
        prior = next(record for record in previous if record['trial_id'] == trial_id)
        proof = prior['strict_intermediate']
        if fq.digest(proof['archive_path']) != proof['archive_sha256']:
            raise ValueError('Saved intermediate archive hash mismatch')
        with np.load(proof['archive_path'], allow_pickle=False) as archive:
            pose = archive[archive.files[0]].copy()
        if geometry_sha(pose) != proof['geometry_sha256'] or not proof['certificate']['valid']:
            raise ValueError('Saved intermediate geometry/certificate mismatch')
        initial_certificate = full_certificate(pose)
        if not initial_certificate['valid']:
            raise ValueError('Matched starting pose fails full gates')
        key = prior['key']; poses[key] = pose
        input_records.append({'key': key, 'original_trial_id': trial_id, 'seed': prior['seed'],
            'source_archive': proof['archive_path'], 'source_archive_sha256': proof['archive_sha256'],
            'geometry_sha256': geometry_sha(pose), 'source_certificate': initial_certificate,
            'old_parent_excess': prior['before'], 'intermediate_excess': fq.bloat(pose, *map(int, key.split('_')[:2])),
            'old_released_excess': prior['after'], 'current_reference_excess': references[key]})
        for mode in OPTIONS:
            jobs.append(((key, pose.copy(), mode, str(binary.resolve()), str(trials.resolve()),
                          prior['seed'], 20., deadline), references[key]))
    atomic_npz(inputs/'intermediates.npz', poses); (inputs/'intermediates.npz').chmod(0o444)
    atomic_json(args.out/'manifest.json', {'source_hashes': source_hashes,
        'binary_sha256': fq.digest(binary), 'intermediates_sha256': fq.digest(inputs/'intermediates.npz'),
        'current_reference_sha256': fq.digest(reference_path), 'previous_results_sha256': fq.digest(snapshot/'results.json'),
        'source_commit': fq.SOURCE_COMMIT, 'inputs': input_records, 'modes': OPTIONS,
        'seconds': args.seconds, 'workers': 2, 'native_cap_seconds': 20,
        'note': 'Each pair uses identical exact coordinates, binary and seed. Parent-relative recovery and current-reference improvement are reported separately. Full official raw/pandas plus independent interval gates remain required.'})
    records, donors = [], {}
    with ProcessPoolExecutor(max_workers=2) as pool:
        active = {pool.submit(release_trial, *job): job for job in jobs}
        for future in as_completed(active):
            try:
                record, donor = future.result()
            except Exception as error:
                job, reference = active[future]
                record, donor = {'key': job[0], 'mode': job[2], 'status': 'exception',
                                 'error_type': type(error).__name__}, None
            if donor is not None:
                _, pose = donor
                name = record['key']+'__matched_'+record['mode']+'_'+geometry_sha(pose)
                donors[name] = pose.copy(); record['archive_key'] = name
            records.append(record)
            atomic_json(args.out/'results.json', records); atomic_npz(args.out/'donors.npz', donors)
            print(json.dumps({key: value for key, value in record.items()
                              if key not in ['fq', 'certificate', 'full_certificate']}), flush=True)
    summary = {'elapsed_seconds': time.monotonic()-started, 'trials': len(records),
        'certified_variants': len(donors), 'manifest_sha256': fq.digest(args.out/'manifest.json'),
        'results_sha256': fq.digest(args.out/'results.json'), 'donors_sha256': fq.digest(args.out/'donors.npz'),
        'pairs': {key: {record['mode']: {field: record.get(field) for field in
                  ['status', 'before', 'after', 'gain', 'current_reference_gain', 'strict_current_reference_improvement']}
                  for record in records if record['key'] == key} for key in poses}}
    atomic_json(args.out/'summary.json', summary)
    for path in args.out.glob('*.json'): path.chmod(0o444)
    (args.out/'donors.npz').chmod(0o444)
    print(json.dumps(summary), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--previous-run', type=Path, required=True)
    parser.add_argument('--reference', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--seconds', type=float, default=120)
    args = parser.parse_args()
    if not 30 <= args.seconds <= 120 or args.out.exists():
        parser.error('Require a new directory and a30–120s outer budget')
    started = time.monotonic()
    child = mp.get_context('fork').Process(target=control, args=(args,)); child.start()
    child.join(timeout=max(0., args.seconds-2-(time.monotonic()-started)))
    killed = child.is_alive()
    if killed:
        os.killpg(child.pid, signal.SIGKILL); child.join(timeout=1)
    if args.out.exists():
        atomic_json(args.out/'supervisor.json', {'elapsed_seconds': time.monotonic()-started,
            'hard_deadline_enforced': killed, 'exitcode': child.exitcode, 'configured_seconds': args.seconds})
    if child.exitcode and not killed:
        raise SystemExit(child.exitcode)


if __name__ == '__main__':
    main()
