"""Independent finite-candidate upright refill inspired by Chris Deotte FTMC.

Simplicial reductions preserve the maximum independent set. HiGHS MILP is
exact only when it proves optimality; time-limited feasible seeds are labelled.
This module never certifies a continuous packing or changes unit-square sizes.
"""
import time, math
import numpy as np
from scipy.spatial import cKDTree
from scipy.optimize import milp, Bounds, LinearConstraint
from scipy.sparse import coo_matrix

def half(a):return .5*(abs(np.cos(a))+abs(np.sin(a)))

def gaps(p):
    if len(p)<2:return 1.
    pairs=cKDTree(p[:,:2]).query_pairs(1.415,output_type='ndarray')
    if not len(pairs):return 1.
    i,j=pairs.T;d=p[j,:2]-p[i,:2];a,b=p[i,2],p[j,2]
    proj=np.maximum.reduce([abs(d[:,0]*np.cos(t)+d[:,1]*np.sin(t))for t in [a,a+np.pi/2,b,b+np.pi/2]])
    return float(np.min(proj-.5*(1+abs(np.cos(a-b))+abs(np.sin(a-b)))))

def core_gaps(xy,core):
    if not len(core):return np.full(len(xy),100.)
    d=xy[:,None,:]-core[None,:,:2];a=core[:,2];c,s=np.cos(a),np.sin(a)
    rad=.5*(1+abs(c)+abs(s))
    sep=np.maximum.reduce([abs(d[:,:,0]),abs(d[:,:,1]),abs(d[:,:,0]*c+d[:,:,1]*s),abs(-d[:,:,0]*s+d[:,:,1]*c)])-rad
    # On upright axes the support is also (1+|cos a|+|sin a|)/2.
    return sep.min(1)

def candidates(W,H,core,extra=None,soft=0.,depth=4):
    xs=np.unique(np.r_[np.arange(.5,W-.499999,1.),W-np.arange(.5,W-.499999,1.)])
    ys=np.unique(np.r_[np.arange(.5,H-.499999,1.),H-np.arange(.5,H-.499999,1.)])
    X,Y=np.meshgrid(xs,ys);points=[np.column_stack((X.ravel(),Y.ravel()))]
    if extra is not None and len(extra):points.append(np.asarray(extra)[:,:2])
    margin=3e-7-soft
    # Intersect the four SAT strips: exact Minkowski-obstacle sections.
    for t in core:
        c,s=np.cos(t[2]),np.sin(t[2]);r=.5*(1+abs(c)+abs(s));extent=r
        for swap,grid,lim in [(False,ys,W),(True,xs,H)]:
            fixed=grid-t[0 if swap else 1]
            axes=[(1.,0.),(c,s),(-s,c)] if not swap else [(1.,0.),(s,c),(c,-s)]
            lo=np.full(len(grid),-extent);hi=np.full(len(grid),extent);valid=abs(fixed)<extent+1e-8
            for a,b in axes[1:]:
                if abs(a)<1e-10:valid&=abs(b*fixed)<=r
                else:
                    l=(-r-b*fixed)/a;h=(r-b*fixed)/a;lo=np.maximum(lo,np.minimum(l,h));hi=np.minimum(hi,np.maximum(l,h))
            valid&=lo<=hi
            center=t[1 if swap else 0]
            for bound,sign in [(lo,-1),(hi,1)]:
                for k in range(depth+1):
                    moving=center+bound+sign*(k+margin)
                    z=np.column_stack((grid[valid],moving[valid]))if swap else np.column_stack((moving[valid],grid[valid]))
                    points.append(z)
    xy=np.vstack(points);xy=xy[(xy[:,0]>=.5-1e-8)&(xy[:,0]<=W-.5+1e-8)&(xy[:,1]>=.5-1e-8)&(xy[:,1]<=H-.5+1e-8)]
    if not len(xy):return xy
    _,ids=np.unique(np.round(xy,7),axis=0,return_index=True);xy=xy[np.sort(ids)]
    keep=[]
    for start in range(0,len(xy),512):keep.extend(np.flatnonzero(core_gaps(xy[start:start+512],core)>=-soft-2e-8)+start)
    return xy[np.asarray(keep,dtype=int)]

def independent_set(xy,target=None,seconds=.35):
    started=time.perf_counter();n=len(xy)
    if not n:return [],dict(candidates=0,simplicial=0,milp=0,optimal=True)
    pairs=cKDTree(xy).query_pairs(math.sqrt(2),output_type='ndarray')
    pairs=pairs[(abs(xy[pairs[:,0]]-xy[pairs[:,1]])<1.-1e-8).all(1)] if len(pairs)else pairs
    adj=[set()for _ in range(n)]
    for a,b in pairs:adj[int(a)].add(int(b));adj[int(b)].add(int(a))
    live=set(range(n));fixed=[];changed=True
    while changed:
        changed=False
        for v in sorted(live,key=lambda i:len(adj[i]&live)):
            if v not in live:continue
            nb=adj[v]&live
            if len(nb)<=1 or (len(nb)<=12 and all((nb-{u})<=adj[u]for u in nb)):
                fixed.append(v);live-=nb|{v};changed=True
        if target is not None and len(fixed)>=target:return fixed[:target],dict(candidates=n,simplicial=len(fixed),milp=0,optimal=False,reason='target reached')
    def greedy(vertices):
        available=set(vertices);result=[]
        while available:
            u=min(available,key=lambda k:len(adj[k]&available));result.append(u);available-=adj[u]|{u}
        return result
    selected=fixed.copy();visited=set();components=[]
    for v in live:
        if v in visited:continue
        stack=[v];visited.add(v);comp=[]
        while stack:
            u=stack.pop();comp.append(u)
            for z in (adj[u]&live)-visited:visited.add(z);stack.append(z)
        components.append(comp)
    guesses=[greedy(comp)for comp in components]
    if target is not None and len(fixed)+sum(map(len,guesses))>=target:
        return (fixed+sum(guesses,[]))[:target],dict(candidates=n,simplicial=len(fixed),milp=0,optimal=False,reason='feasible greedy target')
    solved=0;optimal=True
    for comp,guess in zip(components,guesses):
        remaining=seconds-(time.perf_counter()-started)
        if remaining<.02 or len(comp)>1800:selected+=guess;optimal=False;continue
        index={v:i for i,v in enumerate(comp)};edges=[(index[u],index[v])for u in comp for v in adj[u]&set(comp)if u<v]
        row=np.repeat(np.arange(len(edges)),2);col=np.asarray(edges,dtype=int).ravel()
        A=coo_matrix((np.ones(len(col)),(row,col)),shape=(len(edges),len(comp))).tocsc()
        fit=milp(-np.ones(len(comp)),integrality=np.ones(len(comp)),bounds=Bounds(0,1),constraints=LinearConstraint(A,-np.inf,1),options={'time_limit':max(.02,remaining),'mip_rel_gap':0.,'threads':1})
        take=guess
        if fit.x is not None:
            trial=[comp[i]for i in np.flatnonzero(fit.x>.5)]
            if len(trial)>len(take)and all(v not in adj[u]for i,u in enumerate(trial)for v in trial[i+1:]):take=trial
        selected+=take;solved+=1;optimal&=fit.status==0
    return selected,dict(candidates=n,simplicial=len(fixed),milp=solved,optimal=bool(optimal),seconds=time.perf_counter()-started)

def refill(W,H,core,total,extra=None,seconds=.35,soft=0.):
    need=total-len(core)
    if need<0:return None,dict(reason='too many tilted squares')
    xy=candidates(W,H,core,extra,soft);ids,report=independent_set(xy,need,seconds)
    report.update(needed=need,found=len(ids),soft=soft)
    if len(ids)<need:return None,report
    upright=np.column_stack((xy[ids[:need]],np.zeros(need)))
    return np.vstack((core,upright)),report

def check():
    xy=np.array([[.5,.5],[1.5,.5],[.5,1.5],[1.5,1.5],[1.,1.]])
    ids,r=independent_set(xy,seconds=2.)
    assert len(ids)==4,(ids,r)
    p,r=refill(3.,3.,np.empty((0,3)),9,seconds=2.)
    assert p is not None and len(p)==9 and gaps(p)>-1e-10
    t=np.array([[1.5,1.5,.3]]);p,r=refill(4.,4.,t,8,seconds=2.)
    assert p is not None and gaps(p)>-1e-7,(p,r)
    return dict(conflict_graph_known_optimum=4,empty_3x3_capacity=9,tilted_seed_count=len(p),tilted_seed_gap=gaps(p))
