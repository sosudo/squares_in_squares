"""Prepare an offline, bounded complete-puzzle FTMC pilot without launching it."""
from __future__ import annotations

import argparse
import base64
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import re
import sys
import zipfile

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'experiments'))
from full_puzzle_bank import build_full_puzzle_bank

METRIC_HASH = '312458227c78f56bd5e2eec3dc5fbb8787989422bbf72ce66c3c290048e89733'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def npz_bytes(arrays):
    stream = io.BytesIO()
    np.savez_compressed(stream, **arrays)
    return stream.getvalue()


def adapt_runtime(source):
    """Extend a frozen copy of our supervisor, preserving the public solver."""
    marker = "if manifest.get('frontier_mode')=='active_chains':"
    if source.count(marker) != 1:
        raise ValueError('Campaign bank interface changed; review adapter before building')
    replacement = (
        "if manifest.get('frontier_mode')=='full_puzzles':\n"
        "    from full_puzzle_bank import load_prepared_bank\n"
        "    bank,variants,provenance,resume,priorities,targeting=load_prepared_bank()\n"
        "    assert targeting['baseline_sha256']==manifest['baseline_sha256']\n"
        "    atomic_json('full_puzzle_targeting.json',targeting)\n"
        "elif manifest.get('frontier_mode')=='active_chains':")
    output_marker = "atomic_json('ftmc_candidates.json',candidates)"
    if source.count(output_marker) != 1:
        raise ValueError('Campaign export interface changed; review adapter before building')
    full_export = """
full_candidates={}
for variant,record in candidates.items():
    if not record['strict_improvement']:continue
    assert record['w']==record['h']
    n=record['w']*record['h']+record['surplus']
    side=record['w']+record['bloat']
    old=full_candidates.get(str(n))
    if old is None or side<old['side']:
        full_candidates[str(n)]={'side':side,'squares':record['squares'],
            'source':'public Lightning v21 FTMC, current full-puzzle private pilot',
            'variant':variant,'baseline_sha256':manifest['baseline_sha256']}
atomic_json('full_puzzle_candidates.json',full_candidates)
"""
    return source.replace(marker, replacement).replace(output_marker, output_marker+'\n'+full_export).replace(
        'lightningv08 public v21 FTMC; private resumed dual-T4 campaign',
        'lightningv08 public v21 FTMC; private current full-puzzle single-T4 pilot').replace(
        "Strict gains are measured against the published+pilot+transposed incumbent at campaign start; full-puzzle composition remains required.",
        "Strict gains are measured against the complete current baseline puzzle. Merge, raw official and transport validation remain required; L-frame propagation may add gains.")


def validate_seeds(bank):
    """Run unchanged official geometry on the exact serialized seed floats."""
    metric_path = ROOT/'research/official_metric_v17.py'
    if digest(metric_path.read_bytes()) != METRIC_HASH:
        raise ValueError('Official metric source differs from pinned v17')
    spec = importlib.util.spec_from_file_location('full_puzzle_metric', metric_path)
    metric = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(metric)
    results = {}
    for key, poses in bank.items():
        n = len(poses)
        rows = [dict(n=str(n), square_id=str(i), x=format(x, '.17g'),
                     y=format(y, '.17g'), angle=format(a, '.17g'))
                for i, (x, y, a) in enumerate(poses)]
        raw = metric._evaluate_puzzle_worker((n, rows))
        frame = pd.read_csv(io.StringIO(pd.DataFrame(rows).to_csv(index=False)))
        import csv
        rounded = list(csv.DictReader(io.StringIO(frame.to_csv(index=False, float_format='%.17g'))))
        roundtrip = metric._evaluate_puzzle_worker((n, rounded))
        if raw[3] != 'ok' or roundtrip[3] != 'ok' or abs(raw[1]-roundtrip[1]) > 1e-10:
            raise ValueError('Full-puzzle seed failed official transport validation: ' + key)
        results[key] = {'n': n, 'raw_status': raw[3], 'roundtrip_status': roundtrip[3],
                        'raw_score': raw[1], 'roundtrip_score': roundtrip[1]}
    return {'valid': True, 'metric_sha256': METRIC_HASH, 'count': len(results), 'results': results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path, default=ROOT/'artifacts/submission-safe.csv')
    parser.add_argument('--baseline-report', type=Path, default=ROOT/'artifacts/submission-safe-official.json')
    parser.add_argument('--baseline-source', default='sos54352/squares-certified-portfolio-source-export/2')
    parser.add_argument('--source-dir', type=Path, default=ROOT/'vendor/lightning_ftmc')
    parser.add_argument('--out', type=Path, default=ROOT/'artifacts/full-puzzle-ftmc-job')
    parser.add_argument('--slug', default='sos54352/squares-full-puzzle-ftmc-pilot')
    parser.add_argument('--title', default='Squares Full Puzzle FTMC Pilot')
    parser.add_argument('--seconds', type=int, default=600)
    parser.add_argument('--grace-seconds', type=int, default=60)
    parser.add_argument('--wall-seconds', type=int, default=960)
    parser.add_argument('--replicas', type=int, default=64)
    parser.add_argument('--seed', type=int, default=83117)
    parser.add_argument('--min-n', type=int, default=80)
    parser.add_argument('--max-n', type=int, default=324)
    parser.add_argument('--count', type=int, default=24)
    parser.add_argument('--max-core', type=int, default=100)
    parser.add_argument('--max-code-bytes', type=int, default=1_000_000)
    args = parser.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9_-]+/[A-Za-z0-9_-]+/[1-9][0-9]*', args.baseline_source):
        raise ValueError('Input notebook must be an immutable owner/slug/version reference')
    if (args.seconds <= 0 or args.grace_seconds < 0
            or args.wall_seconds < args.seconds+args.grace_seconds+120
            or not 1 <= args.replicas <= 256 or not 1 <= args.count <= 64
            or not 1 <= args.min_n <= args.max_n <= 1000 or not 4 <= args.max_core <= 160):
        raise ValueError('Invalid bounded experiment settings')
    baseline_hash = digest(args.baseline.read_bytes())
    report = json.loads(args.baseline_report.read_text())
    if not (report.get('sha256') == baseline_hash and report.get('valid') is True
            and report.get('invalid_count') == 0 and report.get('puzzles') == 1000
            and report.get('metric_sha256') == METRIC_HASH):
        raise ValueError('Current baseline requires its matching complete official report')
    bank, variants, provenance, priorities, targeting = build_full_puzzle_bank(args.baseline,
        min_n=args.min_n, max_n=args.max_n, count=args.count, max_core=args.max_core)
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
        raise ValueError('Worker metric is not the same pinned official source')
    for name in ['ftmc_seed_bank.py', 'full_puzzle_bank.py']:
        data[name] = (ROOT/'experiments'/name).read_bytes()
    seed_origin = {'baseline_sha256': baseline_hash,
        'baseline_official_report_sha256': digest(args.baseline_report.read_bytes()),
        'baseline_notebook_provenance': args.baseline_source,
        'selected_original_puzzle_hashes': {str(r['n']): report['puzzle_hashes'][str(r['n'])]
                                           for r in targeting['selected']},
        'note': 'Builder verified complete baseline/report binding, then certified each normalized seed. All exact search inputs are embedded and hashed; no remote input mount is needed.'}
    data.update({'full_bank.npz': npz_bytes(bank), 'full_variants.npz': npz_bytes(variants),
        'full_provenance.json': json.dumps(provenance, indent=2).encode(),
        'full_priorities.json': json.dumps(priorities, indent=2).encode(),
        'full_targeting.json': json.dumps(targeting, indent=2).encode(),
        'full_seed_origin.json': json.dumps(seed_origin, indent=2).encode(),
        'full_seed_validation.json': json.dumps(validation, indent=2).encode()})
    for name, contents in data.items():
        if name.endswith('.py'):
            compile(contents, name, 'exec')
        if b'KGAT_' in contents:
            raise ValueError('Credential-shaped bytes are forbidden in job payload: ' + name)
    runtime_source = (ROOT/'experiments/ftmc_campaign_runtime.py').read_text()
    runtime = adapt_runtime(runtime_source)
    manifest = {'source': source_manifest['source'], 'source_version': source_manifest['version'],
        'source_license': 'Apache-2.0 with retained notices', 'frontier_mode': 'full_puzzles',
        'profile_guard': False, 'baseline_sha256': baseline_hash,
        'baseline_official_score': report['score'], 'seed_validation': validation,
        'devices': [0], 'gadget_ids': [], 'resume_files': [], 'history_resume_disabled': True,
        'search_seconds': args.seconds, 'grace_seconds': args.grace_seconds,
        'wall_seconds': args.wall_seconds, 'replicas': args.replicas,
        'device_configs': {'0': {'device': 0, 'replicas': args.replicas, 'seed': args.seed,
            'source_rng_seed': 20261024+args.seed, 'search_seconds': args.seconds, 'resume_files': [],
            'profile_guard': False}},
        'quota_expectation': {'nominal_search_wall_hours': args.seconds/3600,
            'nominal_device_hours': args.seconds/3600, 'hard_wall_hours': args.wall_seconds/3600,
            'hard_device_hours': args.wall_seconds/3600,
            'note': 'One worker uses T4 device0; platform may attach two cards. Inspect actual Kaggle quota separately.'},
        'input_attachments': [], 'baseline_notebook_provenance': args.baseline_source,
        'seed_origin': seed_origin,
        'selected_n': [r['n'] for r in targeting['selected']],
        'targeting_note': 'Diverse complete current puzzles, with hypothetical L-frame score leverage; no historical fixture bank or separator constraints.',
        'runtime_source_sha256': digest(runtime_source.encode()), 'runtime_sha256': digest(runtime.encode()),
        'runtime_adapter': 'Local full_puzzles seed-loader branch; no public solver or metric changes.',
        'slug': args.slug, 'embedded_sha256': {k: digest(v) for k, v in data.items()}}
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, contents in data.items():
            archive.writestr(name, contents)
    script = ('# Private bounded complete-puzzle FTMC pilot. No credentials embedded.\n'
              + 'CONFIG = ' + repr(manifest) + '\nPAYLOAD = '
              + repr(base64.b64encode(stream.getvalue()).decode()) + '\n' + runtime)
    compile(script, 'search.py', 'exec')
    code_bytes = len(script.encode())
    if code_bytes >= args.max_code_bytes:
        raise ValueError('Generated notebook source exceeds the configured source limit')
    metadata = {'id': args.slug, 'title': args.title, 'code_file': 'search.py', 'language': 'python',
        'kernel_type': 'script', 'is_private': True, 'enable_gpu': True, 'enable_internet': False,
        'enable_tpu': False, 'dataset_sources': [], 'kernel_sources': [],
        'competition_sources': ['squares-in-squares'], 'machine_shape': 'NvidiaTeslaT4'}
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out/'search.py').write_text(script)
    (args.out/'kernel-metadata.json').write_text(json.dumps(metadata, indent=2)+'\n')
    (args.out/'job_manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    (args.out/'targeting_review.json').write_text(json.dumps(targeting, indent=2)+'\n')
    (args.out/'seed_validation.json').write_text(json.dumps(validation, indent=2)+'\n')
    print(json.dumps({'built': str(args.out), 'code_bytes': code_bytes, 'target_types': len(bank),
        'selected_n': manifest['selected_n'], 'seconds_nominal': args.seconds,
        'wall_seconds': args.wall_seconds, 'devices': [0], 'replicas': args.replicas,
        'all_seed_transport_checks_passed': True, 'launched': False}))


if __name__ == '__main__':
    main()
