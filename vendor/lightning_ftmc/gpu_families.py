"""CUDA enumeration of four staircases and an arbitrarily rotated rectangular core.

Starting point: avazaku's Squarecraft v1, asymmetric 45-degree cores.
Extension: independent corner lengths and a free core angle. The minimum
container follows from SAT between two rectangles of feasible core centers.
"""
import argparse
import json
import math
import time
from pathlib import Path
import numpy as np
import torch
from scipy.spatial import cKDTree
from solver import side, normalize


def corner_parameters(limit=33):
    # Rotate a largest corner to BL; reflect to restrict the core to [0,45] deg.
    return np.array([(bl,br,tr,tl) for bl in range(1,limit)
                     for br in range(min(bl,limit-bl)+1)
                     for tr in range(bl+1)
                     for tl in range(min(bl,limit-bl)+1)], dtype=np.int16)


def minimum_side(corners,b,c,theta,xp=np):
    co,si=math.cos(theta),math.sin(theta)
    bl,br,tr,tl=[corners[...,k] for k in range(4)]
    # Support of a nonempty staircase on the inward core normal.
    # For an empty staircase omit its plane using the no-corner limit -infinity.
    # Zero-step support = min(cos,sin) is conservative and valid.
    t_bl=bl*max(co,si)+min(co,si)
    t_br=br*max(co,si)+min(co,si)
    t_tr=tr*max(co,si)+min(co,si)
    t_tl=tl*max(co,si)+min(co,si)
    hx=(b*co+c*si)/2; hy=(b*si+c*co)/2
    B=b+t_bl+t_tr; C=c+t_br+t_tl
    du=(t_bl-t_tr)/2; dv=(t_br-t_tl)/2
    terms=[2*hx,2*hy,B/(co+si),C/(co+si),
           (xp.abs(du)+B/2+co*hx+si*hy)/(co+si),
           (xp.abs(dv)+C/2+si*hx+co*hy)/(co+si),
           (2*xp.abs(co*du-si*dv)+2*hx+co*B+si*C)/(1+(co+si)**2),
           (2*xp.abs(si*du+co*dv)+2*hy+si*B+co*C)/(1+(co+si)**2),
           xp.maximum(xp.maximum(bl+br,br+tr),xp.maximum(tr+tl,tl+bl))]
    result=terms[0]
    for term in terms[1:]:result=xp.maximum(result,term)
    return result


def clip(poly,a,b,rhs):
    out=[]
    for p,q in zip(poly,poly[1:]+poly[:1]):
        fp=a*p[0]+b*p[1]-rhs; fq=a*q[0]+b*q[1]-rhs
        if fp<=1e-10:out.append(p)
        if (fp<0)!=(fq<0):
            t=fp/(fp-fq);out.append([p[0]+t*(q[0]-p[0]),p[1]+t*(q[1]-p[1])])
    return out


def construct(corners,b,c,theta):
    corners=np.asarray(corners,dtype=float)
    L=float(minimum_side(corners,b,c,theta))+2e-8
    co,si=math.cos(theta),math.sin(theta); hx=(b*co+c*si)/2;hy=(b*si+c*co)/2
    tb=corners*max(co,si)+min(co,si);bl,br,tr,tl=tb
    poly=[[hx,hy],[L-hx,hy],[L-hx,L-hy],[hx,L-hy]]
    for a,z,r in [(co,si,L*(co+si)-b/2-tr),(-co,-si,-b/2-bl),
                  (-si,co,co*L-c/2-tl),(si,-co,si*L-c/2-br)]:
        poly=clip(poly,a,z,r)
        if not poly:raise ValueError(('empty center domain',corners,b,c,theta,L))
    cx,cy=np.mean(poly,axis=0)
    poses=[]
    for k,steps in enumerate(corners.astype(int)):
        for i in range(steps):
            for j in range(steps-i):
                x,y=i+.5,j+.5
                for _ in range(k):x,y=L-y,x
                poses.append([x,y,0.])
    for i in range(b):
        for j in range(c):
            u=i-(b-1)/2;v=j-(c-1)/2
            poses.append([cx+co*u-si*v,cy+si*u+co*v,theta])
    return normalize(np.asarray(poses),4e-7)


def min_gap(p):
    pairs=np.asarray(list(cKDTree(p[:,:2]).query_pairs(1.5)),dtype=int).reshape(-1,2)
    if not len(pairs):return float('inf')
    i,j=pairs.T;ai,aj=p[i,2],p[j,2];d=p[j,:2]-p[i,:2]
    proj=np.stack([np.abs(d[:,0]*np.cos(t)+d[:,1]*np.sin(t)) for t in [ai,ai+np.pi/2,aj,aj+np.pi/2]],axis=1)
    r=(1+np.abs(np.cos(ai-aj))+np.abs(np.sin(ai-aj)))/2
    return float((proj.max(axis=1)-r).min())


def search(degrees,chunk=256,max_n=1100,limit=33,output='artifacts/gpu_family_recipes.json'):
    assert torch.cuda.is_available(),'CUDA is required for this enumeration'
    started=time.perf_counter();params=corner_parameters(limit)
    counts=(params.astype(np.int64)*(params+1)).sum(axis=1)//2
    params=params[counts<=max_n];counts=counts[counts<=max_n]
    bc=np.array([(b,c) for b in range(1,46) for c in range(1,46)],dtype=np.int16)
    bc=bc[np.prod(bc.astype(int),axis=1)<=max_n]
    b=torch.tensor(bc[:,0],dtype=torch.float32,device='cuda')[None]
    c=torch.tensor(bc[:,1],dtype=torch.float32,device='cuda')[None]
    capacity_core=(b*c).long()
    best=torch.full((max_n+1,),float('inf'),device='cuda');winning=torch.full((max_n+1,),-1,device='cuda',dtype=torch.long)
    evaluated=0;rows=[]
    for angle_index,deg in enumerate(degrees):
        theta=math.radians(deg);at=time.perf_counter()
        for start in range(0,len(params),chunk):
            pp=torch.tensor(params[start:start+chunk],dtype=torch.float32,device='cuda')[:,None,:]
            ns=torch.tensor(counts[start:start+chunk],device='cuda')[:,None]+capacity_core
            L=minimum_side(pp,b,c,theta,torch)
            valid=(ns<=max_n)&(L<torch.ceil(torch.sqrt(ns.float()))-1e-5)&(L<32)
            idx=ns.clamp_max(max_n).ravel()
            values=torch.where(valid,L,float('inf')).ravel()
            newbest=best.clone();newbest.scatter_reduce_(0,idx,values,reduce='amin',include_self=True)
            mask=(values==newbest[idx])&(values<best[idx])
            # Stable tie-breaking: smallest flattened parameter id.
            ids=(angle_index*len(params)+(start+torch.arange(len(pp),device='cuda'))[:,None])*len(bc)+torch.arange(len(bc),device='cuda')[None,:]
            chosen=torch.full_like(winning,torch.iinfo(torch.long).max)
            chosen.scatter_reduce_(0,idx,torch.where(mask,ids.ravel(),torch.iinfo(torch.long).max),reduce='amin',include_self=True)
            changed=newbest<best;winning[changed]=chosen[changed];best=newbest
            evaluated+=len(pp)*len(bc)
        torch.cuda.synchronize()
        row={'degrees':deg,'seconds':time.perf_counter()-at,'capacities':int(torch.isfinite(best).sum())}
        rows.append(row);print(json.dumps(row),flush=True)
        ids=winning.cpu().numpy();out=[]
        for n,z in enumerate(ids):
            if z<0:continue
            ai,rest=divmod(int(z),len(params)*len(bc));pi,bi=divmod(rest,len(bc))
            bb,cc=map(int,bc[bi]);corners=list(map(int,params[pi]));angle=math.radians(degrees[ai])
            out.append(dict(n=n,corners=corners,b=bb,c=cc,degrees=degrees[ai],L=float(minimum_side(np.array(corners),bb,cc,angle))))
        Path(output).write_text(json.dumps(out,indent=2))
        Path('research/gpu_family_status.json').write_text(json.dumps(dict(gpu=torch.cuda.get_device_name(0),evaluated=evaluated,elapsed=time.perf_counter()-started,results=rows),indent=2))
    accepted=[];bad=[]
    for rec in out:
        p=construct(rec['corners'],rec['b'],rec['c'],math.radians(rec['degrees']))
        gap=min_gap(p)
        if gap<1e-8:bad.append((rec['n'],gap))
        else:accepted.append(rec)
    assert not bad,bad[:10]
    print('DONE',json.dumps(dict(evaluated=evaluated,seconds=time.perf_counter()-started,validated=len(accepted))),flush=True)
    return accepted


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--degrees',nargs='+',type=float,default=[45,44,43,42,40,37.5,35,30,25,20,15,10,5])
    ap.add_argument('--chunk',type=int,default=256);ap.add_argument('--limit',type=int,default=33)
    args=ap.parse_args();search(args.degrees,chunk=args.chunk,limit=args.limit)
