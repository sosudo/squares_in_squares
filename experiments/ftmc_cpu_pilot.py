"""Bounded CPU pilot for tilted-core mutation, exact upright refill and quench.

Uses publicly released Deotte before/after gadget fixtures. The architecture is
described by Deotte's public FTMC notebook and lightningv08's public code; this
pilot uses our independent Torch and refill implementations. It is a diagnostic,
not a claim of replicating their CUDA throughput or reported improvements.
"""
from __future__ import annotations
import argparse
import json
import math
from pathlib import Path
import time
import numpy as np
import torch
from scipy.spatial import cKDTree
from packing_gpu_search import normalize,extent,legalize,min_gap,polish
from refill_search import fill_rect


def dimensions(p):
    h=extent(p)
    return (p[:,:2]+h[:,None]).max(0)-(p[:,:2]-h[:,None]).min(0)


def bloat(p,w,h):return float(np.max(dimensions(p)-[w,h]))


def mutation(p,w,h,f,rng,mode):
    angle=(p[:,2]+np.pi/4)%(np.pi/2)-np.pi/4
    core=p[np.abs(angle)>.018].copy()
    uprights=p[np.abs(angle)<=.018]
    if len(core)<3:return core
    if mode==0:
        # Preserve the incumbent's lattice phase for a small local control.
        core+=rng.normal(size=core.shape)*[.0002,.0002,.0001]
        return core
    center=core[:,:2].mean(0)
    axis=np.array([w,h],float);axis/=np.linalg.norm(axis)
    if mode==2:
        projection=core[:,:2]@axis
        k=min(len(core)-3,int(rng.integers(1,3)))
        if k:core=np.delete(core,np.argsort(projection)[:k] if rng.random()<.5 else np.argsort(projection)[-k:],axis=0)
    elif mode==3 and len(uprights):
        dist=cKDTree(core[:,:2]).query(uprights[:,:2])[0]
        x=uprights[int(rng.choice(np.argsort(dist)[:min(8,len(dist))]))].copy()
        x[2]=.25*np.angle(np.mean(np.exp(4j*core[:,2])))
        core[np.argmax(np.linalg.norm(core[:,:2]-x[:2],axis=1))]=x
    elif mode==4:
        target=rng.choice(np.arctan([.5,2/3,.75,1.]))*rng.choice([-1,1])
        c,s=np.cos(target),np.sin(target)
        uv=np.array([(i,j)for i in range(-30,31)for j in range(-30,31)],float)+rng.uniform(-.5,.5,2)
        xy=uv@np.array([[c,s],[-s,c]])+[(w+f)/2,(h+f)/2]
        e=.5*(abs(c)+abs(s))
        xy=xy[(xy[:,0]>=e)&(xy[:,0]<=w+f-e)&(xy[:,1]>=e)&(xy[:,1]<=h+f-e)]
        if len(xy)>=len(core):
            normal=np.array([-axis[1],axis[0]])
            score=abs((xy-[(w+f)/2,(h+f)/2])@normal-rng.uniform(-.5,.5))
            core=np.column_stack([xy[np.argsort(score)[:len(core)]],np.full(len(core),target)])
        return core
    elif mode==5:
        projection=core[:,:2]@axis
        core[projection>np.median(projection),:2]+=.4*axis
        core[projection<=np.median(projection),:2]-=.4*axis
        add=core[int(rng.integers(len(core)))].copy();add[:2]=center+rng.normal(0,.1,2)
        core=np.vstack([core,add])
    delta=rng.normal(0,.025)
    if mode==1:
        old=.25*np.angle(np.mean(np.exp(4j*core[:,2])))
        target=rng.choice(np.arctan([.5,2/3,.75,1.]))*np.sign(old or 1)
        delta=(target-old+np.pi/4)%(np.pi/2)-np.pi/4
    c,s=np.cos(delta),np.sin(delta)
    core[:,:2]=(core[:,:2]-center)@np.array([[c,s],[-s,c]])+center
    core[:,2]+=delta
    core[:,0]+=(core[:,1]-center[1])*rng.normal(0,.01)
    core[:,:2]+=rng.normal(0,.002,core[:,:2].shape)
    core=normalize(core);core[:,:2]+=(np.array([w+f,h+f])-dimensions(core))/2
    return core


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--examples',default='artifacts/public/gadgets_39_and_baselines.npz')
    ap.add_argument('--ids',default='38,5,0')
    ap.add_argument('--stage',choices=['before','after'],default='before')
    ap.add_argument('--seconds',type=float,default=45)
    ap.add_argument('--seed',type=int,default=20261024)
    ap.add_argument('--soft',type=float,default=.008,help='Core overlap allowed only in temporary refill seeds; final SAT remains strict.')
    ap.add_argument('--out',default='artifacts/candidates/ftmc_pilot.json')
    a=ap.parse_args();torch.set_num_threads(1)
    z=np.load(a.examples);rng=np.random.default_rng(a.seed);device=torch.device('cpu')
    out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True)
    results=json.loads(out.read_text()) if out.exists() else {}
    for idx in [int(x)for x in a.ids.split(',')]:
        w,h,d=map(int,z['meta_39'][idx,:3]);p=normalize(z[f'{a.stage}_{idx}']);n=len(p)
        original=best=bloat(p,w,h);start=time.monotonic();attempt=0;capacity_hits=0
        while time.monotonic()-start<a.seconds:
            mode=attempt%6;attempt+=1
            loose=min(.999,best+.025);target=best-[.001,.004,.01,.025][attempt%4]
            core=mutation(p,w,h,loose,rng,mode)
            if len(core)<2 or len(core)>=n:continue
            core=polish(core,(w+loose,h+loose),device,steps=100)
            offset=(core[:,:2]-extent(core)[:,None]).min(0)
            core=legalize(core)
            if core is None or bloat(core,w,h)>loose+1e-6:continue
            # A tilted core's phase relative to both walls matters to refill.
            # Legalization normalizes its bounding box; restore that offset.
            core[:,:2]+=np.clip(offset,0,np.maximum(0,np.array([w+loose,h+loose])-dimensions(core)))
            upright=p[np.abs((p[:,2]+np.pi/4)%(np.pi/2)-np.pi/4)<=.018]
            up,info=fill_rect(w+loose,h+loose,core,incumbents=upright,
                              time_limit=.25,depth=3,margin=3e-10,soft=a.soft)
            if len(up)+len(core)<n:
                print(json.dumps({'event':'refill_short','id':idx,'mode':mode,'core':len(core),'capacity':len(up)+len(core),'need':n}),flush=True)
                continue
            capacity_hits+=1
            q=np.vstack([core,up[:n-len(core)]])
            q=polish(q,(w+target,h+target),device,steps=200)
            q=legalize(q)
            if q is None:continue
            f=bloat(q,w,h)
            if f<best-1e-7 and min_gap(q)>0:
                best,p=f,q
                rec={'w':w,'h':h,'surplus':d,'bloat':best,'original_bloat':original,
                     'squares':q.tolist(),'source':f'Deotte {a.stage}_{idx}; independent FTMC CPU pilot',
                     'mode':mode,'min_gap':min_gap(q),'seed':a.seed,'refill':info}
                results[f'{w}_{h}_{d}']=rec
                tmp=out.with_suffix('.tmp');tmp.write_text(json.dumps(results));tmp.replace(out)
                print(json.dumps({'event':'gadget_improved','id':idx,'before':original,'after':best,'mode':mode}),flush=True)
            print(json.dumps({'event':'quench','id':idx,'mode':mode,'f':f,'best':best,'elapsed':time.monotonic()-start}),flush=True)
        print(json.dumps({'event':'gadget_complete','id':idx,'stage':a.stage,'attempts':attempt,'capacity_hits':capacity_hits,'before':original,'after':best,'elapsed':time.monotonic()-start}),flush=True)


if __name__=='__main__':main()
