#!/usr/bin/env python3
"""Conservative angle-cell screen followed by bounded rigid-block composition.

Internal centers and angles undergo one coherent rotation, without deformation.
The angular screen proves only exclusions inside its stated angle/translation
boxes. Surviving cells are unresolved, not feasible-packing claims.
"""
from __future__ import annotations
import os
for _v in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[_v]='1'
import argparse
import itertools
import json
import math
from pathlib import Path
import shutil
import time
import numpy as np
from compose_gadgets import extents,side,legalize
from fractional_interface_search import solve_phases
from fq_capacity_probe import full_certificate
from fq_variant_campaign import atomic_json,atomic_npz,geometry_sha
from fq_active_pilot import digest

ROOT=Path(__file__).resolve().parents[1]


def rotate(p,angle):
    q=p.copy();center=p[:,:2].mean(0);c,s=math.cos(angle),math.sin(angle)
    q[:,:2]=(p[:,:2]-center)@np.array([[c,s],[-s,c]])+center
    q[:,2]+=angle
    return q


def rotation_cells(p,anchor,L,midpoints,halfwidth,translation=.25):
    center=p[:,:2].mean(0)
    # A square's vertices are <=sqrt(1/2) from its center. This radius
    # encloses every original vertex about the fixed rotation center.
    point_radii=np.linalg.norm(p[:,:2]-center,axis=1)
    vertex_radius=float(point_radii.max()+math.sqrt(.5))
    poses=np.array([rotate(p,float(a))for a in midpoints])
    extent=.5*(abs(np.cos(poses[:,:,2]))+abs(np.sin(poses[:,:,2])))
    lower=(poses[:,:,:2]-extent[:,:,None]).min(1)+anchor
    upper=(poses[:,:,:2]+extent[:,:,None]).max(1)+anchor
    # Every vertex moves by <=R*halfwidth. Relax each wall by this amount,
    # so the resulting translation box contains every feasible angle in cell.
    allowance=vertex_radius*halfwidth+1e-12
    lo=np.maximum(-translation,-lower-allowance)
    hi=np.minimum(translation,L-upper+allowance)
    valid=(lo<=hi).all(1)
    return dict(poses=poses,lo=lo,hi=hi,valid=valid,radii=point_radii,
                midpoint=(lo+hi)/2,half=(hi-lo)/2,anchor=np.asarray(anchor))


def pair_gap_upper(A,B,i,j,halfwidth):
    """Upper bound on the maximum SAT gap throughout every angle-cell pair."""
    p=A['poses'][:,i];q=B['poses'][:,j]
    x=p[:,:2]+A['midpoint']+A['anchor'];y=q[:,:2]+B['midpoint']+B['anchor']
    delta=y[None,:,:]-x[:,None,:]
    half=A['half'][:,None,:]+B['half'][None,:,:]
    ai=p[:,2,None];aj=q[None,:,2]
    radius=.5*(1+abs(np.cos(ai-aj))+abs(np.sin(ai-aj)))
    best=np.full(radius.shape,-np.inf)
    for angle in (np.broadcast_to(ai,radius.shape),np.broadcast_to(ai+math.pi/2,radius.shape),
                  np.broadcast_to(aj,radius.shape),np.broadcast_to(aj+math.pi/2,radius.shape)):
        nx,ny=np.cos(angle),np.sin(angle)
        projection=abs(delta[:,:,0]*nx+delta[:,:,1]*ny)
        projection+=abs(nx)*half[:,:,0]+abs(ny)*half[:,:,1]
        best=np.maximum(best,projection-radius)
    rho=(A['radii'][i]+B['radii'][j])*halfwidth
    # Center movement, rotation of every candidate SAT normal, and change of
    # support radius are all included. |d radius / d relative angle|<=1.
    distance=np.linalg.norm(delta,axis=2)+np.linalg.norm(half,axis=2)
    return best+rho+(distance+rho)*halfwidth+2*halfwidth+1e-10


def witnesses(p,q,anchorA,anchorB,L,count=6):
    A=rotation_cells(p,anchorA,L,np.array([0.]),0.)
    B=rotation_cells(q,anchorB,L,np.array([0.]),0.)
    x=p[:,:2]+A['midpoint'][0]+anchorA;y=q[:,:2]+B['midpoint'][0]+anchorB
    d=y[None,:,:]-x[:,None,:];half=A['half'][0]+B['half'][0]
    ai=p[:,2,None];aj=q[None,:,2]
    r=.5*(1+abs(np.cos(ai-aj))+abs(np.sin(ai-aj)))
    gap=np.full(r.shape,-np.inf)
    for a in (ai,ai+math.pi/2,aj,aj+math.pi/2):
        nx,ny=np.cos(a),np.sin(a)
        gap=np.maximum(gap,abs(d[:,:,0]*nx+d[:,:,1]*ny)+abs(nx)*half[0]+abs(ny)*half[1]-r)
    ids=np.argsort(gap.ravel(),kind='stable')[:count]
    return [tuple(map(int,np.unravel_index(k,gap.shape)))for k in ids]


def controls():
    p=np.array([[.5,.5,0.],[1.5,.5,.2],[.6,2.1,-.1]])
    q=rotate(p,.07)
    np.testing.assert_allclose(np.linalg.norm(p[:,None,:2]-p[None,:,:2],axis=2),
                               np.linalg.norm(q[:,None,:2]-q[None,:,:2],axis=2),atol=2e-15)
    assert np.max(abs((q[:,2]-p[:,2])-.07))<1e-15
    # Sample all signs near a cell's endpoints; the angular envelope must
    # enclose the exact maximized single-pair SAT gap at each sampled angle.
    a=np.array([0.,.02]);h=.001
    A=rotation_cells(p,np.array([0.,2.]),7.,a,h)
    B=rotation_cells(p,np.array([2.,0.]),7.,a,h)
    bound=pair_gap_upper(A,B,1,2,h)
    for da,db in itertools.product((-h,0.,h),repeat=2):
        aa=rotation_cells(p,np.array([0.,2.]),7.,a+da,0.)
        bb=rotation_cells(p,np.array([2.,0.]),7.,a+db,0.)
        assert np.all(pair_gap_upper(aa,bb,1,2,0.)<=bound+1e-9)
    # Full composition positive/negative controls use actual rotated motifs.
    L=2+math.sqrt(.5)
    seed=legalize(np.array([[.5,.5,0.],[.5,L-.5,0.],[L-.5,.5,0.],
                           [L-.5,L-.5,0.],[L/2,L/2,np.pi/4]]))
    first=dict(w=2,h=2,d=1,f=0.,pose=rotate(seed,.01))
    second=dict(w=2,h=2,d=1,f=0.,pose=rotate(seed,-.01))
    info,positive=solve_phases(first,second,5,.9,seconds=3,domain='global',mode=1)
    assert positive is not None
    proof=full_certificate(positive);assert proof['valid']
    fail,negative=solve_phases(first,second,4,.70,seconds=3,domain='global')
    assert negative is None
    return dict(valid=True,rigid_distance_control=True,angular_bound_sample_control=True,
                positive=info,positive_certificate=proof,negative=fail)


def run(args):
    start=time.monotonic();out=args.out;out.mkdir(parents=True,exist_ok=False)
    control=controls();atomic_json(out/'controls.json',control)
    old=ROOT/'artifacts/fractional-interface-v1';old_manifest=json.loads((old/'manifest.json').read_text())
    archive=old/'input-options.npz';metadata=old/'input-options.json'
    assert digest(archive)==old_manifest['input_options_sha256']
    assert digest(metadata)==old_manifest['input_metadata_sha256']
    pointer_path=ROOT/'artifacts/current-best-portfolio.json';pointer=json.loads(pointer_path.read_text())
    official=Path(pointer['raw']['official_report']);report=json.loads(official.read_text())
    assert report['valid']and report['sha256']==pointer['raw']['sha256']==digest(Path(pointer['raw']['path']))
    sides={r['n']:float(r['side'])for r in report['results']}
    options=json.loads(metadata.read_text());z=np.load(archive)
    sources=[Path(__file__),ROOT/'experiments/fractional_interface_search.py',ROOT/'experiments/compose_gadgets.py',
        ROOT/'experiments/fq_capacity_probe.py',ROOT/'experiments/extract_broad_active_frontier.py',
        ROOT/'experiments/fq_active_pilot.py',ROOT/'experiments/fq_variant_campaign.py',
        ROOT/'scripts/validate_submission.py',ROOT/'scripts/score_official.py',ROOT/'research/official_metric_v17.py']
    source_dir=out/'sources';source_dir.mkdir()
    for path in sources:shutil.copyfile(path,source_dir/path.name)
    manifest=dict(pointer=pointer,pointer_sha256=digest(pointer_path),official_sha256=digest(official),
        input_archive=str(archive),input_archive_sha256=digest(archive),metadata_sha256=digest(metadata),
        source_sha256=digest(Path(__file__)),source_hashes={str(p):digest(p)for p in sources},
        translation_box=[-.25,.25],angle_box=[-.1,.1],
        angle_cells=100,halfwidth=.001,workers=1,prototype_limit_seconds=args.seconds,
        scope='Continuous angle-cell bounds cover each finite source pair inside explicit global translation boxes; '
              'unresolved cells are not feasible claims. Optional MILP checks only selected cell midpoints.')
    atomic_json(out/'manifest.json',manifest)
    mid=np.linspace(-.099,.099,100);half=.001;records=[];survivors=[];best_bounds=[]
    for n,k,types in ((498,22,((5,17,7),(17,5,7))),(814,28,((7,21,15),(21,7,15)))):
        L=sides[n]-2e-7
        for order in (types,types[::-1]):
            left=[dict(r,pose=z[r['array_key']])for r in options if(r['w'],r['h'],r['d'])==order[0]]
            right=[dict(r,pose=z[r['array_key']])for r in options if(r['w'],r['h'],r['d'])==order[1]]
            for a,b in itertools.product(left,right):
                anchorA=np.array([0,b['h']]);anchorB=np.array([a['w'],0])
                A=rotation_cells(a['pose'],anchorA,L,mid,half);B=rotation_cells(b['pose'],anchorB,L,mid,half)
                mask=A['valid'][:,None]&B['valid'][None,:];initial=int(mask.sum())
                witness=witnesses(a['pose'],b['pose'],anchorA,anchorB,L)
                bound=np.full(mask.shape,np.inf)
                for i,j in witness:
                    bound=np.minimum(bound,pair_gap_upper(A,B,i,j,half));mask&=bound>=0
                    if not mask.any():break
                row=dict(n=n,k=k,first_uid=a['uid'],second_uid=b['uid'],wall_possible_cells=initial,
                         unresolved_cells=int(mask.sum()),witnesses=witness,
                         maximum_surviving_witness_bound=float(bound[A['valid'][:,None]&B['valid'][None,:]].max())if initial else None)
                records.append(row)
                if mask.any():
                    indices=np.argwhere(mask)
                    chosen=sorted(indices,key=lambda ab:abs(mid[ab[0]])+abs(mid[ab[1]]))[:6]
                    for ia,ib in chosen:survivors.append((a,b,k,n,float(mid[ia]),float(mid[ib]),float(bound[ia,ib])))
        print(json.dumps({'stage':'angle_screen','n':n,'pairs':sum(r['n']==n for r in records),
                          'unresolved_pairs':sum(r['n']==n and r['unresolved_cells']>0 for r in records)}),flush=True)
    screen=dict(seconds=time.monotonic()-start,source_pairs=len(records),angle_cell_pairs=len(records)*10000,
                wall_possible_cells=sum(r['wall_possible_cells']for r in records),
                unresolved_cells=sum(r['unresolved_cells']for r in records),
                records=records,rigid_rotations_only=True,certified_improvements=0)
    atomic_json(out/'screen.json',screen)
    trials=[];candidates={};deadline=time.monotonic()+args.seconds
    # Each trial retains every unit square and uses complete walls plus the
    # translation solver's proven worst-displacement neighbor set.
    for a,b,k,n,ta,tb,bound in survivors:
        if time.monotonic()>deadline-4:break
        aa=dict(a,pose=rotate(a['pose'],ta),f=0.);bb=dict(b,pose=rotate(b['pose'],tb),f=0.)
        info,p=solve_phases(aa,bb,k,sides[n]-k-2e-7,seconds=min(.5,deadline-time.monotonic()-3),domain='global')
        row=dict(n=n,first_uid=a['uid'],second_uid=b['uid'],angles=[ta,tb],angular_witness_bound=bound,result=info)
        if p is not None:
            certificate=full_certificate(p);row['certificate']=certificate
            if certificate['valid']and float(certificate['independent_raw']['side_upper'])<sides[n]-1e-7:
                candidates[str(n)]=dict(side=certificate['independent_raw']['side_upper'],
                    squares=[[f'{v:.17g}'for v in line]for line in p],source='Rigid donor rotations and continuous translations',provenance=row)
                sides[n]=float(certificate['independent_raw']['side_upper'])
        trials.append(row);atomic_json(out/'trials.json',trials);atomic_json(out/'candidates.json',candidates)
    atomic_json(out/'candidates.json',candidates)
    summary=dict(screen_seconds=screen['seconds'],total_seconds=time.monotonic()-start,
        angle_cell_pairs=screen['angle_cell_pairs'],unresolved_angle_cells=screen['unresolved_cells'],
        midpoint_trials=len(trials),available_selected_midpoints=len(survivors),certified_improvements=len(candidates),
        manifest_sha256=digest(out/'manifest.json'),screen_sha256=digest(out/'screen.json'),
        candidates_sha256=digest(out/'candidates.json'),scope=manifest['scope'])
    atomic_json(out/'summary.json',summary);print(json.dumps(summary),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--seconds',type=float,default=280.);args=parser.parse_args()
    assert 0<=args.seconds<=300
    run(args)
