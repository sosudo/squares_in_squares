#!/usr/bin/env python3
"""Audit downloaded targeted FTMC aggregates without recertifying geometry.

Checks the exact frozen source, download hashes, post-gate certificate/array
bindings and device union. Local immutable snapshots are deliberately not
claimed: the pinned remote runtime verified those before exporting aggregates.
Profile diversity is descriptive and does not establish a full-puzzle gain.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import io
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'experiments'))
from extract_broad_active_frontier import profiles
from ftmc_certified_archive import PUBLIC_METRIC_SHA256, _bloat
from monitor_targeted_ftmc import NOTEBOOK, VERSION, SOURCE_SHA256, OUTPUT_FILES


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def arrays(path):
    with np.load(path, allow_pickle=False) as archive:
        return {name: archive[name] for name in archive.files}


def verify_record(name, q, record):
    payload = io.BytesIO()
    np.save(payload, q, allow_pickle=False)
    digest = hashlib.sha256(payload.getvalue()).hexdigest()
    w, h, d = map(int, record['key'].split('_'))
    if (q.shape != (w*h+d, 3) or q.dtype.str != '<f8' or not np.isfinite(q).all()
            or name != record['key']+'__'+digest
            or record['geometry_sha256'] != digest or record['npy_sha256'] != digest
            or record['snapshot'] != digest+'.npy' or record['shape'] != list(q.shape)
            or record['dtype'] != q.dtype.str or record['w'] != w or record['h'] != h
            or record['official_metric_sha256'] != PUBLIC_METRIC_SHA256
            or record['status'] != 'certified_geometry'
            or record['certification_contract'] != 'unchanged_public_certify_exact_geometry'
            or any(record[field] is not True for field in ('raw', 'roundtrip', 'official_raw_and_pandas'))
            or abs(_bloat(q, w, h)-record['bloat']) > 1e-12):
        raise ValueError('Certificate/array binding failed: '+name)
    return hashlib.sha256(q.tobytes()).hexdigest()


def analyze(output, state, job, degrees):
    ledger = load(state/'downloads.json')
    if (ledger['notebook'] != NOTEBOOK or ledger['version'] != VERSION
            or ledger['source_sha256'] != SOURCE_SHA256 or not ledger['complete']
            or sha(job/'search.py') != SOURCE_SHA256):
        raise ValueError('Exact job/download identity mismatch')
    for name in OUTPUT_FILES:
        item = ledger['files'][name]
        if item['status'] != 'downloaded' or item['sha256'] != sha(output/name):
            raise ValueError('Downloaded bytes changed: '+name)
    frozen = load(job/'job_manifest.json')
    remote = load(output/'job_manifest.json')
    if any(remote[key] != value for key, value in frozen.items()):
        raise ValueError('Remote manifest differs from frozen configuration')
    summary = load(output/'ftmc_summary.json')
    candidates = load(output/'ftmc_candidates.json')
    union = arrays(output/'artifacts/campaign_gadgets.npz')
    if set(union) != set(candidates) or summary['campaign_archive_sha256'] != sha(output/'artifacts/campaign_gadgets.npz'):
        raise ValueError('Exported candidate union differs')
    device_poses = {}; certificate_records = {}; device_counts = {}
    for device in ('0', '1'):
        prefix = output/f'artifacts/certified_device{device}'
        index = load(str(prefix)+'.json')
        if (index['status'] != 'certified_geometry'
                or index['official_metric_sha256'] != PUBLIC_METRIC_SHA256
                or index['certification_contract'] != 'keep_only_after_unchanged_public_certify'):
            raise ValueError('Unexpected post-gate archive contract')
        for filename, expected in index['aggregate_sha256'].items():
            if sha(prefix.parent/filename) != expected:
                raise ValueError('Device aggregate hash changed')
        poses = arrays(str(prefix)+'.npz')
        if set(poses) != set(index['records']):
            raise ValueError('Device index/array names differ')
        binding = summary['certificate_binding_checks'][device]
        if (binding['aggregate_sha256'] != sha(str(prefix)+'.npz')
                or binding['index_sha256'] != sha(str(prefix)+'.json')
                or binding['verified_poses'] != len(poses)
                or binding['certification_reused_for_identical_bytes'] is not True):
            raise ValueError('Remote snapshot verification receipt differs')
        counts = Counter()
        for name, q in poses.items():
            record = index['records'][name]
            verify_record(name, q, record)
            if name not in union or not np.array_equal(q, union[name]):
                raise ValueError('Device geometry absent from exported union')
            if candidates[name]['exact_geometry_certificate'] != record:
                raise ValueError('Union certificate differs from original index')
            if name in certificate_records and certificate_records[name] != record:
                raise ValueError('Shared devices disagree on exact certificate')
            certificate_records[name] = record
            counts[record['key']] += 1
        if summary['per_device'][device]['certified_variants'] != len(poses):
            raise ValueError('Device retained count differs')
        device_poses[device] = poses
        device_counts[device] = dict(counts)
    if set(certificate_records) != set(union) or summary['candidate_variants'] != len(union):
        raise ValueError('Device union is incomplete')
    strict = arrays(output/'artifacts/campaign_strict_gadgets.npz')
    expected_strict = {name for name, row in candidates.items() if row['gain_from_original'] > 2e-7}
    if set(strict) != expected_strict or len(strict) != summary['strict_variants_vs_original']:
        raise ValueError('Strict archive differs')
    groups = defaultdict(list); typed_hashes = Counter(); global_hashes = Counter()
    for name, q in union.items():
        record = candidates[name]['exact_geometry_certificate']; key = record['key']
        raw_hash = verify_record(name, q, record)
        groups[key].append((name, q, record))
        typed_hashes[(key, raw_hash)] += 1; global_hashes[raw_hash] += 1
    per_type = {}
    for key, entries in groups.items():
        w, h, _ = map(int, key.split('_'))
        initial = summary['best_by_key'][key]['bloat']+summary['best_by_key'][key]['gain_from_original']
        interface = {}
        for angle in degrees:
            signatures = set(); support_pairs = set(); brs = []; tls = []
            for _, q, _ in entries:
                profile = profiles(q, w, h, angle, angle, 32)
                signatures.add((profile['br_bin'], profile['tl_bin']))
                br = profile['outgoing_br_support']; tl = profile['incoming_tl_support']
                support_pairs.add((float(br).hex(), float(tl).hex())); brs.append(br); tls.append(tl)
            interface[str(angle)] = {'bins32_pairs': sorted(map(list, signatures)),
                'distinct_exact_support_pairs': len(support_pairs),
                'outgoing_br_support_range': [min(brs), max(brs)],
                'incoming_tl_support_range': [min(tls), max(tls)]}
        per_type[key] = {'poses': len(entries),
            'mutation_fingerprints': len({r['signature'] for _, _, r in entries}),
            'initial_bloat': initial, 'minimum_bloat': min(r['bloat'] for _, _, r in entries),
            'maximum_bloat': max(r['bloat'] for _, _, r in entries),
            'strictly_better_than_initial_2e_7': sum(r['bloat'] < initial-2e-7 for _, _, r in entries),
            'tilted_core_counts': sorted({int(np.sum(abs((q[:,2]+np.pi/4)%(np.pi/2)-np.pi/4)>.018)) for _,q,_ in entries}),
            'interface_original_phase_orientation': interface}
    effort = {}
    for device in ('0', '1'):
        status = summary['status'][device]; funnel = summary['funnels'][device]; budget = summary['refill_budgets'][device]
        effort[device] = {key: status[key] for key in ('seconds','batches','core_trials','refill_success','full_quenches','accepted','cuda_seconds')}
        effort[device].update(certified_exact_poses=len(device_poses[device]),
            certified_n65_poses=device_counts[device].get('8_8_1',0),
            raw_pandas_certify_seconds=funnel['certify']['wall_seconds'],
            raw_pandas_certify_wall_fraction=funnel['certify']['wall_seconds']/status['seconds'],
            refill_seconds=budget['refill_seconds'],refill_wall_fraction=budget['observed_refill_fraction'],
            core_residual_eligible=funnel['stages']['core_fp32']['eligible_for_next_stage'],
            full_fp64_rows=funnel['stages']['full_fp64']['rows'],
            full_fp64_residual_eligible=funnel['stages']['full_fp64']['eligible_for_next_stage'])
    oriented = 8*len(union); jobs_per_donor=31*31*63
    return {'notebook': NOTEBOOK, 'version': VERSION, 'source_sha256': SOURCE_SHA256,
        'download_manifest_sha256': sha(state/'downloads.json'), 'verified_named_files': len(OUTPUT_FILES),
        'job_manifest_sha256': sha(output/'job_manifest.json'), 'summary_sha256': sha(output/'ftmc_summary.json'),
        'typed_bank_path': str(output/'artifacts/campaign_gadgets.npz'),
        'typed_bank_sha256': sha(output/'artifacts/campaign_gadgets.npz'),
        'candidates_sha256': sha(output/'ftmc_candidates.json'),
        'status': summary['stage'],'wall_seconds':summary['wall_seconds'],
        'parallel_search_wall_seconds': summary['parallel_search_wall_seconds'],
        'bounded_worker_timeout': summary['bounded_worker_timeout'], 'failures': summary['failures'],
        'unique_typed_poses':len(union),'exact_typed_array_duplicates_within_union':sum(v-1 for v in typed_hashes.values()),
        'exact_array_duplicates_across_all_types':sum(v-1 for v in global_hashes.values()),
        'device_retained_poses_sum':sum(map(len,device_poses.values())),
        'exact_device_overlap':len(set(device_poses['0'])&set(device_poses['1'])),
        'strict_variants_vs_frozen_initial':len(strict),'per_type':per_type,'device_type_counts':device_counts,'effort':effort,
        'd4_encoding':{'planned_oriented_sources_before_other_inputs':oriented,
            'jobs_per_donor':jobs_per_donor,'largest_packed_lower32_job_in_isolated_partition':oriented*jobs_per_donor-1,
            'requires_unsigned_or_wider_multiplication':oriented*jobs_per_donor-1>2**31-1,
            'fits_uint32_in_isolated_partition':oriented*jobs_per_donor<=2**32,
            'maximum_total_oriented_sources_for_this_packed_format':2**32//jobs_per_donor,
            'warning':'Recalculate with every baseline, donor and extra crop source; signed32 products are unsafe.'},
        'proof_scope':{'exact_post_gate_certificate_and_array_bindings_verified':True,
            'remote_immutable_snapshot_receipts_bound':True,'local_immutable_snapshots_downloaded':False,
            'independent_geometry_rerun':False,'full_puzzle_score_gain_claimed':False},
        'per_key_effort':{'core_trials':None,'full_quenches':None,'wall_seconds':None,
            'reason':'Frozen instrumentation has no per-key effort or timing; retained certificate counts are selection-biased.'}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'artifacts/targeted-ftmc-n65-results-v1')
    parser.add_argument('--state',type=Path,default=ROOT/'artifacts/targeted-ftmc-n65-monitor-v1')
    parser.add_argument('--job',type=Path,default=ROOT/'artifacts/targeted-ftmc-n65-job-v2')
    parser.add_argument('--report',type=Path,default=ROOT/'artifacts/targeted-ftmc-n65-analysis-v1/report.json')
    parser.add_argument('--degrees',type=float,nargs='*',default=[30.,45.,60.])
    args=parser.parse_args();result=analyze(args.output,args.state,args.job,args.degrees)
    result['analysis_source_sha256']=sha(__file__)
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({key:result[key] for key in ('status','unique_typed_poses','strict_variants_vs_frozen_initial','typed_bank_sha256')}))


if __name__=='__main__':main()
