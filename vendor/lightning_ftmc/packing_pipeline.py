"""Offline atlas transfer, border expansion, and monotone subset selection."""
import math
import numpy as np
from solver import grid, normalize, side, strip_blocks, pair_gaps

def border_expand(p,t):
    p=normalize(p,0)
    L=side(p)
    k=int(math.floor(L+1e-9))
    if t==0:return p.copy()
    right=np.array([(L+i+.5,j+.5,0.) for i in range(t) for j in range(k)])
    top=np.array([(i+.5,L+j+.5,0.) for j in range(t) for i in range(k+t)])
    return np.vstack((p,right,top))

def trim_order(p,shift=(0.,0.)):
    """Keep spatially central squares; bounding side can only decrease."""
    h=(np.abs(np.cos(p[:,2]))+np.abs(np.sin(p[:,2])))/2
    low=(p[:,:2]-h[:,None]).min(axis=0)
    high=(p[:,:2]+h[:,None]).max(axis=0)
    center=(low+high)/2+np.asarray(shift)
    radius=np.max(np.abs(p[:,:2]-center)+h[:,None],axis=1)
    return np.argsort(radius,kind='stable')

def solve(reference_records, max_n=1000, use_border=True, use_strips=True, core_records=None):
    ns=np.arange(1,max_n+1)
    best=np.ceil(np.sqrt(ns)).astype(float)
    packings={n:grid(n) for n in ns}
    provenance={int(n):'grid' for n in ns}
    candidates=[]
    for rec in reference_records:
        p=np.array(rec['packing'],dtype=float)
        candidates.append((p,'reference:'+rec['url'].rsplit('/',1)[-1]))
    if core_records:
        from corner_search import corner_layout
        for idx,rec in enumerate(core_records):
            p=corner_layout(rec['L'],rec['w'],rec['m'],rec['sx'],rec['sy'])
            candidates.append((normalize(p),f'core:{idx}'))
    if use_strips:
        for k in range(2,33):
            for w in range(1,7):
                for r in range(math.floor(1+w/math.sqrt(2))+1):
                    L=k+w/math.sqrt(2)
                    m=math.floor(math.sqrt(2)*k+1e-10) if r==0 else min(math.floor(math.sqrt(2)*k+1e-10),math.floor(math.sqrt(2)*(L-r-1)+1e-10))
                    N=k*(k-1)+r*(r+1)+w*m
                    if m<=0 or N>max_n+80 or L>=math.ceil(math.sqrt(max(1,N)))-1e-7:continue
                    p,_=strip_blocks(k,w,r,m)
                    # Analytic construction requires disjoint corner triangles.
                    if r>1+w/math.sqrt(2)+1e-10:continue
                    p=normalize(p)
                    if pair_gaps(p)[2].max(axis=1).min() < -1e-9:continue
                    candidates.append((p,f'strip:k{k},w{w},r{r},m{m}'))
    stages={}
    for p,label in candidates:
        L=side(p)
        max_t=max(0,int(math.ceil(math.sqrt(max_n))-L)) if use_border else 0
        for t in range(max_t+1):
            q=border_expand(p,t)
            if len(q)==0:continue
            Lq=side(q)
            # A layout of side L cannot improve n <= floor(L)^2.
            first=1
            last=min(max_n,len(q))
            if first>last:continue
            for dx in (-.5,0.,.5):
                for dy in (-.5,0.,.5):
                    order=trim_order(q,(dx,dy))
                    sorted_q=q[order]
                    h=(np.abs(np.cos(sorted_q[:,2]))+np.abs(np.sin(sorted_q[:,2])))/2
                    lower=np.minimum.accumulate(sorted_q[:,:2]-h[:,None],axis=0)
                    upper=np.maximum.accumulate(sorted_q[:,:2]+h[:,None],axis=0)
                    lengths=np.max(upper-lower,axis=1)
                    improved=np.flatnonzero(lengths[:last]<best[:last]-1e-8)
                    for ix in improved:
                        n=int(ix+1)
                        best[ix]=lengths[ix]
                        packings[n]=sorted_q[:n].copy()
                        provenance[n]=label+(f'+border{t}' if t else '')
    return best,packings,provenance
