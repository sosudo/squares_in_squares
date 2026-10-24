#!/usr/bin/env python3
"""Finite direct 2D refill around changed43-square n299 tilted cores.

No row-capacity eligibility surrogate is called. Candidate hints are unforced
positions and are screened anew. Only fixed-count, wall-safe, full-certified
unit-square arrays are retained; finite MIS failures are not global bounds.
"""
from __future__ import annotations
import argparse
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

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'experiments')]
import refill_search as refill
from compose_gadgets import read_baseline,normalize,side,legalize
from extract_broad_active_frontier import certify_array
from fq_variant_campaign import atomic_json,atomic_npz,geometry_sha
from fq_active_pilot import digest
from period5_branch_lp import data,violations


class TrialLimit(Exception):pass


def templates():
    result=[{'global_angle_degrees':a,'central_transverse_shift':v,'central_cant_degrees':0.}
            for a in(0.,-.25,-.5,-1.)for v in(-.06,0.,.06)]
    result.extend({'global_angle_degrees':-.5,'central_transverse_shift':0.,'central_cant_degrees':a}for a in(-1.,1.))
    return result


def changed_core(original,central,spec,depth):
    q=original.copy();q[:,:2]-=depth/2
    q[:,2]+=math.radians(spec['global_angle_degrees'])
    theta=float(np.median(original[:,2]));normal=np.array([-math.sin(theta),math.cos(theta)])
    q[central,:2]+=spec['central_transverse_shift']*normal
    a=math.radians(spec['central_cant_degrees'])
    if a:
        center=q[central,:2].mean(0);c,s=math.cos(a),math.sin(a)
        q[central,:2]=(q[central,:2]-center)@np.array([[c,s],[-s,c]])+center
        q[central,2]+=a
    return q


def core_lp(warm,L,deadline):
    """Fixed-angle core-only feasibility with bounded L1 center movement."""
    n=len(warm);m=2*n;angles=warm[:,2];extent=.5*(abs(np.cos(angles))+abs(np.sin(angles)))
    pairs=np.array(list(zip(*np.triu_indices(n,1))),dtype=int)
    ux,uy,projection,gaps,radii=data(warm,pairs)
    A=[];b=[]
    for k,(i,j)in enumerate(pairs):
        axis=int(np.argmax(gaps[k]));sg=1 if projection[k,axis]>=0 else -1
        vx,vy=ux[k,axis]*sg,uy[k,axis]*sg;row=np.zeros(2*m)
        row[2*i:2*i+2]=[vx,vy];row[2*j:2*j+2]=[-vx,-vy]
        A.append(row);b.append(-radii[k]-5e-10)
    target=warm[:,:2].ravel();bounds=[]
    for k,value in enumerate(target):
        e=extent[k//2]+5e-10
        lower=max(value-.10,e);upper=min(value+.10,L-e)
        if lower>upper:return None,{'status':'wall_trust_infeasible'}
        bounds.append((lower,upper))
        row=np.zeros(2*m);row[k]=1;row[m+k]=-1
        A.extend((row,np.r_[-row[:m],row[m:]]));b.extend((value,-value))
    bounds.extend([(0,.10)]*m);objective=np.r_[np.zeros(m),np.ones(m)]
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        fit=linprog(objective,A_ub=csr_matrix(np.array(A)),b_ub=np.array(b),bounds=bounds,method='highs',
            options={'threads':1,'time_limit':min(.7,max(.01,deadline-time.monotonic())),
                     'primal_feasibility_tolerance':1e-9,'dual_feasibility_tolerance':1e-9})
    info={'status':int(fit.status),'success':bool(fit.success)}
    if not fit.success:return None,info
    q=warm.copy();q[:,:2]=fit.x[:m].reshape(n,2)
    bad,gap=violations(q,tolerance=1e-9)
    wall=float(min((q[:,:2]-extent[:,None]).min(),(L-q[:,:2]-extent[:,None]).min()))
    info.update(core_count=n,maximum_center_motion=float(np.max(abs(q[:,:2]-warm[:,:2]))),
                core_sat_minimum=gap,wall_minimum=wall,violating_pairs=len(bad))
    return(q if not bad and wall>=-1e-9 else None),info


def candidates(core,L,upright_hints,depth):
    generated=refill.generate_candidates(L,L,core,None,4,1e-13,0.)
    # Preserve actual source positions before coalescing numerical near-copies.
    # Hints for each wall phase are proposals only and all pass the same filters.
    hints=np.vstack([upright_hints[:,:2]-[dx,dy]for dx,dy in((0,0),(depth,0),(0,depth),(depth,depth))])
    xy=np.vstack((hints,generated))
    xy=xy[(xy>=.5).all(1)&(xy<=L-.5).all(1)]
    xy=xy[refill.sat_gaps(xy,core)>=0.]
    _,indices=np.unique(np.round(xy,12),axis=0,return_index=True)
    return xy[np.sort(indices)],len(generated)


def direct_refill(core,L,upright_hints,depth):
    xy,generated=candidates(core,L,upright_hints,depth)
    if len(xy)>12000:return None,{'status':'finite_candidate_budget','candidates':len(xy)}
    chosen,info=refill.maximum_independent_set(refill.conflict_graph(xy,margin=0.),time_limit=.2)
    up=np.column_stack((xy[chosen],np.zeros(len(chosen))))
    return up,{**info,'candidates':len(xy),'generated_candidates':generated,'selected':len(up),
               'conflict_margin':0.,'candidate_generation_margin':1e-13,'row_gate_called':False}


def gate(q):
    name=str(len(q))+'__direct_refill_'+geometry_sha(q)
    _,raw=certify_array((name,q))
    if raw['valid']:return q,{'raw':raw,'clearance_repair_applied':False,'actual':raw}
    fixed=legalize(q,clearance=2e-9)
    if fixed is None:return None,{'raw':raw,'clearance_repair_failed':True}
    _,certificate=certify_array((name,fixed))
    return(fixed if certificate['valid']else None),{'raw':raw,'clearance_repair_applied':True,
        'actual':certificate,'clearance_side_increase':side(fixed)-side(q)}


def run(args):
    started=time.monotonic();deadline=started+args.seconds-5
    signal.signal(signal.SIGALRM,lambda a,b:(_ for _ in()).throw(TrialLimit()))
    out=args.out;out.mkdir(parents=True,exist_ok=False)
    pointer=json.loads(args.portfolio.read_text());source=Path(pointer['safe']['path'])
    if digest(source)!=pointer['safe']['sha256']:raise ValueError('Certified source portfolio changed')
    official=Path(pointer['safe']['official_report'])
    if digest(official)!=pointer['safe']['official_report_sha256']:raise ValueError('Source official proof changed')
    official_data=json.loads(official.read_text())
    if not(official_data['sha256']==pointer['safe']['sha256'] and official_data['valid']
           and official_data['invalid_count']==0 and official_data['puzzles']==1000):
        raise ValueError('Complete official source certificate mismatch')
    poses=read_baseline(source);p=normalize(poses[299]);L0=side(p)
    mask=abs((p[:,2]+np.pi/4)%(np.pi/2)-np.pi/4)>.018
    core=p[mask];upright=p[~mask];core_ids=np.flatnonzero(mask)
    if len(core)!=43 or len(upright)!=256:raise ValueError('Reference count/type mismatch')
    central=np.array([int(np.flatnonzero(core_ids==i)[0])for i in(276,277)])
    paths=[Path(__file__),ROOT/'experiments/refill_search.py',ROOT/'experiments/compose_gadgets.py',
        ROOT/'experiments/extract_broad_active_frontier.py',ROOT/'experiments/period5_branch_lp.py',
        ROOT/'scripts/validate_submission.py',ROOT/'scripts/score_official.py',ROOT/'research/official_metric_v17.py',
        ROOT/'experiments/fq_variant_campaign.py',ROOT/'experiments/fq_active_pilot.py',
        ROOT/'experiments/period5_column_lp.py',ROOT/'experiments/period5_column_ablation.py']
    frozen=out/'source';frozen.mkdir()
    for path in paths:
        target=frozen/path.name;shutil.copyfile(path,target);target.chmod(0o444)
    original_milp=refill.milp
    def one_thread(*a,**kw):
        options=dict(kw.get('options')or{});options['threads']=1;kw['options']=options
        with warnings.catch_warnings():warnings.simplefilter('ignore');return original_milp(*a,**kw)
    refill.milp=one_thread
    manifest={'portfolio_pointer_sha256':digest(args.portfolio),'source_csv':str(source),'source_csv_sha256':digest(source),
        'source_official_report_sha256':digest(official),'reference_geometry_sha256':geometry_sha(p),
        'source_hashes':{str(path):digest(path)for path in paths},'seconds':args.seconds,'workers':1,
        'source_side':L0,'source_core_count':43,'required_uprights':256,'central_source_ids':[276,277],
        'central_core_indices':central.tolist(),'templates':templates(),'target_reductions':[.002,.010,.020],
        'planned_trials':42,'per_trial_seconds':6.,'row_surrogate_used':False,
        'counts':'Exactly43 tilted; choose256 uprights for299. Preserve any larger actually found count separately with full gates.',
        'scope':'Finite candidate MILP/MIS capacity only; failure is not continuous infeasibility.'}
    atomic_json(out/'manifest.json',manifest);atomic_npz(out/'reference.npz',{'299':p})
    records=[];donors={};proofs={};best=L0;status='running'
    def retain(q,certificate,origin):
        nonlocal best
        n=len(q);name=str(n)+'__direct_refill_'+geometry_sha(q)
        donors[name]=q;proofs[name]=certificate
        if n==299:best=min(best,side(q))
        snapshots=out/'certified_snapshots';snapshots.mkdir(exist_ok=True)
        path=snapshots/(geometry_sha(q)+'.npz')
        if not path.exists():
            atomic_npz(path,{name:q});path.chmod(0o444)
            atomic_json(path.with_suffix('.json'),{'archive_key':name,'n':n,'geometry_sha256':geometry_sha(q),
                'archive_sha256':digest(path),'certificate':certificate,'origin':origin})
        atomic_npz(out/'donors.npz',donors);atomic_json(out/'certificates.json',proofs)
        return name
    try:
        signal.setitimer(signal.ITIMER_REAL,min(12.,max(.01,deadline-time.monotonic())))
        rebuilt,info=direct_refill(core,L0,upright,0.)
        if rebuilt is None or len(rebuilt)<256:raise ValueError('Original-core direct2D refill control failed')
        control=np.vstack((core,rebuilt[:256]));assert len(control)==299
        control,certificate=gate(control)
        if control is None or side(control)>L0+1e-6:raise ValueError('Original-core full gate failed')
        control_name=retain(control,certificate,{'stage':'original_core_control'})
        atomic_json(out/'controls.json',{'passed':True,'required':299,'source_side':L0,'actual_side':side(control),
            'archive_key':control_name,'refill':info,'certificate':certificate})
        signal.setitimer(signal.ITIMER_REAL,0)
        print(json.dumps({'stage':'direct_refill_control_passed','count':299,'actual_side':side(control)}),flush=True)
        for index,(spec,depth)in enumerate((spec,depth)for depth in(.002,.010,.020)for spec in templates()):
            if time.monotonic()>=deadline:status='deadline';break
            began=time.monotonic();record={'template':spec,'target_reduction':depth,'nominal_target_side':L0-depth,
                                            'core_count_required':43,'upright_count_required':256}
            signal.setitimer(signal.ITIMER_REAL,min(6.,max(.01,deadline-time.monotonic())))
            try:
                warm=changed_core(core,central,spec,depth);actual,core_info=core_lp(warm,L0-depth,deadline)
                record['core_lp']=core_info
                if actual is None:record['status']='core_lp_infeasible_or_budget'
                else:
                    assert actual.shape==(43,3)
                    up,fill=direct_refill(actual,L0-depth,upright,depth);record['refill']=fill
                    if up is None:record['status']='candidate_budget'
                    elif len(up)<256:record.update(status='finite_refill_shortfall',uprights_found=len(up))
                    else:
                        counts=[256]+([len(up)]if len(up)>256 else[])
                        record['retained']=[]
                        for count in counts:
                            candidate=np.vstack((actual,up[:count]));assert len(candidate)==43+count
                            q,certificate=gate(candidate)
                            if q is not None:
                                name=retain(q,certificate,{'stage':'changed_core_refill','configuration':record,'template':spec})
                                record['retained'].append({'archive_key':name,'n':len(q),'actual_certified_side':side(q),
                                    'nominal_target_excess':side(q)-(L0-depth),'gain_vs_frozen_case':side(poses[len(q)])-side(q)})
                        record['status']='certified'if record['retained']else'full_gate_rejected'
            except TrialLimit:record['status']='trial_timeout'
            finally:signal.setitimer(signal.ITIMER_REAL,0)
            record['seconds']=time.monotonic()-began;records.append(record);atomic_json(out/'results.json',records)
            print(json.dumps({'stage':'direct_refill_trial','completed':len(records),'status':record['status'],
                'uprights_found':record.get('uprights_found',record.get('refill',{}).get('selected')),
                'seconds':record['seconds'],'best_side':best}),flush=True)
        if status=='running':status='complete'
    except Exception:status='failed';raise
    finally:
        signal.setitimer(signal.ITIMER_REAL,0);refill.milp=original_milp
        atomic_npz(out/'donors.npz',donors);atomic_json(out/'certificates.json',proofs);atomic_json(out/'results.json',records)
        unchanged=all(digest(path)==value for path,value in manifest['source_hashes'].items())and digest(source)==manifest['source_csv_sha256']
        summary={'status':status if unchanged else'source_changed_quarantine','seconds':time.monotonic()-started,
            'limit_seconds':args.seconds,'trials_completed':len(records),'planned_trials':42,'certified_geometries':len(donors),
            'initial_side':L0,'best_299_side':best,'strict_299_side_gain':max(0.,L0-best),
            'strict_299_score_gain':max(0.,L0-best)/math.sqrt(299),'row_surrogate_called':False,
            'source_hashes_unchanged':unchanged,'manifest_sha256':digest(out/'manifest.json'),
            'donors_sha256':digest(out/'donors.npz'),'certificates_sha256':digest(out/'certificates.json'),
            'results_sha256':digest(out/'results.json'),'full_portfolio_merge_performed':False}
        atomic_json(out/'summary.json',summary);print(json.dumps({'stage':'direct_refill_complete',**summary}),flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--portfolio',type=Path,default=ROOT/'artifacts/current-best-portfolio.json')
    parser.add_argument('--out',type=Path,required=True);parser.add_argument('--seconds',type=float,default=290.)
    parser.add_argument('--child',action='store_true',help=argparse.SUPPRESS);args=parser.parse_args()
    if not 1<args.seconds<=295:raise ValueError('Require total outer bound below300seconds')
    if args.child:return run(args)
    child=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),*sys.argv[1:],'--child'],start_new_session=True)
    try:raise SystemExit(child.wait(timeout=args.seconds+3))
    except subprocess.TimeoutExpired:
        os.killpg(child.pid,signal.SIGKILL);child.wait(timeout=2)
        atomic_json(args.out/'supervisor_timeout.json',{'status':'outer_limit','seconds':args.seconds+3});raise SystemExit(2)


if __name__=='__main__':main()
