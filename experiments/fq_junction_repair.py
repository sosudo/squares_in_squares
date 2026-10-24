#!/usr/bin/env python3
"""Bounded full-count repair of an explicitly overlapping donor junction."""
import time
STARTED=time.monotonic()
import argparse
from collections import Counter
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
for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='1'
import numpy as np
import fq_active_pilot as fq
from compose_gadgets import normalize,side
from fq_coherent_clusters import Deadline,alarm,grouped_run,atom_json,atom_npz
from fq_capacity_probe import full_certificate
from extract_broad_active_frontier import geometry_sha

ROOT=Path(__file__).resolve().parents[1]


def run_stage(p,mode,options,seed,binary,out,cap,deadline):
    start=time.monotonic();remaining=min(cap,deadline-start-2);n=len(p)
    record=dict(mode=mode,seed=seed,n=n,input_geometry_sha256=geometry_sha(p),
        input_side=side(p),input_validity='exploration; validity not assumed')
    if remaining<1:return dict(record,status='budget-skipped'),None
    prefix=out/f'{mode}-{seed}';inp=prefix.with_suffix('.in');dst=prefix.with_suffix('.out');log=prefix.with_suffix('.log')
    # The common square-container offset is always zero, even after inflation.
    encoded,offsets=fq.encode(p,math.floor(side(p)),math.floor(side(p)));assert offsets==[0,0]
    inp.write_text(encoded);command=[str(binary),'quench','--in',str(inp),'--out',str(dst),
        '--rect-dx','0','--rect-dy','0','--seed',str(seed),*options]
    record.update(command=command,input_sha256=fq.digest(inp),output_path=str(dst))
    previous=signal.signal(signal.SIGALRM,alarm);signal.setitimer(signal.ITIMER_REAL,remaining)
    try:
        run=grouped_run(command,timeout=remaining);log.write_text(run.stdout+'\n'+run.stderr)
        record.update(returncode=run.returncode,log_sha256=fq.digest(log))
        if run.returncode or not dst.exists():record['status']='native-failed';return record,None
        native=json.loads(run.stdout.strip().splitlines()[-1]);json.dumps(native,allow_nan=False);record['fq']=native
        if '--soft-a0' in options:
            steps=int(options[options.index('--soft-steps')+1]);amplitude=float(options[options.index('--soft-a0')+1])
            values=[float(v)for v in re.findall(r'soft eps ([0-9.eE+-]+) hold',run.stderr)]
            valid=len(values)==steps and values[-1]==0 and all(a>=b>=0 for a,b in zip(values,values[1:])) and native.get('soft',{}).get('a0')==amplitude
            record['rigid_return_trace']=dict(valid=valid,epsilons=values)
            if not valid:record['status']='rigid-return-failed';return record,None
        q=fq.decode(dst,n)
        if q is None:record['status']='clearance-failed';return record,None
        certificate=full_certificate(q);record['certificate']=certificate
        if not certificate['valid']:record['status']='certificate-failed';return record,None
        record.update(status='certified',geometry_sha256=geometry_sha(q),side=certificate['independent_raw']['side_upper'])
        return record,q
    except (Deadline,subprocess.TimeoutExpired):record['status']='whole-stage-timeout';return record,None
    except Exception as exc:record.update(status='error',error_type=type(exc).__name__,error=str(exc)[:200]);return record,None
    finally:
        signal.setitimer(signal.ITIMER_REAL,0);signal.signal(signal.SIGALRM,previous)
        record['seconds']=time.monotonic()-start


def local_options(soft,frozen,seed):
    base=['--loosen','1','--outer','45','--pit','60','--flip-top','12','--kick','.04']
    if soft:base+=['--soft-compress','--soft-a0','.6','--soft-steps','12','--soft-p','2',
        '--soft-kick','.01','--hold-f','1.001','--v']
    if len(frozen):base+=['--freeze',','.join(map(str,map(int,frozen)))]
    return base


def controls(binary,out,deadline):
    result=[]
    for soft in (False,True):
        p=np.array([[x+.5,y+.5,0.]for x in range(3)for y in range(3)])
        p[4,:2]+=[.12,.08]
        options=local_options(soft,[] if soft else np.array([0,1,2,3,5,6,7,8]),0)
        proof,q=run_stage(p,'control-soft' if soft else 'control-rigid',options,880000+int(soft),binary,out,8,deadline)
        if q is None or len(q)!=9 or side(q)>3.1:raise ValueError('Recoverable-overlap native control failed')
        result.append(proof)
    return dict(valid=True,method='Displaced center of a3×3 grid, repaired with fixed surroundings and with soft-to-rigid continuation.',results=result)


def campaign(args):
    os.setsid();signal.signal(signal.SIGTERM,alarm);deadline=STARTED+args.seconds-5
    args.out.mkdir(parents=True,exist_ok=False)
    for name in ('inputs','source','trials','retained'):(args.out/name).mkdir()
    binary=(args.out/'inputs/fq').resolve();shutil.copy2(args.binary,binary);binary.chmod(0o500)
    assert fq.digest(binary)=='10ec7cf773ac0ebca3791d5cfb84e9ecbb10e3f0a9e43194330c80e1cfc9dc3d'
    proof=controls(binary,args.out/'trials',deadline);atom_json(args.out/'positive-controls.json',proof)
    if args.control_only:return
    diagnostic=json.loads((args.diagnostic/'report.json').read_text())
    assert fq.digest(args.diagnostic/'uncertified-junction-starts.npz')==diagnostic['output_sha256']
    selected=next(r for r in diagnostic['results']if r['n']==498)
    with np.load(args.diagnostic/'uncertified-junction-starts.npz') as z:initial=z['n498__UNVALIDATED_OVERLAPPING_START']
    assert geometry_sha(initial)==selected['geometry_sha256'] and selected['valid'] is False
    pointer=json.loads(args.pointer.read_text());report=json.loads(Path(pointer['raw']['official_report']).read_text())
    assert report['valid']and report['sha256']==pointer['raw']['sha256'];reference=float(next(r['side']for r in report['results']if r['n']==498))
    shutil.copy2(args.diagnostic/'uncertified-junction-starts.npz',args.out/'inputs/invalid-starts.npz')
    shutil.copy2(args.diagnostic/'report.json',args.out/'inputs/junction-diagnostic.json')
    sources=[Path(__file__),ROOT/'experiments/fq_active_pilot.py',ROOT/'experiments/fq_coherent_clusters.py',
        ROOT/'experiments/fq_capacity_probe.py',ROOT/'experiments/compose_gadgets.py',ROOT/'scripts/validate_submission.py',
        ROOT/'scripts/score_official.py',ROOT/'research/official_metric_v17.py']
    for path in sources:shutil.copy2(path,args.out/'source'/path.name)
    schedule=[(18,1.00,False,'none'),(40,1.02,False,'none'),(40,1.03,True,'none'),
        (18,1.03,True,'spread'),(40,1.04,True,'spread'),(40,1.03,True,'rotate'),
        (40,1.06,False,'spread'),(40,1.04,True,'rotate'),(40,1.00,True,'spread'),
        (40,1.06,True,'spread'),(18,1.02,False,'rotate'),(40,1.02,True,'rotate')]
    manifest=dict(pointer_sha256=fq.digest(args.pointer),baseline_sha256=pointer['raw']['sha256'],reference_side=reference,
        input_sha256=diagnostic['output_sha256'],diagnostic_report_sha256=fq.digest(args.diagnostic/'report.json'),
        binary_sha256=fq.digest(binary),fq_source_commit=fq.SOURCE_COMMIT,license='MIT; Evan Daniel',
        sources={str(p.relative_to(ROOT)):fq.digest(p)for p in sources},schedule=schedule,
        workers=1,seconds=args.seconds,local_cap_seconds=14,release_cap_seconds=14,
        invalid_start_explicit=True,retention='Every strict full-count repair, even if dominated; no side-band admission filter.',
        no_gpu=True,no_submission=True)
    atom_json(args.out/'manifest.json',manifest);records=[];retained={};candidates={}
    clash=selected['colliding_square_ids'];center=initial[clash,:2].mean(0)
    def checkpoint(status):
        atom_json(args.out/'records.json',records);atom_npz(args.out/'valid-repairs.npz',retained);atom_json(args.out/'candidates.json',candidates)
        atom_json(args.out/'report.json',dict(status=status,seconds=time.monotonic()-STARTED,stages=len(records),
            statuses=dict(Counter(r['status']for r in records)),strict_repairs=len(retained),improved_cases=len(candidates),
            best_repaired_side=min((float(r['side'])for r in records if r['status']=='certified'),default=None),
            reference_side=reference,manifest_sha256=fq.digest(args.out/'manifest.json'),
            repairs_sha256=fq.digest(args.out/'valid-repairs.npz'),records_sha256=fq.digest(args.out/'records.json'),
            candidates_sha256=fq.digest(args.out/'candidates.json'),no_submission=True))
    def retain(record,q):
        if q is None:return
        key='n498__strict_'+geometry_sha(q);retained[key]=q
        record['score_gain_vs_reference']=(reference-float(record['side']))/math.sqrt(498)
        path=args.out/'retained'/(key+'.npz')
        if not path.exists():atom_npz(path,{key:q});atom_json(path.with_suffix('.json'),record)
        if float(record['side'])<reference-1e-8 and ('498'not in candidates or float(record['side'])<float(candidates['498']['side'])):
            candidates['498']=dict(side=record['side'],squares=[[f'{v:.17g}'for v in row]for row in q],
                source='Full-count local reconstruction of an overlapping two-donor junction',certificate=record['certificate'],
                provenance=dict(record_path=str(path.with_suffix('.json')),record_sha256=fq.digest(path.with_suffix('.json'))))
    checkpoint('configured')
    attempted=0
    for trial,(count,inflation,soft,mutation) in enumerate(schedule):
        if time.monotonic()>deadline-3:break
        attempted+=1
        p=initial.copy();p[:,:2]*=inflation;p=normalize(p)
        local_center=center*inflation
        free=np.argsort(((p[:,:2]-local_center)**2).sum(1),kind='stable')[:count]
        free=np.union1d(free,np.array(clash));frozen=np.setdiff1d(np.arange(len(p)),free)
        if mutation=='spread':
            p[clash[0],:2]+=[-.36,.36];p[clash[1],:2]+=[.36,-.36]
        elif mutation=='rotate':
            p[clash[0],2]+=math.pi/4;p[clash[1],2]-=math.pi/4
        seed=880010+trial
        record,q=run_stage(p,'local-'+str(trial),local_options(soft,frozen,seed),seed,binary,args.out/'trials',14,deadline)
        record.update(trial=trial,free_ids=free.tolist(),frozen_ids=frozen.tolist(),inflation=inflation,mutation=mutation)
        if q is not None:
            displacement=q[:,:2]-p[:,:2]
            offset=np.median(displacement[frozen],axis=0)
            record['certified_output_motion']=dict(normalization_offset_removed=offset.tolist(),
                frozen_position_max=float(np.linalg.norm(displacement[frozen]-offset,axis=1).max()),
                free_position_max=float(np.linalg.norm(displacement[free]-offset,axis=1).max()),
                note='Includes native final inflation and strict output legalization; not a claim of exact frozen output coordinates.')
        retain(record,q);records.append(record);checkpoint('running')
        print(json.dumps(dict(trial=trial,status=record['status'],side=record.get('side'))),flush=True)
        # An enormous valid dilation is preserved but is not a promising
        # compression start under this short budget.
        if q is None or side(q)>reference+2 or time.monotonic()>deadline-3:continue
        options=['--loosen','1','--outer','55','--pit','80','--flip-top','16']
        release,finished=run_stage(q,'release-'+str(trial),options,seed+100,binary,args.out/'trials',14,deadline)
        release.update(trial=trial,stage='unrestricted-rigid-release',parent_strict_geometry_sha256=geometry_sha(q))
        retain(release,finished);records.append(release);checkpoint('running')
    checkpoint('complete'if attempted==len(schedule)else'bounded_partial')


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for name in ('pointer','diagnostic','binary','out'):ap.add_argument('--'+name,type=Path,required=True)
    ap.add_argument('--seconds',type=float,default=300);ap.add_argument('--control-only',action='store_true')
    args=ap.parse_args();assert 10<args.seconds<=300
    child=mp.get_context('fork').Process(target=campaign,args=(args,));child.start()
    child.join(max(0,args.seconds-2-(time.monotonic()-STARTED)));forced=child.is_alive()
    if forced:
        child.terminate();child.join(1)
        if child.is_alive():os.killpg(child.pid,signal.SIGKILL);child.join(1)
    result=dict(seconds=time.monotonic()-STARTED,limit=args.seconds,workers=1,forced=forced,exitcode=child.exitcode)
    if args.out.exists():atom_json(args.out/'supervisor.json',result)
    print(json.dumps(result),flush=True)
    if child.exitcode and not forced:raise SystemExit(child.exitcode)


if __name__=='__main__':main()
