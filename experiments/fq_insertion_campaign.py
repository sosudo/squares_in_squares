#!/usr/bin/env python3
"""One-worker insertion-only branching search over certified rectangular types.

Parents and all descendants retain geometry hashes. Exact type references are
orientation-fair; every accepted new count has interval excess below one and
official raw/default-pandas validity. No full-competition submission is made.
"""
from __future__ import annotations
import argparse
from collections import deque
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import time

for variable in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[variable]='1'
import numpy as np
import fq_active_pilot as fq
from fq_coherent_clusters import transpose,atom_json,atom_npz
from fq_insert_delete import load_banks,insertion_sites,run_one,OPTIONS

ROOT=Path(__file__).resolve().parents[1]
NEW_BANK=ROOT/'artifacts/fq-insert-delete-v1/donors.npz'
NEW_BANK_SHA='48ec40dc1056ada58e9af62ae91912272e187f3dc899385acaa72df4c0c10315'


def geom_sha(p):
    return hashlib.sha256(np.asarray(p,dtype='<f8').tobytes()).hexdigest()


def augment(p,site):
    result=np.vstack((p,[site['x'],site['y'],site['angle']]))
    if len(result)!=len(p)+1:raise ValueError('Insertion must add exactly one square')
    return result


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--focus',type=Path,default=ROOT/'artifacts/fq-focus-v1')
    ap.add_argument('--seconds',type=float,default=560)
    ap.add_argument('--trial-seconds',type=float,default=15)
    ap.add_argument('--max-trials',type=int,default=64)
    args=ap.parse_args()
    if not 0<args.seconds<=590 or not 0<args.trial_seconds<=25 or not 0<args.max_trials<=64:
        ap.error('At most590s,25s per trial,64 trials,one worker')
    start=time.monotonic();deadline=start+args.seconds
    args.out.mkdir(parents=True,exist_ok=False);(args.out/'inputs').mkdir();(args.out/'source').mkdir();(args.out/'trials').mkdir()
    bank,proof=load_banks(args.focus)
    if fq.digest(NEW_BANK)!=NEW_BANK_SHA:raise ValueError('New surplus bank changed')
    proof.append({'path':str(NEW_BANK),'sha256':NEW_BANK_SHA})
    with np.load(NEW_BANK,allow_pickle=False)as z:
        for name in z.files:
            w,h,d=map(int,name.split('__')[0].split('_'));p=z[name].copy()
            if w>h:w,h=h,w;p=transpose(p)
            key=f'{w}_{h}_{d}';f=fq.bloat(p,w,h)
            if p.shape!=(w*h+d,3):raise ValueError('Parent count mismatch')
            if key not in bank or f<bank[key]['excess']:
                bank[key]={'p':p,'excess':f,'source':str(NEW_BANK),'archive_key':name}
    for i,entry in enumerate(proof):shutil.copy2(entry['path'],args.out/'inputs'/f'bank-{i}.npz')
    binary=args.out/'inputs/fq';shutil.copy2(args.focus/'inputs/fq',binary);binary.chmod(0o500);binary_sha=fq.digest(binary)
    if binary_sha!=json.loads((args.focus/'manifest.json').read_text())['binary_sha256']:raise ValueError('Executable hash')
    for name in ['fq_insertion_campaign.py','fq_insert_delete.py','fq_coherent_clusters.py','fq_active_pilot.py','compose_gadgets.py']:
        shutil.copy2(ROOT/'experiments'/name,args.out/'source'/name)
    metric=fq.load_metric(ROOT/'research/official_metric_v17.py')
    best={key:dict(value)for key,value in bank.items()};initial_types=set(best)
    initial_poses={key:value['p']for key,value in best.items()};atom_npz(args.out/'inputs/initial-best-bank.npz',initial_poses)
    parents={};parent_poses={};sites={};queue=deque();scheduled=set();donors={};records=[]
    def register(p,w,h,d,generation,origin):
        sha=geom_sha(p)
        if sha not in parents:
            parents[sha]={'type':f'{w}_{h}_{d}','count':len(p),'w':w,'h':h,'d':d,
                          'generation':generation,'origin':origin,'geometry_sha256':sha,'excess':fq.bloat(p,w,h)}
            parent_poses[sha]=p.copy()
        return sha
    def schedule(sha,site_index,mode,front=False):
        token=(sha,site_index,mode)
        if token in scheduled:return
        parent=parents[sha]
        if parent['count']>=1000 or parent['d']>=63 or parent['excess']>=1:return
        scheduled.add(token)
        (queue.appendleft if front else queue.append)(token)
    initial=[]
    for key,value in bank.items():
        w,h,d=map(int,key.split('_'))
        if value['excess']<.95 and len(value['p'])<1000 and d<63:
            sha=register(value['p'],w,h,d,0,{'source':value['source'],'archive_key':value['archive_key']})
            initial.append((key,sha,value['excess']))
    preferred={'5_17_8':0,'9_20_13':1}
    initial.sort(key=lambda x:(preferred.get(x[0],2),x[2],x[0]))
    for key,sha,f in initial:
        if key in preferred:
            schedule(sha,0,'insert_alm');schedule(sha,1,'insert_soft')
    for site_index,mode in [(0,'insert_alm'),(1,'insert_soft'),(2,'insert_alm')]:
        for key,sha,f in initial:schedule(sha,site_index,mode)
    manifest={'workers':1,'seconds':args.seconds,'complete_trial_seconds':args.trial_seconds,'max_trials':args.max_trials,
              'source_commit':fq.SOURCE_COMMIT,'source_license':'MIT; vendor/fq/NOTICE','binary_sha256':binary_sha,
              'source_sha256':fq.digest(Path(__file__)),'reference_banks':proof,'initial_types':sorted(initial_types),
              'initial_parent_types':[k for k,_,_ in initial],'initial_reference_excess':{k:v['excess']for k,v in bank.items()},
              'mode_options':{k:OPTIONS[k]for k in ('insert_alm','insert_soft')},'site_grid_step':.25,
              'site_ranking':'sum of positive SAT penetrations; spatial/angular diversity filter',
              'branch_policy':'try N+1 of every newly encountered or materially improved type while excess<1; two repair modes',
              'matching_reference_policy':'minimum excess per canonical orientation-equivalent type; no parent-count score comparison'}
    atom_json(args.out/'manifest.json',manifest)
    def checkpoint(status):
        index=len(records);snap=args.out/f'snapshot-{index:05d}';snap.mkdir(exist_ok=False)
        atom_json(snap/'results.json',records);atom_json(snap/'parents.json',parents)
        atom_npz(snap/'parent-poses.npz',parent_poses);atom_npz(snap/'donors.npz',donors)
        atom_npz(snap/'best-bank.npz',{k:v['p']for k,v in best.items()})
        new_types=sorted(set(best)-initial_types)
        analysis={'status':status,'elapsed_seconds':time.monotonic()-start,'trials':len(records),'certified_donors':len(donors),
                  'new_types_relative_to_initial_banks':new_types,'new_type_excess':{k:best[k]['excess']for k in new_types},
                  'strictly_improved_initial_types':{k:bank[k]['excess']-v['excess']for k,v in best.items()if k in bank and bank[k]['excess']-v['excess']>1e-7},
                  'queued_trials':len(queue),'maximum_generation':max((r.get('generation',0)for r in records),default=0),
                  'status_counts':{s:sum(r['status']==s for r in records)for s in sorted({r['status']for r in records})},
                  'donors_sha256':fq.digest(snap/'donors.npz'),'best_bank_sha256':fq.digest(snap/'best-bank.npz'),
                  'parents_sha256':fq.digest(snap/'parents.json'),'parent_poses_sha256':fq.digest(snap/'parent-poses.npz'),
                  'results_sha256':fq.digest(snap/'results.json'),'manifest_sha256':fq.digest(args.out/'manifest.json')}
        atom_json(snap/'analysis.json',analysis)
        atom_json(args.out/'current.json',{'snapshot':str(snap),'analysis_sha256':fq.digest(snap/'analysis.json'),'status':status})
        return analysis
    print(json.dumps({'stage':'start','initial_parents':len(initial),'queued':len(queue),'seconds':args.seconds,'workers':1}),flush=True)
    while queue and len(records)<args.max_trials and time.monotonic()<deadline-3:
        parent_sha,site_index,mode=queue.popleft();parent=parents[parent_sha];p=parent_poses[parent_sha]
        w,h,d=parent['w'],parent['h'],parent['d'];new_type=f'{w}_{h}_{d+1}'
        if parent_sha not in sites:sites[parent_sha]=insertion_sites(p,w,h,keep=4)
        if site_index>=len(sites[parent_sha]):continue
        site=sites[parent_sha][site_index];q=augment(p,site);assert len(q)==w*h+d+1
        if time.monotonic()>=deadline-1:break
        record,pose=run_one(q,w,h,d+1,mode,f'trial-{len(records):04d}',binary.resolve(),(args.out/'trials').resolve(),
                            metric,args.trial_seconds,deadline)
        reference=best.get(new_type)
        record.update(trial_id=len(records),parent_geometry_sha256=parent_sha,parent_type=parent['type'],
                      parent_count=len(p),generation=parent['generation']+1,site_index=site_index,site=site,
                      matching_new_type_reference_excess=reference['excess']if reference else None)
        if pose is not None:
            key=new_type+'__insert_'+record['geometry_sha256'];donors[key]=pose
            record['gain_vs_matching_new_type']=reference['excess']-record['excess']if reference else None
            novel=new_type not in best;improved=not novel and record['excess']<best[new_type]['excess']-1e-7
            if novel or record['excess']<best[new_type]['excess']:
                best[new_type]={'p':pose,'excess':record['excess'],'source':str(args.out),'archive_key':key}
            if novel or improved:
                child_sha=register(pose,w,h,d+1,record['generation'],{'trial_id':record['trial_id'],'parent_geometry_sha256':parent_sha})
                schedule(child_sha,1,'insert_soft',front=True);schedule(child_sha,0,'insert_alm',front=True)
        records.append(record)
        analysis=checkpoint('running')
        print(json.dumps({k:record.get(k)for k in('trial_id','parent_type','type','generation','mode','status','excess','gain_vs_matching_new_type')}),flush=True)
    # Preserve the last per-trial snapshot and make completion a separate immutable record.
    final=args.out/'complete';final.mkdir()
    atom_npz(final/'donors.npz',donors);atom_npz(final/'best-bank.npz',{k:v['p']for k,v in best.items()})
    atom_json(final/'parents.json',parents);atom_npz(final/'parent-poses.npz',parent_poses);atom_json(final/'results.json',records)
    summary={'status':'complete','elapsed_seconds':time.monotonic()-start,'trials':len(records),'certified_donors':len(donors),
             'new_types_relative_to_initial_banks':sorted(set(best)-initial_types),
             'new_type_excess':{k:v['excess']for k,v in best.items()if k not in initial_types},
             'strictly_improved_initial_types':{k:bank[k]['excess']-v['excess']for k,v in best.items()if k in bank and bank[k]['excess']-v['excess']>1e-7},
             'maximum_generation':max((r.get('generation',0)for r in records),default=0),
             'status_counts':{s:sum(r['status']==s for r in records)for s in sorted({r['status']for r in records})},
             'donors_sha256':fq.digest(final/'donors.npz'),'best_bank_sha256':fq.digest(final/'best-bank.npz'),
             'results_sha256':fq.digest(final/'results.json'),'parents_sha256':fq.digest(final/'parents.json'),
             'parent_poses_sha256':fq.digest(final/'parent-poses.npz'),'manifest_sha256':fq.digest(args.out/'manifest.json')}
    if fq.digest(binary)!=binary_sha:raise ValueError('Executable snapshot changed')
    atom_json(final/'analysis.json',summary);atom_json(args.out/'current.json',{'snapshot':str(final),'analysis_sha256':fq.digest(final/'analysis.json'),'status':'complete'})
    print(json.dumps({'stage':'complete',**summary}),flush=True)


if __name__=='__main__':main()
