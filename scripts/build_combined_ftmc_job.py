"""Freeze a productive 30-minute dual-T4 FTMC campaign; never launch it."""
from __future__ import annotations

import argparse
import base64
from collections import Counter
import io
import json
import math
from pathlib import Path
import sys
import zipfile

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'experiments'))
from ftmc_frontier_bank import build_frontier_bank
from ftmc_seed_bank import geometry
from ftmc_certified_archive import _fingerprint
from build_full_puzzle_ftmc_job import digest, npz_bytes, validate_seeds, METRIC_HASH


def load_npz(path):
    with np.load(path, allow_pickle=False) as archive:
        return {name: archive[name] for name in archive.files}


def refreshed_priorities(baseline, targets, keys, successful_counts):
    needed = {int(use['n']) for entry in targets.values() for use in entry['uses']}
    frame = pd.read_csv(baseline, usecols=['n','x','y','angle'])
    actual = {}
    for n, rows in frame[frame.n.isin(needed)].groupby('n'):
        if len(rows) != int(n):
            raise ValueError('Incomplete target baseline')
        _, wh = geometry(rows[['x','y','angle']].to_numpy(float))
        actual[int(n)] = float(max(wh))-math.isqrt(int(n))
    if set(actual) != needed:
        raise ValueError('Missing target baseline cases')
    score_priority = {}
    for key in keys:
        entry = targets[key]
        gains = {}
        for use in entry['uses']:
            n = int(use['n'])
            use['original_recipe_target_bloat'] = use['target_bloat']
            use['target_bloat'] = actual[n]
            gain = max(0., actual[n]-max(entry['seed_bloat']-.01, use['partner_bloat']))/math.sqrt(n)
            use['single_stage_hypothetical_gain'] = gain
            gains[n] = max(gains.get(n, 0.), gain)
        score_priority[key] = sum(gains.values())
        entry['hypothetical_gain'] = score_priority[key]
    # Preserve exploration for all supported types; allocate 25% explicitly to
    # the four families proven to yield certified variants in the gentle pilot.
    objective = np.array([score_priority[key] for key in keys], dtype=float)
    objective += max(objective.max(), 1e-12)*.01
    objective /= objective.sum()
    productive = np.array([math.sqrt(successful_counts.get(key, 0)) for key in keys])
    productive = productive/productive.sum() if productive.sum() else objective
    weights = .75*objective+.25*productive
    weights /= weights.max()
    return dict(zip(keys, weights.tolist())), {'current_score_gain_priorities': score_priority,
        'successful_gentle_variants': dict(successful_counts), 'productive_sampling_mass': .25,
        'note': 'Sampling estimates use a hypothetical .01 bloat reduction with old partners fixed. Actual current full-puzzle joins and gain require composition.',
        'targets': targets}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path, default=ROOT/'artifacts/submission-public-refresh-v1-safe.csv')
    parser.add_argument('--baseline-report', type=Path, default=ROOT/'artifacts/submission-public-refresh-v1-safe-official.json')
    parser.add_argument('--active-dir', type=Path, default=ROOT/'artifacts/active-frontier')
    parser.add_argument('--fq-bank', type=Path, default=ROOT/'artifacts/fq-active-v1/best_bank.npz')
    parser.add_argument('--fq-donors', type=Path, default=ROOT/'artifacts/fq-active-v1/donors.npz')
    parser.add_argument('--gentle-donors', type=Path, default=ROOT/'artifacts/gentle-ftmc-results/artifacts/campaign_gadgets.npz')
    parser.add_argument('--extra-variants', type=Path, action='append', default=[])
    parser.add_argument('--source-dir', type=Path, default=ROOT/'vendor/lightning_ftmc')
    parser.add_argument('--out', type=Path, default=ROOT/'artifacts/combined-ftmc-job')
    parser.add_argument('--slug', default='sos54352/squares-combined-ftmc-campaign')
    parser.add_argument('--title', default='Squares Combined FTMC Campaign')
    parser.add_argument('--seconds', type=int, default=1800)
    parser.add_argument('--grace-seconds', type=int, default=120)
    parser.add_argument('--wall-seconds', type=int, default=2400)
    parser.add_argument('--replicas', type=int, default=64)
    parser.add_argument('--max-code-bytes', type=int, default=1_000_000)
    args = parser.parse_args()
    if (args.seconds <= 0 or args.grace_seconds < 30
            or args.wall_seconds < args.seconds+args.grace_seconds+180
            or not 1 <= args.replicas <= 256):
        raise ValueError('Invalid bounded campaign settings')
    baseline_hash = digest(args.baseline.read_bytes())
    certificate = json.loads(args.baseline_report.read_text())
    if not (certificate.get('sha256') == baseline_hash and certificate.get('valid') is True
            and certificate.get('invalid_count') == 0 and certificate.get('puzzles') == 1000
            and certificate.get('metric_sha256') == METRIC_HASH):
        raise ValueError('Matching complete official baseline certificate required')
    bank, variants, provenance, resume, _, targeting = build_frontier_bank(
        args.active_dir/'active_seed_variants.npz', [], args.active_dir/'active_priorities.json',
        args.active_dir/'active_targets.json', baseline_hash)
    if resume:
        raise ValueError('No historical bank overwrite is permitted')
    fq_bank = load_npz(args.fq_bank)
    if set(fq_bank) != set(bank):
        raise ValueError('FQ bank must have the same active types')
    for key, q in fq_bank.items():
        w, h, d = map(int, key.split('_'))
        if q.shape != (w*h+d, 3) or not np.isfinite(q).all():
            raise ValueError('Malformed FQ bank pose')
        _, wh = geometry(q)
        _, old_wh = geometry(bank[key])
        if max(wh-[w,h]) > max(old_wh-[w,h])+1e-10:
            raise ValueError('FQ bank is worse than original: '+key)
    sources = []
    successful_counts = Counter()
    for label, path in [('gentle-v1',args.gentle_donors), ('fq-active-v1',args.fq_donors)]+[
            ('extra'+str(i), path) for i, path in enumerate(args.extra_variants)]:
        archive = load_npz(path)
        added = 0
        for name, q in archive.items():
            key = name.split('__')[0]
            if key not in bank:
                continue
            w, h, d = map(int, key.split('_'))
            if q.shape != (w*h+d,3) or not np.isfinite(q).all():
                raise ValueError('Malformed archive geometry: '+name)
            _, wh = geometry(q)
            core = int(np.sum(abs((q[:,2]+np.pi/4)%(np.pi/2)-np.pi/4) > .018))
            if not 4 <= core <= 160 or not 0 < max(wh-[w,h]) < .999999:
                continue
            identity = key+'__'+label+'_'+digest(np.asarray(q,dtype='<f8').tobytes())
            variants[identity] = q.copy()
            added += 1
            if label == 'gentle-v1':
                successful_counts[key] += 1
        sources.append({'label':label, 'path':str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),
            'sha256':digest(path.read_bytes()), 'input_poses':len(archive), 'retained_archive_only_poses':added})
    for key, q in fq_bank.items():
        variants[key+'__fq_initial'] = q.copy()
    untrimmed_count = len(variants)
    selected = {}
    for key in bank:
        w, h, _ = map(int, key.split('_'))
        by_fingerprint = {}
        for name, q in variants.items():
            if name.split('__')[0] != key:
                continue
            _, wh = geometry(q)
            bloat = float(max(wh-[w,h]))
            fingerprint = _fingerprint(q)
            if fingerprint not in by_fingerprint or bloat < by_fingerprint[fingerprint][0]:
                by_fingerprint[fingerprint] = (bloat,name,q)
        for _, name, q in sorted(by_fingerprint.values(),key=lambda row:row[0])[:12]:
            selected[name] = q
    variants = selected
    priorities, refreshed = refreshed_priorities(args.baseline, targeting['targets'], list(bank), successful_counts)
    targeting.update(refreshed, worker_sampling_priorities=priorities,
        baseline_sha256=baseline_hash, source_archives=sources,
        incumbent_policy='Device0 starts certified FQ best; device1 original active bank. Variants cannot silently overwrite either bank.',
        original_bank_sha256=digest(npz_bytes(bank)), fq_bank_sha256=digest(args.fq_bank.read_bytes()))
    targeting.update(untrimmed_archive_inputs=untrimmed_count, embedded_archive_poses=len(variants),
        archive_selection='Same best-per-fingerprint, max12/key policy as live worker; complete source archives retained locally and in their original notebooks.')
    # Deduplicate exact coordinates for expensive official validation; aliases
    # still refer to the same exact normalized-or-original floating geometry.
    unique = {}
    for name, q in {**{k+'__original':v for k,v in bank.items()},
                    **{k+'__fq':v for k,v in fq_bank.items()}, **variants}.items():
        identity = digest(np.asarray(q,dtype='<f8').tobytes())
        unique.setdefault(identity, (name,q))
    validation = validate_seeds({name:q for name,q in unique.values()})
    validation['exact_unique_poses'] = len(unique)
    data = {}
    for path in sorted(args.source_dir.rglob('*')):
        if path.is_file() and '__pycache__' not in path.parts:
            data[str(path.relative_to(args.source_dir))] = path.read_bytes()
    public_manifest = json.loads(data['SOURCE_MANIFEST.json'])
    for name, expected in public_manifest['files'].items():
        if name not in data or digest(data[name]) != expected:
            raise ValueError('Public source snapshot changed: '+name)
    if digest(data['research/official_metric.py']) != METRIC_HASH:
        raise ValueError('Worker metric differs from pinned source')
    modules = ['ftmc_adaptive_angles.py','ftmc_anchor_mutations.py','ftmc_funnel_metrics.py',
        'ftmc_refill_budget.py','ftmc_certified_archive.py','ftmc_exploratory_archive.py',
        'ftmc_gentle_targets.py','ftmc_combined_policy.py','ftmc_combined_worker.py','ftmc_combined_export.py']
    for name in modules:
        data[name] = (ROOT/'experiments'/name).read_bytes()
    for name in ['LICENSE','NOTICE','SOURCE_MANIFEST.json']:
        data['research/fq_donor_provenance/'+name] = (ROOT/'vendor/fq'/name).read_bytes()
    data.update({'prepared_bank.npz':npz_bytes(bank), 'prepared_bank_device0.npz':npz_bytes(fq_bank),
        'prepared_bank_device1.npz':npz_bytes(bank), 'prepared_variants.npz':npz_bytes(variants),
        'prepared_provenance.json':json.dumps(provenance,indent=2).encode(),
        'prepared_priorities.json':json.dumps(priorities,indent=2).encode(),
        'prepared_targeting.json':json.dumps(targeting,indent=2).encode(),
        'prepared_validation.json':json.dumps(validation,indent=2).encode()})
    for name, payload in data.items():
        if name.endswith('.py'):
            compile(payload, name, 'exec')
        if b'KGAT_' in payload:
            raise ValueError('Credential-shaped bytes forbidden in payload')
    runtime = (ROOT/'experiments/ftmc_combined_runtime.py').read_text()
    manifest = {'source':public_manifest['source'], 'source_version':public_manifest['version'],
        'source_license':'Apache-2.0, retained notices; FQ donor generation MIT Evan Daniel, commit659ee62e4a9d39542a1146e8b011cc3ab6407ede',
        'devices':[0,1], 'baseline_sha256':baseline_hash, 'baseline_official_score':certificate['score'],
        'baseline_report_sha256':digest(args.baseline_report.read_bytes()),
        'active_seed_types':len(bank), 'input_variant_poses':len(variants), 'validated_unique_poses':len(unique),
        'search_seconds':args.seconds, 'grace_seconds':args.grace_seconds, 'wall_seconds':args.wall_seconds,
        'device_configs':{str(device):{'device':device,'replicas':args.replicas,'seed':seed,
            'source_rng_seed':20261024+seed+device*19937, 'initial_bank_label':label,
            'initial_bank_sha256':digest(data[f'prepared_bank_device{device}.npz'])}
            for device,seed,label in [(0,184067,'FQ best contact minima'),(1,194071,'Original active compatible crops')]},
        'policies':{'angle_local_fraction':.75,'anchors':'incumbent','general_refill_fraction':.18,
            'general_refill_attempts_per_batch':1,'general_refill_alarm_seconds':.5,'milp_seconds':.15,
            'reference_deficit_margin':2,'full_target_shrink_depths':[-.002,-.0005,0.,1e-5,5e-5,.0002,.0005,.001],
            'search_archive_fingerprints_per_key':12,'immutable_every_certified_geometry':True,
            'checkpoint_seconds':30,'exploratory_core_slots_per_key':8,'exploratory_full_slots_per_key':16},
        'certificate_policy':'Every new admission uses unchanged public raw+pandas gate; parent verifies exact immutable certificate and aggregate bytes, without redundant metric rerun. Composed full CSV independently requires official raw+roundtrip validation.',
        'source_archives':sources, 'input_attachments':[], 'slug':args.slug,
        'quota_expectation':{'nominal_search_wall_hours':args.seconds/3600,
            'nominal_device_hours':2*args.seconds/3600,'hard_wall_hours':args.wall_seconds/3600,
            'hard_device_hours':2*args.wall_seconds/3600},
        'runtime_sha256':digest(runtime.encode()), 'embedded_sha256':{name:digest(payload) for name,payload in data.items()}}
    stream = io.BytesIO()
    with zipfile.ZipFile(stream,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
        for name,payload in data.items():
            archive.writestr(name,payload)
    script = '# Private productive FTMC campaign. No credentials embedded.\nCONFIG = '+repr(manifest)+'\nPAYLOAD = '+repr(base64.b64encode(stream.getvalue()).decode())+'\n'+runtime
    compile(script,'search.py','exec')
    if len(script.encode()) >= args.max_code_bytes:
        raise ValueError('Source exceeds Kaggle size limit')
    metadata = {'id':args.slug,'title':args.title,'code_file':'search.py','language':'python',
        'kernel_type':'script','is_private':True,'enable_gpu':True,'enable_internet':False,'enable_tpu':False,
        'dataset_sources':[],'kernel_sources':[],'competition_sources':['squares-in-squares'],'machine_shape':'NvidiaTeslaT4'}
    args.out.mkdir(parents=True,exist_ok=True)
    for name,value in [('job_manifest.json',manifest),('kernel-metadata.json',metadata),
                       ('seed_validation.json',validation),('targeting_review.json',targeting)]:
        (args.out/name).write_text(json.dumps(value,indent=2)+'\n')
    (args.out/'search.py').write_text(script)
    print(json.dumps({'built':str(args.out),'script_sha256':digest(script.encode()),
        'source_bytes':len(script.encode()),'seed_types':len(bank),'validated_unique_poses':len(unique),
        'seconds_per_device':args.seconds,'parent_wall_seconds':args.wall_seconds,'launched':False}))


if __name__ == '__main__':
    main()
