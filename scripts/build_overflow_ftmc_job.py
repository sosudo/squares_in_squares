"""Prepare a self-contained two-arm angle/capacity pilot, without launching it."""
from __future__ import annotations

import argparse
import base64
import io
import json
from pathlib import Path
import sys
import zipfile

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'experiments'))
from ftmc_frontier_bank import build_frontier_bank
from full_puzzle_bank import build_full_puzzle_bank, read_packings
from ftmc_overflow_capture import potential_targets
from build_full_puzzle_ftmc_job import digest, npz_bytes, validate_seeds, METRIC_HASH


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path, default=ROOT/'artifacts/submission-gpu-composition-safe.csv')
    parser.add_argument('--baseline-report', type=Path, default=ROOT/'artifacts/submission-gpu-composition-safe-official.json')
    parser.add_argument('--active-dir', type=Path, default=ROOT/'artifacts/active-frontier')
    parser.add_argument('--source-dir', type=Path, default=ROOT/'vendor/lightning_ftmc')
    parser.add_argument('--out', type=Path, default=ROOT/'artifacts/overflow-ftmc-job')
    parser.add_argument('--slug', default='sos54352/squares-overflow-ftmc-pilot')
    parser.add_argument('--title', default='Squares Overflow FTMC Pilot')
    parser.add_argument('--capture-seconds', type=int, default=300)
    parser.add_argument('--repair-seconds', type=int, default=300)
    parser.add_argument('--grace-seconds', type=int, default=60)
    parser.add_argument('--wall-seconds', type=int, default=1000)
    parser.add_argument('--replicas', type=int, default=64)
    parser.add_argument('--repair-max-cores', type=int, default=16)
    parser.add_argument('--repair-copies', type=int, default=8)
    parser.add_argument('--full-controls', default='87,129,180,300')
    parser.add_argument('--max-code-bytes', type=int, default=1_000_000)
    args = parser.parse_args()
    if (min(args.capture_seconds, args.repair_seconds) <= 0 or args.grace_seconds < 0
            or args.wall_seconds < args.capture_seconds+args.repair_seconds+2*args.grace_seconds+120
            or not 1 <= args.replicas <= 256 or not 1 <= args.repair_max_cores <= 64
            or not 1 <= args.repair_copies <= 32):
        raise ValueError('Invalid bounded experiment budgets')
    baseline_hash = digest(args.baseline.read_bytes())
    report = json.loads(args.baseline_report.read_text())
    if not (report.get('sha256') == baseline_hash and report.get('valid') is True
            and report.get('invalid_count') == 0 and report.get('puzzles') == 1000
            and report.get('metric_sha256') == METRIC_HASH):
        raise ValueError('Baseline must have its matching complete official certificate')
    packings = read_packings(args.baseline)
    baseline_sides = {str(n): side for n, (_, side) in packings.items()}
    bank, variants, provenance, resume, _, active_review = build_frontier_bank(
        args.active_dir/'active_seed_variants.npz', [], args.active_dir/'active_priorities.json',
        args.active_dir/'active_targets.json', baseline_hash)
    if resume:
        raise ValueError('No historical checkpoint may overwrite current incumbents')
    active_keys = sorted(bank)
    full_bank, full_variants, full_provenance, _, full_review = build_full_puzzle_bank(args.baseline)
    full_ns = {int(n) for n in args.full_controls.split(',') if n}
    full_keys = []
    for key, entry in full_provenance.items():
        if entry['n'] in full_ns:
            if key in bank:
                raise ValueError('Control and active target keys must remain disjoint')
            bank[key] = full_bank[key]
            variants[key+'__full_control'] = full_bank[key]
            provenance[key] = {**entry, 'experimental_role': 'negative_full_puzzle_control'}
            full_keys.append(key)
    if set(full_ns) != {full_provenance[key]['n'] for key in full_keys}:
        raise ValueError('A requested full control is not in the certified diverse bank')
    priorities = {}
    targeting = {}
    for key in active_keys:
        w, h, surplus = map(int, key.split('_'))
        q = bank[key]
        e = .5*(np.abs(np.cos(q[:, 2]))+np.abs(np.sin(q[:, 2])))
        dims = (q[:, :2]+e[:, None]).max(axis=0)-(q[:, :2]-e[:, None]).min(axis=0)
        f = float(max(dims-[w, h]))
        targets = potential_targets(w, h, surplus, min(.995, f+.035), baseline_sides)
        loose = sum(t['gain_at_loose_box'] for t in targets)
        hypothetical = sum(t['gain_after_hypothetical_04_shrink'] for t in targets)
        value = loose+.25*hypothetical
        priorities[key] = value
        targeting[key] = {'current_bloat': f, 'targets': targets,
            'loose_box_gain_sum': loose, 'hypothetical_04_shrink_gain_sum': hypothetical,
            'scheduling_value': value, 'note': 'Hypothetical scheduling estimates, not achieved gains.'}
    peak = max(priorities.values())
    if peak <= 0:
        raise ValueError('No active overflow target has useful estimated score potential')
    # Give every active family a small exploration floor before the public
    # sampler's own visit-balancing. Both arms receive exactly this same bank.
    priorities = {key: max(.03, value/peak) for key, value in priorities.items()}
    active_weight = sum(.08+100*value for value in priorities.values())
    if full_keys:
        control_weight = active_weight*(.08/.92)/len(full_keys)
        for key in full_keys:
            priorities[key] = max(0., (control_weight-.08)/100)
    initial_control_mass = (sum(.08+100*priorities[key] for key in full_keys)
        /sum(.08+100*value for value in priorities.values())) if full_keys else 0.
    if initial_control_mass > .1:
        raise ValueError('Full-puzzle controls exceed their initial sampling budget')
    validation = validate_seeds(bank)
    data = {}
    for path in sorted(args.source_dir.rglob('*')):
        if path.is_file() and '__pycache__' not in path.parts:
            data[str(path.relative_to(args.source_dir))] = path.read_bytes()
    source_manifest = json.loads(data['SOURCE_MANIFEST.json'])
    for name, expected in source_manifest['files'].items():
        if name not in data or digest(data[name]) != expected:
            raise ValueError('Attributed public source changed: ' + name)
    if digest(data['research/official_metric.py']) != METRIC_HASH:
        raise ValueError('Worker metric does not match the pinned official metric')
    local_modules = ['ftmc_overflow_capture.py', 'ftmc_overflow_repair.py', 'ftmc_overflow_worker.py',
                     'ftmc_adaptive_angles.py', 'ftmc_funnel_metrics.py', 'ftmc_sampling_cap.py']
    for name in local_modules:
        data[name] = (ROOT/'experiments'/name).read_bytes()
    seed_review = {'baseline_sha256': baseline_hash, 'active_keys': active_keys,
        'full_control_keys': sorted(full_keys), 'full_control_n': sorted(full_ns),
        'initial_control_sampling_mass': initial_control_mass, 'maximum_control_sampling_mass': .1,
        'same_bank_and_sampling_policy_both_arms': True, 'resume_disabled': True,
        'historical_incumbent_overwrite_disabled': True, 'active_targeting': targeting,
        'provenance': provenance, 'active_source_review': active_review,
        'baseline_official_report_sha256': digest(args.baseline_report.read_bytes()),
        'validation': validation}
    data.update({'artifacts/night_seed_gadgets.npz': npz_bytes(bank),
        'artifacts/night_seed_variants.npz': npz_bytes(variants),
        'research/night_priorities.json': json.dumps(priorities, indent=2).encode(),
        'research/night_seed_provenance.json': json.dumps(provenance, indent=2).encode(),
        'baseline_sides.json': json.dumps(baseline_sides).encode(),
        'full_control_keys.json': json.dumps(sorted(full_keys)).encode(),
        'seed_review.json': json.dumps(seed_review, indent=2).encode()})
    for name, payload in data.items():
        if name.endswith('.py'):
            compile(payload, name, 'exec')
        if b'KGAT_' in payload:
            raise ValueError('Credential-shaped payload bytes are forbidden')
    manifest = {'source': source_manifest['source'], 'source_version': source_manifest['version'],
        'source_license': 'Apache-2.0 with retained notices', 'baseline_sha256': baseline_hash,
        'baseline_official_score': report['score'], 'devices': [0, 1],
        'capture_seconds': args.capture_seconds, 'repair_seconds': args.repair_seconds,
        'grace_seconds': args.grace_seconds, 'wall_seconds': args.wall_seconds,
        'replicas': args.replicas, 'repair_max_cores': args.repair_max_cores,
        'repair_copies': args.repair_copies, 'active_seed_types': len(active_keys),
        'full_control_types': len(full_keys), 'initial_control_sampling_mass': initial_control_mass,
        'maximum_control_sampling_mass': .1,
        'device_configs': {'0': {'angle_aware': True, 'capture_seed': 94009, 'repair_seed': 114013},
                           '1': {'angle_aware': False, 'capture_seed': 104011, 'repair_seed': 124019}},
        'experimental_difference': 'Incumbent-aware angle library on device0 versus unchanged public angle library on device1; distinct RNG streams, identical bank/sampler/capture/repair policies.',
        'quota_expectation': {'nominal_device_hours': 2*(args.capture_seconds+args.repair_seconds)/3600,
            'hard_parent_wall_hours': args.wall_seconds/3600,
            'note': 'Arithmetic device-hours only; inspect Kaggle actual quota separately.'},
        'archive_status': 'Overflow cores remain explicitly exploratory until full repair and official raw/roundtrip certification.',
        'input_attachments': [], 'slug': args.slug,
        'embedded_sha256': {name: digest(payload) for name, payload in data.items()}}
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, payload in data.items():
            archive.writestr(name, payload)
    runtime = (ROOT/'experiments/ftmc_overflow_runtime.py').read_text()
    script = ('# Private bounded angle/capacity A/B pilot. No credentials embedded.\nCONFIG = '
        +repr(manifest)+'\nPAYLOAD = '+repr(base64.b64encode(stream.getvalue()).decode())+'\n'+runtime)
    compile(script, 'search.py', 'exec')
    code_bytes = len(script.encode())
    if code_bytes >= args.max_code_bytes:
        raise ValueError('Generated source exceeds Kaggle source limit')
    metadata = {'id': args.slug, 'title': args.title, 'code_file': 'search.py', 'language': 'python',
        'kernel_type': 'script', 'is_private': True, 'enable_gpu': True, 'enable_internet': False,
        'enable_tpu': False, 'dataset_sources': [], 'kernel_sources': [],
        'competition_sources': ['squares-in-squares'], 'machine_shape': 'NvidiaTeslaT4'}
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out/'search.py').write_text(script)
    (args.out/'kernel-metadata.json').write_text(json.dumps(metadata, indent=2)+'\n')
    (args.out/'job_manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    (args.out/'seed_review.json').write_text(json.dumps(seed_review, indent=2)+'\n')
    (args.out/'seed_validation.json').write_text(json.dumps(validation, indent=2)+'\n')
    print(json.dumps({'built': str(args.out), 'source_bytes': code_bytes,
        'script_sha256': digest(script.encode()), 'active_types': len(active_keys),
        'full_controls': sorted(full_ns), 'initial_control_mass': initial_control_mass,
        'capture_seconds_per_device': args.capture_seconds, 'repair_seconds_per_device': args.repair_seconds,
        'wall_seconds': args.wall_seconds, 'private': True, 'internet': False,
        'all_seeds_raw_and_roundtrip_valid': True, 'launched': False}))


if __name__ == '__main__':
    main()
