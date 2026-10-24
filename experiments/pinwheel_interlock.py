"""Bounded four-interface cyclic pinwheel test; no continuous repair or GPU.

Four A-by-B donor envelopes rotate around the centre of a square of side L.
Adjacent envelopes may interlock, while a c-by-c upright central grid requires
L >= 2B+c. The exact count is 4m+c*c. No pairwise/profile success is sufficient
for admission: all full raw/default-pandas official and interval gates apply.
"""
import time
STARTED = time.monotonic()
import argparse
from collections import Counter
import hashlib
import itertools
import json
import math
import os
from pathlib import Path
import sys
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[key]='1'
import numpy as np
from scipy.spatial import cKDTree
from compose_gadgets import extents, normalize, legalize, side
from fq_capacity_probe import full_certificate

ROOT=Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def atom(path,value):
    tmp=path.with_suffix(path.suffix+'.incoming')
    tmp.write_text(json.dumps(value,indent=2)+'\n');tmp.replace(path)


def cross_gap(a,b):
    """Floating broad-phase/SAT proposal filter, never a geometry certificate."""
    neighbours=cKDTree(a[:,:2]).query_ball_tree(cKDTree(b[:,:2]),1.5)
    pairs=np.array([(i,j)for i,js in enumerate(neighbours)for j in js],dtype=int)
    if not len(pairs):return 1.
    aa=a[pairs[:,0]];bb=b[pairs[:,1]];delta=bb[:,:2]-aa[:,:2]
    radius=.5*(1+np.abs(np.cos(aa[:,2]-bb[:,2]))+np.abs(np.sin(aa[:,2]-bb[:,2])))
    gaps=[]
    for angle in (aa[:,2],aa[:,2]+np.pi/2,bb[:,2],bb[:,2]+np.pi/2):
        gaps.append(np.abs(delta[:,0]*np.cos(angle)+delta[:,1]*np.sin(angle))-radius)
    return float(np.max(np.stack(gaps),axis=0).min())


def variants(p):
    p=legalize(p)
    if p is None:raise ValueError('Source changed beyond rounding clearance')
    lo,hi=extents(p);span=hi.max(0)-lo.min(0)
    if span[0]<span[1]:
        p[:,:2]=p[:,[1,0]];p[:,2]=np.pi/2-p[:,2];p=normalize(p)
    result=[]
    for sx,sy in ((1,1),(-1,1),(1,-1),(-1,-1)):
        q=p.copy();q[:,0]*=sx;q[:,1]*=sy;q[:,2]*=sx*sy
        result.append(normalize(q))
    spans=[extents(q)[1].max(0)for q in result]
    return result,float(max(s[0]for s in spans)+2e-8),float(max(s[1]for s in spans)+2e-8)


def placed(q,L,B,arm):
    p=q.copy();p[:,1]+=L-B
    for _ in range(arm):
        x=p[:,0].copy();p[:,0]=p[:,1];p[:,1]=L-x;p[:,2]-=np.pi/2
    return p


def grid(c,L):
    return np.array([[(L-c)/2+x+.5,(L-c)/2+y+.5,0.]for x in range(c)for y in range(c)]).reshape(-1,3)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--bank',type=Path,required=True)
    ap.add_argument('--portfolio',type=Path,default=ROOT/'artifacts/current-best-portfolio.json')
    ap.add_argument('--seconds',type=float,default=290)
    args=ap.parse_args();deadline=STARTED+min(args.seconds,290)
    args.out.mkdir(parents=True,exist_ok=False)
    pointer=json.loads(args.portfolio.read_text());baseline=Path(pointer['safe']['path'])
    assert sha(baseline)==pointer['safe']['sha256']
    official=Path(pointer['safe']['official_report']);report=json.loads(official.read_text())
    assert sha(official)==pointer['safe']['official_report_sha256'] and report['valid']
    before={r['n']:float(r['side'])for r in report['results']}
    manifest={'model':'four directed cyclic interlocking interfaces','formula_count':'4m+c²',
              'formula_outer_side':'L=A+B−t, 0<=t<=1, L>=A, L>=2B+c',
              'bank':str(args.bank.resolve()),'bank_sha256':sha(args.bank),
              'portfolio_pointer_sha256':sha(args.portfolio),'baseline':pointer['safe'],
              'source_sha256':sha(Path(__file__)),'helper_hashes':{p:sha(ROOT/p)for p in [
                  'experiments/compose_gadgets.py','experiments/fq_capacity_probe.py',
                  'scripts/validate_submission.py','research/official_metric_v17.py']},
              'finite_reflections_per_arm':4,'workers':1,'maximum_seconds':args.seconds,
              'no_repair':True,'no_gpu':True,'no_submission':True,
              'claim_scope':'Finite same-source four-arm cycles; no mixed-source or continuous optimality claim.'}
    atom(args.out/'manifest.json',manifest)
    positive=np.vstack([placed(np.array([[.5,.5,0.],[1.5,.5,0.]]),3.,1.,i)for i in range(4)]+[grid(1,3.)])
    positive=legalize(positive);cert=full_certificate(positive)
    assert len(positive)==9 and cert['valid']
    negative=positive.copy();negative[-1]=negative[0]
    rejected=full_certificate(negative);assert not rejected['valid']
    atom(args.out/'controls.json',{'upright_pinwheel_n9':cert,'duplicate_square_negative_rejected':not rejected['valid']})
    stats=Counter();trials=[];candidates={};prepared={};jobs=[]
    with np.load(args.bank,allow_pickle=False)as bank:
        for key in bank.files:
            p=bank[key];m=len(p)
            if 4*m>1000:continue
            vv,A,B=variants(p);prepared[key]=(vv,A,B,m)
            for c in range(math.isqrt(1000-4*m)+1):
                n=4*m+c*c;lower=max(A,A+B-1,2*B+c,math.sqrt(n))
                L=min(A+B-1e-7,before[n]-1e-5)
                if L>=lower+1e-7:
                    jobs.append(((before[n]-lower)/math.sqrt(n),key,c,n,L,lower))
    jobs.sort(reverse=True);stats['scalar_promising_jobs']=len(jobs)
    def checkpoint(status):
        atom(args.out/'candidates.json',candidates)
        atom(args.out/'report.json',{'status':status,'seconds':time.monotonic()-STARTED,
             'manifest_sha256':sha(args.out/'manifest.json'),'coverage':dict(stats),'trials':trials,
             'certified_cases':len(candidates),'candidates_sha256':sha(args.out/'candidates.json')})
    checkpoint('controls_passed')
    for headroom,key,c,n,L,lower in jobs:
        if time.monotonic()>=deadline:break
        vv,A,B,m=prepared[key];arms=[[placed(q,L,B,i)for q in vv]for i in range(4)]
        edges=[]
        for i in range(4):
            edges.append(np.array([[cross_gap(arms[i][a],arms[(i+1)%4][b])for b in range(4)]for a in range(4)]))
        stats['adjacent_pair_tests']+=64
        best_gap=-1e9;best_cycle=None;survivors=[]
        for cycle in itertools.product(range(4),repeat=4):
            gap=min(edges[i][cycle[i],cycle[(i+1)%4]]for i in range(4))
            if gap>best_gap:best_gap=gap;best_cycle=cycle
            if gap>=-1e-10:survivors.append(cycle)
        row={'source_key':key,'n':n,'core':c,'count':4*m+c*c,'A':A,'B':B,'trial_side':L,
             'envelope_overlap':A+B-L,'optimistic_side_lower':lower,'optimistic_score_headroom':headroom,
             'adjacent_compatible_cycles':len(survivors),'best_cycle':best_cycle,'best_bottleneck_gap':best_gap}
        for cycle in survivors:
            pieces=[arms[i][cycle[i]]for i in range(4)];centre=grid(c,L)
            if len(centre):pieces.append(centre)
            gaps=[cross_gap(pieces[i],pieces[j])for i in range(len(pieces))for j in range(i)]
            stats['all_piece_pair_tests']+=len(gaps)
            if min(gaps)<-1e-10:continue
            q=legalize(np.vstack(pieces));stats['whole_layout_attempts']+=1
            if q is None or len(q)!=n or side(q)>=before[n]-1e-9:continue
            certificate=full_certificate(q);stats['full_certificate_calls']+=1
            if not certificate['valid']:continue
            length=certificate['independent_raw']['side_upper']
            if float(length)>=before[n]-1e-9:continue
            candidates[str(n)]={'side':length,'squares':[[f'{x:.17g}'for x in r]for r in q],
                 'source':'Four-interface interlocking cyclic pinwheel',
                 'provenance':{'manifest_sha256':sha(args.out/'manifest.json'),'cycle':cycle,'source_key':key,
                               'core':c,'A':A,'B':B,'trial_side':L,'certificate':certificate}}
            row['certificate']=certificate;row['accepted_cycle']=cycle;stats['certified_improvements']+=1
            break
        trials.append(row);stats['jobs_completed']+=1
        checkpoint('running')
    checkpoint('complete'if stats['jobs_completed']==len(jobs)else'bounded_partial')
    print(json.dumps({'seconds':time.monotonic()-STARTED,'coverage':dict(stats),'certified_cases':len(candidates),
                      'best_failed_gap':max((r['best_bottleneck_gap']for r in trials),default=None)}))


if __name__=='__main__':main()
