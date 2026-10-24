"""Constructive square packing with rigid-block linear compaction."""
import math
import numpy as np
from scipy.optimize import linprog

GAP = 2e-7

def side(p):
    h=(np.abs(np.cos(p[:,2]))+np.abs(np.sin(p[:,2])))/2
    lo=(p[:,:2]-h[:,None]).min(axis=0)
    hi=(p[:,:2]+h[:,None]).max(axis=0)
    return float(np.max(hi-lo))

def normalize(p, margin=GAP):
    p=np.asarray(p,dtype=float).copy()
    p[:,:2]*=1+margin
    h=(np.abs(np.cos(p[:,2]))+np.abs(np.sin(p[:,2])))/2
    p[:,:2]-=(p[:,:2]-h[:,None]).min(axis=0)
    return p

def grid(n):
    k=math.ceil(math.sqrt(n))
    return np.array([(i%k+.5,i//k+.5,0.) for i in range(n)])

def strip_blocks(k,w,r,m,theta=math.pi/4):
    L=k+w/math.sqrt(2)
    tri=np.array([(i+.5,j+.5) for i in range(k-1) for j in range(k-1-i)])
    small=np.array([(i+.5,j+.5) for i in range(r) for j in range(r-i)]).reshape(-1,2)
    blocks=[tri,L-tri]
    if len(small):
        blocks += [np.column_stack((L-small[:,0],small[:,1])),np.column_stack((small[:,0],L-small[:,1]))]
    uv=np.array([(i-(w-1)/2,j-(m-1)/2) for i in range(w) for j in range(m)])
    c,s=math.cos(theta),math.sin(theta)
    blocks += [uv@np.array([[c,s],[-s,c]])+L/2]
    xy=np.concatenate(blocks)
    groups=np.concatenate([np.full(len(b),g) for g,b in enumerate(blocks)])
    angles=np.zeros(len(xy)); angles[groups==len(blocks)-1]=theta
    return np.column_stack((xy,angles)),groups

def pair_gaps(p):
    """All pair SAT gaps; nonnegative means disjoint interiors."""
    i,j=np.triu_indices(len(p),1)
    d=p[j,:2]-p[i,:2]
    ai=p[i,2];aj=p[j,2]
    axes=np.stack((np.column_stack((np.cos(ai),np.sin(ai))),np.column_stack((-np.sin(ai),np.cos(ai))),np.column_stack((np.cos(aj),np.sin(aj))),np.column_stack((-np.sin(aj),np.cos(aj)))),axis=1)
    projections=np.abs(np.einsum('ik,ijk->ij',d,axes))
    delta=ai-aj
    radius=(1+np.abs(np.cos(delta))+np.abs(np.sin(delta)))/2
    gaps=projections-radius[:,None]
    return i,j,gaps,axes

def compact(k,w,r,m,theta, return_packing=False):
    reference,g=strip_blocks(k,w,r,m)
    p,_=strip_blocks(k,w,r,m,theta)
    ng=int(g.max()+1); nv=2*ng+1
    i,j,gaps,old_axes=pair_gaps(reference)
    cross=g[i]!=g[j]
    i,j,gaps,old_axes=i[cross],j[cross],gaps[cross],old_axes[cross]
    chosen=gaps.argmax(axis=1)
    # Start with local contacts. Add distant constraints only if needed.
    near=np.max(np.abs(reference[j,:2]-reference[i,:2]),axis=1)<3.0
    selected=set(np.flatnonzero(near).tolist())
    old_a=old_axes[np.arange(len(i)),chosen]
    sign=np.sign(np.sum((reference[j,:2]-reference[i,:2])*old_a,axis=1))
    sign[sign==0]=1
    def constraints(indices):
        ii=i[indices];jj=j[indices];ch=chosen[indices]
        # Axes 0,1 belong to i; axes 2,3 belong to j.
        angle=np.where(ch<2,p[ii,2],p[jj,2])+(ch%2)*math.pi/2
        ax=np.column_stack((np.cos(angle),np.sin(angle)))*sign[indices,None]
        ai=p[ii,2];aj=p[jj,2]
        radius=(np.abs(np.cos(angle-ai))+np.abs(np.sin(angle-ai))+np.abs(np.cos(angle-aj))+np.abs(np.sin(angle-aj)))/2
        a=np.zeros((len(indices),nv))
        rows=np.arange(len(indices))
        a[rows,2*g[ii]]=ax[:,0];a[rows,2*g[ii]+1]=ax[:,1]
        a[rows,2*g[jj]]-=ax[:,0];a[rows,2*g[jj]+1]-=ax[:,1]
        b=np.sum((p[jj,:2]-p[ii,:2])*ax,axis=1)-radius-GAP
        return a,b
    # Only each block's extreme corner matters for containment.
    ac=[];bc=[]
    for z in range(ng):
        pts=p[g==z];h=(abs(math.cos(pts[0,2]))+abs(math.sin(pts[0,2])))/2
        for dim in (0,1):
            row=np.zeros(nv);row[2*z+dim]=-1
            ac.append(row);bc.append(float(pts[:,dim].min()-h))
            row=np.zeros(nv);row[2*z+dim]=1;row[-1]=-1
            ac.append(row);bc.append(float(-pts[:,dim].max()-h))
    objective=np.zeros(nv);objective[-1]=1
    for _ in range(5):
        a,b=constraints(np.array(sorted(selected),dtype=int))
        fit=linprog(objective,A_ub=np.vstack((np.array(ac),a)),b_ub=np.concatenate((bc,b)),bounds=[(None,None)]*(nv-1)+[(0,None)],method='highs')
        if not fit.success:return (math.inf,None) if return_packing else math.inf
        q=p.copy();q[:,:2]+=fit.x[:-1].reshape(ng,2)[g]
        # Check the same fixed separating axes, including formerly distant pairs.
        all_a,all_b=constraints(np.arange(len(i)))
        violated=np.flatnonzero(all_a@fit.x-all_b>1e-7)
        new=set(violated.tolist())-selected
        if not new:
            if return_packing:return side(q),q
            return side(q)
        selected.update(new)
    return (math.inf,None) if return_packing else math.inf
