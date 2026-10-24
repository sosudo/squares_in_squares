"""Batched topology search for Squares in Squares (CPU, CUDA, or Apple MPS).

This file is self-contained for Kaggle/Colab. Requires numpy, scipy, pandas,
torch. Example:
  python packing_gpu_search.py --base merged.csv --ns 129,153,180 --seconds 120 \
      --replicas 128 --device cuda --seed 42 --out candidates.json

Candidates are float64 SAT-checked and legalized, but MUST additionally pass the
official competition metric on the exact exported CSV before submission.
"""
from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import time
import warnings

os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree
import torch


def extent(p):
    return .5*(np.abs(np.cos(p[:,2]))+np.abs(np.sin(p[:,2])))


def normalize(p):
    p=np.array(p,dtype=np.float64,copy=True)
    h=extent(p)
    p[:,:2]-=(p[:,:2]-h[:,None]).min(axis=0)
    return p


def side(p):
    h=extent(p)
    return float(np.max((p[:,:2]+h[:,None]).max(0)-(p[:,:2]-h[:,None]).min(0)))


def legalize(p,margin=3e-11):
    p=normalize(p)
    pairs=cKDTree(p[:,:2]).query_pairs(1.6,output_type='ndarray')
    if len(pairs):
        i,j=pairs.T
        d=p[j,:2]-p[i,:2]
        c,s=np.cos(p[:,2]),np.sin(p[:,2])
        proj=np.stack([d[:,0]*c[i]+d[:,1]*s[i],-d[:,0]*s[i]+d[:,1]*c[i],
                       d[:,0]*c[j]+d[:,1]*s[j],-d[:,0]*s[j]+d[:,1]*c[j]],axis=1)
        delta=p[j,2]-p[i,2]
        r=.5*(1+np.abs(np.cos(delta))+np.abs(np.sin(delta)))
        required=(r+margin)/np.maximum(np.max(np.abs(proj),axis=1),1e-200)
        factor=max(1.,float(required.max()))
        if not np.isfinite(factor) or factor>2: return None
        p[:,:2]*=factor
    return normalize(p)


def min_gap(p):
    pairs=cKDTree(p[:,:2]).query_pairs(1.6,output_type='ndarray')
    if not len(pairs):return math.inf
    i,j=pairs.T;d=p[j,:2]-p[i,:2]
    c,s=np.cos(p[:,2]),np.sin(p[:,2])
    proj=np.stack([d[:,0]*c[i]+d[:,1]*s[i],-d[:,0]*s[i]+d[:,1]*c[i],
                   d[:,0]*c[j]+d[:,1]*s[j],-d[:,0]*s[j]+d[:,1]*c[j]],axis=1)
    delta=p[j,2]-p[i,2]
    r=.5*(1+np.abs(np.cos(delta))+np.abs(np.sin(delta)))
    return float(np.min(np.max(np.abs(proj),axis=1)-r))


def neighbor_pairs(batch,reach=1.9):
    """Union across replicas; refresh as centers move, validate all pairs at end."""
    n=batch.shape[1]
    encoded=[]
    for p in batch:
        pairs=cKDTree(p[:,:2]).query_pairs(reach,output_type='ndarray')
        if len(pairs):encoded.append(pairs[:,0]*n+pairs[:,1])
    if not encoded:return np.empty((0,2),dtype=np.int64)
    k=np.unique(np.concatenate(encoded))
    return np.stack([k//n,k%n],axis=1)


def energies(p,L,pairs):
    """One independent squared-penetration energy per replica."""
    width,height=L if isinstance(L,(tuple,list)) else (L,L)
    c,s=torch.cos(p[:,:,2]),torch.sin(p[:,:,2])
    h=.5*(c.abs()+s.abs())
    walls=(torch.relu(h-p[:,:,0]).square()+torch.relu(p[:,:,0]+h-width).square()
           +torch.relu(h-p[:,:,1]).square()+torch.relu(p[:,:,1]+h-height).square()).sum(1)
    if not pairs.numel():return walls
    i,j=pairs[:,0],pairs[:,1]
    dx,dy=p[:,j,0]-p[:,i,0],p[:,j,1]-p[:,i,1]
    projections=torch.stack([c[:,i]*dx+s[:,i]*dy,-s[:,i]*dx+c[:,i]*dy,
                             c[:,j]*dx+s[:,j]*dy,-s[:,j]*dx+c[:,j]*dy],dim=-1)
    delta=p[:,j,2]-p[:,i,2]
    radius=.5*(1+torch.cos(delta).abs()+torch.sin(delta).abs())
    depths=torch.relu(radius-projections.abs().amax(-1))
    return walls+depths.square().sum(1)


def perturb(base,donor,replicas,rng,amplitude,L):
    batch=[]
    n=len(base)
    for r in range(replicas):
        q=base.copy()
        mode=r%6
        if mode==5 and donor is not None:
            # Prefer a tilted square, where deletion can unlock the seam.
            tilted=np.flatnonzero(np.abs(np.sin(2*donor[:,2]))>.01)
            k=int(rng.choice(tilted if len(tilted) else len(donor)))
            q=normalize(np.delete(donor,k,axis=0))
        q[:,:2]*=L/side(q)
        if r:
            if mode in (0,1):
                center=q[int(rng.integers(n)),:2]
                mask=np.linalg.norm(q[:,:2]-center,axis=1)<rng.uniform(1.5,4.)
                q[mask,:]+=rng.normal(size=(int(mask.sum()),3))*[amplitude,amplitude,amplitude*.6]
            elif mode==2:
                q+=rng.normal(size=q.shape)*[amplitude*.15,amplitude*.15,amplitude*.08]
            elif mode==3:
                # Coherent angle-band kicks preserve some geometric structure.
                folded=(q[:,2]+np.pi/4)%(np.pi/2)-np.pi/4
                bins=np.round(folded/.02).astype(int)
                for band in np.unique(bins):
                    q[bins==band,2]+=rng.normal()*amplitude*.15
            elif mode==4:
                axis=int(rng.integers(2)); seam=rng.uniform(0,L)
                mask=q[:,axis]>seam
                q[mask,1-axis]+=rng.uniform(-amplitude,amplitude)
                q[mask,2]+=rng.uniform(-amplitude*.1,amplitude*.1)
        batch.append(q)
    return np.array(batch)


def polish(q,L,device,steps=200):
    # MPS cannot perform f64; refinement falls back to CPU there.
    if device.type=='mps':device=torch.device('cpu')
    p=torch.tensor(q[None],device=device,dtype=torch.float64,requires_grad=True)
    for _ in range(2):
        pairs=torch.tensor(neighbor_pairs(p.detach().cpu().numpy(),1.8),device=device)
        opt=torch.optim.LBFGS([p],max_iter=steps,tolerance_grad=1e-14,
                              tolerance_change=1e-22,history_size=40,line_search_fn='strong_wolfe')
        def closure():
            opt.zero_grad();e=energies(p,L,pairs).sum();e.backward();return e
        opt.step(closure)
    return p.detach().cpu().numpy()[0]


def optimize(base,donor,seconds,replicas,device,seed,steps,shrink,amplitude):
    rng=np.random.default_rng(seed)
    base=normalize(base); incumbent=base.copy(); best=side(base)
    original=best; start=time.monotonic(); attempt=0;history=[]
    dtype=torch.float32 if device.type!='cpu' else torch.float64
    while time.monotonic()-start<seconds:
        attempt+=1
        # Cycle shrink targets and perturbation magnitudes instead of repeating
        # a single impossible container size.
        delta=shrink*original*(.3,1.,3.,.1)[(attempt-1)%4]
        target=best-delta
        batch=perturb(incumbent,donor,replicas,rng,amplitude*(1.,2.,.3)[(attempt-1)%3],target)
        p=torch.tensor(batch,device=device,dtype=dtype,requires_grad=True)
        pairs=torch.tensor(neighbor_pairs(batch),device=device)
        opt=torch.optim.Adam([p],lr=.008)
        ran=0
        for k in range(steps):
            if k%50==0 and time.monotonic()-start>seconds:break
            if k and k%200==0:
                pairs=torch.tensor(neighbor_pairs(p.detach().cpu().double().numpy()),device=device)
            lr=1e-5+(.008-1e-5)*.5*(1+math.cos(math.pi*k/max(1,steps-1)))
            opt.param_groups[0]['lr']=lr
            opt.zero_grad();loss=energies(p,target,pairs);loss.sum().backward()
            torch.nn.utils.clip_grad_norm_([p],max_norm=10.)
            opt.step();ran=k+1
        with torch.no_grad():
            losses=energies(p,target,pairs).detach().cpu().double().numpy()
            order=np.argsort(losses)[:min(4,replicas)]
            poses=p.detach().cpu().double().numpy()
        candidate_count=0
        for index in order:
            q=poses[index]
            # Always finish one replica, including when the Adam budget elapsed.
            if candidate_count==0 or time.monotonic()-start<seconds:
                q=polish(q,target,device,steps=150)
            candidate_count+=1
            q=legalize(q)
            if q is None:continue
            L=side(q)
            if L<best-1e-9 and min_gap(q)>0:
                best,incumbent=L,q
                print(json.dumps({'event':'improvement','n':len(base),'side':best,'gain':original-best,
                                  'attempt':attempt,'elapsed':time.monotonic()-start}),flush=True)
        rec={'event':'attempt','n':len(base),'attempt':attempt,'target':target,
             'min_energy':float(losses.min()),'best':best,'steps':ran,'elapsed':time.monotonic()-start}
        history.append(rec);print(json.dumps(rec),flush=True)
    return incumbent,{'original_side':original,'side':best,'min_gap':min_gap(incumbent),
                       'attempts':attempt,'elapsed':time.monotonic()-start,'seed':seed,'device':str(device)}


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--base',required=True)
    ap.add_argument('--out',default='candidates.json')
    ap.add_argument('--ns',default='129,130,131,132,152,153,154,155,156,175,176,177,178,179,180,181,182')
    ap.add_argument('--seconds',type=float,default=60,help='Approximate budget per puzzle; one f64 polish may extend it.')
    ap.add_argument('--replicas',type=int,default=64)
    ap.add_argument('--steps',type=int,default=1000)
    ap.add_argument('--device',choices=['auto','cpu','cuda','mps'],default='auto')
    ap.add_argument('--seed',type=int,default=20261024)
    ap.add_argument('--shrink',type=float,default=2e-4)
    ap.add_argument('--amplitude',type=float,default=.05)
    a=ap.parse_args()
    torch.set_num_threads(1)
    if a.device=='auto':
        device=torch.device('cuda' if torch.cuda.is_available() else 'mps' if torch.backends.mps.is_available() else 'cpu')
    else:device=torch.device(a.device)
    if device.type=='cpu' and a.replicas>8:
        warnings.warn('CPU selected: using 8 replicas; pass <=8 explicitly to suppress this warning.')
        a.replicas=8
    torch.manual_seed(a.seed)
    df=pd.read_csv(a.base)
    packs={int(n):normalize(g.sort_values('square_id')[['x','y','angle']].to_numpy(float)) for n,g in df.groupby('n')}
    ns=[int(n) for n in a.ns.split(',')] if a.ns!='all' else sorted(packs)
    out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True)
    saved=json.loads(out.read_text()) if out.exists() else {}
    for n in ns:
        base=packs[n]
        if str(n) in saved and saved[str(n)]['side']<side(base):base=np.array(saved[str(n)]['squares'])
        q,info=optimize(base,packs.get(n+1),a.seconds,a.replicas,device,a.seed+n,a.steps,a.shrink,a.amplitude)
        print(json.dumps({'event':'puzzle_complete','n':n,**info}),flush=True)
        if info['side']<side(base)-1e-9 and info['min_gap']>0:
            saved[str(n)]={'side':info['side'],'squares':q.tolist(),'search':info}
        tmp=out.with_suffix('.tmp');tmp.write_text(json.dumps(saved));tmp.replace(out)


if __name__=='__main__':main()
