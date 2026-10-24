#!/usr/bin/env python3
"""Bounded strict upright-refill capacity audit; never truncate to input count.

Finite candidate/MIS search uses the existing independent refill implementation.
Every increased-capacity export is independently interval-validated and scored
by the pinned official metric. Full-puzzle candidates must beat their target m.
Rectangular surplus variants remain separate composition inputs.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import signal
import sys
import time

for variable in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[variable] = '1'
import numpy as np
from scipy.spatial import cKDTree
from refill_search import generate_candidates, conflict_graph, maximum_independent_set, sat_gaps
from compose_gadgets import normalize, extents, side

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from score_official import load_metric
from validate_submission import Square, validate_puzzle

CONTROL_NS = {83,84,86,87,88,106,107,128,129,152,171,172,179,180,198,205,227,235,259,266,292,300,301,302}


class TrialTimeout(Exception):
    pass


def alarm(signum, frame):
    raise TrialTimeout()


def digest(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def split_core(p):
    # Nearly upright source squares are candidate centres, not asserted upright
    # geometry: strict SAT filtering checks the zero-angle replacement anew.
    angle = np.abs((p[:,2] + math.pi/4) % (math.pi/2) - math.pi/4)
    tilted = angle > 1e-6
    return p[tilted], p[~tilted], len(np.unique(np.round(p[tilted,2], 3)))


def capacity(p, W, H, depth=3, max_candidates=6000):
    core, upright, diversity = split_core(p)
    generated = generate_candidates(W,H,core,incumbents=None,depth=depth,margin=1e-11,soft=0.)
    # Preserve original upright centre values before coalescing any generated
    # near-copies. All are screened against the actual tilted core.
    xy = np.vstack((upright[:,:2], generated))
    inside = ((xy[:,0] >= .5) & (xy[:,0] <= W-.5) &
              (xy[:,1] >= .5) & (xy[:,1] <= H-.5))
    xy = xy[inside]
    xy = xy[sat_gaps(xy,core) >= 0.]
    _, indexes = np.unique(np.round(xy,12),axis=0,return_index=True)
    xy = xy[np.sort(indexes)]
    unpruned_count = len(xy)
    if len(xy)>max_candidates:
        protected=min(len(upright),len(xy))
        keep=np.r_[np.arange(protected),np.linspace(protected,len(xy)-1,max_candidates-protected,dtype=int)]
        xy=xy[keep]
    graph=conflict_graph(xy,margin=0.)
    selected, info=maximum_independent_set(graph,time_limit=.2)
    q=np.vstack((core,np.column_stack((xy[selected],np.zeros(len(selected))))))
    info.update(core=len(core),original_upright=len(upright),angle_classes=diversity,
                candidates=len(xy),unpruned_candidates=unpruned_count,
                source_count=len(p),capacity=len(q),depth=depth,soft=0.)
    return q,info


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--baseline',type=Path,default=ROOT/'artifacts/submission-gpu-composition-safe.csv')
    ap.add_argument('--rectangles',type=Path,default=ROOT/'artifacts/high-n-donors/donors.npz')
    ap.add_argument('--seconds',type=float,default=480)
    ap.add_argument('--max-trials',type=int,default=150)
    ap.add_argument('--per-case',type=float,default=3)
    ap.add_argument('--skip-report',type=Path)
    ap.add_argument('--rectangles-only',action='store_true')
    ap.add_argument('--rectangle-order',choices=['diversity','surplus'],default='diversity')
    ap.add_argument('--out',type=Path,default=ROOT/'artifacts/refill-capacity')
    args=ap.parse_args()
    if args.out.exists():raise ValueError('Preserve previous experiment directory')
    args.out.mkdir(parents=True)
    started=time.monotonic();deadline=started+args.seconds
    poses={}
    with args.baseline.open() as f:
        for row in csv.DictReader(f):
            poses.setdefault(int(row['n']),[]).append([float(row[k]) for k in ('x','y','angle')])
    poses={n:normalize(np.array(q)) for n,q in poses.items()}
    baseline_sides={n:side(q) for n,q in poses.items()}
    portfolio=[]
    for n,p in poses.items():
        core,up,diversity=split_core(p);L=baseline_sides[n]
        if n in CONTROL_NS or n<40 or n>=1000 or not 2<=len(core)<=320 or len(up)<5:continue
        bound=min(1000,math.floor(L*L+1e-9))
        if bound<=n:continue
        opportunity=max((baseline_sides[m]-L)/math.sqrt(m)for m in range(n+1,min(n+6,bound)+1))
        if opportunity<=1e-8:continue
        portfolio.append((opportunity*(1+.15*min(diversity,6)),{'kind':'full','key':f'n{n}',
            'p':p,'W':L,'H':L,'source_n':n,'priority':opportunity,'angle_classes':diversity}))
    portfolio.sort(key=lambda t:-t[0])
    # Interleave size bands rather than spending all time on small historical
    # record instances; diverse angle classes get priority within each band.
    bands={i:[] for i in range(10)}
    for _,job in portfolio:bands[job['source_n']//100].append(job)
    full=[]
    while any(bands.values()):
        for key in reversed(bands):
            if bands[key]:full.append(bands[key].pop(0))
    rectangles=[]
    with np.load(args.rectangles) as z:
        for key in z.files:
            p=normalize(z[key]);lo,hi=extents(p);W,H=hi.max(0)-lo.min(0)
            core,up,diversity=split_core(p)
            if not 2<=len(core)<=320 or len(up)<5 or len(p)>=1000:continue
            rectangles.append({'kind':'rectangle','key':key,'p':p,'W':float(W),'H':float(H),
                'source_n':len(p),'angle_classes':diversity})
    rectangles.sort(key=lambda j:(-min(j['angle_classes'],8),len(split_core(j['p'])[0]),j['source_n']))
    if args.rectangle_order=='surplus':
        rectangles.sort(key=lambda j:(-(j['source_n']-math.floor(j['W'])*math.floor(j['H'])),
                                      len(split_core(j['p'])[0])))
    skipped=set()
    if args.skip_report:
        skipped={(x['kind'],x['key'])for x in json.loads(args.skip_report.read_text())['trials']}
    full=[j for j in full if (j['kind'],j['key'])not in skipped]
    rectangles=[j for j in rectangles if (j['kind'],j['key'])not in skipped]
    if args.rectangles_only:full=[]
    jobs=[]
    for i in range(max(len(full),len(rectangles))):
        if i<len(full):jobs.append(full[i])
        if i<len(rectangles):jobs.append(rectangles[i])
    jobs=jobs[:args.max_trials]
    metric=load_metric(ROOT/'research/official_metric_v17.py')
    trials=[];full_candidates={};rect_candidates={};certified=[]
    signal.signal(signal.SIGALRM,alarm)
    print(json.dumps({'event':'start','eligible_full':len(full),'eligible_rectangles':len(rectangles),
        'selected':len(jobs),'seconds':args.seconds,'per_case':args.per_case}),flush=True)
    for index,job in enumerate(jobs):
        if time.monotonic()>=deadline-1:break
        begin=time.monotonic();result={k:v for k,v in job.items() if k!='p'}
        try:
            signal.setitimer(signal.ITIMER_REAL,min(args.per_case,deadline-time.monotonic()))
            q,info=capacity(job['p'],job['W'],job['H'])
            signal.setitimer(signal.ITIMER_REAL,0)
            result.update(info,status='complete')
            m=len(q)
            if m>job['source_n'] and m<=1000:
                result['excess_capacity']=m-job['source_n']
                signal.setitimer(signal.ITIMER_REAL,max(.01,min(20,deadline-time.monotonic())))
                squares=[Square(*(format(float(v),'.17g') for v in row)) for row in q]
                certificate=validate_puzzle(m,squares)
                if not certificate['valid']:
                    result.update(status='capacity_rejected_geometry',certificate=certificate)
                else:
                    rows=[dict(n=str(m),square_id=str(i),x=s.x,y=s.y,angle=s.angle)for i,s in enumerate(squares)]
                    official=metric.evaluate_single_puzzle(m,rows)
                    result['official']=official
                    if official[2] is not None:
                        qside=float(official[2]);gain=(baseline_sides[m]-qside)/math.sqrt(m)
                        result['potential_full_score_gain']=gain
                        result['status']='capacity_certified'
                        certified.append({**result,'certificate':certificate})
                        if gain>1e-10 and (str(m)not in full_candidates or qside<full_candidates[str(m)]['side']):
                            full_candidates[str(m)]={'side':qside,'squares':[[s.x,s.y,s.angle]for s in squares],
                                'source':'strict increased-capacity refill','source_count':job['source_n'],'origin':job['key'],
                                'official':official,'certificate':certificate}
                        if job['kind']=='rectangle':
                            w,h=int(math.floor(job['W'])),int(math.floor(job['H']));d=m-w*h
                            if 0<d<64:rect_candidates[f'{w}_{h}_{d}__{job["key"]}']=q
                signal.setitimer(signal.ITIMER_REAL,0)
        except TrialTimeout:
            result['status']='case_timeout'
        finally:signal.setitimer(signal.ITIMER_REAL,0)
        result['elapsed']=time.monotonic()-begin;trials.append(result)
        (args.out/'full_candidates.json').write_text(json.dumps(full_candidates)+'\n')
        if rect_candidates:np.savez_compressed(args.out/'increased_surplus.npz',**rect_candidates)
        if index%10==0 or result['status']=='capacity_certified':
            print(json.dumps({'event':'progress','done':len(trials),'status':result['status'],'key':job['key'],
                'source_n':job['source_n'],'capacity':result.get('capacity'),'elapsed':time.monotonic()-started,
                'certified':len(certified),'full_improvements':len(full_candidates)}),flush=True)
    report={'baseline':str(args.baseline),'baseline_sha256':digest(args.baseline),
        'rectangle_archive':str(args.rectangles),'rectangle_sha256':digest(args.rectangles),
        'script_sha256':digest(Path(__file__)),
        'skip_report':str(args.skip_report)if args.skip_report else None,
        'skip_report_sha256':digest(args.skip_report)if args.skip_report else None,
        'rectangles_only':args.rectangles_only,'rectangle_order':args.rectangle_order,
        'budget_seconds':args.seconds,'elapsed_seconds':time.monotonic()-started,'selected':len(jobs),
        'completed':sum(x['status']!='case_timeout' for x in trials),'attempted':len(trials),
        'timeouts':sum(x['status']=='case_timeout' for x in trials),'capacity_certified':len(certified),
        'full_improvements':len(full_candidates),'rectangular_surplus_variants':len(rect_candidates),
        'certified':certified,'trials':trials,
        'scope_note':'Finite candidate maximum independent sets; timeouts and pruning do not establish continuous capacity optimality.'}
    (args.out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ['trials','certified']}),flush=True)


if __name__=='__main__':main()
