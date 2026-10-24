#!/usr/bin/env python3
"""One-CPU FQ treatment of strictly certified omitted night-seed types."""
import time
ENTRY_STARTED=time.monotonic()
import argparse
from collections import Counter
from decimal import Decimal,getcontext
import json
import math
import multiprocessing as mp
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys

for variable in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[variable]='1'
import numpy as np
import fq_active_pilot as fq
from compose_gadgets import legalize
from extract_broad_active_frontier import orient,geometry_sha
from fq_coherent_clusters import Deadline,alarm,grouped_run,atom_json,atom_npz
from fq_capacity_probe import full_certificate
from validate_submission import Square,_geometry,_iv_min,_iv_max,_endpoint_text

ROOT=Path(__file__).resolve().parents[1]
getcontext().prec=100
OPTIONS={
 'contact20':['--no-alm','--loosen','1','--pit','20','--flip-top','0'],
 'kick03':['--loosen','1.002','--kick','.03','--outer','35','--pit','60','--flip-top','12'],
 'soft15':['--loosen','1','--soft-compress','--soft-a0','.15','--soft-steps','8',
           '--soft-kick','.01','--hold-f','1.001','--outer','35','--pit','60','--flip-top','12','--v'],
 'kick08':['--loosen','1.004','--kick','.08','--outer','45','--pit','70','--flip-top','16'],
 'round15':['--loosen','1','--round-r0','.15','--round-compress','--round-steps','10',
            '--round-kick','.01','--outer','30','--pit','60','--flip-top','12'],
}


def excess_interval(p,w,h):
    squares=[Square(*(f'{v:.17g}' for v in row)) for row in p]
    g=_geometry(squares,80)
    x=_iv_max([a[0]+a[4] for a in g])-_iv_min([a[0]-a[4] for a in g])-w
    y=_iv_max([a[1]+a[4] for a in g])-_iv_min([a[1]-a[4] for a in g])-h
    value=_iv_max([x,y])
    return dict(lower=_endpoint_text(value.a,False),upper=_endpoint_text(value.b,True))


def checkpoint_directory(root,count,status):
    suffix='-complete' if status=='complete' else ''
    folder=root/f'snapshot-{count:05d}{suffix}'
    folder.mkdir(exist_ok=False)
    return folder


def run_one(key,p,mode,binary,directory,seed,cap,deadline):
    w,h,d=map(int,key.split('_'));assert p.shape==(w*h+d,3)
    options=OPTIONS[mode];name=f'{key}-{mode}-{seed}'
    inp,dst=directory/(name+'.in'),directory/(name+'.out')
    encoded,offsets=fq.encode(p,w,h);inp.write_text(encoded)
    cmd=[str(binary),'quench','--in',str(inp),'--out',str(dst),'--rect-dx',str(offsets[0]),
         '--rect-dy',str(offsets[1]),'--seed',str(seed),*options]
    start=time.monotonic();remaining=min(cap,deadline-start-2)
    record=dict(key=key,mode=mode,seed=seed,parent_geometry_sha256=geometry_sha(p),
        command=cmd,input_sha256=fq.digest(inp),output_path=str(dst))
    if remaining<1:return dict(record,status='budget-skipped'),None
    previous=signal.signal(signal.SIGALRM,alarm);signal.setitimer(signal.ITIMER_REAL,remaining)
    try:
        run=grouped_run(cmd,capture_output=True,text=True,timeout=remaining)
        log=directory/(name+'.log');log.write_text(run.stdout+'\n'+run.stderr)
        record['returncode']=run.returncode
        if run.returncode or not dst.exists():return dict(record,status='fq-failed'),None
        native=json.loads(run.stdout.strip().splitlines()[-1]);json.dumps(native,allow_nan=False)
        record['fq']=native
        if mode=='soft15':
            values=[float(v) for v in re.findall(r'soft eps ([0-9.eE+-]+) hold',log.read_text())]
            passed=len(values)==8 and values[-1]==0 and all(a>=b>=0 for a,b in zip(values,values[1:])) and native.get('soft',{}).get('a0')==.15
            record['rigid_return_trace']=dict(valid=passed,epsilons=values,log_sha256=fq.digest(log))
            if not passed:return dict(record,status='soft-trace-rejected'),None
        q=fq.decode(dst,len(p))
        if q is None:return dict(record,status='clearance-failed'),None
        bounds=excess_interval(q,w,h);record['excess_interval']=bounds
        if not 0<Decimal(bounds['lower'])<=Decimal(bounds['upper'])<1:
            return dict(record,status='outside-unit-excess'),None
        certificate=full_certificate(q);record['certificate']=certificate
        if not certificate['valid']:return dict(record,status='certificate-failed'),None
        record.update(status='certified',geometry_sha256=geometry_sha(q))
        return record,q
    except (Deadline,subprocess.TimeoutExpired):
        return dict(record,status='whole-trial-timeout'),None
    except Exception as exc:
        return dict(record,status='error',error_type=type(exc).__name__,error=str(exc)[:200]),None
    finally:
        signal.setitimer(signal.ITIMER_REAL,0);signal.signal(signal.SIGALRM,previous)
        record['elapsed_seconds']=time.monotonic()-start


def campaign(args):
    os.setsid();signal.signal(signal.SIGTERM,alarm)
    deadline=ENTRY_STARTED+args.seconds-5
    args.out.mkdir(parents=True,exist_ok=False)
    for name in ('inputs','source','trials'):(args.out/name).mkdir()
    binary=args.out/'inputs/fq';shutil.copy2(args.binary,binary);binary.chmod(0o500)
    expected='10ec7cf773ac0ebca3791d5cfb84e9ecbb10e3f0a9e43194330c80e1cfc9dc3d'
    assert fq.digest(binary)==expected
    inventory=json.loads((args.inventory/'report.json').read_text())
    entries=json.loads((args.inventory/'omitted-poses.json').read_text())
    wanted=set(inventory['novel_types']);assert len(wanted)==26
    sources={};references={};refproof=[]
    for typ in sorted(wanted):
        w,h,d=map(int,typ.split('_'))
        matches=sorted((e for e in entries if e['canonical_type']==typ),key=lambda e:e['excess'])
        # Every historical pose for these absent types is in the omitted list.
        best=None
        for entry in matches:
            origin=entry['source'];path=origin['archive']
            if path not in sources:
                assert fq.digest(path)==origin['archive_sha256']
                with np.load(path,allow_pickle=False) as z:sources[path]={k:z[k] for k in z.files}
            p=sources[path][origin['key']]
            assert geometry_sha(p)==entry['geometry_sha256']
            q=orient(p,entry['w']>entry['h'],1,1)
            bounds=excess_interval(q,w,h)
            # Initial entries are sorted by native floating extent. Inspect all
            # within1e-10 of the current minimum before certifying the best.
            if best is not None and entry['excess']>float(best[0]['upper'])+1e-10:break
            if best is None or Decimal(bounds['upper'])<Decimal(best[0]['upper']):best=(bounds,q,entry)
        assert best is not None
        bounds,p,entry=best;certificate=full_certificate(p)
        if not certificate['valid']:raise ValueError(f'Historical reference failed strict gates: {typ}')
        references[typ]=p;refproof.append(dict(key=typ,source=entry['source'],original_geometry_sha256=entry['geometry_sha256'],
            canonical_geometry_sha256=geometry_sha(p),historical_pose_count=len(matches),excess_interval=bounds,certificate=certificate))
    atom_npz(args.out/'inputs/reference.npz',references);atom_json(args.out/'inputs/reference-proofs.json',refproof)
    paths=[Path(__file__),ROOT/'experiments/fq_active_pilot.py',ROOT/'experiments/fq_coherent_clusters.py',
        ROOT/'experiments/fq_capacity_probe.py',ROOT/'experiments/compose_gadgets.py',
        ROOT/'scripts/validate_submission.py',ROOT/'scripts/score_official.py',ROOT/'research/official_metric_v17.py']
    source_hashes={}
    for path in paths:
        shutil.copy2(path,args.out/'source'/path.name);source_hashes[str(path.relative_to(ROOT))]=fq.digest(path)
    manifest=dict(binary_sha256=expected,source_commit=fq.SOURCE_COMMIT,license='MIT; copyright2026 Evan Daniel',
        inventory_report_sha256=fq.digest(args.inventory/'report.json'),omitted_poses_sha256=fq.digest(args.inventory/'omitted-poses.json'),
        reference_sha256=fq.digest(args.out/'inputs/reference.npz'),reference_proofs_sha256=fq.digest(args.out/'inputs/reference-proofs.json'),
        sources=source_hashes,options=OPTIONS,workers=1,maximum_seconds=args.seconds,
        command=[sys.executable,*sys.argv],baseline_reference='Orientation-fair minima over all audited historical poses of each of the26 absent types.',
        no_gpu=True,no_submission=True)
    atom_json(args.out/'manifest.json',manifest)
    # Native contact polish and full certificate positive control.
    length=2+math.sqrt(.5)
    control=legalize(np.array([[.5,.5,0],[.5,length-.5,0],[length-.5,.5,0],
        [length-.5,length-.5,0],[length/2,length/2,np.pi/4]]))
    proof,pose=run_one('2_2_1',control,'contact20',binary,args.out/'trials',770000,5,deadline)
    atom_json(args.out/'positive-control.json',proof)
    if pose is None:raise ValueError('Native strict positive control failed')
    best=dict(references);all_poses={};records=[];minima={r['key']:r['excess_interval'] for r in refproof}
    reference_bounds=dict(minima);keys=sorted(references,key=lambda k:len(references[k]))
    def checkpoint(status):
        folder=checkpoint_directory(args.out,len(records),status)
        atom_npz(folder/'donors.npz',all_poses);atom_npz(folder/'best_bank.npz',best)
        atom_json(folder/'records.json',records)
        gains={k:str(Decimal(reference_bounds[k]['lower'])-Decimal(v['upper'])) for k,v in minima.items()}
        report=dict(status=status,elapsed_seconds=time.monotonic()-ENTRY_STARTED,trials=len(records),
            status_counts=dict(Counter(r['status'] for r in records)),strict_donors=len(all_poses),
            type_gains=gains,materially_improved_types=[k for k,v in gains.items() if Decimal(v)>Decimal('1e-8')],
            current_excess_intervals=minima,reference_excess_intervals=reference_bounds,
            manifest_sha256=fq.digest(args.out/'manifest.json'),donors_sha256=fq.digest(folder/'donors.npz'),
            best_bank_sha256=fq.digest(folder/'best_bank.npz'),records_sha256=fq.digest(folder/'records.json'),
            scope='Component excess gains only; no full competition score gain established.',no_submission=True)
        atom_json(folder/'report.json',report)
        atom_json(args.out/'current.json',dict(snapshot=str(folder),report_sha256=fq.digest(folder/'report.json'),**report))
        print(json.dumps(dict(stage='checkpoint',trials=len(records),donors=len(all_poses),improved=len(report['materially_improved_types']),
            best_gain=max(map(float,gains.values()),default=0),snapshot=str(folder))),flush=True)
    modes=['contact20','kick03','soft15','kick08','round15'];serial=0
    for cycle in range(8):
        mode=modes[cycle%len(modes)] if cycle else 'contact20'
        # All26 contact controls run before later modes; then smaller donors
        # get the first chance, with newly improved poses as parents.
        for key in keys:
            if time.monotonic()>deadline-3:break
            serial+=1;cap=5 if mode=='contact20' else 12
            record,q=run_one(key,best[key],mode,binary,args.out/'trials',770000+serial,cap,deadline)
            if q is not None:
                g=geometry_sha(q);all_poses[f'{key}__nightfq_{g}']=q
                bounds=record['excess_interval']
                record['gain_vs_frozen_reference_lower']=str(Decimal(reference_bounds[key]['lower'])-Decimal(bounds['upper']))
                if Decimal(bounds['upper'])<Decimal(minima[key]['lower']):best[key]=q;minima[key]=bounds
            records.append(record)
            if serial%5==0:checkpoint('running')
        if time.monotonic()>deadline-3:break
    checkpoint('complete')


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--inventory',type=Path,required=True)
    ap.add_argument('--binary',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--seconds',type=float,default=300)
    args=ap.parse_args()
    if not 20<=args.seconds<=300:ap.error('Require20..300seconds')
    started=time.monotonic();child=mp.get_context('fork').Process(target=campaign,args=(args,));child.start()
    child.join(max(0,args.seconds-2-(time.monotonic()-ENTRY_STARTED)))
    enforced=child.is_alive()
    if enforced:
        child.terminate();child.join(1)
        if child.is_alive():os.killpg(child.pid,signal.SIGKILL);child.join(1)
    proof=dict(status='enforced' if enforced else 'exited',exitcode=child.exitcode,
        elapsed_seconds=time.monotonic()-ENTRY_STARTED,maximum_seconds=args.seconds,workers=1)
    if args.out.exists():atom_json(args.out/'supervisor.json',proof)
    print(json.dumps(proof),flush=True)
    if child.exitcode and not enforced:raise SystemExit(child.exitcode)


if __name__=='__main__':main()
