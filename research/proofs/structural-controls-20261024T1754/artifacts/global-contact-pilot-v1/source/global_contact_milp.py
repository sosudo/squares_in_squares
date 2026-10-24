"""Independent fixed-angle whole-pose contact-disjunction prototype.

All centers and the enclosure side remain continuous. A finite selected pair
set receives signed SAT branch binaries. Every other potential pair keeps its
current strongest branch; therefore optimality statements concern this local
fixed-angle/trust model only, never unrestricted square packing.
"""
from __future__ import annotations
from dataclasses import dataclass
import math,time
import numpy as np
from scipy.optimize import Bounds,LinearConstraint,linprog,milp
from scipy.sparse import coo_matrix
from scipy.spatial import cKDTree


def axes_and_radii(ai,aj):
    ui=np.array([math.cos(ai),math.sin(ai)]);vi=np.array([-ui[1],ui[0]])
    uj=np.array([math.cos(aj),math.sin(aj)]);vj=np.array([-uj[1],uj[0]])
    result=[];seen=set()
    for axis in(ui,vi,uj,vj):
        for sign in(1.,-1.):
            a=axis*sign;key=tuple(map(float,a))
            if key in seen:continue
            seen.add(key)
            radius=.5*(abs(a@ui)+abs(a@vi)+abs(a@uj)+abs(a@vj))
            result.append((a,float(radius)))
    return result


def projection_bounds(axis,lower_i,upper_i,lower_j,upper_j):
    """Exact box extrema of the linear signed relative projection (in float)."""
    low=lower_j-upper_i;high=upper_j-lower_i
    minimum=float(np.where(axis>=0,axis*low,axis*high).sum())
    maximum=float(np.where(axis>=0,axis*high,axis*low).sum())
    return minimum,maximum


@dataclass
class Geometry:
    poses:np.ndarray
    lower:np.ndarray
    upper:np.ndarray
    extent:np.ndarray
    side_lower:float
    side_upper:float
    clearance:float
    guard:float
    pairs:list
    info:dict


def geometry(poses,trust,side_upper,clearance=1e-8,side_lower=None):
    p=np.asarray(poses,dtype=np.float64).copy();n=len(p)
    if p.shape!=(n,3)or n<2 or not np.isfinite(p).all():raise ValueError('Finite full unit poses required')
    t=np.broadcast_to(np.asarray(trust,dtype=float),(n,)).copy()
    if not np.isfinite(t).all()or min(t)<0 or not math.isfinite(side_upper)or side_upper<=0 or not math.isfinite(clearance)or clearance<0:
        raise ValueError('Invalid finite trust/box/clearance')
    if side_lower is not None and (not math.isfinite(side_lower)or side_lower<=0 or side_lower>side_upper):
        raise ValueError('Invalid enclosure lower bound')
    if side_lower is None and math.sqrt(n)>side_upper:
        raise ValueError('Enclosure upper bound below unit-area lower bound')
    h=.5*(abs(np.cos(p[:,2]))+abs(np.sin(p[:,2])))
    lower=np.maximum(p[:,:2]-t[:,None],h[:,None])
    upper=np.minimum(p[:,:2]+t[:,None],side_upper-h[:,None])
    if np.any(lower>upper):raise ValueError('Empty coordinate trust/wall domain')
    radius=math.sqrt(2)+2*math.sqrt(2)*float(t.max())+1e-8
    candidates=cKDTree(p[:,:2]).query_pairs(radius,output_type='ndarray')
    guard=1e-10*max(1.,side_upper);pairs=[];guaranteed=0;impossible=[]
    for i,j in candidates:
        branches=[];full=[]
        for axis,R in axes_and_radii(p[i,2],p[j,2]):
            lo,hi=projection_bounds(axis,lower[i],upper[i],lower[j],upper[j]);target=R+clearance
            full.append(dict(axis=axis,radius=R,target=target,minimum=lo,maximum=hi,
                             current=float(axis@(p[j,:2]-p[i,:2]))-target))
        if any(b['minimum']>=b['target']+guard for b in full):guaranteed+=1;continue
        branches=[b for b in full if b['maximum']>=b['target']-guard]
        if not branches:impossible.append((int(i),int(j)))
        frozen=max(full,key=lambda b:b['current'])
        pairs.append(dict(i=int(i),j=int(j),branches=branches,frozen=frozen))
    info=dict(n=n,trust_max=float(t.max()),neighbor_radius=radius,
        broad_phase_proof='Each center moves at most sqrt(2)*trust; unit-square circumradius sum is sqrt(2).',
        candidate_pairs=len(candidates),guaranteed_separated_pairs=guaranteed,modeled_pairs=len(pairs),
        pair_domain_impossible=impossible,clearance=clearance,bound_roundoff_guard=guard,
        global_geometry_claim=False)
    return Geometry(p,lower,upper,h,float(side_lower if side_lower is not None else math.sqrt(n)),
                    float(side_upper),float(clearance),guard,pairs,info)


def build(g,selected=(),mode='fixed'):
    if mode not in('fixed','relaxed','milp'):raise ValueError('Unknown local model')
    n=len(g.poses);L=2*n;lower=list(g.lower.ravel())+[g.side_lower];upper=list(g.upper.ravel())+[g.side_upper]
    rr=[];cc=[];vv=[];bounds=[];row_pairs=[];integrality=[0]*(L+1);selection=set(tuple(sorted(x))for x in selected)
    def add(values,bottom,pair=None):
        r=len(bounds);bounds.append(bottom);row_pairs.append(pair)
        for c,v in values.items():
            if v:rr.append(r);cc.append(c);vv.append(v)
    for i in range(n):
        for axis in(0,1):
            add({2*i+axis:1.},g.extent[i]);add({L:1.,2*i+axis:-1.},g.extent[i])
    binary_pairs=0;big_m=[]
    for p in g.pairs:
        i,j=p['i'],p['j'];key=(i,j)
        def coefficients(branch):
            a=branch['axis'];return {2*j:float(a[0]),2*j+1:float(a[1]),2*i:-float(a[0]),2*i+1:-float(a[1])}
        if key in selection and mode=='relaxed':continue
        if key not in selection or mode=='fixed':
            b=p['frozen'];add(coefficients(b),b['target'],key);continue
        if not p['branches']:
            add({},1.,key);continue
        if len(p['branches'])==1:
            b=p['branches'][0];add(coefficients(b),b['target'],key);continue
        binary_pairs+=1;selectors=[]
        for b in p['branches']:
            M=max(0.,b['target']-b['minimum'])+g.guard
            index=len(lower);lower.append(0.);upper.append(1.);integrality.append(1);selectors.append(index)
            coefficients_b=coefficients(b);coefficients_b[index]=-M
            add(coefficients_b,b['target']-M,key)
            big_m.append(dict(pair=list(key),axis=b['axis'].tolist(),target=b['target'],
                              projection_minimum=b['minimum'],M=M))
        add({z:1. for z in selectors},1.,key)
    A=coo_matrix((vv,(rr,cc)),shape=(len(bounds),len(lower))).tocsc();objective=np.zeros(len(lower));objective[L]=1.
    return dict(A=A,lower=np.array(lower),upper=np.array(upper),row_lower=np.array(bounds),
                objective=objective,integrality=np.array(integrality),row_pairs=row_pairs,
                info=dict(mode=mode,variables=len(lower),binary_variables=sum(integrality),binary_pairs=binary_pairs,
                          constraints=len(bounds),selected_pairs=sorted(map(list,selection)),big_m=big_m))


def solve(g,selected=(),mode='fixed',seconds=5.):
    start=time.monotonic();model=build(g,selected,mode);info=dict(g.info,**model['info'])
    if g.info['pair_domain_impossible']:
        return dict(info,status='pair-domain-impossible',seconds=time.monotonic()-start),None
    if mode=='milp':
        fit=milp(model['objective'],integrality=model['integrality'],bounds=Bounds(model['lower'],model['upper']),
            constraints=LinearConstraint(model['A'],model['row_lower'],np.full(len(model['row_lower']),np.inf)),
            options=dict(time_limit=seconds,mip_rel_gap=1e-10,presolve=True,threads=1))
    else:
        fit=linprog(model['objective'],A_ub=-model['A'],b_ub=-model['row_lower'],
            bounds=list(zip(model['lower'],model['upper'])),method='highs',options=dict(time_limit=seconds,threads=1))
    info.update(status=int(fit.status),success=bool(fit.success),message=str(fit.message),seconds=time.monotonic()-start)
    for key in('mip_dual_bound','mip_gap','mip_node_count'):
        value=getattr(fit,key,None)
        if value is not None and np.isfinite(value):info[key]=float(value)
    if fit.x is None:return info,None
    if not np.isfinite(fit.x).all():return dict(info,status='nonfinite_solver_return'),None
    residual=float(np.maximum(model['row_lower']-model['A']@fit.x,0).max(initial=0.))
    domain=max(float(np.maximum(model['lower']-fit.x,0).max(initial=0.)),float(np.maximum(fit.x-model['upper'],0).max(initial=0.)))
    q=g.poses.copy();q[:,:2]=fit.x[:2*len(q)].reshape(-1,2)
    info.update(provisional_side=float(fit.x[2*len(q)]),maximum_constraint_violation=residual,maximum_domain_violation=domain,
                maximum_center_coordinate_motion=float(abs(q[:,:2]-g.poses[:,:2]).max()),
                provisional_only=True)
    if mode!='milp'and fit.success:
        pressure={}
        for pair,value in zip(model['row_pairs'],fit.ineqlin.marginals):
            if pair is not None:pressure[pair]=pressure.get(pair,0.)+abs(float(value))
        endpoint=np.zeros(len(q))
        for (i,j),value in pressure.items():endpoint[i]+=value;endpoint[j]+=value
        info['pair_pressure']=[dict(pair=list(key),own_dual=value,score=value+endpoint[key[0]]+endpoint[key[1]])for key,value in pressure.items()]
    return info,q


def select_pairs(g,fixed_info,budget,seed):
    """Half highest LP/endpoint pressure, half seeded random remaining pairs."""
    if budget<0:raise ValueError('Negative contact budget')
    scores={tuple(r['pair']):r['score']for r in fixed_info.get('pair_pressure',[])}
    eligible=[(r['i'],r['j'])for r in g.pairs if len(r['branches'])>1]
    ranked=sorted(eligible,key=lambda p:(-scores.get(p,0.),p));first=ranked[:min((budget+1)//2,len(ranked))]
    remaining=[p for p in ranked if p not in set(first)];rng=np.random.default_rng(seed)
    if remaining:
        ids=rng.choice(len(remaining),size=min(budget-len(first),len(remaining)),replace=False)
        first.extend(remaining[int(i)]for i in ids)
    return first
