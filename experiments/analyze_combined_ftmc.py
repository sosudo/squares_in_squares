"""Summarize downloaded combined outputs without repeating official evaluation."""
import argparse
from collections import Counter
import hashlib
import io
import json
from pathlib import Path

import numpy as np


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def bloat(q, key):
    w, h, _ = map(int, key.split('_'))
    r = .5*(np.abs(np.cos(q[:,2]))+np.abs(np.sin(q[:,2])))
    return float(max((q[:,:2]+r[:,None]).max(0)-(q[:,:2]-r[:,None]).min(0)-[w,h]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--results', type=Path, default=Path('artifacts/combined-ftmc-results'))
    parser.add_argument('--fq-bank', type=Path, default=Path('artifacts/fq-active-v1/best_bank.npz'))
    parser.add_argument('--comparison-bank', type=Path, action='append', default=[])
    args = parser.parse_args()
    root = args.results
    summary = json.loads((root/'ftmc_summary.json').read_text())
    manifest = json.loads((root/'job_manifest.json').read_text())
    candidates = json.loads((root/'ftmc_candidates.json').read_text())
    assert sha(args.fq_bank) == manifest['device_configs']['0']['initial_bank_sha256']
    initial_checks = {}
    for device in manifest['devices']:
        expected_path = root/f'prepared_bank_device{device}.npz'
        actual_path = root/f'artifacts/device{device}_initial_bank.npz'
        assert sha(expected_path) == manifest['device_configs'][str(device)]['initial_bank_sha256']
        with np.load(expected_path,allow_pickle=False) as expected, np.load(actual_path,allow_pickle=False) as actual:
            assert set(actual.files) == set(expected.files)
            for key in expected.files:
                assert actual[key].dtype == expected[key].dtype
                assert np.array_equal(actual[key],expected[key]), (device,key)
        initial_checks[str(device)] = {'actual_arrays_exactly_match_input':True,
            'input_sha256':sha(expected_path),'actual_archive_sha256':sha(actual_path)}
    fq = np.load(args.fq_bank, allow_pickle=False)
    reference = {key:bloat(fq[key],key) for key in fq.files}
    latest_reference = reference.copy()
    comparison_sources = []
    for path in args.comparison_bank:
        with np.load(path,allow_pickle=False) as archive:
            for key in archive.files:
                if key in latest_reference:
                    latest_reference[key] = min(latest_reference[key],bloat(archive[key],key))
        comparison_sources.append({'path':str(path),'sha256':sha(path)})
    path = root/'artifacts/campaign_gadgets.npz'
    assert sha(path) == summary['campaign_archive_sha256']
    best, counts, novel_strict, latest_strict = {}, Counter(), {}, {}
    with np.load(path, allow_pickle=False) as archive:
        assert set(archive.files) == set(candidates)
        for name in archive.files:
            q = archive[name]
            rec = candidates[name]
            key = rec['key']
            buffer = io.BytesIO()
            np.save(buffer,q,allow_pickle=False)
            exact = hashlib.sha256(buffer.getvalue()).hexdigest()
            certificate = rec['exact_geometry_certificate']
            assert certificate['geometry_sha256'] == exact
            assert certificate['official_metric_sha256'] == manifest['embedded_sha256']['research/official_metric.py']
            assert all(certificate[field] is True for field in ['raw','roundtrip','official_raw_and_pandas'])
            assert name == key+'__'+exact
            f = bloat(q,key)
            assert abs(f-rec['bloat']) < 1e-12
            counts[key] += 1
            gain = reference[key]-f
            if key not in best or f < best[key]['bloat']:
                best[key] = {'variant':name,'bloat':f,'fq_reference_bloat':reference[key],
                    'gain_vs_fq':gain,'latest_cpu_reference_bloat':latest_reference[key],
                    'gain_vs_latest_cpu':latest_reference[key]-f,'sources':rec['sources']}
            if gain > 2e-7:
                novel_strict[name] = q
            if latest_reference[key]-f > 2e-7:
                latest_strict[name] = q
    with (root/'artifacts/strict_vs_fq.npz').open('wb') as stream:
        np.savez_compressed(stream,**novel_strict)
    with (root/'artifacts/strict_vs_latest_cpu.npz').open('wb') as stream:
        np.savez_compressed(stream,**latest_strict)
    funnels, budgets, exploratory, retention = {}, {}, {}, {}
    for device in manifest['devices']:
        prefix = root/f'artifacts/certified_device{device}'
        index = json.loads(Path(str(prefix)+'.json').read_text())
        assert sha(Path(str(prefix)+'.npz')) == index['aggregate_sha256'][prefix.name+'.npz']
        events = summary['status'][str(device)].get('records',[])
        for event in events:
            identity = index['best_by_key'][event['key']]
            assert index['records'][identity]['bloat'] <= event['after']+1e-12, event
        retention[str(device)] = {'strict_events_checked':len(events),
            'every_recorded_strict_minimum_preserved':True,'immutable_records':len(index['records']),
            'aggregate_sha256':sha(Path(str(prefix)+'.npz'))}
        f = summary['funnels'].get(str(device), {})
        stages = f.get('stages', {})
        funnels[str(device)] = {'full_fp64_rows':stages.get('full_fp64',{}).get('rows'),
            'full_fp64_eligible':stages.get('full_fp64',{}).get('eligible_for_next_stage'),
            'lp_calls':f.get('rect_lp',{}).get('calls'), 'certify':f.get('certify'),
            'per_device':summary['per_device'].get(str(device))}
        b = summary['refill_budgets'].get(str(device),{})
        budgets[str(device)] = {key:b.get(key) for key in ['observed_refill_fraction','refill_calls',
            'refill_seconds','refill_timeouts','attempt_overruns','maximum_budget_excess_seconds',
            'reference_seconds','reference_deficit_by_key']}
        p = root/f'artifacts/exploratory_device{device}.json'
        if p.exists():
            e = json.loads(p.read_text())
            overflow = [rec for rec in e['core_records'].values()
                if rec['reported_capacity'] > rec['requested_count']]
            exploratory[str(device)] = {'core_records':len(e['core_records']),
                'full_records':len(e['full_records']), 'overflow_records':overflow,
                'all_exploratory_unvalidated':True}
    result = {'notebook':manifest['slug']+'/1','stage':summary['stage'],
        'wall_seconds':summary['wall_seconds'],'baseline_sha256':manifest['baseline_sha256'],
        'campaign_archive_sha256':sha(path),'fq_reference_sha256':sha(args.fq_bank),
        'actual_initial_bank_checks':initial_checks,
        'certified_variants':sum(counts.values()),'variants_by_key':dict(counts),
        'strict_variants_vs_fq':len(novel_strict),'best_by_key':best,
        'strict_improved_keys_vs_fq':[key for key,rec in best.items() if rec['gain_vs_fq']>2e-7],
        'latest_cpu_comparison_sources':comparison_sources,'strict_variants_vs_latest_cpu':len(latest_strict),
        'strict_improved_keys_vs_latest_cpu':[key for key,rec in best.items() if rec['gain_vs_latest_cpu']>2e-7],
        'funnels':funnels,'refill_budgets':budgets,'exploratory':exploratory,'retention':retention,
        'no_duplicate_official_calls':True,
        'note':'Exact archive/certificate hashes checked. FQ comparisons separate seeded contact gains from search gains. No full-puzzle gain is established until composition and independent official validation.'}
    (root/'analysis.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({key:result[key] for key in ['stage','wall_seconds','certified_variants',
        'strict_variants_vs_fq','strict_improved_keys_vs_fq','campaign_archive_sha256']}))


if __name__ == '__main__':
    main()
