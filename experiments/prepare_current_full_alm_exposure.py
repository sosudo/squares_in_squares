"""Read-only exact current-input exposure screen for a finite full-ALM proposal.

This invokes no optimizer or geometry certificate. Historical commands, native
input files, and output geometries are distinct kinds of evidence.
"""
import os
for _name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[_name] = '1'
import argparse
from collections import Counter
import csv
from decimal import Decimal, localcontext
import hashlib
import json
import math
from pathlib import Path
import sys
import time
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'experiments'))
from compose_gadgets import normalize
from fq_active_pilot import encode
from prepare_current_rigid_sweep import equivalent

CORPUS = [
    'fq-full-pilot-v1', 'fq-broad-polish-v1', 'fq-full-basin-v1',
    'fq-full-contact-v1/complete', 'fq-full-local-v1',
    'fq-unvisited-contact-v1', 'fq-broad-contact-v1/complete',
    'fq-current-rigid-v1/complete', 'fq-timeout-extension-v1/complete',
    'fq-timeout-remainder-v1/complete', 'fq-selective-polish-v1/complete',
    'fq-selective-polish-completion-v1/complete', 'fq-sqp-pilot-v2',
    'fq-newton-finish-pilot-v1', 'fq-transfer803861-reference-controls-v2',
    'fq-sustained-reference-controls-v1', 'fq-public35-reference-finish-v1',
    'fq-full-gpu-v2-native-finish-v1', 'fq-broad-contact-recovery-v1',
    'fq-broad-final-native-recovery-v1', 'fq-full-gpu-global-native-finish-v1',
]
EXCLUSIONS = {
    'active_sustained_gpu': {412, 544, 742, 591, 744, 641, 411, 462, 978, 541, 629, 341},
    'fresh_public35_full_alm_final_outputs': {423, 465, 509, 602, 651, 652, 705, 706, 753, 754, 804, 809, 863, 867, 978, 983, 984, 985},
    'closed_fullpose_or_matched_full_controls': {65, 147, 179, 299, 335, 453, 693, 803, 861, 498, 587},
    'concurrent_public35_alternative_case_avoidance': {698, 752, 805, 917, 797, 458, 637, 588, 743, 692, 372, 639, 980, 593, 996, 856, 982, 638, 644, 858, 502, 696, 697, 872},
}


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def gsha(p):
    return hashlib.sha256(np.asarray(p, dtype='<f8').tobytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def save(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def option(command, name):
    return command[command.index(name) + 1] if name in command else None


def classify(command):
    if not command:
        return 'unknown_options'
    if '--no-alm' in command:
        return 'no_alm_LP' + str(option(command, '--pit') or '_default')
    if any(flag in command for flag in ('--round-compress', '--soft-compress', '--freeze', '--kick')):
        return 'modified_ALM'
    if [option(command, flag) for flag in ('--outer', '--pit', '--flip-top')] == ['45', '20', '0']:
        return 'rigid_ALM45_LP20_flip0'
    if [option(command, flag) for flag in ('--outer', '--pit', '--flip-top')] == ['45', '100', '16']:
        return 'full_ALM45_LP100_flip16'
    return 'other_ALM'


def decode_native_input(path, n):
    lines = path.read_text().splitlines()
    assert int(lines[0].split()[0]) == n and len(lines) == n + 1
    p = np.asarray([[float(v) for v in line.split()[:3]] for line in lines[1:]], dtype='<f8')
    assert p.shape == (n, 3) and np.isfinite(p).all()
    p[:, 2] = np.radians(p[:, 2])
    return p


def core_info(p):
    folded = (p[:, 2] + np.pi / 4) % (np.pi / 2) - np.pi / 4
    core = p[np.abs(folded) > np.radians(1)].copy()
    bins = Counter((np.round(np.abs(np.degrees(folded[np.abs(folded) > np.radians(1)])) * 2) / 2).tolist())
    signatures = []
    for swap in (False, True):
        for sx, sy in ((1, 1), (-1, 1), (1, -1), (-1, -1)):
            q = core.copy()
            if swap:
                q[:, :2] = q[:, [1, 0]]
                q[:, 2] = np.pi / 2 - q[:, 2]
            q[:, :2] *= np.array([sx, sy]); q[:, 2] *= sx * sy
            if len(q):
                q[:, :2] -= q[:, :2].min(0)
            q[:, 2] = (q[:, 2] + np.pi / 4) % (np.pi / 2) - np.pi / 4
            z = np.column_stack((np.rint(q[:, :2] / .05), np.rint(np.degrees(q[:, 2]) / .5))).astype('<i4')
            z = z[np.lexsort((z[:, 2], z[:, 1], z[:, 0]))]
            signatures.append(z.tobytes())
    return dict(tilted_units=len(core), angle_half_degree_bins=sorted(bins.items(), key=lambda x: (-x[1], x[0])),
                coarse_D4_core_signature=hashlib.sha256(min(signatures)).hexdigest())


def histories():
    pins, rows, input_poses = [], [], {}
    for relative in CORPUS:
        directory = ROOT / 'artifacts' / relative
        path = directory / 'results.json'
        if not path.exists():
            pins.append(dict(path=str(path), missing=True)); continue
        data = read(path)
        values = data if isinstance(data, list) else data.get('results', [])
        manifests = []
        manifest = {}
        for name in ('manifest.json', 'execution-manifest.json'):
            p = directory / name
            if p.exists():
                m = read(p); manifest.update(m)
                manifests.append(dict(path=str(p), sha256=sha(p), binary_sha256=m.get('binary_sha256'),
                                      source_commit=m.get('source_commit'), source_hashes=m.get('source_hashes', {})))
        pins.append(dict(path=str(path), sha256=sha(path), rows=len(values), manifests=manifests))
        for index, r in enumerate(values):
            n = r.get('n')
            if n is None and isinstance(r.get('key'), str):
                parts = r['key'].split('_')
                if len(parts) == 3 and all(x.isdigit() for x in parts):
                    w, h, d = map(int, parts); n = w * h + d
            if not isinstance(n, int):
                continue
            command = r.get('command', r.get('native_command_for_lineage_only', []))
            provenance_only = 'native_command_for_lineage_only' in r
            mode = r.get('mode', r.get('source_role'))
            command_evidence = 'recorded_command'
            input_path = Path(option(command, '--in')) if '--in' in command else None
            if not command and relative == 'fq-full-pilot-v1':
                command = manifest.get('modes', {}).get(mode, [])
                command_evidence = 'frozen_manifest_modes'
                input_path = directory / f"{r['key']}-{mode}-{r['seed']}.in"
            actual_input_hash = None
            if input_path is not None and input_path.exists():
                actual_input_hash = sha(input_path)
                expected = r.get('input_sha256', r.get('native_input_sha256', r.get('native_encoded_input_sha256')))
                assert expected is None or expected == actual_input_hash, (path, index, 'input hash mismatch')
                input_poses[(str(path), index)] = decode_native_input(input_path, n)
            output_path = Path(option(command, '--out')) if '--out' in command else None
            if output_path is None and relative == 'fq-full-pilot-v1':
                output_path = input_path.with_suffix('.out')
            output_exists = output_path is not None and output_path.exists()
            returncode = r.get('returncode', r.get('native_returncode'))
            returned = output_exists and (returncode == 0 or r.get('native_status') == 'returned' or r.get('status') == 'certified')
            rows.append(dict(n=n, path=str(path), index=index, mode=mode, status=r.get('status'),
                treatment=classify(command), command=command, command_evidence=command_evidence,
                lineage_only_no_new_execution=provenance_only, input_path=str(input_path) if input_path else None,
                actual_input_sha256=actual_input_hash, parent_geometry_sha256=r.get('parent_geometry_sha256', r.get('selected_geometry_sha256')),
                output_geometry_sha256=r.get('geometry_sha256', r.get('decoded_geometry_sha256')),
                native_returned=returned, native_seconds=r.get('native_seconds', r.get('seconds', r.get('elapsed_seconds'))),
                native_seconds_cap=r.get('native_seconds_cap', r.get('whole_stage_cap')),
                output_exists=output_exists, output_sha256=sha(output_path) if output_exists else None,
                output_path=str(output_path) if output_path else None,
                source_manifest_pins=[m['sha256'] for m in manifests]))
    return pins, rows, input_poses


def main(args):
    started = time.monotonic()
    args.out.mkdir(parents=True, exist_ok=False)
    pointer_path = ROOT / 'artifacts/current-best-portfolio.json'
    pointer_bytes = pointer_path.read_bytes(); pointer = json.loads(pointer_bytes)
    raw = pointer['raw']; assert sha(raw['path']) == raw['sha256']
    assert sha(raw['official_report']) == raw['official_report_sha256']
    official = read(raw['official_report']); assert official['valid'] and official['sha256'] == raw['sha256']
    refpath = ROOT / 'research/data/public_puzzle_reference_v10.json'
    references = {r['n']: r for r in read(refpath)}
    (args.out / 'canonical-pointer.json').write_bytes(pointer_bytes)
    poses = {n: [] for n in range(1, 1001)}
    row_hashes = {n: hashlib.sha256() for n in poses}
    with Path(raw['path']).open(newline='') as stream:
        header = stream.readline()
        for line in stream:
            r = next(csv.DictReader([header, line])); n = int(r['n'])
            poses[n].append((int(r['square_id']), [float(r[k]) for k in ('x', 'y', 'angle')]))
            row_hashes[n].update(line.encode())
    poses = {n: np.asarray([p for _, p in sorted(rows)], dtype='<f8') for n, rows in poses.items()}
    assert all(p.shape == (n, 3) and np.isfinite(p).all() for n, p in poses.items())
    pins, trials, input_poses = histories()
    rows = []
    with localcontext() as context:
        context.prec = 80
        for official_row in official['results']:
            n = official_row['n']; p = poses[n]
            gap = (Decimal(official_row['side']) - Decimal(references[n]['L'])) / Decimal(n).sqrt()
            if gap <= Decimal('1e-8'):
                continue
            normalized = normalize(p); identities = {gsha(p), gsha(normalized)}
            native, offsets = encode(p, math.isqrt(n), math.isqrt(n)); assert offsets == [0, 0]
            input_hash = hashlib.sha256(native.encode()).hexdigest()
            exposure = []
            for trial in trials:
                if trial['n'] != n:
                    continue
                row = dict(trial)
                row['exact_encoded_input_match'] = row['actual_input_sha256'] == input_hash
                row['exact_parent_geometry_match'] = row['parent_geometry_sha256'] in identities
                row['exact_output_geometry_match'] = row['output_geometry_sha256'] in identities
                old = input_poses.get((trial['path'], trial['index']))
                row['ordered_D4_input_equivalence'] = equivalent(p, old) if old is not None else None
                exposure.append(row)
            full = [x for x in exposure if x['treatment'] == 'full_ALM45_LP100_flip16' and
                    (x['exact_encoded_input_match'] or x['exact_parent_geometry_match'] or x['ordered_D4_input_equivalence'])]
            exclusions = [label for label, values in EXCLUSIONS.items() if n in values]
            if full:
                exclusions.append('matching_full_ALM_input_already_attempted')
            matched = [x for x in exposure if x['exact_encoded_input_match'] or x['exact_parent_geometry_match'] or x['ordered_D4_input_equivalence']]
            rows.append(dict(n=n, side=official_row['side'], dated_reference=references[n], score_gap=str(gap),
                side_gap=str(Decimal(official_row['side']) - Decimal(references[n]['L'])),
                raw_case_rows_sha256=row_hashes[n].hexdigest(), geometry_sha256=gsha(p),
                normalized_geometry_sha256=gsha(normalized), native_input_sha256=input_hash,
                exclusions=exclusions, matched_input_treatments=dict(Counter(x['treatment'] for x in matched)),
                exact_output_treatments=dict(Counter(x['treatment'] for x in exposure if x['exact_output_geometry_match'])),
                all_same_case_treatments=dict(Counter(x['treatment'] for x in exposure)),
                history=exposure, **core_info(p)))
    rows.sort(key=lambda r: Decimal(r['score_gap']), reverse=True)
    selected = [r for r in rows if not r['exclusions']][:24]
    assert len(selected) == 24
    (args.out / 'inputs').mkdir()
    np.savez_compressed(args.out / 'inputs/current-poses.npz', **{str(r['n']): poses[r['n']] for r in selected})
    for row in selected:
        encoded, _ = encode(poses[row['n']], math.isqrt(row['n']), math.isqrt(row['n']))
        path = args.out / 'inputs' / f"n{row['n']}.in"; path.write_text(encoded)
        assert sha(path) == row['native_input_sha256']
    scope = dict(
        exact='Current float64/translated geometry or native input bytes, separately labeled; commands establish requested options, not completion of every optimizer iteration.',
        equivalence='Additional conservative ordered D4 + uniform center scale within3e-8, center residual5e-10, angle2e-12. Not exact bytes, unlabeled equivalence, or basin proof.',
        history='Only the explicitly hash-pinned corpus is audited. A current output of a prior weaker treatment is not a tested input of full ALM. No global never-tried claim.',
        reference='Dated publicv10 scalar reference, evaluated2026-10-24T00:02:02.353Z. No available-coordinate or attainable-gain claim.',
        signature='Tilted>1degree unit centers, D4 canonical,0.05center/0.5degree quantization; diversity diagnostic only.')
    report = dict(kind='read_only_current_full_ALM_exposure_screen', baseline=raw,
        pointer_sha256=hashlib.sha256(pointer_bytes).hexdigest(), reference_path=str(refpath), reference_sha256=sha(refpath),
        source_sha256=sha(__file__), dependency_hashes={str(Path(m)): sha(m) for m in [ROOT/'experiments/fq_active_pilot.py', ROOT/'experiments/prepare_current_rigid_sweep.py', ROOT/'experiments/compose_gadgets.py']},
        corpus=pins, history_trials=len(trials), scopes=scope, exclusion_policy={k: sorted(v) for k,v in EXCLUSIONS.items()},
        positive_cases=len(rows), eligible_cases=sum(not r['exclusions'] for r in rows),
        selection=[r['n'] for r in selected], selected_dated_score_gap=str(sum(Decimal(r['score_gap']) for r in selected)),
        selected=selected, all_positive_rows=rows, inputs_archive_sha256=sha(args.out/'inputs/current-poses.npz'),
        proposed_flags=['--loosen','1','--outer','45','--pit','100','--flip-top','16'],
        proposed_seed=9710000, proposed_workers=2, proposed_affinity=[2,3], proposed_native_seconds=60,
        proposed_certificate_seconds=8, proposed_work_seconds=880, proposed_whole_seconds=900,
        proposal_not_authorization=True, no_optimization=True, no_geometry_certificates=True, no_gpu=True,
        seconds=time.monotonic()-started)
    save(args.out/'report.json', report)
    save(args.out/'selection.json', {k: report[k] for k in ('baseline','pointer_sha256','source_sha256','reference_sha256','scopes','selection','selected_dated_score_gap','selected','inputs_archive_sha256')})
    lines = ['n,dated_score_gap,tilted_units,matched_input_treatments,exact_output_treatments,same_case_treatments']
    for r in selected:
        lines.append(','.join([str(r['n']),r['score_gap'],str(r['tilted_units'])]+[json.dumps(json.dumps(r[k])) for k in ('matched_input_treatments','exact_output_treatments','all_same_case_treatments')]))
    (args.out/'selection.csv').write_text('\n'.join(lines)+'\n')
    save(args.out/'completion.json', dict(report_sha256=sha(args.out/'report.json'), selection_sha256=sha(args.out/'selection.json'), inputs_sha256=sha(args.out/'inputs/current-poses.npz'), seconds=report['seconds'], no_optimization=True))
    for p in args.out.rglob('*'):
        if p.is_file(): p.chmod(0o444)
    print(json.dumps(dict(selection=report['selection'], gap=report['selected_dated_score_gap'], trials=len(trials), seconds=report['seconds'])))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    main(parser.parse_args())
