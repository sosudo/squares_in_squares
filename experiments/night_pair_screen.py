"""One-worker exact pair follow-up for the frozen newly polished night seeds."""
import time
STARTED=time.monotonic()
import argparse
from collections import Counter,defaultdict
import hashlib
import json
import math
import multiprocessing as mp
import os
from pathlib import Path
import signal
import sys
for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='1'
import numpy as np
import pandas as pd
from scalar_sat_staircase import palette,build,atom,array_sha,sha
from exact_pair_composition import positive_control
from compose_gadgets import extents,side
from cpu_recipe_replay import public_functions,cross_block_separated
from extract_broad_active_frontier import orient
from fq_capacity_probe import full_certificate
ROOT=Path(__file__).resolve().parents[1]


def campaign(args):
    os.setsid();deadline=STARTED+args.seconds-3
    args.out.mkdir(exist_ok=False)
    proof=json.loads(args.official_report.read_text())
    if not proof['valid']or proof['sha256']!=sha(args.baseline):raise ValueError('Baseline hash/proof mismatch')
    frame=pd.read_csv(args.baseline,float_precision='round_trip')
    base={int(n):g.sort_values('square_id')[['x','y','angle']].to_numpy(float)for n,g in frame.groupby('n')}
    before={r['n']:float(r['side'])for r in proof['results']};best=dict(before)
    previous=json.loads(args.palette_manifest.read_text());banks=[Path(x['path'])for x in previous['banks']]
    for rec in previous['banks']:
        if sha(rec['path'])!=rec['sha256']:raise ValueError('Frozen palette input changed')
    types,options,inputs=palette(base,banks,args.high_descriptor,16)
    new=defaultdict(dict)
    with np.load(args.new_bank,allow_pickle=False)as z:
        for key in z.files:
            w,h,d=map(int,key.split('__')[0].split('_'));p=z[key]
            if p.shape!=(w*h+d,3):raise ValueError('Night seed type mismatch')
            for trans in (False,True):
                ow,oh=(h,w)if trans else(w,h)
                for sx,sy in [(1,1),(-1,1),(1,-1),(-1,-1)]:
                    q=orient(p,trans,sx,sy);_,hi=extents(q)
                    f=math.ceil((float(max(hi.max(0)-[ow,oh]))+3e-8)*1e9)*1e-9
                    if not 0<f<1:continue
                    g=array_sha(q);new[ow,oh,d][g]=dict(w=ow,h=oh,d=d,f=f,pose=q,
                        source=str(args.new_bank)+':'+key,transform=[trans,sx,sy],geometry_sha256=g)
    stitch,_=public_functions(ROOT/'vendor/lightning_ftmc')
    control=positive_control(stitch);atom(args.out/'positive-control.json',control)
    manifest={'baseline_sha256':proof['sha256'],'baseline_report_sha256':sha(args.official_report),
        'source_sha256':sha(Path(__file__)),'new_bank':str(args.new_bank),'new_bank_sha256':sha(args.new_bank),
        'palette_manifest_sha256':sha(args.palette_manifest),'banks':inputs,
        'new_oriented_types':len(new),'new_oriented_poses':sum(map(len,new.values())),
        'partner_types':len(types),'partner_options':sum(map(len,options.values())),
        'whole_seconds':args.seconds,'workers':1,'modes':[0,1,2],
        'scope':'Every ordered pair of a new best night-seed type and a finite whole-library partner type, every feasible k. All finite D4 pose pairs tested if necessary; no separating-profile restriction.',
        'no_gpu':True,'no_submission':True}
    atom(args.out/'manifest.json',manifest)
    jobs=[];stats=Counter();records=[];candidates={}
    for dims,values in new.items():
        nf=min(x['f']for x in values.values())
        for tid,t in enumerate(types):
            for reverse in (False,True):
                for mode in (0,1,2):
                    stats['type_pairs_with_mode']+=1
                    W=dims[0]+t['w']+(mode==1);H=dims[1]+t['h']+(mode==2);d=dims[2]+t['d']
                    if max(W,H)>31 or d>63:continue
                    targets=[];f=max(nf,t['f'])
                    for k in range(max(W,H),32):
                        n=k*k+d
                        if n>1000:break
                        stats['containers_screened']+=1
                        gain=(best[n]-k-f)/math.sqrt(n)
                        if gain>1e-8 and n<=(k+f)**2+1e-10:targets.append((k,n,gain))
                    if targets:jobs.append((sum(x[2]for x in targets),dims,tid,reverse,mode,targets))
    jobs.sort(reverse=True,key=lambda x:x[0]);stats['planned_jobs']=len(jobs)
    def checkpoint(status):
        atom(args.out/'candidates.json',candidates)
        atom(args.out/'report.json',{'status':status,'elapsed_seconds':time.monotonic()-STARTED,
            'manifest_sha256':sha(args.out/'manifest.json'),'stats':dict(stats),'records':records,
            'certified_cases':len(candidates),'score_gain':sum((before[int(n)]-float(c['side']))/math.sqrt(int(n))for n,c in candidates.items()),
            'candidates_sha256':sha(args.out/'candidates.json')})
    checkpoint('screened')
    for _,dims,tid,reverse,mode,targets in jobs:
        if time.monotonic()>=deadline-1:break
        a=list(new[dims].values());b=options[tid]
        pairs=sorted(((max(x['f'],y['f']),x,y)for x in a for y in b),key=lambda x:x[0])
        selected=None
        for f,x,y in pairs:
            if time.monotonic()>=deadline-1:break
            first,second=(y,x)if reverse else(x,y);stats['exact_pair_tests']+=1
            if cross_block_separated(first['pose'],second['pose'],first['w'],second['h'],mode):
                selected=[first,second];break
        stats['completed_jobs']+=1
        if selected is None:stats['finite_pose_pair_jobs_rejected']+=1;continue
        stats['pair_jobs_passed']+=1
        for k,n,_ in targets:
            if time.monotonic()>=deadline-1:break
            if k+max(p['f']for p in selected)>=best[n]-1e-8:continue
            q=build(selected,[3,mode],k,stitch);stats['full_layouts_built']+=1
            if q is None or side(q)>=best[n]-1e-8:continue
            cert=full_certificate(q);stats['full_certifications']+=1
            if not cert['valid']:stats['full_gate_rejections']+=1;continue
            length=cert['independent_raw']['side_upper']
            if float(length)>=best[n]-1e-8:continue
            record={'n':n,'k':k,'mode':mode,'pair':[{a:b for a,b in p.items()if a!='pose'}for p in selected],
                'certificate':cert,'side':length,'gain_vs_frozen_baseline':(before[n]-float(length))/math.sqrt(n)}
            candidates[str(n)]={'side':length,'squares':[[f'{v:.17g}'for v in row]for row in q],
                'source':'Exact CPU pair using freshly polished night seed','provenance':record}
            best[n]=float(length);records.append(record);checkpoint('running')
        if stats['completed_jobs']%100==0:checkpoint('running')
    checkpoint('complete'if stats['completed_jobs']==len(jobs)else'bounded_partial')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['baseline','official-report','new-bank','palette-manifest','high-descriptor','out']:
        p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--seconds',type=float,default=90)
    args=p.parse_args()
    if args.out.exists()or not 10<args.seconds<=100:raise ValueError('Fresh directory and bounded search required')
    process=mp.get_context('fork').Process(target=campaign,args=(args,));process.start()
    process.join(max(0.,args.seconds-1.5-(time.monotonic()-STARTED)));forced=process.is_alive()
    if forced:
        try:os.killpg(process.pid,signal.SIGKILL)
        except ProcessLookupError:process.kill()
        process.join(.4)
    receipt={'seconds':time.monotonic()-STARTED,'whole_seconds':args.seconds,'workers':1,'exitcode':process.exitcode,'forced':forced}
    if args.out.exists():atom(args.out/'supervisor.json',receipt)
    print(json.dumps(receipt),flush=True)
    if process.exitcode and not forced:raise SystemExit(process.exitcode)


if __name__=='__main__':main()
