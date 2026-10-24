#!/usr/bin/env python3
"""Bounded fixed-angle MILP for donor translations and upright-grid phases.

All squares are retained. Seven continuous variables describe the square side,
the two upper-grid phase coordinates, and both rigid donor translations.
Potential new neighbors are included using a worst-displacement radius.
"""
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
import pandas as pd
from scipy.optimize import milp,Bounds,LinearConstraint
from scipy.sparse import coo_matrix
from scipy.spatial import cKDTree
from scalar_sat_staircase import palette,atom,sha,array_sha
from compose_gadgets import extents,legalize,side
from fq_capacity_probe import full_certificate
from fq_coherent_clusters import Deadline,alarm

ROOT=Path(__file__).resolve().parents[1]


def symbolic_pair(a,b,k,mode=0):
    spans=[(0,b['h']+(mode==2),a['w'],a['h']),
           (a['w']+(mode==1),0,b['w'],b['h'])]
    assert max(s[0]+s[2] for s in spans)<=k and max(s[1]+s[3] for s in spans)<=k
    base=[];coeff=[];groups=[]
    for x in range(k):
        active=next((s for s in spans if s[0]<=x<s[0]+s[2]),None)
        if active:_,y0,w,h=active
        else:
            following=[s for s in spans if s[0]>x]
            y0=following[0][1]+following[0][3] if following else 0;h=0
        for y in range(k):
            if active and y0<=y<y0+h:continue
            high=y>=y0;c=np.zeros((2,7))
            if high:c[0,1]=c[1,2]=1
            base.append([x+.5,y+.5,0]);coeff.append(c);groups.append(int(high))
    for index,(p,span) in enumerate(zip((a,b),spans)):
        for row in p['pose']:
            c=np.zeros((2,7));c[0,3+2*index]=c[1,4+2*index]=1
            base.append([row[0]+span[0],row[1]+span[1],row[2]])
            coeff.append(c);groups.append(index+2)
    assert len(base)==k*k+a['d']+b['d']
    return np.array(base),np.array(coeff),np.array(groups)


def potential_pairs(base,C,low,high):
    midpoint=(low+high)/2;half=(high-low)/2
    centers=base[:,:2]+np.einsum('nij,j->ni',C,midpoint)
    radius_xy=np.einsum('nij,j->ni',abs(C),half)
    rho=np.sqrt((radius_xy**2).sum(1))
    search_radius=math.sqrt(2)+2*float(rho.max())+1e-8
    pairs=cKDTree(centers).query_pairs(search_radius,output_type='ndarray')
    return pairs,centers,rho,search_radius


def solve_phases(a,b,k,upper,seconds=1.,domain='tile',mode=0,force=None):
    started=time.monotonic();base,C,groups=symbolic_pair(a,b,k,mode)
    lower=max(a['f'],b['f'])
    info=dict(domain=domain,lower_f=lower,upper_f=upper,n=len(base),pair_mode=mode)
    if upper<lower:return dict(info,status='empty-side-domain'),None
    lb=[lower,0.,0.];ub=[upper,upper,upper]
    for item in (a,b):
        lo,hi=extents(item['pose']);excess=(hi.max(0)-lo.min(0))-[item['w'],item['h']]
        lb.extend([0.,0.] if domain=='tile' else [-.25,-.25])
        ub.extend(list(np.maximum(0.,upper-excess)) if domain=='tile' else [.25,.25])
    if force:
        for index,value in force.items():lb[index]=ub[index]=value
    low=np.array(lb);high=np.array(ub);rr=[];cc=[];vv=[];lhs=[];rhs=[];integrality=[0]*7
    def constraint(values,bottom=-np.inf,top=np.inf):
        row=len(lhs)
        for col,value in values.items():
            if value:rr.append(row);cc.append(col);vv.append(value)
        lhs.append(bottom);rhs.append(top)
    for index in (1,2):constraint({index:1,0:-1},top=0)
    if domain=='tile':
        for z,item in enumerate((a,b)):
            lo,hi=extents(item['pose']);ex=(hi.max(0)-lo.min(0))-[item['w'],item['h']]
            for axis in (0,1):constraint({3+2*z+axis:1,0:-1},top=-ex[axis])
    e=.5*(abs(np.cos(base[:,2]))+abs(np.sin(base[:,2])))
    for i in range(len(base)):
        for axis in (0,1):
            v={j:C[i,axis,j] for j in range(7)}
            constraint(v,bottom=e[i]-base[i,axis])
            v=dict(v);v[0]=v.get(0,0)-1
            constraint(v,top=k-e[i]-base[i,axis])
    # An interval box over all continuous variables encloses every center.
    # Each point's Euclidean displacement from its midpoint is bounded by rho.
    pairs,centers,rho,search_radius=potential_pairs(base,C,low,high)
    uncertain=0;tested=0;invariant=0;binary_count=0
    for i,j in pairs:
        if groups[i]==groups[j]:invariant+=1;continue
        if np.linalg.norm(centers[i]-centers[j])>math.sqrt(2)+rho[i]+rho[j]+1e-8:continue
        tested+=1;delta=base[j,:2]-base[i,:2];DC=C[j]-C[i]
        radius=.5*(1+abs(math.cos(base[i,2]-base[j,2]))+abs(math.sin(base[i,2]-base[j,2])))
        branches=[];seen=set();guaranteed=False
        for angle in (base[i,2],base[i,2]+math.pi/2,base[j,2],base[j,2]+math.pi/2):
            for sign in (-1,1):
                normal=sign*np.array([math.cos(angle),math.sin(angle)])
                token=tuple(np.round(normal,12))
                if token in seen:continue
                seen.add(token);coef=normal@DC;bound=radius+5e-9-float(normal@delta)
                minimum=float(np.where(coef>=0,coef*low,coef*high).sum())
                maximum=float(np.where(coef>=0,coef*high,coef*low).sum())
                if minimum>=bound:guaranteed=True;break
                if maximum>=bound-1e-12:branches.append((coef,bound,minimum))
            if guaranteed:break
        if guaranteed:continue
        if not branches:return dict(info,status='pair-domain-impossible',pair=[int(i),int(j)],
            neighbor_radius=search_radius,tested_pairs=tested),None
        uncertain+=1
        if len(branches)==1:
            c,b,_=branches[0];constraint(dict(enumerate(c)),bottom=b);continue
        selectors=[]
        for c,b,minimum in branches:
            index=len(lb);lb.append(0);ub.append(1);integrality.append(1);selectors.append(index)
            M=b-minimum+1e-10;values=dict(enumerate(c));values[index]=-M
            constraint(values,bottom=b-M)
        binary_count+=len(selectors);constraint({i:1 for i in selectors},bottom=1)
    A=coo_matrix((vv,(rr,cc)),shape=(len(lhs),len(lb))).tocsc()
    objective=np.zeros(len(lb));objective[0]=1
    result=milp(objective,integrality=np.array(integrality),bounds=Bounds(lb,ub),
        constraints=LinearConstraint(A,lhs,rhs),options={'time_limit':seconds,'mip_rel_gap':1e-9,'presolve':True,'threads':1})
    info.update(status='milp-'+str(result.status),message=result.message,variables=len(lb),
        binary_variables=binary_count,constraints=len(lhs),uncertain_pairs=uncertain,tested_pairs=tested,
        invariant_pairs_skipped=invariant,neighbor_radius=search_radius,maximum_displacement=float(rho.max()),
        seconds=time.monotonic()-started)
    if result.x is None:return info,None
    v=result.x[:7];q=base.copy();q[:,:2]+=np.einsum('nij,j->ni',C,v)
    info.update(phase_variables=v.tolist(),native_objective=float(v[0]),preclearance_side=side(q))
    return info,legalize(q)


def controls():
    L=2+math.sqrt(.5)
    p=legalize(np.array([[.5,.5,0],[.5,L-.5,0],[L-.5,.5,0],[L-.5,L-.5,0],[L/2,L/2,np.pi/4]]))
    item=dict(w=2,h=2,d=1,f=side(p)-2+3e-8,pose=p)
    positive,q=solve_phases(item,item,5,item['f']+.1,seconds=5,mode=1,force={3:.02})
    assert q is not None and len(q)==27
    cert=full_certificate(q);assert cert['valid']
    positive['certificate']=cert
    negative,_=solve_phases(item,item,4,item['f']+1e-5,seconds=5,mode=0)
    assert negative['status'] in ('pair-domain-impossible','milp-2')
    return dict(positive=positive,negative=negative,valid=True)


def campaign(args):
    os.setsid();signal.signal(signal.SIGTERM,alarm);deadline=STARTED+args.seconds-5
    args.out.mkdir(parents=True,exist_ok=False);(args.out/'source').mkdir()
    pointer=json.loads(args.pointer.read_text());baseline=Path(pointer['raw']['path'])
    report_path=Path(pointer['raw']['official_report']);proof=json.loads(report_path.read_text())
    assert sha(baseline)==proof['sha256']==pointer['raw']['sha256'] and proof['valid']
    frame=pd.read_csv(baseline,float_precision='round_trip')
    base={int(n):g.sort_values('square_id')[['x','y','angle']].to_numpy(float)for n,g in frame.groupby('n')}
    before={r['n']:float(r['side'])for r in proof['results']};best=dict(before)
    prior=json.loads(args.palette_manifest.read_text());banks=[Path(x['path'])for x in prior['banks']]
    for item in prior['banks']:assert sha(item['path'])==item['sha256']
    types,options,inputs=palette(base,banks,args.high_descriptor,16)
    headroom=json.loads(args.headroom.read_text());assert headroom['baseline_sha256']==proof['sha256']
    assert types==headroom['types']
    control=controls();atom(args.out/'controls.json',control)
    jobs=headroom['jobs'];jobs.sort(key=lambda j:(not any(t[1] in (498,814) for t in j['targets']),-j['gain_bound']))
    used={j[x]for j in jobs for x in ('first','second')};arrays={};option_records=[]
    for tid in sorted(used):
        for p in options[tid]:
            key=f"{p['w']}_{p['h']}_{p['d']}__uid_{p['uid']}";arrays[key]=p['pose']
            option_records.append(dict(type_id=tid,array_key=key,**{k:v for k,v in p.items()if k!='pose'}))
    np.savez_compressed(args.out/'input-options.npz',**arrays);atom(args.out/'input-options.json',option_records)
    paths=[Path(__file__),ROOT/'experiments/scalar_sat_staircase.py',ROOT/'experiments/compose_gadgets.py',
        ROOT/'experiments/fq_capacity_probe.py',ROOT/'experiments/fq_active_pilot.py',ROOT/'experiments/extract_broad_active_frontier.py',
        ROOT/'scripts/validate_submission.py',ROOT/'scripts/score_official.py',ROOT/'research/official_metric_v17.py']
    for path in paths:shutil.copy2(path,args.out/'source'/path.name)
    manifest=dict(pointer_sha256=sha(args.pointer),baseline_sha256=proof['sha256'],baseline_path=str(baseline),
        official_report_sha256=sha(report_path),palette_manifest_sha256=sha(args.palette_manifest),banks=inputs,
        headroom_sha256=sha(args.headroom),input_options_sha256=sha(args.out/'input-options.npz'),
        input_metadata_sha256=sha(args.out/'input-options.json'),source_hashes={str(p.relative_to(ROOT)):sha(p)for p in paths},
        workers=1,seconds=args.seconds,milp_seconds=args.milp_seconds,planned_type_jobs=len(jobs),
        method='Fixed unit-square angles and counts; continuous rigid-donor translations plus independent x/y phases of upper upright continent. '
               'Complete walls and finite SAT disjunctions over every neighbor possible anywhere in the continuous variable bounds.',
        no_gpu=True,no_submission=True)
    atom(args.out/'manifest.json',manifest);candidates={};records=[];stats=Counter();seen=set()
    def checkpoint(status):
        atom(args.out/'candidates.json',candidates)
        atom(args.out/'report.json',dict(status=status,elapsed_seconds=time.monotonic()-STARTED,
            manifest_sha256=sha(args.out/'manifest.json'),stats=dict(stats),records=records,
            candidates_sha256=sha(args.out/'candidates.json'),certified_cases=len(candidates),
            score_gain=sum((before[int(n)]-float(c['side']))/math.sqrt(int(n))for n,c in candidates.items())))
    checkpoint('screened')
    for job in jobs:
        if time.monotonic()>deadline-3:break
        first,second=job['first'],job['second']
        for a in options[first]:
            for b in options[second]:
                if time.monotonic()>deadline-3:break
                targets=[t for t in job['targets'] if max(a['f'],b['f'])<best[t[1]]-t[0]-2e-7]
                if not targets:continue
                # The tightest container gives the largest possible shared
                # phase feasibility region; its geometry can be rechecked at
                # larger frame sizes after a successful repair.
                k,n,_=min(targets,key=lambda t:t[0]);upper=best[n]-k-2e-7
                token=(a['uid'],b['uid'],k)
                if token in seen:continue
                seen.add(token)
                for domain in ('tile','global'):
                    if time.monotonic()>deadline-3:break
                    stats['phase_models']+=1
                    info,q=solve_phases(a,b,k,upper,min(args.milp_seconds,max(.1,deadline-time.monotonic()-2)),domain)
                    stats[info['status']]+=1
                    row=dict(n=n,k=k,first_uid=a['uid'],second_uid=b['uid'],phase_model=info)
                    won=False
                    if q is not None and side(q)<best[n]-1e-7:
                        cert=full_certificate(q);row['certificate']=cert;stats['full_certifications']+=1
                        if cert['valid'] and float(cert['independent_raw']['side_upper'])<best[n]-1e-7:
                            length=cert['independent_raw']['side_upper'];row['gain']=(before[n]-float(length))/math.sqrt(n)
                            candidates[str(n)]=dict(side=length,squares=[[f'{v:.17g}'for v in r]for r in q],
                                source='Fractional rigid-donor and upright-grid phase composition',provenance=row)
                            best[n]=float(length);stats['certified_improvements']+=1
                            won=True
                            print(json.dumps(dict(n=n,gain=row['gain'],side=length)),flush=True)
                            for larger_k,larger_n,_ in targets:
                                if larger_k==k or time.monotonic()>deadline-3:continue
                                base2,C2,_=symbolic_pair(a,b,larger_k)
                                base2[:,:2]+=np.einsum('nij,j->ni',C2,np.array(info['phase_variables']))
                                expanded=legalize(base2)
                                if expanded is None or side(expanded)>=best[larger_n]-1e-7:continue
                                expansion_certificate=full_certificate(expanded);stats['full_certifications']+=1
                                if not expansion_certificate['valid']:continue
                                expanded_side=expansion_certificate['independent_raw']['side_upper']
                                if float(expanded_side)>=best[larger_n]-1e-7:continue
                                expansion=dict(n=larger_n,k=larger_k,first_uid=a['uid'],second_uid=b['uid'],
                                    phase_model=info,certificate=expansion_certificate,expanded_from=n,
                                    gain=(before[larger_n]-float(expanded_side))/math.sqrt(larger_n))
                                candidates[str(larger_n)]=dict(side=expanded_side,squares=[[f'{v:.17g}'for v in r]for r in expanded],
                                    source='Fractional-interface construction with a certified larger grid frame',provenance=expansion)
                                best[larger_n]=float(expanded_side);stats['certified_improvements']+=1;records.append(expansion)
                    records.append(row)
                    if won or stats['phase_models']%20==0:checkpoint('running')
                    if won:break
        stats['completed_type_jobs']+=1;checkpoint('running')
    checkpoint('complete'if stats['completed_type_jobs']==len(jobs)else'bounded_partial')


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for name in ('pointer','palette-manifest','high-descriptor','headroom','out'):ap.add_argument('--'+name,type=Path,required=True)
    ap.add_argument('--seconds',type=float,default=570)
    ap.add_argument('--milp-seconds',type=float,default=.75)
    args=ap.parse_args();assert 10<args.seconds<=600
    child=mp.get_context('fork').Process(target=campaign,args=(args,));child.start()
    child.join(max(0,args.seconds-2-(time.monotonic()-STARTED)));forced=child.is_alive()
    if forced:
        child.terminate();child.join(1)
        if child.is_alive():os.killpg(child.pid,signal.SIGKILL);child.join(1)
    result=dict(seconds=time.monotonic()-STARTED,limit=args.seconds,workers=1,forced=forced,exitcode=child.exitcode)
    if args.out.exists():atom(args.out/'supervisor.json',result)
    print(json.dumps(result),flush=True)
    if child.exitcode and not forced:raise SystemExit(child.exitcode)


if __name__=='__main__':main()
