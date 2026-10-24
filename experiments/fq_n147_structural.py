#!/usr/bin/env python3
"""Finite n148 deletion and coherent diamond-vacancy reconstruction for n147."""
import time
STARTED=time.monotonic()
import argparse
from collections import Counter
import json
import math
import multiprocessing as mp
import os
from pathlib import Path
import shutil
import signal
import sys
for _v in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[_v]='1'
import numpy as np
import pandas as pd
from fq_junction_repair import run_stage
from fq_coherent_clusters import Deadline,alarm,atom_json,atom_npz
from fq_active_pilot import digest,SOURCE_COMMIT
from fq_variant_campaign import geometry_sha
from compose_gadgets import side

ROOT=Path(__file__).resolve().parents[1]
CONTACT=['--no-alm','--loosen','1','--pit','30','--flip-top','0']
REPAIR=['--loosen','1','--outer','45','--pit','70','--flip-top','0']


def tilted_ids(p):
    return np.flatnonzero(abs((p[:,2]+math.pi/4)%(math.pi/2)-math.pi/4)>.01)


def deletion_classes(p):
    """D4 point-position classes are a scheduling heuristic, not identity proof."""
    center=p[:,:2].mean(0);core=set(tilted_ids(p));groups={}
    for i in range(len(p)):
        token=(i in core,*np.round(np.sort(abs(p[i,:2]-center)),7))
        groups.setdefault(token,[]).append(i)
    return sorted(groups.values(),key=lambda ids:(ids[0]not in core,min(ids)))


def mutate(parent,removed,mode,sign):
    p=np.delete(parent,removed,axis=0);source_ids=np.delete(np.arange(len(parent)),removed)
    core=tilted_ids(p);center=parent[tilted_ids(parent),:2].mean(0)
    vacancy=parent[removed,:2];axis=np.array([[math.sqrt(.5),-math.sqrt(.5)],
                                           [math.sqrt(.5),math.sqrt(.5)]])
    uv=(p[core,:2]-center)@axis;slot=(vacancy-center)@axis
    if mode=='whole-diamond':ids=core;angle=sign*.025;pivot=center
    elif mode in ('one-row-bend','two-row-bend'):
        dim=int(np.argmax(abs(slot)));distance=abs(uv[:,dim]-slot[dim])
        width=1 if mode=='one-row-bend'else 2
        threshold=np.unique(np.round(distance,6))[min(width-1,len(np.unique(np.round(distance,6)))-1)]+1e-5
        ids=core[distance<=threshold];angle=sign*.06;pivot=vacancy
    elif mode=='vacancy-slip':
        # Shift a coherent half-row toward/away from the missing cell. This
        # creates a controlled dislocation; it is not assumed initially valid.
        distance=np.linalg.norm(p[core,:2]-vacancy,axis=1)
        ids=core[np.argsort(distance,kind='stable')[:8]]
        vector=vacancy-p[ids,:2].mean(0)
        if np.linalg.norm(vector)<1e-8:vector=axis[:,0]
        p[ids,:2]+=sign*.12*vector/np.linalg.norm(vector)
        return p,dict(mode=mode,sign=sign,moved_source_ids=source_ids[ids].tolist(),shift=.12)
    else:raise ValueError(mode)
    c,s=math.cos(angle),math.sin(angle)
    p[ids,:2]=(p[ids,:2]-pivot)@np.array([[c,s],[-s,c]])+pivot
    p[ids,2]+=angle
    return p,dict(mode=mode,sign=sign,moved_source_ids=source_ids[ids].tolist(),angle=angle,pivot=pivot.tolist())


def campaign(args):
    os.setsid();signal.signal(signal.SIGTERM,alarm);deadline=STARTED+args.seconds-5
    out=args.out;out.mkdir(parents=True,exist_ok=False)
    for name in ('inputs','sources','trials','certified_snapshots'):(out/name).mkdir()
    pointer=json.loads(args.pointer.read_text());raw=Path(pointer['raw']['path']);official=Path(pointer['raw']['official_report'])
    report=json.loads(official.read_text());assert report['valid']and report['sha256']==pointer['raw']['sha256']==digest(raw)
    side_ref=float(next(r['side']for r in report['results']if r['n']==147))
    frame=pd.read_csv(raw,float_precision='round_trip')
    inputs={n:frame[frame.n==n].sort_values('square_id')[['x','y','angle']].to_numpy(float)for n in (147,148)}
    parent=inputs[148];assert len(tilted_ids(parent))==64 and len(parent)-len(tilted_ids(parent))==84
    atom_npz(out/'inputs/reference.npz',{str(n):p for n,p in inputs.items()})
    binary=(out/'inputs/fq').resolve();shutil.copyfile(args.binary,binary);binary.chmod(0o500)
    assert digest(binary)=='10ec7cf773ac0ebca3791d5cfb84e9ecbb10e3f0a9e43194330c80e1cfc9dc3d'
    sources=[Path(__file__),ROOT/'experiments/fq_junction_repair.py',ROOT/'experiments/fq_coherent_clusters.py',
        ROOT/'experiments/fq_active_pilot.py',ROOT/'experiments/fq_capacity_probe.py',ROOT/'experiments/compose_gadgets.py',
        ROOT/'experiments/fq_variant_campaign.py',ROOT/'scripts/validate_submission.py',ROOT/'scripts/score_official.py',
        ROOT/'research/official_metric_v17.py']
    for path in sources:shutil.copyfile(path,out/'sources'/path.name)
    classes=deletion_classes(parent)
    manifest=dict(pointer=pointer,pointer_sha256=digest(args.pointer),raw_sha256=digest(raw),official_sha256=digest(official),
        input_archive_sha256=digest(out/'inputs/reference.npz'),binary_sha256=digest(binary),fq_commit=SOURCE_COMMIT,
        source_hashes={str(p):digest(p)for p in sources},license='MIT; Evan Daniel native FQ',workers=1,
        seconds=args.seconds,reference147_side=side_ref,public_target_side=12.651043553627,
        public_target_is_not_achieved=True,all_deletions_planned=148,structural_classes=classes,
        class_scope='D4 point coordinates group scheduling only; all148 first-pass deletions are independent trials.',
        contact_options=CONTACT,repair_options=REPAIR,per_trial_caps=dict(contact=3,repair=7),
        retention='Every strict certified147-square result, including dominated poses; no generic random perturbations.',
        no_gpu=True,no_submission=True)
    atom_json(out/'manifest.json',manifest)
    records=[];donors={};certificates={};candidates={};status='running';deletion_results={}
    def checkpoint():
        atom_npz(out/'donors.npz',donors);atom_json(out/'certificates.json',certificates)
        atom_json(out/'records.json',records);atom_json(out/'candidates.json',candidates)
        atom_json(out/'report.json',dict(status=status,seconds=time.monotonic()-STARTED,stages=len(records),
            statuses=dict(Counter(r['status']for r in records)),completed_deletions=len(deletion_results),
            strict_geometries=len(donors),best_side=min((float(r['side'])for r in records if r['status']=='certified'),default=None),
            improved_cases=len(candidates),reference_side=side_ref,
            score_gain=max((side_ref-float(c['side']))/math.sqrt(147)for c in candidates.values())if candidates else 0.,
            manifest_sha256=digest(out/'manifest.json'),donors_sha256=digest(out/'donors.npz'),
            certificates_sha256=digest(out/'certificates.json'),candidates_sha256=digest(out/'candidates.json')))
    def retain(record,p):
        if p is not None:
            key='147__strict_'+geometry_sha(p);donors[key]=p;certificates[key]=record['certificate'];record['archive_key']=key
            path=out/'certified_snapshots'/(geometry_sha(p)+'.npz')
            if not path.exists():atom_npz(path,{key:p});atom_json(path.with_suffix('.json'),record)
            if float(record['side'])<side_ref-1e-8 and ('147'not in candidates or float(record['side'])<float(candidates['147']['side'])):
                candidates['147']=dict(side=record['side'],squares=[[f'{v:.17g}'for v in line]for line in p],
                    source='N148 deletion with coherent diamond-vacancy reconstruction',certificate=record['certificate'],
                    provenance=dict(record_path=str(path.with_suffix('.json')),record_sha256=digest(path.with_suffix('.json'))))
                print(json.dumps({'stage':'strict_improvement','side':record['side'],
                    'score_gain':(side_ref-float(record['side']))/math.sqrt(147)}),flush=True)
        records.append(record);checkpoint()
    try:
        control,p=run_stage(inputs[147],'reference-control',CONTACT,147000,binary,out/'trials',10,deadline)
        assert p is not None and len(p)==147 and side(p)<side_ref+1e-5
        atom_json(out/'positive-control.json',control);retain(control,p)
        for removed in range(148):
            if time.monotonic()>deadline-4:break
            initial=np.delete(parent,removed,axis=0)
            rec,p=run_stage(initial,'delete-'+str(removed),CONTACT,147001+removed,binary,out/'trials',3,deadline)
            rec.update(removed_source_id=removed,source148_geometry_sha256=geometry_sha(parent),structural_mode='single-deletion-contact')
            deletion_results[removed]=rec;retain(rec,p)
            if removed%20==0:print(json.dumps({'stage':'all-deletions','completed':removed+1,'strict':len(donors),
                                              'seconds':time.monotonic()-STARTED}),flush=True)
        # Cover each finite positional class before returning to its other
        # modes. Each reconstructed start is explicitly allowed to overlap.
        representatives=[min(ids,key=lambda i:float(deletion_results.get(i,{}).get('side',1e6)))for ids in classes]
        jobs=[(i,mode,sign)for mode in ('one-row-bend','whole-diamond','vacancy-slip','two-row-bend')
              for sign in(-1,1)for i in representatives]
        for trial,(removed,mode,sign)in enumerate(jobs):
            if time.monotonic()>deadline-4:break
            initial,mutation=mutate(parent,removed,mode,sign)
            rec,p=run_stage(initial,'structural-'+str(trial),REPAIR,147200+trial,binary,out/'trials',7,deadline)
            rec.update(removed_source_id=removed,source148_geometry_sha256=geometry_sha(parent),mutation=mutation,
                structural_mode=mode,input_validity='Deliberately deformed deletion seed; no feasibility claim before full gates.')
            retain(rec,p)
            if trial%10==0:print(json.dumps({'stage':'coherent-reconstruction','completed':trial+1,
                'strict':len(donors),'seconds':time.monotonic()-STARTED}),flush=True)
        status='complete'if len(records)==1+148+len(jobs)else'bounded_partial'
    except Deadline:status='hard_deadline'
    finally:
        checkpoint()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True);parser.add_argument('--pointer',type=Path,default=ROOT/'artifacts/current-best-portfolio.json')
    parser.add_argument('--binary',type=Path,default=ROOT/'artifacts/fq-focus-v1/inputs/fq')
    parser.add_argument('--seconds',type=float,default=490.);args=parser.parse_args();assert 20<=args.seconds<=500
    child=mp.get_context('fork').Process(target=campaign,args=(args,));child.start()
    child.join(max(0,args.seconds-2-(time.monotonic()-STARTED)));forced=child.is_alive()
    if forced:
        child.terminate();child.join(1)
        if child.is_alive():os.killpg(child.pid,signal.SIGKILL);child.join(1)
    supervisor=dict(seconds=time.monotonic()-STARTED,limit=args.seconds,forced=forced,exitcode=child.exitcode,workers=1)
    if args.out.exists():atom_json(args.out/'supervisor.json',supervisor)
    print(json.dumps(supervisor),flush=True)
    if child.exitcode and not forced:raise SystemExit(child.exitcode)


if __name__=='__main__':main()
