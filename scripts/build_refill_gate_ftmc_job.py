"""Prepare a bounded anchor-preserving comparison of the public MILP row gate."""
from __future__ import annotations

import argparse
import base64
import copy
import hashlib
import io
import json
from pathlib import Path
import zipfile

from build_anchor_ftmc_job import read_template, digest, ROOT


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--template', type=Path, default=ROOT/'artifacts/anchor-ftmc-job/search.py')
    parser.add_argument('--out', type=Path, default=ROOT/'artifacts/refill-gate-ftmc-job')
    parser.add_argument('--slug', default='sos54352/squares-refill-gate-pilot')
    parser.add_argument('--title', default='Squares Refill Gate Pilot')
    parser.add_argument('--seconds', type=int, default=300)
    parser.add_argument('--grace-seconds', type=int, default=60)
    parser.add_argument('--wall-seconds', type=int, default=700)
    args = parser.parse_args()
    if args.seconds <= 0 or args.grace_seconds < 0 or args.wall_seconds < args.seconds+args.grace_seconds+120:
        raise ValueError('Invalid bounded experiment settings')
    original, data, runtime = read_template(args.template)
    config = copy.deepcopy(original)
    if config['selected_n'] != [83, 86, 106, 129, 171, 205, 259, 302] or config['input_attachments']:
        raise ValueError('Expected frozen self-contained eight-seed anchor template')
    for name in ('ftmc_refill_gate.py', 'ftmc_refill_gate_worker.py', 'ftmc_refill_gate_preflight.py', 'refill_search.py'):
        data[name] = (ROOT/'experiments'/name).read_bytes()
    replacements = {
        "worker_file='ftmc_anchor_worker.py'": "worker_file='ftmc_refill_gate_worker.py'",
        "'--anchor-policy',cfg['anchor_policy']]": "'--anchor-policy',cfg['anchor_policy'],'--refill-policy',cfg['refill_policy']]",
        "worker_started=time.monotonic();deadline=worker_started+manifest['search_seconds']+manifest['grace_seconds']":
            "from ftmc_refill_gate_preflight import run as refill_gate_preflight\n"
            "atomic_json('refill_gate_preflight.json',refill_gate_preflight(bank))\n"
            "worker_started=time.monotonic();deadline=worker_started+manifest['search_seconds']+manifest['grace_seconds']"
    }
    for before, after in replacements.items():
        if runtime.count(before) != 1:
            raise ValueError('Frozen runtime interface changed; review adapter')
        runtime = runtime.replace(before, after)
    config.update(slug=args.slug, search_seconds=args.seconds, grace_seconds=args.grace_seconds,
        wall_seconds=args.wall_seconds,
        device_configs={str(device): {'device': device, 'replicas': config['replicas'],
            'seed': 105117+9973*device, 'source_rng_seed': 20261024+105117+29910*device,
            'search_seconds': args.seconds, 'resume_files': [], 'profile_guard': False,
            'anchor_policy': 'incumbent',
            'refill_policy': 'row_gate' if device == 0 else 'bounded_general'} for device in (0, 1)},
        quota_expectation={'nominal_search_wall_hours': args.seconds/3600,
            'nominal_device_hours': 2*args.seconds/3600, 'hard_wall_hours': args.wall_seconds/3600,
            'hard_device_hours': 2*args.wall_seconds/3600,
            'note': 'Arithmetic device-hours; inspect actual Kaggle quota separately.'},
        anchor_experiment={'both_arms': 'incumbent fractional wall anchor restored',
                           'angles': 'original public library on both arms'},
        refill_gate_experiment={'arm0': 'original whole-row N-4 heuristic',
            'arm1': 'up to four 2D attempts without the row-deficit filter',
            'per_attempt_alarm_seconds': 1.25, 'core_max_penetration_gate': .01,
            'whole_row_capacity_is_lower_bound': True,
            'actual_cuda_and_strict_2d_preflight': True,
            'all_geometry_and_official_admission_unchanged': True},
        template_sha256=digest(args.template.read_bytes()), runtime_sha256=digest(runtime.encode()),
        runtime_adapter='Frozen anchor supervisor with gate-worker command and bounded known-seed capacity preflight',
        embedded_sha256={name: digest(blob) for name, blob in data.items()})
    source_manifest = json.loads(data['SOURCE_MANIFEST.json'])
    for name, expected in source_manifest['files'].items():
        if digest(data[name]) != expected:
            raise ValueError('Public source changed: '+name)
    for name, blob in data.items():
        if name.endswith('.py'):
            compile(blob, name, 'exec')
        if b'KGAT_' in blob:
            raise ValueError('Credential-shaped payload forbidden')
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, blob in data.items():
            archive.writestr(name, blob)
    code = ('# Private bounded refill-gate A/B pilot; no credentials embedded.\nCONFIG = '
            +repr(config)+'\nPAYLOAD = '+repr(base64.b64encode(stream.getvalue()).decode())+'\n'+runtime)
    compile(code, 'search.py', 'exec')
    if len(code.encode()) >= 1_000_000:
        raise ValueError('Source exceeds Kaggle source limit')
    metadata = json.loads((args.template.parent/'kernel-metadata.json').read_text())
    metadata.update(id=args.slug, title=args.title)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out/'search.py').write_text(code)
    (args.out/'kernel-metadata.json').write_text(json.dumps(metadata, indent=2)+'\n')
    (args.out/'job_manifest.json').write_text(json.dumps(config, indent=2)+'\n')
    local = {'code_bytes': len(code.encode()), 'script_sha256': digest(code.encode()),
        'all_template_payload_hashes_verified': True, 'public_source_hashes_unchanged': True,
        'exact_same_eight_seed_poses': True, 'original_angle_library_both_arms': True,
        'anchor_restoration_both_arms': True, 'maximum_milp_attempts_per_batch': 4,
        'per_attempt_alarm_seconds': 1.25, 'core_residual_gate': .01,
        'nominal_seconds_per_device': args.seconds, 'grace_seconds': args.grace_seconds,
        'overall_alarm_seconds': args.wall_seconds, 'external_runtime_inputs': 0,
        'gpu_preflight_not_yet_executed': True, 'launched': False}
    (args.out/'local_validation.json').write_text(json.dumps(local, indent=2)+'\n')
    print(json.dumps({'built': str(args.out), **local}))


if __name__ == '__main__':
    main()
