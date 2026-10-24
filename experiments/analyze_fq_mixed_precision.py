#!/usr/bin/env python3
"""Audit retained diagnostic bytes and summarize timing/physical-energy evidence."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np


SOURCE_SHA = 'f7bfd48c5dfcb1dd16933c16d56e8fcd04fcec5864e6e61bc0582039cab2768c'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def quantiles(values):
    a = np.asarray(values, dtype=float)
    assert a.size and np.isfinite(a).all()
    return dict(zip(('min', 'p10', 'p25', 'median', 'p75', 'p90', 'max'),
                    map(float, np.quantile(a, (0, .1, .25, .5, .75, .9, 1)))))


def compare_energy(candidate, reference):
    candidate, reference = np.asarray(candidate), np.asarray(reference)
    assert candidate.shape == reference.shape and (reference > 0).all()
    tolerance = 1e-12 + 1e-8 * abs(reference)
    return dict(rows=int(candidate.size), ratio=quantiles(candidate / reference),
                lower=int(np.count_nonzero(candidate < reference - tolerance)),
                higher=int(np.count_nonzero(candidate > reference + tolerance)),
                tied=int(np.count_nonzero(abs(candidate - reference) <= tolerance)),
                absolute_difference=quantiles(candidate-reference))


def analyze(results: Path, arrays: Path):
    receipt = json.loads((results/'download-receipt.json').read_text())
    array_receipt = json.loads((arrays/'download-receipt.json').read_text())
    for root, record in ((results, receipt), (arrays, array_receipt)):
        assert record['status'] == 'complete' and record['private_source_verified']
        assert record['source_sha256'] == SOURCE_SHA
        for name, expected in record['files'].items():
            path = root/'outputs'/name
            assert digest(path) == expected['sha256'] and path.stat().st_size == expected['bytes']
    output = results/'outputs'
    report_path = output/'diagnostic/benchmark-report.json'
    report = json.loads(report_path.read_text())
    index = json.loads((output/'diagnostic/array-index.json').read_text())
    assert report['status'] == 'complete' and not report['omitted']
    assert report['fp64_controls_passed'] and report['fp32_controls_passed']
    assert report['completed_primary_pipelines'] == len(report['primary']) == 36
    assert report['no_score_claim'] and report['no_native_finish'] and report['no_search']
    for record in index:
        relative = Path(record['path']).relative_to('/kaggle/working')
        path = arrays/'outputs'/relative
        assert digest(path) == record['sha256'] and path.stat().st_size == record['bytes']
        with np.load(path, allow_pickle=False) as archive:
            assert set(archive.files) == set(record['arrays'])
            for key, expected in record['arrays'].items():
                value = archive[key]
                assert list(value.shape) == expected['shape'] and value.dtype.str == expected['dtype']
                assert hashlib.sha256(value.tobytes()).hexdigest() == expected['sha256']
    summary = dict(source_sha256=SOURCE_SHA, report_sha256=digest(report_path),
                   array_index_sha256=digest(output/'diagnostic/array-index.json'),
                   download_receipt_sha256=digest(results/'download-receipt.json'),
                   array_receipt_sha256=digest(arrays/'download-receipt.json'),
                   analyzer_sha256=digest(__file__), all_retained_arrays_verified=len(index),
                   retained_bytes=sum(r['bytes'] for r in index),
                   supervisor=json.loads((output/'supervisor-summary.json').read_text()),
                   no_score_claim=True, no_optimization_or_certification=True)
    base = report['occupancy'][0]
    assert [r['batch'] for r in report['occupancy']] == [32, 64, 128]
    occupancy = []
    for record in report['occupancy']:
        count = record['batch']
        reference = np.tile(base['physical_energy'], count//32)
        occupancy.append(dict(batch=count, fixture=record['fixture'],
            quench_seconds=record['timing']['wall_seconds_conversion_allocation_launch_sync'],
            quench_poses_per_second=record['poses_per_second'],
            quench_speedup_vs_B32=record['poses_per_second']/base['poses_per_second'],
            dense_physical_seconds=record['dense_fp64_physical_evaluation']['wall_seconds'],
            quench_plus_physical_poses_per_second=count/record['solver_plus_physical_seconds'],
            torch_peak_allocated_bytes=record['dense_fp64_physical_evaluation']['torch_peak_allocated_bytes'],
            cupy_pool_total_bytes=record['timing']['memory_pool_total_bytes'],
            coordinate_max_vs_B32=record['endpoint_differences_vs_B32']['coordinate_max'],
            physical_energy_vs_B32=compare_energy(record['physical_energy'], reference)))
    summary['occupancy'] = occupancy
    lookup = {(x['repeat'], x['fixture'], x['arm']): x for x in report['primary']}
    assert len(lookup) == 36 and all(x['status'] == 'completed' for x in lookup.values())
    fixtures = sorted({x['fixture'] for x in lookup.values()})
    summary['arms'] = {}
    for arm in 'ABC':
        records = [r for r in lookup.values() if r['arm'] == arm]
        summary['arms'][arm] = dict(
            pipelines=len(records),
            compute_seconds=sum(r['compute_wall_sum_excludes_retention_io'] for r in records),
            whole_pipeline_seconds=sum(r['wall_including_retention_and_physical_evaluation'] for r in records),
            per_fixture={fixture: dict(
                compute_seconds=quantiles([r['compute_wall_sum_excludes_retention_io'] for r in records if r['fixture'] == fixture]),
                physical_energy=quantiles([e for r in records if r['fixture'] == fixture for e in r['fp64_physical_energy_on_original_boxes']]),
                first_phase_last_iteration=quantiles([i for r in records if r['fixture'] == fixture for i in r['phases'][0]['last_iteration_indices']]))
                for fixture in fixtures})
    summary['matched_to_A'] = {}
    for arm in 'BC':
        control_energy, treatment_energy, speedups = [], [], []
        for repeat in range(3):
            for fixture in fixtures:
                a, b = lookup[repeat, fixture, 'A'], lookup[repeat, fixture, arm]
                control_energy.extend(a['fp64_physical_energy_on_original_boxes'])
                treatment_energy.extend(b['fp64_physical_energy_on_original_boxes'])
                speedups.append(a['compute_wall_sum_excludes_retention_io']/b['compute_wall_sum_excludes_retention_io'])
        summary['matched_to_A'][arm] = dict(physical_energy=compare_energy(treatment_energy, control_energy),
            paired_compute_speedup=quantiles(speedups),
            aggregate_compute_speedup=summary['arms']['A']['compute_seconds']/summary['arms'][arm]['compute_seconds'])
    summary['B32_repeat_endpoint_variation'] = [dict(repeat=repeat,
        physical_energy_vs_occupancy_B32=compare_energy(lookup[repeat, base['fixture'], 'A']['fp64_physical_energy_on_original_boxes'], base['physical_energy']))
        for repeat in range(3)]
    summary['scope'] = ('One exact-duplicate occupancy batch at each size, not a repeated throughput study. '
        'Initial objective/gradient row equivalence passed. Optimizer endpoints are nondeterministic; '
        'differences are measured, not silently treated as exact equivalence. '
        'No matched-wall search, feasible-side certificate or score improvement is claimed.')
    target = results/'analysis.json'
    target.write_text(json.dumps(summary, indent=2, allow_nan=False)+'\n')
    print(json.dumps(dict(analysis=str(target),sha256=digest(target),arrays_verified=len(index),
                         occupancy=occupancy,matched=summary['matched_to_A']),indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--results', type=Path, default=Path('artifacts/fq-mixed-precision-results-v1'))
    parser.add_argument('--arrays', type=Path, default=Path('artifacts/fq-mixed-precision-arrays-v1'))
    args = parser.parse_args()
    analyze(args.results, args.arrays)
