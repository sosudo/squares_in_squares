"""Four bounded whole-continent rigid rotations followed by unchanged native FQ.

Only the initial near-upright continents rotate; all335 units are then free in
the existing native ALM/polish. Raw starts are deliberately unverified. Every
retained final uses the established independent/raw/default-pandas gates.
"""
import time
STARTED = time.monotonic()
import argparse
import csv
from decimal import Decimal
import json
import math
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys

for name in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[name] = '1'
import numpy as np
import fq_active_pilot as fq
import fq_remote_cpu_search as remote
from fq_torch_raw_finish_control import recorded_run
from fq_full_structural import descendants
from fq_variant_campaign import atomic_json, atomic_npz, geometry_sha
from packer_hop_physical_energy import physical_energy

ROOT = Path(__file__).resolve().parents[1]
BINARY_SHA = '10ec7cf773ac0ebca3791d5cfb84e9ecbb10e3f0a9e43194330c80e1cfc9dc3d'
OPTIONS = ['--loosen', '1', '--outer', '45', '--pit', '100', '--flip-top', '16', '--v']
SPECS = [('opposite_positive_full', (.1, -.1), False),
         ('opposite_negative_full', (-.1, .1), False),
         ('same_positive_interior', (.5, .5), True),
         ('opposite_positive_interior', (.5, -.5), True)]


def construction(p, current_side):
    folded = (p[:, 2] + np.pi/4) % (np.pi/2) - np.pi/4
    tilted = np.flatnonzero(abs(folded) > .018)
    upright = np.flatnonzero(abs(folded) <= .018)
    centre = p[tilted, :2].mean(0)
    _, singular, vectors = np.linalg.svd(p[tilted, :2]-centre, full_matrices=False)
    axis = vectors[0].copy()
    if axis[0] < 0:
        axis *= -1
    normal = np.array([-axis[1], axis[0]])
    projection = (p[:, :2]-centre) @ normal
    groups = [upright[projection[upright] >= 0], upright[projection[upright] < 0]]
    extent = .5 * (abs(np.cos(p[:, 2])) + abs(np.sin(p[:, 2])))
    wall = np.min(np.c_[p[:, :2]-extent[:, None],
                        current_side-p[:, :2]-extent[:, None]], axis=1)
    assert len(p) == 335 and len(tilted) == 44 and list(map(len, groups)) == [137, 154]
    inputs, records = {}, {}
    for name, degrees, interior in SPECS:
        q = p.copy()
        moves = []
        selected = []
        for label, indices, angle in zip(('upper_left', 'lower_right'), groups, degrees):
            ids = indices[wall[indices] >= .05] if interior else indices
            selected.extend(map(int, ids))
            pivot = p[ids, :2].mean(0)
            radians = math.radians(angle)
            c, s = math.cos(radians), math.sin(radians)
            rotation = np.array([[c, s], [-s, c]])
            q[ids, :2] = (p[ids, :2]-pivot) @ rotation + pivot
            q[ids, 2] += radians
            # Cheap geometric controls on the actual selected continent.
            i, j = np.triu_indices(len(ids), 1)
            before = np.linalg.norm(p[ids[i], :2]-p[ids[j], :2], axis=1)
            after = np.linalg.norm(q[ids[i], :2]-q[ids[j], :2], axis=1)
            error = float(np.max(abs(after-before)))
            inverse_error = float(abs((q[ids, :2]-pivot) @ rotation.T + pivot-p[ids, :2]).max())
            assert error < 1e-12 and inverse_error < 1e-12
            assert np.max(abs(q[ids, 2]-p[ids, 2]-radians)) < 1e-14
            moves.append(dict(continent=label, ids=ids.tolist(), count=len(ids),
                pivot=pivot.tolist(), angle_degrees=angle, angle_radians=radians,
                maximum_pair_distance_error=error, inverse_rotation_error=inverse_error))
        selected = np.array(sorted(selected))
        fixed = np.setdiff1d(np.arange(335), selected)
        assert np.array_equal(q[fixed], p[fixed]) and np.array_equal(q[tilted], p[tilted])
        assert np.array_equal(np.flatnonzero(np.any(q != p, axis=1)), selected)
        inputs[name] = q
        records[name] = dict(status='UNVERIFIED rotated initial state', moves=moves,
            interior_only=interior, fixed_ids=fixed.tolist(), tilted_ids_unchanged=tilted.tolist(),
            geometry_sha256=geometry_sha(q),
            physical_at_current_box=physical_energy(q, current_side),
            physical_at_target18807=physical_energy(q, 18.807),
            input_span=fq.bloat(q, 18, 18)+18,
            maximum_center_displacement=float(np.linalg.norm(q[:, :2]-p[:, :2], axis=1).max()))
    return inputs, records, dict(tilted_ids=tilted.tolist(), near_upright_ids=upright.tolist(),
        axis=axis.tolist(), normal=normal.tolist(), tilted_centroid=centre.tolist(),
        singular_values=singular.tolist(), near_upright_angle_threshold_radians=.018,
        border_exclusion_distance=.05, continent_sizes=list(map(len, groups)))


def worker(out, deadline):
    out.mkdir(exist_ok=False)
    trials = out/'trials'
    trials.mkdir()
    pointer_path = ROOT/'artifacts/current-best-portfolio.json'
    pointer = json.loads(pointer_path.read_text())
    raw = pointer['raw']
    csv_path, report_path = Path(raw['path']), Path(raw['official_report'])
    assert fq.digest(csv_path) == raw['sha256']
    assert fq.digest(report_path) == raw['official_report_sha256']
    report = json.loads(report_path.read_text())
    assert report['valid'] and report['sha256'] == raw['sha256']
    current_side = next(row['side'] for row in report['results'] if row['n'] == 335)
    with csv_path.open() as stream:
        rows = [r for r in csv.DictReader(stream) if int(r['n']) == 335]
    rows.sort(key=lambda r: int(r['square_id']))
    assert [int(r['square_id']) for r in rows] == list(range(335))
    p = np.array([[float(r[k]) for k in ('x', 'y', 'angle')] for r in rows])
    binary = Path('/tmp/squares-fq-portable-target/release/fq')
    assert fq.digest(binary) == BINARY_SHA
    frozen_binary = out/'fq'
    shutil.copyfile(binary, frozen_binary)
    frozen_binary.chmod(0o500)
    assert fq.digest(frozen_binary) == BINARY_SHA
    inputs, motions, selection = construction(p, float(current_side))
    atomic_npz(out/'source335.npz', {'pose': p})
    atomic_json(out/'source335-decimal-rows.json', rows)
    atomic_npz(out/'raw-starts.npz', inputs)
    atomic_json(out/'motion-records.json', motions)
    helpers = [Path(fq.__file__), Path(remote.__file__), ROOT/'experiments/fq_torch_raw_finish_control.py',
               ROOT/'experiments/fq_capacity_probe.py', ROOT/'experiments/compose_gadgets.py',
               ROOT/'experiments/full_structural_gpu_moves.py', ROOT/'experiments/packer_hop_physical_energy.py',
               ROOT/'scripts/validate_submission.py', ROOT/'research/official_metric_v17.py']
    source = out/'source'
    source.mkdir()
    for path in [Path(__file__), *helpers]:
        shutil.copyfile(path, source/path.name)
    manifest = dict(kind='Coordinated near-upright continent rotations followed by free full335 native repair',
        current_raw=raw, current_raw_side=current_side, current_pointer_sha256=fq.digest(pointer_path),
        input_sha256=fq.digest(out/'raw-starts.npz'), source_geometry_sha256=geometry_sha(p),
        source_rows_sha256=fq.digest(out/'source335-decimal-rows.json'), selection=selection,
        motions_sha256=fq.digest(out/'motion-records.json'), specs=SPECS,
        native_binary_sha256=BINARY_SHA, source_commit=fq.SOURCE_COMMIT, license='MIT; Evan Daniel',
        script_sha256=fq.digest(Path(__file__)), helper_hashes={str(path.relative_to(ROOT)):fq.digest(path) for path in helpers},
        options=OPTIONS, whole_seconds=75, trial_inclusive_seconds=15, workers=1, max_trials=4,
        actual_controls='Rigid distances/angles, inverse transform and exact untouched rows checked for each input.',
        novelty='Reviewed GPU coherent_start preserves all upright rows; prior498/814 interface study rotates donor blocks. This probe rotates137/154 upright continents or their105/120 interior subsets.',
        acceptance='Only full independent/raw/default-pandas final certificates. Generic trial gain compares the inflated input; actual portfolio gain below uses canonical RAW Decimal side.',
        input_box='Established fq.encode translates centers and takes raw bounding span; no input legalization or independent random kick.',
        no_submission=True, no_portfolio_mutation=True)
    atomic_json(out/'manifest.json', manifest)
    remote.grouped_run = recorded_run
    records = []
    for index, (name, _, _) in enumerate(SPECS):
        mode = 'upright_continents_'+name
        fq.MODES[mode] = list(OPTIONS)
        record, _ = remote.strict_trial(('18_18_11', inputs[name], mode, str(frozen_binary.resolve()),
                                        str(trials.resolve()), 33551001+index, 15., deadline-4))
        record.update(start_name=name, start_verified=False, current_raw_side=current_side,
                      initial_motion=motions[name])
        if record.get('certificate', {}).get('valid'):
            gate = record['certificate']['shared_official_gate']
            gain = Decimal(str(current_side))-Decimal(str(gate['raw_side']))
            record.update(terminal_official_side=gate['raw_side'], current_side_gain=str(gain),
                material_current_improvement=(gain > Decimal('1e-9') and
                    Decimal(str(gate['roundtrip_side'])) < Decimal(str(current_side))-Decimal('1e-9')))
        records.append(record)
        atomic_json(out/'results.json', records)
        print(json.dumps({k:record.get(k) for k in ('start_name','status','seconds',
                        'terminal_official_side','current_side_gain','material_current_improvement')}), flush=True)
    aggregate = remote.collect(out)
    atomic_json(out/'summary.json', dict(trials=len(records), aggregate=aggregate,
        statuses={s:sum(r['status']==s for r in records) for s in sorted({r['status'] for r in records})},
        current_raw_side=current_side,
        material_current_wins=[r['start_name'] for r in records if r.get('material_current_improvement')],
        terminal_sides={r['start_name']:r.get('terminal_official_side') for r in records},
        elapsed_seconds=time.monotonic()-STARTED, results_sha256=fq.digest(out/'results.json'),
        manifest_sha256=fq.digest(out/'manifest.json'), no_raw_initializer_gain_claim=True))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--worker', action='store_true')
    parser.add_argument('--deadline', type=float)
    args = parser.parse_args()
    if args.worker:
        worker(args.out, args.deadline)
    else:
        if args.out.exists():
            raise ValueError('Fresh immutable output directory required')
        process = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), '--out',
            str(args.out.resolve()), '--worker', '--deadline', str(STARTED+71)], start_new_session=True)
        forced = False
        try:
            process.wait(timeout=max(.01, STARTED+73-time.monotonic()))
        except subprocess.TimeoutExpired:
            forced = True
            try:
                os.kill(process.pid, signal.SIGSTOP)
            except ProcessLookupError:
                pass
            for pid in descendants(process.pid):
                try:
                    os.kill(pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait(timeout=1)
        receipt = dict(returncode=process.returncode, maximum_seconds=75, workers=1,
            whole_seconds=time.monotonic()-STARTED, hard_deadline_enforced=forced,
            executed_source_sha256=fq.digest(Path(__file__)))
        if args.out.exists():
            atomic_json(args.out/'supervisor.json', receipt)
        print(json.dumps(receipt), flush=True)
        if process.returncode:
            raise SystemExit(process.returncode)
