#!/usr/bin/env python3
"""Bounded full-puzzle vacancy/strip search from immutable N+1 constructions.

Deliberately infeasible coherent moves are optimizer inputs only. Every saved
pose passes official raw, 17g/default-pandas and independent interval gates.
"""
from __future__ import annotations
import os
for _name in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[_name] = '1'
import argparse
from concurrent.futures import ProcessPoolExecutor, wait, FIRST_COMPLETED
import hashlib
import json
import math
import multiprocessing as mp
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time
import numpy as np
from scipy.spatial import cKDTree
import fq_active_pilot as fq
from compose_gadgets import normalize, read_baseline, side
from fq_capacity_probe import full_certificate
from fq_coherent_clusters import Deadline, alarm, atom_json, atom_npz

ROOT = Path(__file__).resolve().parents[1]
TARGETS = (299, 335, 412, 454)
OPTIONS = ['--loosen', '1.001', '--outer', '45', '--pit', '100', '--flip-top', '16']
CONTROL_OPTIONS = ['--no-alm', '--loosen', '1', '--pit', '20', '--flip-top', '0']


def geometry_sha(p):
    return hashlib.sha256(np.asarray(p, dtype='<f8').tobytes()).hexdigest()


def contact_edges(p):
    pairs = cKDTree(p[:,:2]).query_pairs(1.5,output_type='ndarray')
    if not len(pairs): return []
    i,j = pairs.T
    delta = p[j,:2]-p[i,:2]
    a,b = p[i,2],p[j,2]
    projected = np.maximum.reduce([abs(delta[:,0]*np.cos(t)+delta[:,1]*np.sin(t))
                                   for t in (a,a+np.pi/2,b,b+np.pi/2)])
    radius = .5*(1+abs(np.cos(a-b))+abs(np.sin(a-b)))
    return pairs[projected-radius <= .003].tolist()


def strip_frame(p):
    angles = (p[:, 2]+np.pi/4) % (np.pi/2)-np.pi/4
    tilted = np.flatnonzero(abs(angles) > .018)
    if len(tilted) < 4:
        raise ValueError('No diagonal strip')
    centre = p[tilted, :2].mean(0)
    _, _, vt = np.linalg.svd(p[tilted, :2]-centre, full_matrices=False)
    axis = vt[0]
    if axis[0] < 0:
        axis = -axis
    transverse = np.array([-axis[1], axis[0]])
    return tilted, centre, axis, transverse


def deletion_order(p):
    tilted, centre, axis, _ = strip_frame(p)
    ordered = tilted[np.argsort((p[tilted, :2]-centre)@axis)]
    # Endpoints, central vacancies and intermediate junctions before full sweep.
    result = []
    for fraction in (0., 1., .5, .25, .75, .1, .9, .4, .6):
        i = int(ordered[round(fraction*(len(ordered)-1))])
        if i not in result:
            result.append(i)
    upright = np.setdiff1d(np.arange(len(p)), tilted)
    for endpoint in (ordered[0], ordered[-1]):
        for i in upright[np.argsort(np.linalg.norm(p[upright,:2]-p[endpoint,:2], axis=1))[:2]]:
            if int(i) not in result:
                result.append(int(i))
    result += [int(i) for i in ordered if int(i) not in result]
    return result


def mutate(source, deleted, mode, sign):
    ancestor_sha = geometry_sha(source)
    p = np.delete(source, deleted, axis=0)
    vacancy = source[deleted, :2].copy()
    q = p.copy()
    details = dict(ancestor_geometry_sha256=ancestor_sha, ancestor_count=len(source),
                   deleted_index=int(deleted), deleted_square=source[deleted].tolist(),
                   feasible_seed_geometry_sha256=geometry_sha(p), mode=mode, sign=sign)
    if mode in ('delete','control'):
        details['selected'] = []
    elif mode.startswith('rotate'):
        angle = sign*math.radians(6 if mode == 'rotate6' else 12)
        chosen = np.argsort(np.linalg.norm(p[:,:2]-vacancy, axis=1))[:12]
        c, s = math.cos(angle), math.sin(angle)
        rotation = np.array([[c, -s], [s, c]])
        q[chosen,:2] = (p[chosen,:2]-vacancy)@rotation.T+vacancy
        q[chosen,2] += angle
        details.update(selected=chosen.tolist(), pivot=vacancy.tolist(), rotation_radians=angle)
    elif mode == 'bend':
        tilted, centre, axis, transverse = strip_frame(p)
        projection = (p[tilted,:2]-centre)@axis
        length = float(np.ptp(projection))
        t = (projection-projection.min())/length
        amplitude = sign*.18
        displacement = amplitude*np.sin(2*np.pi*t)
        # Tangent rotation keeps the strip's local square orientations coherent.
        angular = np.arctan(amplitude*2*np.pi/length*np.cos(2*np.pi*t))
        q[tilted,:2] += displacement[:,None]*transverse
        q[tilted,2] += angular
        details.update(selected=tilted.tolist(), amplitude=amplitude, axis=axis.tolist(),
                       transverse=transverse.tolist(), strip_length=length)
    else:
        raise ValueError(mode)
    details['optimizer_input_geometry_sha256'] = geometry_sha(q)
    details['maximum_center_displacement'] = float(np.linalg.norm(q[:,:2]-p[:,:2], axis=1).max())
    details['maximum_angle_displacement'] = float(abs(q[:,2]-p[:,2]).max())
    return q, details


def descendants(pid):
    children = {}
    for entry in Path('/proc').iterdir():
        if not entry.name.isdigit():
            continue
        try:
            data = (entry/'stat').read_text().rsplit(')',1)[1].split()
            children.setdefault(int(data[1]), []).append(int(entry.name))
        except (OSError, ValueError, IndexError):
            continue
    result, queue = [], [pid]
    for parent in queue:
        near = children.get(parent, [])
        result.extend(near); queue.extend(near)
    return result


def run_native(command, seconds):
    # Inherit the outer campaign group: its hard deadline includes native work.
    proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        out, err = proc.communicate(timeout=seconds)
        return subprocess.CompletedProcess(command, proc.returncode, out, err)
    except BaseException:
        for pid in reversed(descendants(proc.pid)):
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        proc.kill(); proc.communicate()
        raise


def run_one(job):
    source, deleted, mode, sign, reference, seed, binary, out, cap, deadline = job
    start = time.monotonic()
    q, mutation = mutate(source, deleted, mode, sign)
    n = len(q); name = f'n{n}-{seed}'
    folder = Path(out)/name; folder.mkdir()
    atom_npz(folder/'input.npz', {'pose':q})
    encoded, offsets = fq.encode(q, math.floor(side(q)), math.floor(side(q)))
    assert offsets == [0, 0]
    inp, dst = folder/'input.txt', folder/'output.txt'
    inp.write_text(encoded)
    command = [str(binary), 'quench', '--in', str(inp), '--out', str(dst),
               '--rect-dx', '0', '--rect-dy', '0', '--seed', str(seed),
               *(CONTROL_OPTIONS if mode == 'control' else OPTIONS)]
    record = dict(n=n, seed=seed, mutation=mutation, reference_side=reference,
                  input_npz_sha256=fq.digest(folder/'input.npz'), native_input_sha256=fq.digest(inp),
                  folder=str(folder), command=command, binary_sha256=fq.digest(binary))
    record['feasible_seed_contacts'] = contact_edges(np.delete(source,deleted,axis=0))
    remaining = min(cap, deadline-start-2)
    previous = signal.signal(signal.SIGALRM, alarm)
    result_pose = None
    try:
        if remaining <= 1:
            record['status'] = 'budget-skipped'
            return record, None
        signal.setitimer(signal.ITIMER_REAL, remaining)
        result = run_native(command, remaining)
        (folder/'native.log').write_text(result.stdout+'\n'+result.stderr)
        if result.returncode or not dst.exists():
            record['status'] = 'native-failed'
            return record, None
        report = json.loads(result.stdout.strip().splitlines()[-1])
        if not isinstance(report, dict):
            raise ValueError('Native report is not an object')
        json.dumps(report, allow_nan=False)
        record['native_report'] = report
        result_pose = fq.decode(dst, n)
        if result_pose is None:
            record['status'] = 'failed-clearance'
            return record, None
        certificate = full_certificate(result_pose)
        record['certificate'] = certificate
        if not certificate['valid']:
            record['status'] = 'failed-full-certificate'
            return record, None
        length = float(certificate['independent_raw']['side_upper'])
        record.update(status='certified', geometry_sha256=geometry_sha(result_pose), side=length,
                      side_gain=reference-length, score_gain=(reference-length)/math.sqrt(n))
        record['certified_contacts'] = contact_edges(result_pose)
        record['changed_contact_edges'] = len(set(map(tuple,record['feasible_seed_contacts'])) ^
                                             set(map(tuple,record['certified_contacts'])))
        atom_npz(folder/'certified.npz', {'pose':result_pose})
        record['certified_npz_sha256'] = fq.digest(folder/'certified.npz')
        return record, result_pose
    except (Deadline, subprocess.TimeoutExpired):
        record['status'] = 'whole-trial-timeout'
        return record, None
    except Exception as exc:
        record.update(status='error', error_type=type(exc).__name__, error=str(exc)[:300])
        return record, None
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)
        record['elapsed_seconds'] = time.monotonic()-start
        atom_json(folder/'record.json', record)


def make_plan(poses, smoke, cap_control=False):
    orders = {n:deletion_order(poses[n+1]) for n in TARGETS}
    if cap_control:
        caps = {}
        for n in TARGETS:
            p = poses[n+1]
            tilted = set(strip_frame(p)[0].tolist())
            candidates = [i for i in orders[n] if i not in tilted]
            length = side(p)
            # Actual corner caps precede upright neighbors along the wall.
            corners = np.array([[.5,.5],[.5,length-.5],[length-.5,.5],[length-.5,length-.5]])
            caps[n] = sorted(candidates,key=lambda i:float(np.linalg.norm(corners-p[i,:2],axis=1).min()))
        plan = [(n,i,'delete',1) for j in range(4) for n in TARGETS for i in caps[n][j:j+1]]
        plan += [(n,i,'rotate6',sign) for n in (299,335) for i in caps[n] for sign in (1,-1)]
        return plan
    if smoke:
        return [(299, orders[299][0], 'delete', 1), (335, orders[335][2], 'delete', 1),
                (299, orders[299][2], 'rotate6', 1), (335, orders[335][4], 'bend', -1)]
    plan = []
    # All four cases see each structural method; 299/335 receive twice the visits.
    for sweep in range(12):
        for n in (299,335,299,335,412,454):
            j = sum(x[0] == n for x in plan)
            mode = ('delete','rotate6','bend','rotate12')[j % 4]
            deletion = orders[n][(j//4) % len(orders[n])]
            plan.append((n, deletion, mode, 1 if (j//4)%2 == 0 else -1))
    return plan


def campaign(args, started):
    os.setsid()
    deadline = started+args.seconds-5
    args.out.mkdir(parents=True, exist_ok=False)
    for name in ('source','inputs','trials'):
        (args.out/name).mkdir()
    report = json.loads(args.report.read_text())
    assert report['valid'] and report['sha256'] == fq.digest(args.raw_baseline)
    raw = {r['n']:float(r['side']) for r in report['results']}
    baseline = read_baseline(args.baseline)
    poses = {n:normalize(baseline[n]) for n in sorted(set(TARGETS)|{n+1 for n in TARGETS})}
    source_certificates = {n:full_certificate(poses[n+1]) for n in TARGETS}
    if not all(c['valid'] for c in source_certificates.values()):
        raise ValueError('A selected N+1 source failed full certification')
    atom_npz(args.out/'inputs/selected.npz', {str(n):p for n,p in poses.items()})
    binary = (args.out/'inputs/fq').resolve(); shutil.copy2(args.binary,binary); binary.chmod(0o500)
    sources = [Path(__file__),ROOT/'experiments/fq_active_pilot.py', ROOT/'experiments/fq_capacity_probe.py',
               ROOT/'experiments/fq_coherent_clusters.py', ROOT/'experiments/compose_gadgets.py',
               ROOT/'scripts/score_official.py', ROOT/'scripts/validate_submission.py',
               ROOT/'research/official_metric_v17.py']
    for p in sources:
        shutil.copy2(p,args.out/'source'/p.name)
        (args.out/'source'/p.name).chmod(0o444)
    plan = make_plan(poses,args.smoke,args.cap_control)
    manifest = dict(kind='N+1 deletion and coherent full-puzzle structural search', workers=2,
                    seconds=args.seconds, trial_seconds=args.trial_seconds, binary_sha256=fq.digest(binary),
                    source_commit=fq.SOURCE_COMMIT, source_hashes={str(p):fq.digest(p) for p in sources},
                    inputs={str(p):fq.digest(p) for p in [args.baseline,args.raw_baseline,args.report,args.public]},
                    selected_sha256=fq.digest(args.out/'inputs/selected.npz'), reference_sides={n:raw[n] for n in TARGETS},
                    source_certificates=source_certificates,
                    modes=OPTIONS, plan=plan, seed=args.seed, smoke=args.smoke, cap_control=args.cap_control,
                    comparison='Frozen raw b937 case side, never deleted/mutated parent side',
                    geometry_gates='official raw, 17g pandas, default pandas; independent interval raw and default pandas')
    atom_json(args.out/'manifest.json',manifest)
    for p in (args.out/'inputs').iterdir():
        if p.name != 'fq': p.chmod(0o444)
    records, donors, best = [], {}, {}
    snapshot_index = 0

    def checkpoint(status):
        nonlocal snapshot_index
        snapshot_index += 1
        dest = args.out/f'snapshot-{snapshot_index:05d}'; dest.mkdir()
        atom_json(dest/'results.json',records)
        atom_npz(dest/'donors.npz',donors)
        candidates = {str(n):dict(side=item['side'], squares=[[f'{v:.17g}' for v in row] for row in item['pose']],
                                 certificate=item['certificate'], provenance=item['provenance']) for n,item in best.items()}
        atom_json(dest/'candidates.json',candidates)
        summary = dict(status=status, elapsed_seconds=time.monotonic()-started, trials=len(records),
                       certified_variants=len(donors), improved_cases=len(best),
                       total_score_gain=sum((raw[n]-item['side'])/math.sqrt(n) for n,item in best.items()),
                       statuses={s:sum(r['status']==s for r in records) for s in sorted({r['status'] for r in records})},
                       manifest_sha256=fq.digest(args.out/'manifest.json'),
                       output_hashes={p.name:fq.digest(p) for p in dest.iterdir()})
        atom_json(dest/'summary.json',summary)
        for p in dest.iterdir(): p.chmod(0o444)
        atom_json(args.out/'current.json',dict(snapshot=str(dest),summary_sha256=fq.digest(dest/'summary.json')))
        return summary

    checkpoint('prepared')
    with ProcessPoolExecutor(max_workers=2,mp_context=mp.get_context('fork')) as pool:
        pending = {}; cursor = 0
        while pending or (cursor < len(plan) and time.monotonic() < deadline-args.trial_seconds):
            while len(pending)<2 and cursor<len(plan) and time.monotonic()<deadline-args.trial_seconds:
                n,deleted,mode,sign = plan[cursor]
                job = (poses[n+1],deleted,mode,sign,raw[n],args.seed+cursor,binary,
                       (args.out/'trials').resolve(),args.trial_seconds,deadline)
                pending[pool.submit(run_one,job)] = cursor; cursor += 1
            if not pending: break
            done,_ = wait(pending,timeout=1,return_when=FIRST_COMPLETED)
            for future in done:
                index = pending.pop(future)
                try: record,q = future.result()
                except Exception as exc:
                    record,q = dict(status='unexpected-worker-error',error=str(exc)[:300]),None
                record['trial_index'] = index; records.append(record)
                if q is not None:
                    n = len(q); sha = geometry_sha(q); donors[f'{n}__{sha}'] = q
                    if record['side'] < min(raw[n]-1e-9,best.get(n,{}).get('side',float('inf'))):
                        best[n] = dict(side=record['side'],pose=q,certificate=record['certificate'],
                                       provenance=dict(trial_index=index,record=str(Path(record['folder'])/'record.json'),
                                                       manifest_sha256=fq.digest(args.out/'manifest.json')))
                summary = checkpoint('running')
                print(json.dumps({k:record[k] for k in ('trial_index','n','status','side_gain','elapsed_seconds') if k in record}),flush=True)
                if q is not None and record['side_gain']>1e-5:
                    print(json.dumps(dict(stage='material-candidate',current=str(args.out/'current.json'),**summary)),flush=True)
    assert fq.digest(binary) == manifest['binary_sha256']
    print(json.dumps(checkpoint('complete')),flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline',type=Path,default=ROOT/'artifacts/submission-omitted-donor-pair-v1-safe.csv')
    parser.add_argument('--raw-baseline',type=Path,default=ROOT/'artifacts/merged-omitted-donor-pair-v1.csv')
    parser.add_argument('--report',type=Path,default=ROOT/'artifacts/merged-omitted-donor-pair-v1-official.json')
    parser.add_argument('--public',type=Path,default=ROOT/'artifacts/public-freshness/notebooks-20261024T092136Z/public-gap-analysis.json')
    parser.add_argument('--binary',type=Path,default=Path('/tmp/squares-fq-portable-target/release/fq'))
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--seconds',type=float,default=600)
    parser.add_argument('--trial-seconds',type=float,default=20)
    parser.add_argument('--seed',type=int,default=13270001)
    parser.add_argument('--smoke',action='store_true')
    parser.add_argument('--cap-control',action='store_true')
    args = parser.parse_args()
    if args.out.exists() or not 20<=args.seconds<=600 or not 2<=args.trial_seconds<=25:
        parser.error('Require new output, 20–600 seconds total and 2–25 seconds per trial')
    started = time.monotonic()
    process = mp.get_context('fork').Process(target=campaign,args=(args,started));process.start()
    process.join(max(0,args.seconds-1-(time.monotonic()-started)))
    enforced = process.is_alive()
    if enforced:
        try:
            os.killpg(process.pid,signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.join(.5)
    receipt = dict(elapsed_seconds=time.monotonic()-started,exitcode=process.exitcode,hard_deadline_enforced=enforced)
    if args.out.exists(): atom_json(args.out/'supervisor.json',receipt)
    print(json.dumps(receipt),flush=True)
    if process.exitcode and not enforced: raise SystemExit(process.exitcode)


if __name__ == '__main__':
    main()
