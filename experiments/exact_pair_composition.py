#!/usr/bin/env python3
"""Bounded CPU composition of every screened two-block chain using a new type.

At least one block comes from the separately pinned new-type bank. D4 variants,
all three public join modes and every feasible square container size are
considered. Exact cross-block SAT screens proposals; complete-puzzle official
and independent raw/default-pandas checks decide exports. No GPU/submission.
"""
from __future__ import annotations
import time
ENTRY_STARTED=time.monotonic()

import argparse
from collections import Counter
import hashlib
import json
import math
import multiprocessing as mp
import os
from pathlib import Path
import shutil
import signal
import sys

for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[name]='1'

import numpy as np
from compose_gadgets import extents,legalize,read_baseline,side
from extract_broad_active_frontier import orient,geometry_sha
from cpu_recipe_replay import public_functions,cross_block_separated
from fq_capacity_probe import full_certificate

ROOT=Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def atomic_json(path,value):
    incoming=path.with_suffix(path.suffix+'.incoming')
    incoming.write_text(json.dumps(value,indent=2)+'\n');incoming.replace(path)


def pair_dimensions(a,b,mode):
    return a['w']+b['w']+(mode==1),a['h']+b['h']+(mode==2),a['d']+b['d']


def build_pair(a,b,mode,k,stitch):
    gadgets=[dict(w=p['w'],h=p['h'],dm=p['d'],f=p['f'],donor=i)for i,p in enumerate((a,b))]
    q,_=stitch([(0,3),(1,mode)],gadgets,[(a['pose'],'first'),(b['pose'],'second')],box=(k,k))
    if len(q)!=k*k+a['d']+b['d']:raise ValueError('Public pair composition count mismatch')
    return legalize(q)


def positive_control(stitch):
    length=2+math.sqrt(.5)
    motif=legalize(np.array([[.5,.5,0.],[.5,length-.5,0.],[length-.5,.5,0.],
                            [length-.5,length-.5,0.],[length/2,length/2,np.pi/4]]))
    _,hi=extents(motif);f=math.ceil((max(hi.max(0)-2)+3e-8)*1e9)*1e-9
    a={'w':2,'h':2,'d':1,'f':f,'pose':motif};b=dict(a)
    if not cross_block_separated(a['pose'],b['pose'],a['w'],b['h'],1):
        raise ValueError('Separated positive-control blocks rejected')
    q=build_pair(a,b,1,5,stitch)
    if q is None:raise ValueError('Positive-control construction rejected')
    expanded=build_pair(a,b,1,6,stitch)
    if len(q)!=27 or expanded is None or len(expanded)!=38:
        raise ValueError('Positive-control k/container counts failed')
    certificate=full_certificate(q)
    if not certificate['valid']:raise ValueError('Positive-control whole-puzzle certificates failed')
    return {'count':len(q),'expanded_container_count':len(expanded),
            'method':'Two classic five-square diamond motifs with a one-cell buffered join.',
            'geometry_sha256':geometry_sha(q),'certificate':certificate}


def campaign(args):
    os.setsid();deadline=ENTRY_STARTED+args.seconds-3.
    args.out.mkdir(parents=True,exist_ok=False);(args.out/'inputs').mkdir();(args.out/'source').mkdir()
    report=json.loads(args.portfolio_report.read_text())
    if not report['valid']or report['sha256']!=digest(args.portfolio):
        raise ValueError('Current portfolio certificate/hash mismatch')
    base=read_baseline(args.portfolio);best_side={n:side(p)for n,p in base.items()}
    pools={};input_records=[]
    for index,(path,is_new)in enumerate([(args.new_bank,True)]+[(p,False)for p in args.bank]):
        snapshot=args.out/'inputs'/f'bank-{index:02d}.npz';shutil.copyfile(path,snapshot);snapshot.chmod(0o444)
        sha=digest(snapshot);input_records.append({'original_path':str(path),'snapshot':str(snapshot),'sha256':sha,'is_new':is_new})
        with np.load(snapshot,allow_pickle=False)as archive:
            for key in archive.files:
                w,h,d=map(int,key.split('__')[0].split('_'));p=np.asarray(archive[key],dtype=float)
                if p.shape!=(w*h+d,3)or not np.isfinite(p).all()or not 0<d<=63:
                    raise ValueError('Invalid surplus donor type or array')
                source={'archive_sha256':sha,'array_key':key,'original_geometry_sha256':geometry_sha(p),'is_new':is_new}
                for transpose in (False,True):
                    ow,oh=(h,w)if transpose else(w,h)
                    for sx,sy in ((1,1),(-1,1),(1,-1),(-1,-1)):
                        q=orient(p,transpose,sx,sy);_,hi=extents(q)
                        actual=float(max(hi.max(0)-[ow,oh]));f=math.ceil((actual+3e-8)*1e9)*1e-9
                        if not 0<f<1:continue
                        signature=(ow,oh,d,geometry_sha(q))
                        if signature in pools:
                            pools[signature]['is_new']|=is_new
                            pools[signature]['sources'].append(source)
                            continue
                        pools[signature]={'w':ow,'h':oh,'d':d,'pose':q,'f':f,'actual_bloat':actual,
                            'geometry_sha256':signature[-1],'is_new':is_new,'sources':[source],
                            'transpose':transpose,'reflection_x':sx,'reflection_y':sy}
    poses=list(pools.values());new_ids=[i for i,p in enumerate(poses)if p['is_new']]
    vendor=ROOT/'vendor/lightning_ftmc';stitch,_=public_functions(vendor)
    source_paths=[Path(__file__),ROOT/'experiments/cpu_recipe_replay.py',ROOT/'experiments/compose_gadgets.py',
                  ROOT/'experiments/extract_broad_active_frontier.py',ROOT/'experiments/fq_capacity_probe.py',
                  ROOT/'experiments/fq_active_pilot.py',ROOT/'scripts/validate_submission.py',
                  ROOT/'scripts/score_official.py',ROOT/'research/official_metric_v17.py',
                  vendor/'solver.py',vendor/'gpu_fault_composition.py',vendor/'packing_pipeline.py']
    source_hashes={}
    for index,path in enumerate(source_paths):
        target=args.out/'source'/f'{index:02d}-{path.name}';shutil.copyfile(path,target);target.chmod(0o444)
        source_hashes[str(path.relative_to(ROOT))]=digest(target)
    command=[sys.executable,str(Path(__file__).resolve()),*sys.argv[1:]]
    manifest={'portfolio':str(args.portfolio),'portfolio_sha256':digest(args.portfolio),
              'portfolio_report_sha256':digest(args.portfolio_report),'inputs':input_records,
              'evidence':[{'path':str(p),'sha256':digest(p)}for p in args.evidence],
              'source_hashes':source_hashes,'command':command,
              'command_sha256':hashlib.sha256(json.dumps(command,separators=(',',':')).encode()).hexdigest(),
              'workers':1,'maximum_seconds':args.seconds,'oriented_variants':len(poses),
              'oriented_new_variants':len(new_ids),'modes':[0,1,2],'max_dimension':31,'max_surplus':63,
              'method':'Every ordered two-block D4 pair containing a new donor, all join modes and all k>=max(total dimensions). '
                       'Scalar and area necessary bounds precede exact block SAT and full construction/certification.',
              'no_gpu':True,'no_submission':True}
    atomic_json(args.out/'manifest.json',manifest)
    control=positive_control(stitch);atomic_json(args.out/'positive-control.json',control)
    counts=Counter();jobs=[]
    new_set=set(new_ids)
    # Ordered pairs include new/new exactly once per order and new/old both ways.
    for first,a in enumerate(poses):
        partners=range(len(poses))if first in new_set else new_ids
        for second in partners:
            b=poses[second]
            for mode in (0,1,2):
                counts['ordered_pairs_with_mode']+=1
                w,h,d=pair_dimensions(a,b,mode)
                if max(w,h)>31 or d>63:
                    counts['dimension_or_surplus_rejected']+=1;continue
                f=max(a['f'],b['f']);targets=[]
                for k in range(max(w,h),32):
                    n=k*k+d
                    if n>1000:break
                    counts['containers_screened']+=1
                    if n>(k+f)**2+1e-10:
                        counts['area_rejected']+=1;continue
                    gain=(best_side[n]-(k+f))/math.sqrt(n)
                    if gain>1e-9:targets.append((k,n,gain))
                if targets:
                    jobs.append((sum(t[2]for t in targets),first,second,mode,targets))
    jobs.sort(key=lambda row:-row[0]);counts['promising_pair_jobs']=len(jobs)
    counts['promising_target_containers']=sum(len(row[4])for row in jobs)
    trials=[];candidates={}

    def checkpoint(status):
        atomic_json(args.out/'candidates.json',candidates)
        atomic_json(args.out/'report.json',{'status':status,'manifest_sha256':digest(args.out/'manifest.json'),
            'candidates_sha256':digest(args.out/'candidates.json'),'elapsed_seconds':time.monotonic()-ENTRY_STARTED,
            'coverage':dict(counts),'planned_pair_jobs':len(jobs),'trials':trials,
            'certified_cases':len(candidates),'positive_control_valid':control['certificate']['valid']})

    checkpoint('screened')
    for _,first,second,mode,targets in jobs:
        if time.monotonic()>=deadline-1:break
        a,b=poses[first],poses[second]
        counts['exact_pair_tests']+=1
        if not cross_block_separated(a['pose'],b['pose'],a['w'],b['h'],mode):
            counts['pair_sat_rejected']+=1;counts['target_containers_completed']+=len(targets);continue
        counts['pair_sat_passed']+=1
        for k,n,_ in targets:
            if time.monotonic()>=deadline-1:break
            if k+max(a['f'],b['f'])>=best_side[n]-1e-9:
                counts['dominated_by_new_incumbent']+=1;counts['target_containers_completed']+=1;continue
            trial={'n':n,'k':k,'mode':mode,'max_bloat':max(a['f'],b['f']),
                   'first':{key:value for key,value in a.items()if key!='pose'},
                   'second':{key:value for key,value in b.items()if key!='pose'}}
            q=build_pair(a,b,mode,k,stitch);counts['whole_layouts_built']+=1
            if q is None:trial['status']='rejected_more_than_rounding_overlap'
            elif side(q)>=best_side[n]-1e-9:trial['status']='no_side_gain_after_rounding'
            else:
                certificate=full_certificate(q);trial['certificate']=certificate
                if certificate['valid']:
                    length=certificate['independent_raw']['side_upper']
                    gain=(side(base[n])-float(length))/math.sqrt(n)
                    candidate={'side':length,'squares':[[f'{v:.17g}'for v in row]for row in q],
                               'source':'Exact CPU two-block composition using a new N±1 surplus donor',
                               'provenance':{'manifest_sha256':digest(args.out/'manifest.json'),'pair':trial}}
                    candidates[str(n)]=candidate;best_side[n]=float(length)
                    trial.update(status='certified_improvement',gain_vs_frozen_baseline=gain,
                                 geometry_sha256=geometry_sha(q))
                    counts['certified_improvement_events']+=1
                else:trial['status']='rejected_geometry_or_numeric_transport'
            trials.append(trial);counts['target_containers_completed']+=1;checkpoint('running')
            print(json.dumps({'n':n,'status':trial['status'],'gain':trial.get('gain_vs_frozen_baseline',0.),
                              'elapsed_seconds':time.monotonic()-ENTRY_STARTED}),flush=True)
    counts['search_complete']=int(counts['exact_pair_tests']==len(jobs)and
        counts['target_containers_completed']==counts['promising_target_containers'])
    checkpoint('complete'if counts['search_complete']else'bounded_partial')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--new-bank',type=Path,required=True)
    parser.add_argument('--bank',type=Path,action='append',required=True)
    parser.add_argument('--evidence',type=Path,action='append',default=[])
    parser.add_argument('--portfolio',type=Path,required=True)
    parser.add_argument('--portfolio-report',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--seconds',type=float,default=300.)
    args=parser.parse_args()
    if args.out.exists()or not 5<args.seconds<=300:parser.error('Require new output directory and 5<seconds<=300')
    process=mp.get_context('fork').Process(target=campaign,args=(args,));process.start()
    process.join(timeout=max(0.,args.seconds-1.5-(time.monotonic()-ENTRY_STARTED)))
    enforced=process.is_alive()
    if enforced:
        try:os.killpg(process.pid,signal.SIGKILL)
        except ProcessLookupError:process.kill()
        process.join(timeout=.4)
    receipt={'status':'hard_deadline_enforced'if enforced else'exited','exitcode':process.exitcode,
             'elapsed_seconds':time.monotonic()-ENTRY_STARTED,'configured_seconds':args.seconds,'workers':1,'no_gpu':True}
    if args.out.exists():atomic_json(args.out/'supervisor.json',receipt)
    print(json.dumps(receipt),flush=True)
    if process.exitcode and not enforced:raise SystemExit(process.exitcode)


if __name__=='__main__':main()
