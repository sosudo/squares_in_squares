#!/usr/bin/env python3
"""Cheap335 occupancy-seed screen; outputs are optimizer inputs, not certificates."""
import argparse
import json
import math
import os
from pathlib import Path
import sys
import time
for name in('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='1'
import numpy as np
from scipy.spatial import cKDTree
from compose_gadgets import normalize,read_baseline,side,extents
from period5_branch_lp import data
from fq_variant_campaign import atomic_json,atomic_npz,geometry_sha
from fq_active_pilot import digest
from analyze_fq_full_structural import alignment

ROOT=Path(__file__).resolve().parents[1]


def compress_centres(p,target):
    q=normalize(p);length=side(q)
    q[:,:2]=(q[:,:2]-length/2)*(target/length)+target/2
    return q


def stresses(q,target):
    pairs=cKDTree(q[:,:2]).query_pairs(math.sqrt(2)+1e-8,output_type='ndarray')
    _,_,_,gap,_=data(q,pairs)
    loss=np.maximum(0.,-gap.max(1))**2
    extent=.5*(abs(np.cos(q[:,2]))+abs(np.sin(q[:,2])))
    walls=np.column_stack([q[:,0]-extent,q[:,1]-extent,
        target-q[:,0]-extent,target-q[:,1]-extent])
    wall_loss=(np.maximum(0.,-walls)**2).sum(1)
    score=wall_loss.copy();np.add.at(score,pairs[:,0],loss);np.add.at(score,pairs[:,1],loss)
    return pairs,loss,wall_loss,score


def select_deletions(p,target,count,policy):
    q=compress_centres(p,target);pairs,loss,wall_loss,score=stresses(q,target)
    deleted=[];active=np.ones(len(q),dtype=bool)
    if policy in('stress','forced_tilt'):
        tilted=abs((p[:,2]+np.pi/4)%(np.pi/2)-np.pi/4)>.018
        for step in range(count):
            eligible=active&tilted if policy=='forced_tilt'and step==0 else active
            chosen=int(np.argmax(np.where(eligible,score,-np.inf)));deleted.append(chosen);active[chosen]=False
            incident=np.flatnonzero((pairs==chosen).any(1))
            for edge in incident:
                i,j=pairs[edge];other=int(j if i==chosen else i)
                if active[other]:score[other]-=loss[edge]
    elif policy=='boundary_strip':
        lo,hi=extents(p);length=side(p)
        distances=np.column_stack([lo[:,0],lo[:,1],length-hi[:,0],length-hi[:,1]])
        eligible=distances.min(1)<.51
        anchor=int(np.argmax(np.where(eligible,score,-np.inf)));wall=int(np.argmin(distances[anchor]))
        ids=np.flatnonzero(distances[:,wall]<.51)
        ordered=sorted(map(int,ids),key=lambda i:(float(np.linalg.norm(p[i,:2]-p[anchor,:2])),-float(score[i]),i))
        deleted=ordered[:count]
        if len(deleted)!=count:raise ValueError('Not enough actual boundary-strip candidates')
    else:raise ValueError(policy)
    keep=np.delete(np.arange(len(p)),deleted);seed=q[keep]
    if len(seed)!=335 or not np.array_equal(seed[:,2],p[keep,2]):raise ValueError('Count/unit-angle identity failed')
    _,new_loss,new_wall,_=stresses(seed,target)
    return seed,dict(policy=policy,deleted_ids=deleted,deleted_units=p[deleted].tolist(),
        original_parent_side=side(p),nominal_target_box=target,actual_seed_envelope=side(seed),
        initial_squared_sat_wall_loss=float(loss.sum()+wall_loss.sum()),
        retained_squared_sat_wall_loss=float(new_loss.sum()+new_wall.sum()),
        pair_overlap_count=int((new_loss>1e-20).sum()),wall_violation_count=int((new_wall>1e-20).sum()),
        compression='Centres uniformly compressed; unit-square sizes and individual angles unchanged.',
        geometry_status='Raw optimizer input; intentional overlaps/wall violations allowed, no validity or gain claim.')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--portfolio',type=Path,default=ROOT/'artifacts/current-best-portfolio.json')
    parser.add_argument('--target',type=float,default=18.803)
    parser.add_argument('--out',type=Path,required=True);args=parser.parse_args();start=time.monotonic()
    args.out.mkdir(parents=True,exist_ok=False)
    pointer=json.loads(args.portfolio.read_text());source=Path(pointer['safe']['path']);official=Path(pointer['safe']['official_report'])
    if digest(source)!=pointer['safe']['sha256']or digest(official)!=pointer['safe']['official_report_sha256']:
        raise ValueError('Source portfolio changed')
    baseline=read_baseline(source);reference=normalize(baseline[335])
    parents={str(n):normalize(baseline[n])for n in(337,338,340)}
    seeds={};records=[]
    for n,p in parents.items():
        for policy in(('stress','boundary_strip','forced_tilt')if int(n)in(338,340)else('stress','boundary_strip')):
            q,record=select_deletions(p,args.target,len(p)-335,policy)
            key='335_from_'+n+'_'+policy;seeds[key]=q
            folded=(q[:,2]+np.pi/4)%(np.pi/2)-np.pi/4
            record.update(key=key,parent_n=int(n),parent_geometry_sha256=geometry_sha(p),
                seed_geometry_sha256=geometry_sha(q),tilted_count=int((abs(folded)>.018).sum()),
                alignment_to_incumbent=alignment(q,reference))
            records.append(record)
    atomic_npz(args.out/'parents.npz',parents);atomic_npz(args.out/'optimizer-seeds.npz',seeds)
    atomic_json(args.out/'screen.json',records)
    manifest=dict(status='cheap_screen_complete',seconds=time.monotonic()-start,seed_count=len(seeds),
        portfolio_csv=str(source),portfolio_csv_sha256=digest(source),official_report_sha256=digest(official),
        canonical335_side=side(reference),nominal_target=args.target,
        parents_sha256=digest(args.out/'parents.npz'),seeds_sha256=digest(args.out/'optimizer-seeds.npz'),
        screen_sha256=digest(args.out/'screen.json'),source_sha256=digest(__file__),
        native_trials_run=0,no_certificate_or_gain_claim=True)
    atomic_json(args.out/'manifest.json',manifest)
    print(json.dumps(manifest),flush=True)
    print(json.dumps([{k:r[k]for k in('key','deleted_ids','tilted_count','actual_seed_envelope',
        'retained_squared_sat_wall_loss','pair_overlap_count','alignment_to_incumbent')}for r in records]),flush=True)


if __name__=='__main__':main()
