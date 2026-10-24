#!/usr/bin/env python3
"""Freeze least-overlapping full-count junction starts; these are NOT packings."""
import argparse
import json
import math
import os
from pathlib import Path
import time
for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='1'
import numpy as np
from scipy.spatial import cKDTree
from fractional_interface_search import symbolic_pair
from compose_gadgets import extents
from scalar_sat_staircase import sha,array_sha,atom


def overlap_edges(p,q=None):
    if q is None:
        pairs=cKDTree(p[:,:2]).query_pairs(1.5,output_type='ndarray')
        if not len(pairs):return [],[]
        a,b=p[pairs[:,0]],p[pairs[:,1]]
    else:
        neighbors=cKDTree(p[:,:2]).query_ball_tree(cKDTree(q[:,:2]),1.5)
        pairs=np.array([(i,j)for i,js in enumerate(neighbors)for j in js],dtype=int).reshape(-1,2)
        if not len(pairs):return [],[]
        a,b=p[pairs[:,0]],q[pairs[:,1]]
    delta=b[:,:2]-a[:,:2]
    projection=np.maximum.reduce([abs(delta[:,0]*np.cos(t)+delta[:,1]*np.sin(t))
        for t in (a[:,2],a[:,2]+math.pi/2,b[:,2],b[:,2]+math.pi/2)])
    radius=.5*(1+abs(np.cos(a[:,2]-b[:,2]))+abs(np.sin(a[:,2]-b[:,2])))
    gaps=projection-radius;bad=gaps< -1e-8
    return pairs[bad].tolist(),(-gaps[bad]).tolist()


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--phase-run',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True)
    args=ap.parse_args();started=time.monotonic();args.out.mkdir(parents=True,exist_ok=False)
    manifest=json.loads((args.phase_run/'manifest.json').read_text())
    metadata=json.loads((args.phase_run/'input-options.json').read_text())
    official=Path(manifest['baseline_path']).with_name(Path(manifest['baseline_path']).stem+'-official.json')
    baseline=json.loads(official.read_text());assert baseline['sha256']==manifest['baseline_sha256']
    old={r['n']:float(r['side'])for r in baseline['results']}
    assert sha(args.phase_run/'input-options.npz')==manifest['input_options_sha256']
    with np.load(args.phase_run/'input-options.npz') as z:
        options=[dict(r,pose=z[r['array_key']])for r in metadata]
    results=[];saved={}
    for n,k,first_type,second_type in [(498,22,(5,17,7),(17,5,7)),(814,28,(7,21,15),(21,7,15))]:
        first=[p for p in options if (p['w'],p['h'],p['d'])==first_type]
        second=[p for p in options if (p['w'],p['h'],p['d'])==second_type]
        F=old[n]-k-1e-4;choices=[]
        for a in first:
            for b in second:
                _,ahi=extents(a['pose']);_,bhi=extents(b['pose'])
                ay=max(0.,F-(ahi[:,1].max()-a['h']));bx=max(0.,F-(bhi[:,0].max()-b['w']))
                pa=a['pose'].copy();pb=b['pose'].copy()
                pa[:,:2]+=[0,b['h']+ay];pb[:,:2]+=[a['w']+bx,0]
                edges,depth=overlap_edges(pa,pb)
                choices.append((sum(d*d for d in depth),max(depth,default=0.),len(edges),a,b,ay,bx,edges,depth))
        choices.sort(key=lambda x:x[:3]);best=choices[0]
        energy,maximum,count,a,b,ay,bx,edges,depth=best
        base,C,groups=symbolic_pair(a,b,k);variables=np.array([F,F,F,0,ay,bx,0])
        base[:,:2]+=np.einsum('nij,j->ni',C,variables)
        all_edges,all_depth=overlap_edges(base);colliding=sorted({i for edge in all_edges for i in edge})
        if colliding:
            distances=np.min(np.linalg.norm(base[:,:2,None]-base[colliding,:2].T[None,:,:],axis=1),axis=1)
            local=np.flatnonzero(distances<=2.5)
            if len(local)>40:local=np.argsort(distances)[:max(40,len(colliding))]
        else:local=np.array([],int)
        saved[f'n{n}__UNVALIDATED_OVERLAPPING_START']=base
        record=dict(n=n,k=k,target_side=k+F,current_side=old[n],source_pair_count=len(choices),
            first={k:v for k,v in a.items()if k!='pose'},second={k:v for k,v in b.items()if k!='pose'},
            phase_variables=variables.tolist(),cross_overlap_pairs=edges,cross_overlap_depths=depth,
            squared_cross_penetration=energy,maximum_cross_penetration=maximum,
            full_overlap_pairs=all_edges,full_overlap_depths=all_depth,
            colliding_square_ids=colliding,local_repair_square_ids=local.tolist(),
            local_tilted_count=int(np.sum(abs((base[local,2]+np.pi/4)%(np.pi/2)-np.pi/4)>.018)),
            geometry_sha256=array_sha(base),valid=False,
            status='Deliberately overlapping exploration seed; not certified, not eligible for merge or submission.')
        results.append(record)
    np.savez_compressed(args.out/'uncertified-junction-starts.npz',**saved)
    report=dict(seconds=time.monotonic()-started,baseline_sha256=manifest['baseline_sha256'],
        phase_manifest_sha256=sha(args.phase_run/'manifest.json'),input_options_sha256=manifest['input_options_sha256'],
        output_sha256=sha(args.out/'uncertified-junction-starts.npz'),source_sha256=sha(__file__),results=results,no_submission=True)
    atom(args.out/'report.json',report);(args.out/'source.py').write_bytes(Path(__file__).read_bytes())
    for r in results:print(json.dumps({k:r[k]for k in ['n','source_pair_count','maximum_cross_penetration','cross_overlap_pairs','colliding_square_ids','local_repair_square_ids','local_tilted_count']}))


if __name__=='__main__':main()
