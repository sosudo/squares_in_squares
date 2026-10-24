#!/usr/bin/env python3
"""Bounded sliding-dimer strip continuation with fixed-angle LP subproblems.

One CPU, no refill or GPU. LP feasibility is exploratory; only fresh full
independent interval and official raw/default-pandas gates certify a pose.
The dated public score table supplies targets, never coordinates.
"""
from __future__ import annotations
import argparse
import hashlib
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
for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[name]='1'
import numpy as np
from scipy.optimize import linprog
from scipy.spatial import cKDTree
from scipy.sparse import csr_matrix

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'experiments')]
from compose_gadgets import read_baseline,side,legalize
from extract_broad_active_frontier import certify_array
from fq_variant_campaign import atomic_json,atomic_npz,geometry_sha
from fq_active_pilot import digest


class RunLimit(Exception):pass


def sat(p):
    i,j=np.triu_indices(len(p),1);a=p[:,2];c,s=np.cos(a),np.sin(a)
    ux=np.column_stack((c[i],-s[i],c[j],-s[j]));uy=np.column_stack((s[i],c[i],s[j],c[j]))
    delta=p[j,:2]-p[i,:2]
    distance=np.max(abs(delta[:,0,None]*ux+delta[:,1,None]*uy),axis=1)
    radii=.5*(1+abs(np.cos(a[i]-a[j]))+abs(np.sin(a[i]-a[j])))
    return float(np.min(distance-radii))


def clusters(values,tolerance=1e-6):
    centers=[];labels=[]
    for value in values:
        hits=[i for i,center in enumerate(centers)if abs(value-center)<tolerance]
        if len(hits)>1:raise ValueError('Ambiguous grid line')
        if hits:labels.append(hits[0])
        else:labels.append(len(centers));centers.append(float(value))
    return np.array(labels),np.array(centers)


def template(p):
    folded=(p[:,2]+np.pi/4)%(np.pi/2)-np.pi/4
    core=np.flatnonzero(abs(folded)>.018);upright=np.flatnonzero(abs(folded)<=.018)
    if len(p)!=299 or len(core)!=43 or np.max(abs(folded[upright]))>1e-6:
        raise ValueError('Prototype requires the frozen43-core n299 scaffold')
    theta=float(np.median(folded[core]))
    if np.max(abs(folded[core]-theta))>1e-6:raise ValueError('Reference core is not one coherent angle')
    origin=p[core,:2].mean(0)
    rotation=np.array([[math.cos(theta),-math.sin(theta)],[math.sin(theta),math.cos(theta)]])
    uv=(p[core,:2]-origin)@rotation
    col=np.rint(uv[:,0]-uv[:,0].min()).astype(int)
    if np.max(abs(uv[:,0]-uv[:,0].min()-col))>1e-6:raise ValueError('Longitudinal unit-column control failed')
    columns=sorted(set(col));u=[];v=[];slot=np.zeros(len(core),dtype=int)
    for column in columns:
        ids=np.flatnonzero(col==column);u.append(float(np.mean(uv[ids,0])));v.append(float(uv[ids,1].min()))
        slot[ids]=np.rint(uv[ids,1]-v[-1]).astype(int)
        if (len(ids)not in(1,2)or len(set(slot[ids]))!=len(ids)
                or np.max(abs(uv[ids,1]-v[-1]-slot[ids]))>1e-6):
            raise ValueError('Exact dimer-count/spacing control failed')
    if len(columns)!=22 or sum(np.sum(col==j)==2 for j in columns)!=21:
        raise ValueError('Unexpected fixed-count strip topology')
    gx,x=clusters(p[upright,0]);gy,y=clusters(p[upright,1])
    return {'theta':theta,'origin':origin,'core':core,'upright':upright,'column':col,'slot':slot,
            'u':np.array(u),'v':np.array(v),'gx':gx,'gy':gy,'x':x,'y':y,'n':len(p)}


def mapping(t,angle_offsets,phase_offsets):
    n=t['n'];nx=len(t['x']);ny=len(t['y']);m=len(t['u']);nv=nx+ny+2*m
    C=np.zeros((2*n,nv));offset=np.zeros((n,2));angles=np.zeros(n)
    z=np.r_[t['x'],t['y'],np.column_stack((t['u'],t['v']+phase_offsets)).ravel()]
    for k,index in enumerate(t['upright']):C[2*index,t['gx'][k]]=1;C[2*index+1,nx+t['gy'][k]]=1
    for k,index in enumerate(t['core']):
        column=t['column'][k];a=t['theta']+angle_offsets[column];c,s=math.cos(a),math.sin(a)
        b=nx+ny+2*column;C[2*index:2*index+2,b:b+2]=[[c,-s],[s,c]]
        offset[index]=t['origin']+t['slot'][k]*np.array([-s,c]);angles[index]=a
    q=np.column_stack(((C@z).reshape(n,2)+offset,angles))
    return C,offset,angles,z,q


def solve(t,angle_offsets,phase_offsets,baseline,deadline,trust=.35):
    C,offset,angles,z,warm=mapping(t,angle_offsets,phase_offsets)
    n=t['n'];nv=len(z);e=.5*(abs(np.cos(angles))+abs(np.sin(angles)))
    # Each coordinate stays within trust of warm. A pair initially farther
    # than3 cannot overlap: sqrt2+2sqrt2*trust<3 for trust<=.5.
    if not 0<trust<=.5:raise ValueError('Unsafe sparse pair radius')
    pairs=cKDTree(warm[:,:2]).query_pairs(3.,output_type='ndarray')
    labels=np.full(n,-1);labels[t['core']]=t['column']
    internal=(labels[pairs[:,0]]>=0)&(labels[pairs[:,0]]==labels[pairs[:,1]])
    # Members of a rigid dimer touch at exactly one unit. Their fixed model
    # relation cannot carry an artificial positive LP clearance. Full SAT and
    # the final center-only legalizer still check every such pair.
    pairs=pairs[~internal];i,j=pairs.T
    bounds=[(value-.8,value+.8)for value in z]+[(math.sqrt(n),baseline+.12)]
    current=warm;records=[];answer=None
    for iteration in range(3):
        if deadline-time.monotonic()<1:break
        c,s=np.cos(angles),np.sin(angles)
        ux=np.column_stack((c[i],-s[i],c[j],-s[j]));uy=np.column_stack((s[i],c[i],s[j],c[j]))
        delta=current[j,:2]-current[i,:2];projections=delta[:,0,None]*ux+delta[:,1,None]*uy
        which=abs(projections).argmax(1);row=np.arange(len(i));sgn=np.where(projections[row,which]>=0,1.,-1.)
        vx=ux[row,which]*sgn;vy=uy[row,which]*sgn
        A=(C[2*i]-C[2*j])*vx[:,None]+(C[2*i+1]-C[2*j+1])*vy[:,None]
        r=.5*(1+abs(np.cos(angles[i]-angles[j]))+abs(np.sin(angles[i]-angles[j])))+5e-9
        b=-r-(offset[i,0]-offset[j,0])*vx-(offset[i,1]-offset[j,1])*vy
        A=np.column_stack((A,np.zeros(len(A))))
        extra=[];rhs=[]
        for index in range(n):
            for dim in(0,1):
                lower=np.r_[-C[2*index+dim],0.];upper=np.r_[C[2*index+dim],-1.]
                extra.extend((lower,upper));rhs.extend((offset[index,dim]-e[index]-5e-9,-offset[index,dim]-e[index]-5e-9))
                coeff=np.r_[C[2*index+dim],0.]
                extra.extend((coeff,-coeff));rhs.extend((warm[index,dim]+trust-offset[index,dim],
                                                        -warm[index,dim]+trust+offset[index,dim]))
        A=np.vstack((A,extra));b=np.r_[b,rhs];objective=np.zeros(nv+1);objective[-1]=1
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            fit=linprog(objective,A_ub=csr_matrix(A),b_ub=b,bounds=bounds,method='highs',
                options={'threads':1,'time_limit':min(2.,max(.1,deadline-time.monotonic()-.5)),
                         'primal_feasibility_tolerance':1e-9,'dual_feasibility_tolerance':1e-9})
        record={'iteration':iteration,'status':int(fit.status),'success':bool(fit.success)}
        if not fit.success:records.append(record);break
        q=np.column_stack(((C@fit.x[:nv]).reshape(n,2)+offset,angles))
        minimum=sat(q);wall=float(min((q[:,:2]-e[:,None]).min(),(fit.x[-1]-q[:,:2]-e[:,None]).min()))
        record.update(lp_side=float(fit.x[-1]),maximum_constraint_violation=float(max(0.,(A@fit.x-b).max())),
                      full_sat_minimum=minimum,wall_minimum=wall)
        records.append(record)
        if minimum< -2e-8 or wall< -2e-8:break
        answer=q;current=q
    return answer,records


def configurations(m):
    zero=np.zeros(m)
    yield {'kind':'global','degrees':0},zero,zero
    for degrees in(-3.,-2.,-1.,-.5,-.25,.25,.5,1.,2.,3.):
        yield {'kind':'global','degrees':degrees},np.full(m,math.radians(degrees)),zero
    for period in(4,5,6):
        for phase,amplitude in itertools.product((0.,math.pi/2,math.pi,3*math.pi/2),(.5,1.5,3.)):
            curve=np.sin(2*math.pi*np.arange(m)/period+phase)
            yield {'kind':'periodic_angle','period':period,'phase':phase,'degrees':amplitude},np.radians(amplitude)*curve,zero
        for phase,amplitude in itertools.product((0.,math.pi/2,math.pi,3*math.pi/2),(.10,.25,.45)):
            curve=np.sin(2*math.pi*np.arange(m)/period+phase)
            yield {'kind':'periodic_phase','period':period,'phase':phase,'amplitude':amplitude},zero,amplitude*curve
    for amplitude in(.5,1.5,3.,5.):
        curve=np.linspace(-1,1,m)
        yield {'kind':'linear_bend','degrees':amplitude},np.radians(amplitude)*curve,zero


def run(args):
    started=time.monotonic();deadline=started+args.seconds-3
    signal.signal(signal.SIGALRM,lambda a,b:(_ for _ in()).throw(RunLimit()))
    signal.setitimer(signal.ITIMER_REAL,args.seconds-1)
    out=args.out;out.mkdir(parents=True,exist_ok=False)
    frozen=out/'source-at-execution.py';shutil.copyfile(__file__,frozen);frozen.chmod(0o444)
    report=json.loads(args.official.read_text());baseline_sha=digest(args.baseline)
    if not(report['valid']and report['sha256']==baseline_sha and report['invalid_count']==0):raise ValueError('Complete baseline certificate mismatch')
    p=read_baseline(args.baseline)[299];initial=side(p);t=template(p)
    atomic_npz(out/'reference.npz',{'299':p})
    manifest={'baseline':str(args.baseline),'baseline_sha256':baseline_sha,'official_report_sha256':digest(args.official),
        'reference_sha256':digest(out/'reference.npz'),'source_sha256':digest(frozen),'seconds':args.seconds,'workers':1,
        'n':299,'fixed_count':len(p),'core_count':len(t['core']),'columns':len(t['u']),
        'dimers':21,'singleton_columns':1,'upright_x_lines':len(t['x']),'upright_y_lines':len(t['y']),
        'variables_before_container':len(t['x'])+len(t['y'])+2*len(t['u']),
        'initial_side':initial,'theta_degrees':math.degrees(t['theta']),
        'model':'Shared upright grid lines; per-dimer longitudinal/transverse phases; rigid dimer spacing; fixed per-column angle in each LP.'}
    atomic_json(out/'manifest.json',manifest)
    records=[];donors={};certificates={};best=initial;status='complete'
    try:
        C,offset,angles,z,reconstructed=mapping(t,np.zeros(22),np.zeros(22))
        error=float(np.max(abs(reconstructed[:,:2]-p[:,:2])))
        control,trace=solve(t,np.zeros(22),np.zeros(22),initial,deadline)
        if control is None:raise ValueError('Baseline LP positive control infeasible')
        control=legalize(control,clearance=2e-9)
        _,proof=certify_array(('299-control',control))
        duplicate=control.copy();duplicate[0]=duplicate[1]
        if not(proof['valid']and error<1e-6 and abs(side(control)-initial)<1e-6 and sat(duplicate)<-.9):
            raise ValueError('Fixed-count/SAT/LP positive or negative control failed')
        expanded={key:value.copy()if isinstance(value,np.ndarray)else value for key,value in t.items()}
        for key in('origin','x','y','u','v'):expanded[key]*=1.0005
        recovered,recovery_trace=solve(expanded,np.zeros(22),np.zeros(22),initial*1.0005,deadline)
        if recovered is None:raise ValueError('Dilated strip recovery control infeasible')
        recovered=legalize(recovered,clearance=2e-9)
        _,recovery_certificate=certify_array(('299-recovered',recovered))
        if not recovery_certificate['valid']or abs(side(recovered)-initial)>1e-6:
            raise ValueError('Dilated strip did not recover the known baseline')
        atomic_json(out/'controls.json',{'passed':True,'reconstruction_center_error':error,
            'baseline_lp_side':side(control),'initial_side':initial,'trace':trace,'full_certificate':proof,
            'duplicate_negative_sat_gap':sat(duplicate),'fixed_count':len(control),
            'dilated_recovery_side':side(recovered),'dilated_recovery_trace':recovery_trace,
            'dilated_recovery_certificate':recovery_certificate})
        print(json.dumps({'stage':'column_lp_controls_passed','variables':C.shape[1],'side':side(control)}),flush=True)
        for index,(config,angle,phase)in enumerate(configurations(22)):
            if time.monotonic()>=deadline-1:status='deadline';break
            q,trace=solve(t,angle,phase,initial,deadline)
            record={'configuration':config,'trace':trace,'status':'no_feasible_lp','elapsed_seconds':time.monotonic()-started}
            if q is not None:
                q=legalize(q,clearance=2e-9)
                if q is not None:
                    L=side(q);record.update(side=L,full_sat_minimum=sat(q),geometry_sha256=geometry_sha(q),status='exploratory_lp')
                    name='299__column_lp_'+geometry_sha(q)
                    if L<initial+.08 and name not in donors:
                        _,certificate=certify_array((name,q))
                        if certificate['valid']:
                            donors[name]=q;certificates[name]=certificate
                            record.update(status='certified',archive_key=name,gain_vs_frozen=initial-L)
                            best=min(best,L)
                            atomic_npz(out/'donors.npz',donors);atomic_json(out/'certificates.json',certificates)
            records.append(record);atomic_json(out/'results.json',records)
            if index%10==0:print(json.dumps({'stage':'column_lp','completed':len(records),'seconds':time.monotonic()-started,'best_side':best,'certified':len(donors)}),flush=True)
    except RunLimit:status='hard_deadline'
    except Exception:
        status='failed';raise
    finally:
        signal.setitimer(signal.ITIMER_REAL,0)
        atomic_npz(out/'donors.npz',donors);atomic_json(out/'certificates.json',certificates);atomic_json(out/'results.json',records)
        summary={'status':status,'seconds':time.monotonic()-started,'limit_seconds':args.seconds,
            'configurations_completed':len(records),'certified_poses':len(donors),'initial_side':initial,'best_side':best,
            'strict_side_gain':max(0.,initial-best),'strict_full_score_gain':max(0.,initial-best)/math.sqrt(299),
            'manifest_sha256':digest(out/'manifest.json'),'donors_sha256':digest(out/'donors.npz'),
            'certificates_sha256':digest(out/'certificates.json'),'results_sha256':digest(out/'results.json'),
            'source_unchanged':digest(__file__)==digest(frozen),'baseline_unchanged':digest(args.baseline)==baseline_sha,
            'full_portfolio_merge_performed':False}
        atomic_json(out/'summary.json',summary);print(json.dumps({'stage':'column_lp_complete',**summary}),flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline',type=Path,default=ROOT/'artifacts/merged-omitted-donor-pair-v1.csv')
    parser.add_argument('--official',type=Path,default=ROOT/'artifacts/merged-omitted-donor-pair-v1-official.json')
    parser.add_argument('--out',type=Path,required=True);parser.add_argument('--seconds',type=float,default=590.)
    parser.add_argument('--child',action='store_true',help=argparse.SUPPRESS);args=parser.parse_args()
    if not 1<args.seconds<=595:raise ValueError('Require an outer total below600seconds')
    if args.child:return run(args)
    process=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),*sys.argv[1:],'--child'],start_new_session=True)
    try:raise SystemExit(process.wait(timeout=args.seconds+3))
    except subprocess.TimeoutExpired:
        os.killpg(process.pid,signal.SIGKILL);process.wait(timeout=2)
        atomic_json(args.out/'supervisor_timeout.json',{'status':'outer_limit','seconds':args.seconds+3})
        raise SystemExit(2)


if __name__=='__main__':main()
