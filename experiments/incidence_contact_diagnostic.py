"""Finite diagnostic of Evan Daniel's MIT incidence contact model.

The pinned public model is unmodified. Relaxed LPs are lower bounds only;
every returned direction is unverified until nonlinear and full gates pass.
"""
from __future__ import annotations
import os
for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[key] = '1'
import argparse
from decimal import Decimal
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import signal
import subprocess
import sys
import time
import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def gsha(p):
    return hashlib.sha256(np.asarray(p, dtype='<f8').tobytes()).hexdigest()


def save(path, obj):
    temp = path.with_suffix(path.suffix + '.incoming')
    temp.write_text(json.dumps(obj, indent=2) + '\n')
    temp.replace(path)


def archive(path, **arrays):
    temp = path.with_suffix(path.suffix + '.incoming')
    with temp.open('wb') as f:
        np.savez_compressed(f, **arrays)
    temp.replace(path)


def load_model(out):
    spec = importlib.util.spec_from_file_location('pinned_incidence', out/'source/public/inc.py')
    model = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(model)
    return model


def solve(out, spec_path):
    spec = json.loads(spec_path.read_text())
    assert sha(out/'source/public/inc.py') == spec['model_sha256']
    assert sha(spec['input']) == spec['input_sha256']
    p = np.load(spec['input'])['pose']; n = len(p)
    model = load_model(out)
    rows, disj = model.model_fast(spec['side'], p, 3*spec['R'])
    solver_reports=[]; joint_binary=None
    original_milp=model.milp
    def observed_milp(*args, **kwargs):
        nonlocal joint_binary
        result=original_milp(*args, **kwargs)
        solver_reports.append(dict(status=int(result.status),message=str(result.message),
            mip_gap=None if getattr(result,'mip_gap',None) is None else float(result.mip_gap),
            mip_dual_bound=None if getattr(result,'mip_dual_bound',None) is None else float(result.mip_dual_bound)))
        if result.x is not None:joint_binary=np.asarray(result.x[3*n+1:],dtype='<f8')
        return result
    model.milp=observed_milp
    started = time.monotonic(); mode = spec['mode']
    if mode == 'relaxed':
        A, g = model._mat(rows, 3*n+1)
        ds, z = model._lp(A, g, 3*n+1, spec['R'], False, (),
                          time_limit=spec['solver_seconds'], clip=True)
    elif mode in ('default', 'rounded'):
        ds, z, _, _ = model.shrink(spec['side'], p, 3*spec['R'], spec['R'],
                                   exact=False, switch=mode == 'rounded')
    elif mode == 'joint':
        ds, z, _ = model.shrink_milp(spec['side'], p, delta=3*spec['R'],
                                    R=spec['R'], exact=False, time_limit=spec['solver_seconds'])
    else:
        raise ValueError(mode)
    record = dict(status='UNVERIFIED_LINEAR_DIRECTION', mode=mode,
                  ordinary_rows=len(rows[0]), disjunctions=len(disj),
                  predicted_ds=None if ds is None else float(ds), seconds=time.monotonic()-started,
                  joint_solver_reports=solver_reports, ordinary_negative_gap_count=int(np.sum(rows[0]<0)),
                  no_global_jam_claim=True)
    if z is not None:
        assert np.asarray(z).shape == (3*n+1,) and np.isfinite(z).all()
        path = spec_path.with_suffix('.direction.npz')
        arrays=dict(direction=np.asarray(z, dtype='<f8'))
        if joint_binary is not None:arrays['joint_binary']=joint_binary
        archive(path, **arrays)
        original=[max(range(len(alts)),key=lambda k:min(alts[k][0])) for _,alts in disj]
        preferred=[max(range(len(alts)),key=lambda k:model._alt_slack(alts[k],z)) for _,alts in disj]
        record['direction_preferred_branch_changes']=sum(a!=b for a,b in zip(original,preferred))
        record.update(direction=str(path), direction_sha256=sha(path))
    save(spec_path.with_suffix('.result.json'), record)


def bounded_solve(out, case, input_path, side, R, mode, cap, deadline):
    cap = min(cap, deadline-time.monotonic())
    name = f"{case}-r{R:g}-{mode}"
    path = out/'trials'/f'{name}.spec.json'
    spec = dict(input=str(input_path), input_sha256=sha(input_path), side=side, R=R,
                mode=mode, model_sha256=sha(out/'source/public/inc.py'),
                solver_seconds=max(.1, cap-.5), status='UNVERIFIED')
    save(path, spec)
    if cap < .75:
        return dict(mode=mode, status='budget_skipped', spec=str(path))
    started = time.monotonic()
    proc = subprocess.Popen([sys.executable, str(out/'source/driver.py'), '--out', str(out),
                             '--solve', str(path)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    timed_out = False
    try:
        log, _ = proc.communicate(timeout=cap)
    except subprocess.TimeoutExpired:
        timed_out = True; proc.kill(); log, _ = proc.communicate()
    path.with_suffix('.log').write_bytes(log)
    result_path = path.with_suffix('.result.json')
    record = json.loads(result_path.read_text()) if result_path.exists() else dict(status='no_returned_direction')
    record.update(mode=mode, spec=str(path), spec_sha256=sha(path), process_returncode=proc.returncode,
                  timeout=timed_out, wall_seconds=time.monotonic()-started)
    if timed_out:
        record['status'] = 'interrupted_UNVERIFIED'
    return record


def nonlinear(p, side):
    a=p[:,2]; e=.5*(abs(np.cos(a))+abs(np.sin(a)))
    wall=max(0.,float(np.max(e[:,None]-p[:,:2])),float(np.max(p[:,:2]+e[:,None]-side)))
    i,j=np.triu_indices(len(p),1); d=p[j,:2]-p[i,:2]
    proj=np.maximum.reduce([abs(d[:,0]*np.cos(t)+d[:,1]*np.sin(t))
                            for t in (a[i],a[i]+np.pi/2,a[j],a[j]+np.pi/2)])
    radius=.5*(1+abs(np.cos(a[i]-a[j]))+abs(np.sin(a[i]-a[j])))
    pair=max(0.,float(np.max(radius-proj)))
    actual=float(np.max(np.max(p[:,:2]+e[:,None],axis=0)-np.min(p[:,:2]-e[:,None],axis=0)))
    return dict(pair_residual=pair,wall_residual=wall,actual_side=actual)


def full_gate(p, seconds):
    from fq_capacity_probe import full_certificate
    from fq_coherent_clusters import Deadline, alarm
    old=signal.signal(signal.SIGALRM,alarm); signal.setitimer(signal.ITIMER_REAL,seconds)
    try:
        return full_certificate(p)
    except Deadline:
        return dict(valid=False,timeout=True)
    finally:
        signal.setitimer(signal.ITIMER_REAL,0); signal.signal(signal.SIGALRM,old)


def worst_side(cert):
    gate=cert['shared_official_gate']
    return max(Decimal(cert['ordinary_pandas_official_side']),Decimal(gate['raw_side']),
               Decimal(gate['roundtrip_side']),Decimal(cert['independent_raw']['side_upper']),
               Decimal(cert['independent_roundtrip']['side_upper']))


def retain_direction(out, case, record, p, side, reference, deadline, donors):
    from compose_gadgets import legalize
    if record.get('timeout') or 'direction' not in record:
        return
    path=Path(record['direction']); assert sha(path)==record['direction_sha256']
    z=np.load(path)['direction']; n=len(p)
    arrays={}; screens=[]; viable=[]
    for k in range(9):
        alpha=2.**(-k); q=p+alpha*z[:3*n].reshape(n,3); box=side+alpha*z[-1]
        arrays[f'raw_{k}']=q; screen=dict(alpha=alpha,box=float(box),status='UNVERIFIED',
                                         geometry_sha256=gsha(q),**nonlinear(q,box))
        repaired=legalize(q)
        if repaired is not None:
            arrays[f'legalized_{k}']=repaired
            screen['legalized_geometry_sha256']=gsha(repaired)
            screen['legalized_screen']=nonlinear(repaired,nonlinear(repaired,box)['actual_side'])
            viable.append((screen['legalized_screen']['actual_side'],k,repaired))
        screens.append(screen)
    raw_path=path.with_name(path.stem+'.nonlinear.npz'); archive(raw_path,**arrays)
    record.update(nonlinear_screens=screens,nonlinear_archive=str(raw_path),nonlinear_sha256=sha(raw_path))
    if not viable or deadline-time.monotonic()<.5:
        return
    _, k, q=min(viable,key=lambda v:(v[0],v[1]))
    cert=full_gate(q,min(8.,deadline-time.monotonic()))
    cert_path=path.with_name(path.stem+'.certificate.json'); save(cert_path,cert)
    record.update(certified=bool(cert['valid']),certificate=str(cert_path),certificate_sha256=sha(cert_path),selected_alpha=2.**(-k))
    if cert['valid']:
        assert cert['independent_raw']['n']==n
        key=f'{case}__{record["mode"]}__{gsha(q)}'; donors[key]=q
        archive(out/'certified-donors.npz',**donors)
        final=worst_side(cert)
        record.update(certified_key=key,certified_geometry_sha256=gsha(q),certified_worst_side=str(final),
                      strict_gain=str(Decimal(reference)-final),strict_improvement=final<Decimal(reference)-Decimal('1e-9'))


def campaign(out):
    manifest=json.loads((out/'manifest.json').read_text())
    for entry in manifest['files']:
        assert sha(entry['path'])==entry['sha256'],entry['path']
    allowed=os.sched_getaffinity(0); os.sched_setaffinity(0,{4 if 4 in allowed else min(allowed)})
    started=time.monotonic(); deadline=started+120.; records=[]; donors={}
    # Historical controls get a smaller finite allocation; no new starts are generated.
    allocations=(24.,18.,37.,37.)
    for case, allocation in zip(manifest['cases'],allocations):
        if deadline-time.monotonic()<.5:break
        if case['name'].startswith('current') and not all(r.get('control_passed') for r in records[:2]):
            records.append(dict(case=case['name'],status='skipped_failed_or_inconclusive_historical_control'))
            save(out/'results.json',records);continue
        case_end=min(deadline,time.monotonic()+allocation)
        input_path=Path(case['input']); p=np.load(input_path)['pose']; side=float(case['side'])
        record=dict(case=case['name'],n=len(p),input_sha256=sha(input_path),reference_side=case['side'],trials=[])
        cert=full_gate(p,min(8.,case_end-time.monotonic()));save(out/'trials'/f'{case["name"]}-input.certificate.json',cert)
        record['input_certified']=bool(cert['valid'])
        if not cert['valid']:
            record['status']='input_gate_failed';records.append(record);save(out/'results.json',records);continue
        donors[f'{case["name"]}__input__{gsha(p)}']=p;archive(out/'certified-donors.npz',**donors)
        joint_attempted=False
        for R in (1e-3,1e-2):
            if case_end-time.monotonic()<2.:break
            relaxed=bounded_solve(out,case['name'],input_path,side,R,'relaxed',4.,case_end)
            record['trials'].append(relaxed)
            ds=relaxed.get('predicted_ds'); eligible=not relaxed.get('timeout') and ds is not None and ds < -max(1e-11,1e-6*R)
            relaxed['joint_eligible']=eligible
            if not eligible:
                relaxed['decision']='skip restricted/joint: relaxed model has no material returned descent'
                save(out/'results.json',records+[record]);continue
            for mode, cap in (('default',4.),('rounded',5.),('joint',15.)):
                if mode=='joint' and joint_attempted:continue
                if case_end-time.monotonic()<2.:break
                trial=bounded_solve(out,case['name'],input_path,side,R,mode,cap,case_end)
                trial['R']=R; record['trials'].append(trial)
                if mode=='joint':joint_attempted=True
                retain_direction(out,case['name'],trial,p,side,case['side'],case_end,donors)
                save(out/'results.json',records+[record])
        record['seconds']=allocation-max(0.,case_end-time.monotonic())
        if case['name'].startswith('control'):
            gains=[Decimal(t['strict_gain']) for t in record['trials'] if t.get('certified')]
            returned_relaxed=any(t.get('mode')=='relaxed' and not t.get('timeout') and t.get('predicted_ds') is not None for t in record['trials'])
            if case['name']=='control_false110':record['control_passed']=bool(gains and max(gains)>Decimal('1e-8'))
            else:record['control_passed']=bool(returned_relaxed and (not gains or max(gains)<Decimal('1e-7')))
        records.append(record);save(out/'results.json',records)
    save(out/'summary.json',dict(seconds=time.monotonic()-started,requested_work_seconds=120,
                                 cases=len(records),certified_poses=len(donors),native_calls=0,
                                 results_sha256=sha(out/'results.json'),
                                 donors_sha256=sha(out/'certified-donors.npz') if donors else None,
                                 current_case_wins=[dict(case=r['case'],mode=t['mode'],side=t['certified_worst_side'])
                                    for r in records if r['case'].startswith('current') for t in r.get('trials',[]) if t.get('strict_improvement')]))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,required=True);parser.add_argument('--solve',type=Path)
    args=parser.parse_args()
    if args.solve:solve(args.out,args.solve)
    else:campaign(args.out)
