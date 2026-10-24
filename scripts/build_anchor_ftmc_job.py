"""Freeze an independent full-puzzle anchor A/B from a certified job template.

Only local adapters change. Both arms use the original public mutation angles,
the same eight exact seed poses and uniform priorities. No job is launched here.
"""
from __future__ import annotations

import argparse
import ast
import base64
import copy
import hashlib
import io
import json
from pathlib import Path
import zipfile

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SELECTED = {83, 86, 106, 129, 171, 205, 259, 302}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def npz_bytes(arrays):
    stream = io.BytesIO()
    np.savez_compressed(stream, **arrays)
    return stream.getvalue()


def read_template(path):
    text = path.read_text()
    assignments = {}
    for node in ast.parse(text).body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            if node.targets[0].id in ('CONFIG', 'PAYLOAD'):
                assignments[node.targets[0].id] = (ast.literal_eval(node.value), node.end_lineno)
    config, _ = assignments['CONFIG']
    encoded, end_line = assignments['PAYLOAD']
    runtime = ''.join(text.splitlines(keepends=True)[end_line:])
    with zipfile.ZipFile(io.BytesIO(base64.b64decode(encoded))) as archive:
        data = {name: archive.read(name) for name in archive.namelist()}
    if set(data) != set(config['embedded_sha256']):
        raise ValueError('Template manifest and embedded source differ')
    for name, contents in data.items():
        if digest(contents) != config['embedded_sha256'][name]:
            raise ValueError('Template payload hash mismatch: '+name)
    return config, data, runtime


def adapt_runtime(runtime):
    old = "worker_file='ftmc_guarded_worker.py'if guarded else 'gpu_ftmc_refill.py'"
    if runtime.count(old) != 1:
        raise ValueError('Frozen worker interface changed; review before packaging')
    runtime = runtime.replace(old, "worker_file='ftmc_anchor_worker.py'")
    old = "'--seed',str(cfg['seed'])]"
    if runtime.count(old) != 1:
        raise ValueError('Frozen command interface changed; review before packaging')
    runtime = runtime.replace(old, "'--seed',str(cfg['seed']),'--anchor-policy',cfg['anchor_policy']]")
    return runtime


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--template', type=Path, default=ROOT/'artifacts/full-puzzle-ftmc-job/search.py')
    parser.add_argument('--out', type=Path, default=ROOT/'artifacts/anchor-ftmc-job')
    parser.add_argument('--slug', default='sos54352/squares-core-anchor-pilot')
    parser.add_argument('--title', default='Squares Core Anchor Pilot')
    parser.add_argument('--seconds', type=int, default=300)
    parser.add_argument('--grace-seconds', type=int, default=60)
    parser.add_argument('--wall-seconds', type=int, default=700)
    parser.add_argument('--replicas', type=int, default=64)
    args = parser.parse_args()
    if (args.seconds <= 0 or args.grace_seconds < 0 or not 1 <= args.replicas <= 256
            or args.wall_seconds < args.seconds+args.grace_seconds+120):
        raise ValueError('Invalid bounded experiment settings')
    original_config, data, runtime = read_template(args.template)
    config = copy.deepcopy(original_config)
    if (config['frontier_mode'] != 'full_puzzles' or config.get('profile_guard')
            or config.get('input_attachments')):
        raise ValueError('Expected a self-contained certified full-puzzle template')
    with np.load(io.BytesIO(data['full_bank.npz'])) as source:
        bank = {k: source[k] for k in source.files if len(source[k]) in SELECTED}
    if {len(q) for q in bank.values()} != SELECTED:
        raise ValueError('Not all eight controlled seeds exist in the frozen bank')
    arrays_verified = {key: digest(np.asarray(q, dtype='<f8').tobytes()) for key, q in bank.items()}
    with np.load(io.BytesIO(data['full_variants.npz'])) as source:
        variants = {k: source[k] for k in source.files if k.split('__')[0] in bank}
    data['full_bank.npz'] = npz_bytes(bank)
    data['full_variants.npz'] = npz_bytes(variants)
    provenance = json.loads(data['full_provenance.json'])
    data['full_provenance.json'] = json.dumps({k: provenance[k] for k in bank}, indent=2).encode()
    priorities = {key: 1. for key in bank}
    data['full_priorities.json'] = json.dumps(priorities, indent=2).encode()
    targeting = json.loads(data['full_targeting.json'])
    targeting['selected'] = [r for r in targeting['selected'] if r['n'] in SELECTED]
    targeting['target_types'] = len(bank)
    targeting['worker_sampling_priorities'] = priorities
    targeting['anchor_control'] = {'selected_n': sorted(SELECTED), 'priority': 'uniform across eight controlled types',
        'evidence': 'artifacts/core-anchor-control.json',
        'comparison': 'Unchanged source initializer versus restoring original fractional wall clearance; original angle library in both arms.'}
    data['full_targeting.json'] = json.dumps(targeting, indent=2).encode()
    validation = json.loads(data['full_seed_validation.json'])
    validation['results'] = {k: validation['results'][k] for k in bank}
    validation['count'] = len(bank)
    if not validation['valid'] or any(r['raw_status'] != 'ok' or r['roundtrip_status'] != 'ok'
                                      for r in validation['results'].values()):
        raise ValueError('Frozen seed validation incomplete')
    data['full_seed_validation.json'] = json.dumps(validation, indent=2).encode()
    origin = json.loads(data['full_seed_origin.json'])
    origin['selected_original_puzzle_hashes'] = {str(n): origin['selected_original_puzzle_hashes'][str(n)] for n in sorted(SELECTED)}
    origin['certified_template_sha256'] = digest(args.template.read_bytes())
    origin['selected_pose_array_sha256'] = arrays_verified
    data['full_seed_origin.json'] = json.dumps(origin, indent=2).encode()
    for name in ('ftmc_anchor_mutations.py', 'ftmc_anchor_worker.py', 'ftmc_funnel_metrics.py'):
        data[name] = (ROOT/'experiments'/name).read_bytes()
    source_manifest = json.loads(data['SOURCE_MANIFEST.json'])
    for name, expected in source_manifest['files'].items():
        if digest(data[name]) != expected:
            raise ValueError('Public source changed: '+name)
    for name, blob in data.items():
        if name.endswith('.py'):
            compile(blob, name, 'exec')
        if b'KGAT_' in blob:
            raise ValueError('Credential-shaped content forbidden in payload')
    runtime = adapt_runtime(runtime)
    config.update(slug=args.slug, devices=[0, 1], selected_n=sorted(SELECTED), seed_validation=validation,
        seed_origin=origin, search_seconds=args.seconds, grace_seconds=args.grace_seconds,
        wall_seconds=args.wall_seconds, replicas=args.replicas,
        device_configs={str(device): {'device': device, 'replicas': args.replicas,
            'seed': 94117+10007*device, 'source_rng_seed': 20261024+94117+29944*device,
            'search_seconds': args.seconds, 'resume_files': [], 'profile_guard': False,
            'anchor_policy': 'unchanged' if device == 0 else 'incumbent'} for device in (0, 1)},
        quota_expectation={'nominal_search_wall_hours': args.seconds/3600,
            'nominal_device_hours': 2*args.seconds/3600, 'hard_wall_hours': args.wall_seconds/3600,
            'hard_device_hours': 2*args.wall_seconds/3600,
            'note': 'Arithmetic device-hours; inspect actual Kaggle quota separately.'},
        anchor_experiment={'arm0': 'original centered initializer', 'arm1': 'original wall anchor restored',
            'angles': 'original public library on both arms', 'public_source_unchanged': True,
            'extra_rng_draws': 0, 'funnel_metrics': True, 'overflow_repair': False},
        template_sha256=digest(args.template.read_bytes()), runtime_sha256=digest(runtime.encode()),
        runtime_adapter='Frozen full-puzzle supervisor, optional anchor worker command only',
        embedded_sha256={name: digest(blob) for name, blob in data.items()})
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, blob in data.items():
            archive.writestr(name, blob)
    code = ('# Private bounded core-anchor A/B pilot; no credentials embedded.\nCONFIG = '
            +repr(config)+'\nPAYLOAD = '+repr(base64.b64encode(stream.getvalue()).decode())+'\n'+runtime)
    compile(code, 'search.py', 'exec')
    if len(code.encode()) >= 1_000_000:
        raise ValueError('Generated source exceeds Kaggle source limit')
    metadata = {'id': args.slug, 'title': args.title, 'code_file': 'search.py', 'language': 'python',
        'kernel_type': 'script', 'is_private': True, 'enable_gpu': True, 'enable_internet': False,
        'enable_tpu': False, 'dataset_sources': [], 'kernel_sources': [],
        'competition_sources': ['squares-in-squares'], 'machine_shape': 'NvidiaTeslaT4'}
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out/'search.py').write_text(code)
    (args.out/'kernel-metadata.json').write_text(json.dumps(metadata, indent=2)+'\n')
    (args.out/'job_manifest.json').write_text(json.dumps(config, indent=2)+'\n')
    local = {'script_sha256': digest(code.encode()), 'code_bytes': len(code.encode()),
        'template_payload_hashes_verified': True, 'public_source_hashes_verified': True,
        'selected_pose_array_sha256': arrays_verified, 'official_raw_roundtrip_certificates_reused': len(bank),
        'input_attachments': 0, 'nominal_seconds_per_device': args.seconds,
        'grace_seconds': args.grace_seconds, 'overall_alarm_seconds': args.wall_seconds,
        'source_angles_unchanged_both_arms': True, 'launched': False}
    (args.out/'local_validation.json').write_text(json.dumps(local, indent=2)+'\n')
    print(json.dumps({'built': str(args.out), **local}), flush=True)


if __name__ == '__main__':
    main()
