"""Prepare an active-frontier A/B of full-packing target sides, without launch."""
from __future__ import annotations

import argparse
import base64
import io
import json
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'experiments'))
from ftmc_frontier_bank import build_frontier_bank
from build_full_puzzle_ftmc_job import digest, npz_bytes, validate_seeds, METRIC_HASH


def adapted_supervisor(source):
    replacements = {
        "if manifest.get('frontier_mode')=='active_chains':":
        """if manifest.get('frontier_mode')=='prepared_active':
    with np.load('prepared_bank.npz')as z:bank={key:z[key]for key in z.files}
    with np.load('prepared_variants.npz')as z:variants={key:z[key]for key in z.files}
    provenance=json.loads(Path('prepared_provenance.json').read_text())
    priorities=json.loads(Path('prepared_priorities.json').read_text())
    targeting=json.loads(Path('prepared_targeting.json').read_text());resume={}
    assert targeting['baseline_sha256']==manifest['baseline_sha256']
elif manifest.get('frontier_mode')=='active_chains':""",
        "worker_file='ftmc_guarded_worker.py'if guarded else 'gpu_ftmc_refill.py'":
        "worker_file='ftmc_gentle_worker.py'",
        "        logs[device]=open(f'ftmc_worker{device}.log','w')":
        "        if cfg['gentle_targets']:command.append('--gentle')\n        logs[device]=open(f'ftmc_worker{device}.log','w')",
        "atomic_json('ftmc_summary.json',summary)":
        """summary['gentle_funnels']={}
for device in manifest['devices']:
    path=Path(f'research/gentle_funnel_device{device}.json')
    summary['gentle_funnels'][str(device)]=json.loads(path.read_text())if path.exists()else {'missing':True}
atomic_json('ftmc_summary.json',summary)""",
    }
    for original, replacement in replacements.items():
        if source.count(original) != 1:
            raise ValueError('Campaign supervisor interface changed; review gentle adapter')
        source = source.replace(original, replacement)
    return source.replace('lightningv08 public v21 FTMC; private resumed dual-T4 campaign',
                          'lightningv08 public v21 FTMC; private gentle-target A/B').replace(
        'Strict gains are measured against the published+pilot+transposed incumbent at campaign start; full-puzzle composition remains required.',
        'Both arms start from the same current active-frontier bank with angle-aware proposals. Only full-packing target sides differ. All certified novel variants are retained for composition, regardless of strict bloat gain.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path, default=ROOT/'artifacts/submission-gpu-composition-safe.csv')
    parser.add_argument('--baseline-report', type=Path, default=ROOT/'artifacts/submission-gpu-composition-safe-official.json')
    parser.add_argument('--active-dir', type=Path, default=ROOT/'artifacts/active-frontier')
    parser.add_argument('--source-dir', type=Path, default=ROOT/'vendor/lightning_ftmc')
    parser.add_argument('--out', type=Path, default=ROOT/'artifacts/gentle-ftmc-job')
    parser.add_argument('--slug', default='sos54352/squares-gentle-ftmc-pilot')
    parser.add_argument('--title', default='Squares Gentle FTMC Pilot')
    parser.add_argument('--seconds', type=int, default=300)
    parser.add_argument('--grace-seconds', type=int, default=60)
    parser.add_argument('--wall-seconds', type=int, default=700)
    parser.add_argument('--replicas', type=int, default=64)
    parser.add_argument('--max-code-bytes', type=int, default=1_000_000)
    args = parser.parse_args()
    if (args.seconds <= 0 or args.grace_seconds < 0
            or args.wall_seconds < args.seconds+args.grace_seconds+120
            or not 1 <= args.replicas <= 256):
        raise ValueError('Invalid bounded experiment settings')
    baseline_hash = digest(args.baseline.read_bytes())
    certificate = json.loads(args.baseline_report.read_text())
    if not (certificate.get('sha256') == baseline_hash and certificate.get('valid') is True
            and certificate.get('invalid_count') == 0 and certificate.get('puzzles') == 1000
            and certificate.get('metric_sha256') == METRIC_HASH):
        raise ValueError('A matching complete official baseline certificate is required')
    bank, variants, provenance, resume, priorities, targeting = build_frontier_bank(
        args.active_dir/'active_seed_variants.npz', [], args.active_dir/'active_priorities.json',
        args.active_dir/'active_targets.json', baseline_hash)
    if resume:
        raise ValueError('Historical incumbents cannot overwrite this active bank')
    validation = validate_seeds(bank)
    data = {}
    for path in sorted(args.source_dir.rglob('*')):
        if path.is_file() and '__pycache__' not in path.parts:
            data[str(path.relative_to(args.source_dir))] = path.read_bytes()
    public_manifest = json.loads(data['SOURCE_MANIFEST.json'])
    for name, expected in public_manifest['files'].items():
        if name not in data or digest(data[name]) != expected:
            raise ValueError('Public source snapshot changed: ' + name)
    if digest(data['research/official_metric.py']) != METRIC_HASH:
        raise ValueError('Worker metric is not the pinned official version')
    modules = ['ftmc_seed_bank.py', 'ftmc_gentle_targets.py', 'ftmc_gentle_worker.py',
               'ftmc_adaptive_angles.py', 'ftmc_funnel_metrics.py']
    for name in modules:
        data[name] = (ROOT/'experiments'/name).read_bytes()
    data.update({'prepared_bank.npz': npz_bytes(bank), 'prepared_variants.npz': npz_bytes(variants),
        'prepared_provenance.json': json.dumps(provenance, indent=2).encode(),
        'prepared_priorities.json': json.dumps(priorities, indent=2).encode(),
        'prepared_targeting.json': json.dumps(targeting, indent=2).encode(),
        'prepared_seed_validation.json': json.dumps(validation, indent=2).encode()})
    for name, payload in data.items():
        if name.endswith('.py'):
            compile(payload, name, 'exec')
        if b'KGAT_' in payload:
            raise ValueError('Credential-shaped bytes are forbidden in the payload')
    source_runtime = (ROOT/'experiments/ftmc_campaign_runtime.py').read_text()
    runtime = adapted_supervisor(source_runtime)
    manifest = {'source': public_manifest['source'], 'source_version': public_manifest['version'],
        'source_license': 'Apache-2.0 with retained notices', 'frontier_mode': 'prepared_active',
        'profile_guard': False, 'devices': [0, 1], 'gadget_ids': [], 'resume_files': [],
        'baseline_sha256': baseline_hash, 'baseline_official_score': certificate['score'],
        'baseline_report_sha256': digest(args.baseline_report.read_bytes()),
        'active_seed_types': len(bank), 'full_control_types': 0,
        'search_seconds': args.seconds, 'grace_seconds': args.grace_seconds,
        'wall_seconds': args.wall_seconds, 'replicas': args.replicas,
        'device_configs': {str(device): {'device': device, 'replicas': args.replicas,
            'seed': seed, 'source_rng_seed': 20261024+seed+device*19937,
            'search_seconds': args.seconds, 'resume_files': [], 'profile_guard': False,
            'angle_aware': True, 'gentle_targets': device == 0,
            'arm': 'near-incumbent-full-targets' if device == 0 else 'original-full-targets'}
            for device, seed in [(0, 134033), (1, 144037)]},
        'experimental_difference': 'Only ff, the full-packing fractional target side schedule; both arms use the same bank and angle-aware core proposals, with distinct RNG streams.',
        'target_schedule': {'replicas_per_refill': 16,
            'shrink_depths': [-.002, -.0005, 0., 1e-5, 5e-5, .0002, .0005, .001],
            'repetitions_per_refill': 2, 'formula': 'ff=f0-shrink_depth; negative depths expand'},
        'admission': 'Unchanged public fixed-angle LP, positive SAT clearance, official raw/roundtrip certification, strict incumbent improvement and novel-signature archive rules.',
        'quota_expectation': {'nominal_search_wall_hours': args.seconds/3600,
            'nominal_device_hours': 2*args.seconds/3600, 'hard_wall_hours': args.wall_seconds/3600,
            'hard_device_hours': 2*args.wall_seconds/3600,
            'note': 'Arithmetic device-hours; inspect actual Kaggle quota separately.'},
        'runtime_source_sha256': digest(source_runtime.encode()), 'runtime_sha256': digest(runtime.encode()),
        'input_attachments': [], 'slug': args.slug,
        'embedded_sha256': {name: digest(payload) for name, payload in data.items()}}
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, payload in data.items():
            archive.writestr(name, payload)
    script = ('# Private bounded gentle-target A/B. No credentials embedded.\nCONFIG = '
        +repr(manifest)+'\nPAYLOAD = '+repr(base64.b64encode(stream.getvalue()).decode())+'\n'+runtime)
    compile(script, 'search.py', 'exec')
    size = len(script.encode())
    if size >= args.max_code_bytes:
        raise ValueError('Generated source exceeds Kaggle source limit')
    metadata = {'id': args.slug, 'title': args.title, 'code_file': 'search.py', 'language': 'python',
        'kernel_type': 'script', 'is_private': True, 'enable_gpu': True, 'enable_internet': False,
        'enable_tpu': False, 'dataset_sources': [], 'kernel_sources': [],
        'competition_sources': ['squares-in-squares'], 'machine_shape': 'NvidiaTeslaT4'}
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out/'search.py').write_text(script)
    (args.out/'kernel-metadata.json').write_text(json.dumps(metadata, indent=2)+'\n')
    (args.out/'job_manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    (args.out/'seed_validation.json').write_text(json.dumps(validation, indent=2)+'\n')
    (args.out/'targeting_review.json').write_text(json.dumps(targeting, indent=2)+'\n')
    print(json.dumps({'built': str(args.out), 'source_bytes': size, 'script_sha256': digest(script.encode()),
        'active_seed_types': len(bank), 'full_controls': 0, 'seconds_per_device': args.seconds,
        'wall_seconds': args.wall_seconds, 'angle_aware_both_arms': True,
        'same_bank_both_arms': True, 'all_seed_raw_and_roundtrip_valid': True, 'launched': False}))


if __name__ == '__main__':
    main()
