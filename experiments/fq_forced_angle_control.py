"""Four forced-angle, true-held rounded-return controls; one CPU, <=120 seconds."""
import time
STARTED = time.monotonic()
import argparse
import json
import math
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
for variable in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[variable] = '1'
import numpy as np
import pandas as pd
import fq_full_round_control as base

BUFFER_SHA = 'e1e2b2d38986a181b6c7079aa1bee2d242f75ec9da73ec6661cff229ddc9be32'
BUFFER_KEY = '18_18_11__initial_2b991001752920f046765b9d90bbc01e1e55353b5b405d5669cad43ed2921b80'
RAW_SHA = 'a5086672035b695a9a67ebd551a1e595161d3a88436d9f27abd41835564cb0f0'
OPTIONS = ['--loosen', '1', '--round-r0', '.49', '--round-steps', '24', '--round-p', '1',
           '--round-kick', '0', '--hold-f', '1', '--outer', '45', '--pit', '100', '--flip-top', '16', '--v']


def fixed_encode(pose, box):
    """Keep the deliberately invalid input and original box; no normalization."""
    assert pose.shape == (335, 3) and np.isfinite(pose).all()
    text = f'335 {box:.17g}\n'
    text += '\n'.join(f'{x:.17g} {y:.17g} {math.degrees(a):.17g}' for x, y, a in pose) + '\n'
    return text, (0., 0.)


def forced_start(parent, seed, all_units):
    rng = np.random.default_rng(seed)
    jitter = rng.uniform(-.02, .02, (335, 2))
    angle_offsets = rng.uniform(-math.pi / 4, math.pi / 4, 335)
    tilted = np.abs((parent[:, 2] + math.pi / 4) % (math.pi / 2) - math.pi / 4) > .018
    near = np.min(np.linalg.norm(parent[:, None, :2] - parent[None, tilted, :2], axis=2), axis=1) <= 1.7
    mask = np.ones(335, dtype=bool) if all_units else tilted | near
    result = parent.copy()
    result[:, :2] += jitter
    result[mask, 2] += angle_offsets[mask]
    return result, np.flatnonzero(mask), jitter, angle_offsets


def held_linear_run(command, **kwargs):
    result = base.rounded_run(command, **kwargs)
    if result.returncode == 0:
        expected_box = float(Path(command[command.index('--in') + 1]).read_text().splitlines()[0].split()[1])
        report = json.loads(result.stdout.strip().splitlines()[-1])['round']
        values = [float(x) for x in re.findall(r'round r ([0-9.eE+-]+) hold', result.stderr)]
        expected = [.49 * (1 - k / 24) for k in range(1, 25)]
        if ('--round-compress' in command or command[command.index('--hold-f') + 1] != '1'
                or len(values) != 24 or max(abs(a-b) for a,b in zip(values, expected)) > .000050001
                or values[-1] != 0. or max(abs(report[k]-expected_box) for k in ('s_soft','s_hold')) > 1e-10):
            raise ValueError('Fixed-box linear24 exact-zero return control failed')
    return result


def worker(args):
    out = args.out; trials = out / 'trials'; trials.mkdir(exist_ok=False)
    raw = args.repo / 'artifacts/merged-fq-cpu-followup-v2.csv'
    buffered = args.repo / 'artifacts/n335-buffered-seed-v1/retained-seeds.npz'
    assert base.fq.digest(raw) == RAW_SHA and base.fq.digest(buffered) == BUFFER_SHA
    assert base.fq.digest(args.binary) == base.BINARY_SHA
    frame = pd.read_csv(raw)
    current = frame[frame.n == 335].sort_values('square_id')[['x','y','angle']].to_numpy(float)
    with np.load(buffered, allow_pickle=False) as z:
        parents = {'current': current, 'buffered_initial': z[BUFFER_KEY].copy()}
    certificates = {name: base.full_certificate(p) for name,p in parents.items()}
    assert all(c['valid'] and c['independent_raw']['n'] == 335 for c in certificates.values())
    boxes = {name: float(c['independent_raw']['side_upper']) for name,c in certificates.items()}
    fair_reference = boxes['current'] - 18
    arrays = dict(parents); plan = []
    for parent_index, (name,p) in enumerate(parents.items()):
        seed = 22133501 + parent_index
        for all_units in (True, False):
            mode = name + ('_all' if all_units else '_core_near')
            q, ids, jitter, offsets = forced_start(p, seed, all_units)
            arrays[mode] = q; arrays[mode+'__mask'] = ids
            arrays[mode+'__jitter'] = jitter; arrays[mode+'__angle_offsets'] = offsets
            plan.append(dict(mode=mode, seed=seed, parent=name, source_geometry_sha256=base.geometry_sha(p),
                actual_start_geometry_sha256=base.geometry_sha(q), fixed_box=boxes[name], selected_ids=ids.tolist(),
                initial_status='UNVALIDATED deliberately angle-randomized unit squares; no feasible-packing claim',
                current_reference_side=boxes['current']))
    base.atomic_npz(out/'inputs.npz', arrays); (out/'inputs.npz').chmod(0o444)
    base.atomic_json(out/'manifest.json', dict(plan=plan, workers=1, whole_seconds=120, trial_seconds=25,
        raw_baseline_sha256=RAW_SHA, buffered_archive_sha256=BUFFER_SHA, buffered_key=BUFFER_KEY,
        source_certificates=certificates, input_archive_sha256=base.fq.digest(out/'inputs.npz'),
        binary_sha256=base.fq.digest(args.binary), options=OPTIONS, fair_before_semantics='Current valid n335 excess, never invalid-start span',
        angle_distribution='Uniform offsets over one symmetry period [-pi/4,pi/4]', center_jitter='Uniform [-.02,.02] per axis, same for paired treatments',
        core_mask='Folded angle > .018 radians; plus every center within1.7 of any tilted center',
        source_snapshot_sha256=base.fq.digest(out/'source-bindings.json'), no_gpu=True, no_submission=True))
    (out/'manifest.json').chmod(0o444)
    original_encode, original_bloat = base.fq.encode, base.fq.bloat
    base.remote.grouped_run = held_linear_run
    records = []
    for row in plan:
        pose = arrays[row['mode']]; box = row['fixed_box']
        base.fq.MODES[row['mode']] = OPTIONS.copy()
        # This exact-object special case supplies the valid comparator only; encoded coordinates remain raw.
        base.fq.bloat = lambda p,w,h: fair_reference if p is pose else original_bloat(p,w,h)
        base.fq.encode = lambda p,w,h: fixed_encode(p, box)
        started = time.monotonic()
        try:
            record, _ = base.remote.strict_trial(('18_18_11',pose,row['mode'],str(args.binary),str(trials),row['seed'],25.,args.deadline-3))
        finally:
            base.fq.bloat, base.fq.encode = original_bloat, original_encode
        record.update(source=row, elapsed_seconds=time.monotonic()-started)
        stderr = trials / f"18_18_11-{row['mode']}-{row['seed']}.native-stderr"
        if stderr.exists():
            radii = [float(x) for x in re.findall(r'round r ([0-9.eE+-]+) hold',stderr.read_text())]
            record.update(completed_return_steps=len(radii),reported_radii=radii,native_stderr_sha256=base.fq.digest(stderr))
        records.append(record); base.atomic_json(out/'results.json',records)
        print(json.dumps({k:record.get(k) for k in ('mode','status','elapsed_seconds','completed_return_steps','after','gain')}),flush=True)
    aggregate = base.remote.collect(out)
    base.atomic_json(out/'summary.json',dict(trials=len(records),aggregate=aggregate,
        gain_comparator_side=boxes['current'],results_sha256=base.fq.digest(out/'results.json'),
        worker_seconds=time.monotonic()-STARTED, no_full_score_claim=True))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True);parser.add_argument('--repo',type=Path,required=True)
    parser.add_argument('--binary',type=Path,required=True);parser.add_argument('--worker',action='store_true')
    parser.add_argument('--deadline',type=float);args=parser.parse_args()
    if args.worker:
        worker(args);return
    command=[sys.executable,str(Path(__file__).resolve()),'--out',str(args.out),'--repo',str(args.repo),
             '--binary',str(args.binary),'--worker','--deadline',str(STARTED+116)]
    process=subprocess.Popen(command,start_new_session=True);forced=False
    try:process.wait(timeout=max(.01,STARTED+118-time.monotonic()))
    except subprocess.TimeoutExpired:
        forced=True
        try:os.kill(process.pid,signal.SIGSTOP)
        except ProcessLookupError:pass
        for pid in base.descendants(process.pid):
            try:os.kill(pid,signal.SIGKILL)
            except ProcessLookupError:pass
        try:os.killpg(process.pid,signal.SIGKILL)
        except ProcessLookupError:pass
        process.wait(timeout=1)
    receipt=dict(returncode=process.returncode,whole_seconds=time.monotonic()-STARTED,workers=1,
                 hard_deadline_enforced=forced,maximum_seconds=120)
    base.atomic_json(args.out/'supervisor.json',receipt);print(json.dumps(receipt),flush=True)
    if process.returncode:raise SystemExit(process.returncode)


if __name__=='__main__':main()
