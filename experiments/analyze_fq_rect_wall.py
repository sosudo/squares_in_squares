"""Read-only finite rectangular-wall trajectory and square-endpoint audit."""
import os
for name in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[name] = '1'
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
from prepare_wall_aspect_inputs import rectangular_control
from compose_gadgets import legalize


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def analyze(folder):
    root = folder/'outputs'
    receipt = json.loads((folder/'download-receipt.json').read_text())
    assert receipt['status'] == 'complete'
    for name, record in receipt['files'].items():
        assert sha(root/name) == record['sha256']
    config = json.loads((root/'rect-config.json').read_text())
    events = [json.loads(row) for row in (root/'wall-events.jsonl').read_text().splitlines()]
    index = json.loads((root/'raw-index.json').read_text())
    summary = json.loads((root/'pilot-summary.json').read_text())
    finished = json.loads((root/'search-finished.json').read_text())
    recovery = summary['recovery']
    assert len(events) == finished['stages'] == len(index['packets'])
    assert recovery['square_best_sha256'] == sha(root/'final-square-best.npz')
    with np.load(root/'final-square-best.npz', allow_pickle=False) as archive:
        best = {key: archive[key] for key in archive.files}
    rows, stages = [], []
    iteration_counts = {}
    for i, event in enumerate(events):
        assert event['stage'] == i and event['packet'] == index['packets'][i]
        assert event['steps_requested'] == 2000 and event['tau'] == 0
        energy = np.array([record['energy'] for record in event['physical_rectangle_metrics']])
        native = np.asarray(event['native_quench_report'])
        for count in native[:, 2].astype(int):
            iteration_counts[str(count)] = iteration_counts.get(str(count), 0)+1
        by_family = {}
        for family in ('19x18', '20x17'):
            ids = [r['chain'] for r in config['design'] if r['family'] == family]
            subset = energy[ids]
            by_family[family] = dict(min_energy=float(subset.min()), max_energy=float(subset.max()), median_energy=float(np.median(subset)),
                numerical_zero_count=int((subset == 0).sum()))
        stages.append(dict(stage=i, final_square=event['final_square'], families=by_family,
            quench_seconds=event['quench_seconds'],
            native_zero_iteration_reports=int((native[:, 2] == 0).sum()),
            native_saturated_reports=int((native[:, 2] == 1999).sum())))
    for i, record in enumerate(config['design']):
        pose = best['poses'][i]
        independent = rectangular_control(pose, config['target_side'], config['target_side'])
        assert abs(independent['energy']-best['energy'][i]) < 1e-12
        origin = int(best['stage'][i])
        assert abs(events[origin]['physical_rectangle_metrics'][i]['energy']-best['energy'][i]) < 1e-12
        folded = (pose[:, 2]+np.pi/4) % (np.pi/2)-np.pi/4
        rows.append(dict(chain=i, family=record['family'], pattern=record['pattern'], replica=record['replica'],
            source_geometry_sha256=record['geometry_sha256'], best_stage=origin,
            best_geometry_sha256=hashlib.sha256(pose.tobytes()).hexdigest(),
            independent_square_metrics=independent, rounding_only_repair_passed=legalize(pose) is not None,
            angles_over_one_degree=int((abs(folded)>np.pi/180).sum()),
            max_angle_degrees=float(np.degrees(abs(folded)).max())))
    families = {}
    for family in ('19x18', '20x17'):
        selected = [r for r in rows if r['family'] == family]
        energies = [r['independent_square_metrics']['energy'] for r in selected]
        first_nonzero = next(s['stage'] for s in stages if s['families'][family]['numerical_zero_count'] < 16)
        first_material = next(s['stage'] for s in stages if s['families'][family]['max_energy'] > 1e-8)
        families[family] = dict(best_energy=min(energies), median_best_energy=float(np.median(energies)),
            first_nonzero_stage=first_nonzero, first_energy_over_1e_8_stage=first_material,
            square_tail_best_ratio=min(energies)/stages[32]['families'][family]['min_energy'],
            rounding_only_passes=sum(r['rounding_only_repair_passed'] for r in selected),
            median_angles_over_one_degree=float(np.median([r['angles_over_one_degree'] for r in selected])),
            maximum_angle_degrees=max(r['max_angle_degrees'] for r in selected))
    return dict(source_sha256=receipt['source_sha256'], analyzer_sha256=sha(__file__),
        input_sha256=config['inputs_sha256'], controls_passed=summary['controls_passed'],
        search=finished, whole_seconds=json.loads((root/'supervisor-summary.json').read_text())['seconds'],
        completed_stage_poses=32*len(events), raw_packets=len(index['packets']),
        raw_bytes=sum(r['bytes'] for r in index['packets']), families=families,
        native_report_iteration_histogram=iteration_counts,
        native_iteration_scope='Native iteration diagnostic; no inferred stop reason or accepted-pose residual.',
        certified_improvements=recovery['certified_improvements'], candidate_count=recovery['candidate_count'],
        remaining_unattempted=recovery['remaining_uncertified'],
        remaining_not_certified=recovery['candidate_count']-len(recovery['certified_candidates']),
        stages=stages, chains=rows,
        conclusion='Finite cold-grid wall path completed. Physical residual is not a geometry certificate; no portfolio admission is inferred.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--folder', type=Path, required=True)
    args = parser.parse_args()
    result = analyze(args.folder)
    (args.folder/'analysis.json').write_text(json.dumps(result, indent=2, allow_nan=False)+'\n')
    print(json.dumps({key: result[key] for key in ('search', 'families', 'certified_improvements', 'raw_bytes')}))
