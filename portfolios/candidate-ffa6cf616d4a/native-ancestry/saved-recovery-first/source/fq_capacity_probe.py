#!/usr/bin/env python3
"""One-worker, externally bounded strict extra-square probe on frozen FQ cores.

Removing a nearly upright square supplies only a candidate center. Strict SAT,
upright conflict constraints and independent/official numeric transport checks
decide whether any increased-capacity donor is admissible. No GPU/submission.
"""
from __future__ import annotations

import time
ENTRY_STARTED = time.monotonic()

import argparse
import csv
import hashlib
import io
import json
import math
import multiprocessing as mp
import os
from pathlib import Path
import shutil
import signal
import sys

for variable in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[variable] = '1'

import numpy as np
import pandas as pd

from compose_gadgets import extents, normalize
from refill_capacity import capacity
from fq_active_pilot import certify, bloat, SOURCE_COMMIT

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from validate_submission import Square, validate_puzzle
from score_official import load_metric, OFFICIAL_SHA256


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def geometry_sha(p):
    return hashlib.sha256(np.asarray(p, dtype='<f8').tobytes()).hexdigest()


def atomic_json(path, value):
    temporary = path.with_suffix(path.suffix+'.incoming')
    temporary.write_text(json.dumps(value, indent=2)+'\n')
    temporary.replace(path)


def canonical_pose(key, p):
    w, h, d = map(int, key.split('__')[0].split('_'))
    if p.shape != (w*h+d, 3) or not np.isfinite(p).all():
        raise ValueError('Input type/count/geometry mismatch')
    transpose = w > h
    q = p.copy()
    if transpose:
        w, h = h, w
        q[:, :2] = q[:, [1, 0]]
        q[:, 2] = np.pi/2-q[:, 2]
    return f'{w}_{h}_{d}', normalize(q), transpose


def finite_worker(connection, p, W, H, threshold):
    try:
        q, info = capacity(p, W, H, upright_threshold=threshold)
        connection.send(('complete', q, info))
    except BaseException as error:
        connection.send(('error', type(error).__name__, None))
    finally:
        connection.close()


def bounded_capacity(p, W, H, threshold, seconds):
    """Kill the sole finite-candidate worker before the two-second trial ceiling."""
    begin = time.monotonic()
    receiver, sender = mp.get_context('fork').Pipe(duplex=False)
    worker = mp.get_context('fork').Process(target=finite_worker, args=(sender,p,W,H,threshold))
    worker.start(); sender.close()
    value = ('timeout', None, None)
    try:
        if receiver.poll(max(0., seconds-.12-(time.monotonic()-begin))):
            value = receiver.recv()
    except EOFError:
        value = ('worker_exit', None, None)
    finally:
        receiver.close()
        worker.join(timeout=min(.02,max(0.,seconds-.06-(time.monotonic()-begin))))
        if worker.is_alive():
            worker.kill()
        worker.join(timeout=max(0.,seconds-.01-(time.monotonic()-begin)))
    return value, time.monotonic()-begin


def full_certificate(q):
    """Use the shared official gate plus ordinary default-pandas and interval gates."""
    shared = certify(q)
    rows = [dict(n=str(len(q)),square_id=str(i),x=f'{x:.17g}',y=f'{y:.17g}',angle=f'{a:.17g}')
            for i,(x,y,a) in enumerate(q)]
    raw_csv = pd.DataFrame(rows).to_csv(index=False)
    numeric_csv = pd.read_csv(io.StringIO(raw_csv)).to_csv(index=False)
    numeric = list(csv.DictReader(io.StringIO(numeric_csv)))
    metric = load_metric(ROOT/'research/official_metric_v17.py')
    official_numeric = metric._evaluate_puzzle_worker((len(q),numeric))
    interval = [validate_puzzle(len(q),[Square(r['x'],r['y'],r['angle'])for r in rr])
                for rr in (rows,numeric)]
    valid = shared['valid'] and official_numeric[3]=='ok' and all(r['valid']for r in interval)
    return {'valid':valid,'shared_official_gate':shared,
            'ordinary_pandas_official_reason':official_numeric[3],
            'ordinary_pandas_official_side':official_numeric[2],
            'independent_raw':interval[0],'independent_roundtrip':interval[1],
            'raw_csv_sha256':hashlib.sha256(raw_csv.encode()).hexdigest(),
            'ordinary_pandas_csv_sha256':hashlib.sha256(numeric_csv.encode()).hexdigest()}


def campaign(args):
    os.setsid()
    deadline = ENTRY_STARTED+args.seconds-3.
    args.out.mkdir(parents=True,exist_ok=False)
    inputs = args.out/'inputs'; inputs.mkdir()
    sources = args.out/'source'; sources.mkdir()
    input_records, choices = [], {}
    for i, original in enumerate(args.bank):
        path = inputs/f'bank-{i:02d}.npz'; shutil.copyfile(original,path); path.chmod(0o444)
        record = {'original_path':str(original),'snapshot':str(path),'sha256':digest(path),'poses':[]}
        with np.load(path,allow_pickle=False)as z:
            for source_key in z.files:
                original_pose = np.asarray(z[source_key],dtype=float)
                key,p,transpose = canonical_pose(source_key,original_pose)
                w,h,d = map(int,key.split('_')); f = bloat(p,w,h)
                meta = {'source_key':source_key,'canonical_key':key,'transposed':transpose,
                        'original_geometry_sha256':geometry_sha(original_pose),
                        'canonical_geometry_sha256':geometry_sha(p),'actual_bloat':f,
                        'source_archive_sha256':record['sha256']}
                record['poses'].append(meta)
                if key not in choices or f<choices[key]['f']:
                    choices[key] = {'p':p,'f':f,'source':meta,'w':w,'h':h,'d':d}
        input_records.append(record)
    source_files = [Path(__file__),ROOT/'experiments/refill_capacity.py',ROOT/'experiments/refill_search.py',
                    ROOT/'experiments/compose_gadgets.py',ROOT/'experiments/fq_active_pilot.py',
                    ROOT/'scripts/score_official.py',ROOT/'scripts/validate_submission.py',
                    ROOT/'research/official_metric_v17.py']
    source_hashes = {}
    for original in source_files:
        target = sources/original.name; shutil.copyfile(original,target); target.chmod(0o444)
        source_hashes[str(original.relative_to(ROOT))] = digest(target)
    # Freeze the executed command as structured tokens; no shell interpolation.
    command = [sys.executable,str(Path(__file__).resolve()),*sys.argv[1:]]
    command_sha = hashlib.sha256(json.dumps(command,separators=(',',':')).encode()).hexdigest()
    manifest = {'kind':'fresh_fq_strict_capacity_probe','inputs':input_records,'sources':source_hashes,
                'command':command,'command_sha256':command_sha,'fq_source_commit':SOURCE_COMMIT,
                'official_metric_sha256':OFFICIAL_SHA256,'slack':[0.,.002,.02],
                'upright_thresholds':[1e-6,.018],'soft':0.,'workers':1,
                'finite_trial_seconds':args.trial_seconds,'maximum_outer_seconds':args.seconds,
                'canonical_types':len(choices),'discarded_transpose_entries':sum(len(i['poses'])for i in input_records)-len(choices),
                'warning':'Finite candidate capacities are lower bounds, not continuous optimality certificates. '
                    'Removed near-uprights contribute candidate centers only; all output geometry is checked anew.'}
    atomic_json(args.out/'manifest.json',manifest)
    trials,certified = [],{}

    def checkpoint(status):
        temporary = args.out/'increased_surplus.incoming.npz'
        np.savez_compressed(temporary,**certified)
        temporary.replace(args.out/'increased_surplus.npz')
        report = {'status':status,'elapsed_seconds':time.monotonic()-ENTRY_STARTED,
                  'manifest_sha256':digest(args.out/'manifest.json'),'trials':trials,
                  'attempted':len(trials),'certified_variants':len(certified),
                  'increased_surplus_sha256':digest(args.out/'increased_surplus.npz'),
                  'finite_trial_seconds':args.trial_seconds,'maximum_outer_seconds':args.seconds,
                  'scope':'Strict finite candidate search. Counts/soft estimates are not certificates; '
                          'only entries with full certificate.valid=true are exported.'}
        atomic_json(args.out/'report.json',report)

    checkpoint('configured')
    # Complete every family at each slack before spending time on further slack.
    ordered = sorted(choices.items(),key=lambda item:(item[1]['w']*item[1]['h'],item[0]))
    for slack in (0.,.002,.02):
        for threshold in (1e-6,.018):
            for key,item in ordered:
                if time.monotonic()>=deadline-2:break
                begin = time.monotonic(); f = item['f']; allowed = f+slack
                record = {'type':key,'source':item['source'],'source_count':len(item['p']),
                          'actual_bloat':f,'slack':slack,'box_bloat':allowed,
                          'upright_threshold':threshold,'soft':0.}
                if allowed>=1:
                    record['status']='rejected_box_bloat_at_least_one'
                else:
                    W,H = item['w']+allowed,item['h']+allowed
                    record.update(W=W,H=H)
                    (status,q,info),elapsed = bounded_capacity(item['p'],W,H,threshold,
                        min(args.trial_seconds,deadline-time.monotonic()))
                    record.update(status=status,finite_elapsed_seconds=elapsed)
                    if status=='complete':
                        record.update(info); count = len(q)
                        if count>len(item['p']):
                            record['extra_squares']=count-len(item['p'])
                            lo,hi = extents(q)
                            within = bool((lo>=-1e-12).all()and(hi<=np.array([W,H])+1e-12).all())
                            record['within_allowed_box']=within
                            if not within:
                                record['status']='rejected_box'
                            elif time.monotonic()<deadline-1:
                                certificate = full_certificate(q)
                                record['certificate']=certificate
                                if certificate['valid']:
                                    newd = count-item['w']*item['h']
                                    identity = f"{item['w']}_{item['h']}_{newd}__capacity_{geometry_sha(q)[:20]}"
                                    certified[identity]=q.copy()
                                    record.update(status='capacity_certified',donor_key=identity,
                                                  donor_geometry_sha256=geometry_sha(q),
                                                  new_surplus=newd,exported_bloat=bloat(q,item['w'],item['h']))
                                else:record['status']='rejected_geometry_or_transport'
                            else:record['status']='capacity_observed_but_not_certified_deadline'
                record['elapsed_seconds']=time.monotonic()-begin
                trials.append(record); checkpoint('running')
                if len(trials)%10==0 or record['status']=='capacity_certified':
                    print(json.dumps({'event':'progress','attempted':len(trials),'type':key,
                                      'status':record['status'],'capacity':record.get('capacity'),
                                      'certified':len(certified),'elapsed_seconds':time.monotonic()-ENTRY_STARTED}),flush=True)
            if time.monotonic()>=deadline-2:break
        if time.monotonic()>=deadline-2:break
    changed = [str(original)for original in source_files if digest(original)!=source_hashes[str(original.relative_to(ROOT))]]
    if changed:
        atomic_json(args.out/'provenance-error.json',{'changed_source_paths':changed})
        checkpoint('source_changed_during_run')
        raise ValueError('Executed helper source changed during run; quarantine outputs')
    checkpoint('complete')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bank',type=Path,action='append',required=True)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--seconds',type=float,default=240.)
    parser.add_argument('--trial-seconds',type=float,default=1.9)
    args = parser.parse_args()
    if args.out.exists()or not 5<args.seconds<=240 or not .1<args.trial_seconds<=2:
        parser.error('Require a new output directory,5<seconds<=240 and.1<trial-seconds<=2')
    process = mp.get_context('fork').Process(target=campaign,args=(args,))
    process.start()
    process.join(timeout=max(0.,args.seconds-1.5-(time.monotonic()-ENTRY_STARTED)))
    enforced = process.is_alive()
    if enforced:
        try:os.killpg(process.pid,signal.SIGKILL)
        except ProcessLookupError:process.kill()
        process.join(timeout=.4)
    receipt = {'status':'hard_deadline_enforced'if enforced else'exited','exitcode':process.exitcode,
               'elapsed_seconds':time.monotonic()-ENTRY_STARTED,'configured_seconds':args.seconds,
               'includes_input_copy_solving_validation_and_checkpoints':True,
               'single_finite_worker':True,'no_gpu':True,'no_competition_submission':True}
    if args.out.exists():atomic_json(args.out/'supervisor.json',receipt)
    print(json.dumps(receipt),flush=True)
    if process.exitcode and not enforced:raise SystemExit(process.exitcode)


if __name__=='__main__':main()
