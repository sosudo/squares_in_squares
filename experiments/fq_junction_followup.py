#!/usr/bin/env python3
"""Bounded compression of certified full-count junction reconstruction basins."""
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
for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='1'
import numpy as np
import fq_active_pilot as fq
from fq_junction_repair import run_stage,local_options
from fq_coherent_clusters import alarm,atom_json,atom_npz
from compose_gadgets import side,normalize
from extract_broad_active_frontier import geometry_sha

ROOT=Path(__file__).resolve().parents[1]


def campaign(args):
    os.setsid();signal.signal(signal.SIGTERM,alarm);deadline=STARTED+args.seconds-5
    args.out.mkdir(parents=True,exist_ok=False)
    for name in ('inputs','source','trials','retained'):(args.out/name).mkdir()
    previous=json.loads((args.prior/'report.json').read_text());rows=json.loads((args.prior/'records.json').read_text())
    assert fq.digest(args.prior/'valid-repairs.npz')==previous['repairs_sha256']
    assert fq.digest(args.prior/'records.json')==previous['records_sha256']
    proof={r['geometry_sha256']:r for r in rows if r['status']=='certified'}
    seeds=[];seen=set()
    with np.load(args.prior/'valid-repairs.npz') as z:
        for key in sorted(z.files,key=lambda k:float(proof[k.split('__strict_')[1]]['side'])):
            p=z[key];g=geometry_sha(p);assert proof[g]['certificate']['valid']
            token=np.round(p,4).astype('<f8').tobytes()
            if token in seen:continue
            seen.add(token);seeds.append((g,p))
            if len(seeds)==3:break
    assert len(seeds)>0
    atom_npz(args.out/'inputs/strict-seeds.npz',{g:p for g,p in seeds})
    atom_json(args.out/'inputs/seed-proofs.json',{g:proof[g]for g,p in seeds})
    pointer=json.loads(args.pointer.read_text());official=json.loads(Path(pointer['raw']['official_report']).read_text())
    assert official['valid']and official['sha256']==pointer['raw']['sha256']
    reference=float(next(r['side']for r in official['results']if r['n']==498))
    binary=(args.out/'inputs/fq').resolve();shutil.copy2(args.binary,binary);binary.chmod(0o500)
    assert fq.digest(binary)=='10ec7cf773ac0ebca3791d5cfb84e9ecbb10e3f0a9e43194330c80e1cfc9dc3d'
    paths=[Path(__file__),ROOT/'experiments/fq_junction_repair.py',ROOT/'experiments/fq_active_pilot.py',
        ROOT/'experiments/fq_capacity_probe.py',ROOT/'experiments/fq_coherent_clusters.py',ROOT/'scripts/validate_submission.py',
        ROOT/'scripts/score_official.py',ROOT/'research/official_metric_v17.py']
    for p in paths:shutil.copy2(p,args.out/'source'/p.name)
    manifest=dict(prior_report_sha256=fq.digest(args.prior/'report.json'),prior_repairs_sha256=previous['repairs_sha256'],
        baseline_sha256=pointer['raw']['sha256'],reference_side=reference,seeds=[g for g,p in seeds],
        seed_bank_sha256=fq.digest(args.out/'inputs/strict-seeds.npz'),seed_proofs_sha256=fq.digest(args.out/'inputs/seed-proofs.json'),
        binary_sha256=fq.digest(binary),sources={str(p.relative_to(ROOT)):fq.digest(p)for p in paths},
        seconds=args.seconds,workers=1,maximum_trials=24,
        seed_sampling='At most3 certified basins, using1e-4-rounded arrays only to avoid duplicate sampling; all actual hashes retained.',
        modes=['compress','shrink','local_soft','tip_kick'],no_gpu=True,no_submission=True)
    atom_json(args.out/'manifest.json',manifest);records=[];retained={};candidates={};parents=[p.copy()for g,p in seeds]
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
        g=geometry_sha(q);retained['n498__strict_'+g]=q;record['score_gain_vs_reference']=(reference-float(record['side']))/math.sqrt(498)
        path=args.out/'retained'/(g+'.npz')
        if not path.exists():atom_npz(path,{g:q});atom_json(path.with_suffix('.json'),record)
        if float(record['side'])<reference-1e-8 and ('498'not in candidates or float(record['side'])<float(candidates['498']['side'])):
            candidates['498']=dict(side=record['side'],squares=[[f'{v:.17g}'for v in row]for row in q],
                source='Compression of a fully certified reconstructed donor junction',certificate=record['certificate'],
                provenance=dict(record_path=str(path.with_suffix('.json')),record_sha256=fq.digest(path.with_suffix('.json'))))
    checkpoint('configured');attempts=0
    for cycle in range(2):
        for mode in ('compress','shrink','local_soft','tip_kick'):
            for index,p0 in enumerate(parents):
                if time.monotonic()>deadline-3:break
                trial=attempts;attempts+=1;p=p0.copy();selection=None
                if mode=='compress':
                    factor=(reference-.001)/side(p);p[:,:2]*=factor;p=normalize(p)
                    options=['--loosen','1','--outer','65','--pit','120','--flip-top','24']
                elif mode=='shrink':
                    options=['--loosen','1','--shrink','--d0','.003','--dmin','.00002','--hops','4',
                        '--hop-sigma','.06','--hop-k','8','--pit','100','--flip-top','16','--v']
                elif mode=='local_soft':
                    center=p[[396,488],:2].mean(0);free=np.argsort(((p[:,:2]-center)**2).sum(1))[:40]
                    frozen=np.setdiff1d(np.arange(len(p)),free);options=local_options(True,frozen,trial)
                    selection=dict(free_ids=free.tolist(),frozen_ids=frozen.tolist())
                else:
                    p[[396,488],2]+=[.15 if cycle else -.15,-.15 if cycle else .15]
                    options=['--loosen','1.001','--outer','55','--pit','100','--flip-top','16']
                record,q=run_stage(p,mode+'-'+str(trial),options,881000+trial,binary,args.out/'trials',14,deadline)
                record.update(trial=trial,seed_index=index,seed_geometry_sha256=seeds[index][0],selection=selection)
                retain(record,q);records.append(record);checkpoint('running')
                if q is not None and side(q)<side(parents[index]):parents[index]=q.copy()
                print(json.dumps(dict(trial=trial,mode=mode,status=record['status'],side=record.get('side'))),flush=True)
                if mode=='local_soft'and q is not None and side(q)<reference+2 and time.monotonic()<deadline-3:
                    release,finished=run_stage(q,'release-'+str(trial),['--loosen','1','--outer','45','--pit','100','--flip-top','16'],
                        882000+trial,binary,args.out/'trials',12,deadline)
                    release.update(trial=trial,seed_index=index,parent_strict_geometry_sha256=geometry_sha(q))
                    retain(release,finished);records.append(release);checkpoint('running')
                    if finished is not None and side(finished)<side(parents[index]):parents[index]=finished.copy()
            if time.monotonic()>deadline-3:break
        if time.monotonic()>deadline-3:break
    checkpoint('complete'if attempts==2*4*len(seeds)else'bounded_partial')


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for name in ('prior','pointer','binary','out'):ap.add_argument('--'+name,type=Path,required=True)
    ap.add_argument('--seconds',type=float,default=220);args=ap.parse_args();assert 10<args.seconds<=220
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
