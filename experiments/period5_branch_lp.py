#!/usr/bin/env python3
"""Bounded corner-disjunction experiments and LP contact-load diagnostics.

Provisional omitted-constraint results are never feasible-packing claims.
Every retained geometry passes all-pair SAT/walls plus fresh independent
interval and official raw/default-pandas gates after all violated-pair cuts.
"""
from __future__ import annotations
import argparse
import itertools
import json
import math
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time
import warnings
for name in('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='1'
import numpy as np
from scipy.optimize import linprog
from scipy.sparse import csr_matrix
from scipy.spatial import cKDTree

import period5_column_lp as base
from period5_column_ablation import relaxed_template
from fq_variant_campaign import atomic_json,atomic_npz,geometry_sha
from fq_active_pilot import digest
from extract_broad_active_frontier import certify_array


def data(p,pairs):
    i,j=pairs.T;a=p[:,2];c,s=np.cos(a),np.sin(a)
    ux=np.column_stack((c[i],-s[i],c[j],-s[j]));uy=np.column_stack((s[i],c[i],s[j],c[j]))
    delta=p[j,:2]-p[i,:2];projection=delta[:,0,None]*ux+delta[:,1,None]*uy
    radii=.5*(1+abs(np.cos(a[i]-a[j]))+abs(np.sin(a[i]-a[j])))
    return ux,uy,projection,abs(projection)-radii[:,None],radii


def distinct(ux,uy,indices):
    result=[]
    for index in indices:
        if all(abs(ux[index]*ux[old]+uy[index]*uy[old])<1-1e-8 for old in result):result.append(int(index))
    return result


def corner_pairs(p,upright_only=False):
    pairs=np.array(list(zip(*np.triu_indices(len(p),1))),dtype=int)
    ux,uy,projection,gap,radii=data(p,pairs)
    upright=abs((p[:,2]+np.pi/4)%(np.pi/2)-np.pi/4)<1e-6
    result=set()
    for row,pair in enumerate(pairs):
        if upright_only and not all(upright[pair]):continue
        if gap[row].max()>1e-7:continue
        touching=np.flatnonzero(abs(gap[row])<1e-7)
        if len(distinct(ux[row],uy[row],touching))>=2:result.add(tuple(map(int,pair)))
    return result


def choose(p,pairs,policy,rng):
    ux,uy,projection,gap,radii=data(p,pairs);answer={};ties=0
    for row,pair in enumerate(pairs):
        maximum=float(np.max(gap[row]));indices=np.flatnonzero(gap[row]>=maximum-1e-8)
        indices=distinct(ux[row],uy[row],indices)
        if len(indices)>1:ties+=1
        if policy=='random':index=int(rng.choice(indices))
        elif policy=='prefer_y':index=max(indices,key=lambda k:abs(uy[row,k]))
        elif policy=='checker':index=indices[int(sum(pair))%len(indices)]
        else:index=int(np.argmax(gap[row]))
        sg=1. if projection[row,index]>=0 else -1.
        answer[tuple(map(int,pair))]=(float(ux[row,index]*sg),float(uy[row,index]*sg),float(radii[row]+5e-9))
    return answer,ties


def violations(p,tolerance=1e-8):
    pairs=np.array(list(zip(*np.triu_indices(len(p),1))),dtype=int)
    _,_,_,gap,_=data(p,pairs);minimum=gap.max(1);bad=np.flatnonzero(minimum < -tolerance)
    return [(tuple(map(int,pairs[row])),float(minimum[row]))for row in bad],float(minimum.min())


def solve(model,p,baseline,offset,policy,omitted,seed,deadline,max_rounds=16):
    m=len(model['u']);C,constant,angles,z,warm=base.mapping(model,np.full(m,math.radians(offset)),np.zeros(m))
    n=len(p);nv=len(z);e=.5*(abs(np.cos(angles))+abs(np.sin(angles)));trust=.35
    pairs=cKDTree(warm[:,:2]).query_pairs(3.,output_type='ndarray')
    branches,ties=choose(warm,pairs,policy,np.random.default_rng(seed))
    branches={pair:value for pair,value in branches.items()if pair not in omitted}
    bounds=[(value-.8,value+.8)for value in z]+[(math.sqrt(n),baseline+.12)]
    trace=[];answer=None;dual_summary=None;added=set();source_corners=corner_pairs(p,True)
    for iteration in range(max_rounds):
        if deadline-time.monotonic()<1:break
        labels=list(branches);A=[];b=[]
        for i,j in labels:
            vx,vy,r=branches[(i,j)]
            coeff=(C[2*i]-C[2*j])*vx+(C[2*i+1]-C[2*j+1])*vy
            A.append(np.r_[coeff,0.]);b.append(-r-(constant[i,0]-constant[j,0])*vx-(constant[i,1]-constant[j,1])*vy)
        pair_count=len(labels)
        for index in range(n):
            for dim in(0,1):
                coeff=np.r_[C[2*index+dim],0.]
                A.extend((-coeff,np.r_[C[2*index+dim],-1.],coeff,-coeff))
                b.extend((constant[index,dim]-e[index]-5e-9,-constant[index,dim]-e[index]-5e-9,
                          warm[index,dim]+trust-constant[index,dim],-warm[index,dim]+trust+constant[index,dim]))
        A=csr_matrix(np.array(A));b=np.array(b);objective=np.zeros(nv+1);objective[-1]=1
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            fit=linprog(objective,A_ub=A,b_ub=b,bounds=bounds,method='highs',
                options={'threads':1,'time_limit':min(2.,max(.1,deadline-time.monotonic()-.5)),
                         'primal_feasibility_tolerance':1e-9,'dual_feasibility_tolerance':1e-9})
        row={'iteration':iteration,'status':int(fit.status),'success':bool(fit.success),'pair_constraints':pair_count}
        if not fit.success:trace.append(row);break
        q=np.column_stack(((C@fit.x[:nv]).reshape(n,2)+constant,angles))
        bad,minimum=violations(q)
        wall=float(min((q[:,:2]-e[:,None]).min(),(fit.x[-1]-q[:,:2]-e[:,None]).min()))
        row.update(provisional_lp_side=float(fit.x[-1]),full_sat_minimum=minimum,wall_minimum=wall,
                   violating_pairs=len(bad),maximum_constraint_violation=float(max(0.,(A@fit.x-b).max())))
        loads=np.abs(fit.ineqlin.marginals[:pair_count]);slacks=b[:pair_count]-A[:pair_count]@fit.x
        order=np.argsort(-loads);corner_ids=[k for k,pair in enumerate(labels)if pair in source_corners]
        dual_summary={'initial_tied_distinct_axes':ties,'source_upright_corner_pairs':len(source_corners),
            'enforced_corner_rows':len(corner_ids),'active_corner_rows':int(sum(abs(slacks[k])<1e-7 for k in corner_ids)),
            'nonzero_corner_duals':int(sum(loads[k]>1e-8 for k in corner_ids)),
            'corner_absolute_dual_sum':float(sum(loads[k]for k in corner_ids)),
            'all_pair_absolute_dual_sum':float(loads.sum()),
            'largest_pair_duals':[{'pair':labels[k],'absolute_dual':float(loads[k]),'slack':float(slacks[k]),
                'initial_upright_corner':labels[k]in source_corners,'axis':list(branches[labels[k]][:2])}for k in order[:30]if loads[k]>1e-8]}
        if not bad and wall>=-1e-8:
            row['passed_all_pair_and_wall_numerical_screen']=True;answer=q;trace.append(row);break
        # Every cut is a true unit-square SAT disjunct. Choosing its side is a
        # local heuristic, so failure is not a global infeasibility proof.
        new_pairs=[pair for pair,gap in sorted(bad,key=lambda item:item[1])if pair not in branches][:64]
        row['cuts_added']=len(new_pairs)
        if not new_pairs:trace.append(row);break
        choices,_=choose(q,np.array(new_pairs,dtype=int),policy,np.random.default_rng(seed+iteration+1))
        branches.update(choices);added.update(new_pairs);trace.append(row)
    return answer,{'trace':trace,'final_duals':dual_summary,'added_violated_pair_cuts':len(added),
                   'initial_omissions':len(omitted),'initial_distinct_axis_ties':ties}


def synthetic_control(deadline):
    p=np.array([[.5,.5,0.],[1.5,1.5,0.]])
    model={'n':2,'theta':0.,'origin':np.zeros(2),'core':np.array([],int),'upright':np.array([0,1]),
        'column':np.array([],int),'slot':np.array([],int),'u':np.array([]),'v':np.array([]),
        'x':p[:,0].copy(),'y':p[:,1].copy(),'gx':np.arange(2),'gy':np.arange(2)}
    corners=corner_pairs(p,True)
    q,report=solve(model,p,2.,0.,'baseline',corners,1,deadline)
    if (corners!={(0,1)} or q is None or report['trace'][0].get('violating_pairs')!=1
            or report['added_violated_pair_cuts']!=1 or base.sat(q)<-1e-8):
        raise ValueError('Provisional overlap/cut-repair control failed')
    return report


def run(args):
    started=time.monotonic();deadline=started+args.seconds-5
    signal.signal(signal.SIGALRM,lambda a,b:(_ for _ in()).throw(base.RunLimit()))
    signal.setitimer(signal.ITIMER_REAL,args.seconds-2)
    out=args.out;out.mkdir(parents=True,exist_ok=False)
    source_paths=[Path(__file__),Path(base.__file__),Path(sys.modules['period5_column_ablation'].__file__),
        base.ROOT/'experiments/compose_gadgets.py',base.ROOT/'experiments/extract_broad_active_frontier.py',
        base.ROOT/'scripts/validate_submission.py',base.ROOT/'scripts/score_official.py',base.ROOT/'research/official_metric_v17.py',
        base.ROOT/'experiments/fq_variant_campaign.py',base.ROOT/'experiments/fq_active_pilot.py']
    source=out/'source';source.mkdir()
    for path in source_paths:
        target=source/path.name;shutil.copyfile(path,target);target.chmod(0o444)
    baseline_sha=digest(args.baseline);official=json.loads(args.official.read_text())
    if not(official['valid']and official['sha256']==baseline_sha and official['invalid_count']==0):raise ValueError('Frozen portfolio proof mismatch')
    p=base.read_baseline(args.baseline)[299];initial=base.side(p);t=base.template(p)
    model=relaxed_template(t,p,True,range(22));upright_corners=corner_pairs(p,True);all_corners=corner_pairs(p,False)
    manifest={'baseline_sha256':baseline_sha,'official_report_sha256':digest(args.official),'reference_geometry_sha256':geometry_sha(p),
        'source_hashes':{str(path):digest(path)for path in source_paths},'seconds':args.seconds,'workers':1,'n':299,
        'position_variables':598,'source_upright_corner_pairs':len(upright_corners),'all_source_multiaxis_corner_pairs':len(all_corners),
        'theta_offsets':[0.,-.25,-.5,-1.,-2.],'policies':['baseline','prefer_y','checker','random_seed0..15',
            'omit_initial_upright_corners_then_exact_cuts','omit_all_initial_multiaxis_corners_then_exact_cuts'],
        'assurance':'Provisional relaxed sides are not geometry gains; only complete all-pair/wall and fresh full gates retain poses.'}
    atomic_json(out/'manifest.json',manifest);atomic_npz(out/'reference.npz',{'299':p})
    records=[];donors={};certificates={};best=initial;status='running'
    try:
        synthetic=synthetic_control(deadline)
        control,control_trace=solve(model,p,initial,0.,'baseline',set(),1,deadline)
        if control is None:raise ValueError('Matched baseline branch control failed')
        control=base.legalize(control,clearance=2e-9);_,certificate=certify_array(('299-control',control))
        if not certificate['valid']or abs(base.side(control)-initial)>1e-6:raise ValueError('Baseline full gate failed')
        atomic_json(out/'controls.json',{'passed':True,'synthetic_omission_and_cut_repair':synthetic,
            'baseline_side':base.side(control),'baseline_branch_diagnostics':control_trace,'full_certificate':certificate})
        print(json.dumps({'stage':'branch_controls_passed','upright_corner_pairs':len(upright_corners),
                          'all_multiaxis_corner_pairs':len(all_corners)}),flush=True)
        jobs=[]
        for offset in(0.,-.25,-.5,-1.,-2.):
            jobs.extend((offset,policy,set(),seed)for policy,seed in[('baseline',0),('prefer_y',0),('checker',0),
                *[('random',seed)for seed in range(16)]])
            jobs.extend([(offset,'baseline',upright_corners,800),(offset,'baseline',all_corners,900)])
        for index,(offset,policy,omitted,seed)in enumerate(jobs):
            if time.monotonic()>=deadline:raise base.RunLimit()
            q,diagnostic=solve(model,p,initial,offset,policy,omitted,seed,deadline)
            record={'theta_offset':offset,'policy':policy,'seed':seed,'omission_kind':
                    'all_multiaxis'if omitted is all_corners else'upright_diagonal'if omitted is upright_corners else'none',
                    'diagnostic':diagnostic,'status':'no_certified_geometry'}
            if q is not None:
                q=base.legalize(q,clearance=2e-9)
                if q is not None:
                    name='299__branch_'+geometry_sha(q)
                    if name in donors:proof=certificates[name];record['exact_certificate_reuse']=True
                    else:_,proof=certify_array((name,q))
                    if proof['valid']:
                        donors[name]=q;certificates[name]=proof;L=base.side(q);best=min(best,L)
                        record.update(status='certified',archive_key=name,geometry_sha256=geometry_sha(q),side=L,
                                      gain_vs_frozen=initial-L)
                        snapshots=out/'certified_snapshots';snapshots.mkdir(exist_ok=True)
                        target=snapshots/(geometry_sha(q)+'.npz')
                        if not target.exists():
                            atomic_npz(target,{name:q});target.chmod(0o444)
                            atomic_json(target.with_suffix('.json'),{'archive_key':name,'geometry_sha256':geometry_sha(q),
                                'archive_sha256':digest(target),'certificate':proof,'configuration':record})
                        atomic_npz(out/'donors.npz',donors);atomic_json(out/'certificates.json',certificates)
            records.append(record);atomic_json(out/'results.json',records)
            if index%10==0:print(json.dumps({'stage':'branch_search','completed':len(records),'seconds':time.monotonic()-started,
                                           'certified':len(donors),'best_side':best}),flush=True)
        status='complete'
    except base.RunLimit:status='hard_deadline'
    except Exception:status='failed';raise
    finally:
        signal.setitimer(signal.ITIMER_REAL,0)
        atomic_npz(out/'donors.npz',donors);atomic_json(out/'certificates.json',certificates);atomic_json(out/'results.json',records)
        summary={'status':status,'seconds':time.monotonic()-started,'limit_seconds':args.seconds,'completed':len(records),
            'certified_poses':len(donors),'initial_side':initial,'best_side':best,'strict_side_gain':max(0.,initial-best),
            'strict_full_score_gain':max(0.,initial-best)/math.sqrt(299),'manifest_sha256':digest(out/'manifest.json'),
            'donors_sha256':digest(out/'donors.npz'),'certificates_sha256':digest(out/'certificates.json'),
            'results_sha256':digest(out/'results.json'),'source_hashes_unchanged':all(digest(path)==value for path,value in manifest['source_hashes'].items()),
            'baseline_unchanged':digest(args.baseline)==baseline_sha,'scope':'Finite local separating-axis disjunction choices; no global impossibility proof.',
            'full_portfolio_merge_performed':False}
        atomic_json(out/'summary.json',summary);print(json.dumps({'stage':'branch_complete',**summary}),flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline',type=Path,default=base.ROOT/'artifacts/merged-omitted-donor-pair-v1.csv')
    parser.add_argument('--official',type=Path,default=base.ROOT/'artifacts/merged-omitted-donor-pair-v1-official.json')
    parser.add_argument('--out',type=Path,required=True);parser.add_argument('--seconds',type=float,default=590.)
    parser.add_argument('--child',action='store_true',help=argparse.SUPPRESS);args=parser.parse_args()
    if not 1<args.seconds<=595:raise ValueError('Require total outer bound below600seconds')
    if args.child:return run(args)
    child=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),*sys.argv[1:],'--child'],start_new_session=True)
    try:raise SystemExit(child.wait(timeout=args.seconds+3))
    except subprocess.TimeoutExpired:
        os.killpg(child.pid,signal.SIGKILL);child.wait(timeout=2)
        atomic_json(args.out/'supervisor_timeout.json',{'status':'outer_limit','seconds':args.seconds+3});raise SystemExit(2)


if __name__=='__main__':main()
