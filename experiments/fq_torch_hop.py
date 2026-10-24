"""Physical-energy persistent hopping helpers; ALM objective is never acceptance.

Move scales and ratio acceptance adapt Evan Daniel's MIT packer, commit
659ee62e4a9d39542a1146e8b011cc3ab6407ede. No jam-line operator is claimed.
"""
from __future__ import annotations
import math
import numpy as np
import torch

OPERATORS=('shake','cluster_rotation','cluster_translation','strip_slide')
WEIGHTS=np.array([2.,2.,3.,3.])/10


@torch.no_grad()
def physical_energy(poses,sides):
    """Fresh all-unordered-pairs four-axis SAT + four walls, exact unit shape.

    Returns squared-penetration sums, not a feasibility certificate. There is
    no neighbor list, smoothing, rounding, multiplier, or ALM penalty factor.
    """
    if poses.dtype!=torch.float64 or poses.ndim!=3 or poses.shape[-1]!=3:
        raise ValueError('FP64 [batch,n,3] poses required')
    B,N,_=poses.shape
    if sides.shape!=(B,)or sides.dtype!=torch.float64:raise ValueError('FP64 side per chain required')
    if not bool(torch.isfinite(poses).all()and torch.isfinite(sides).all()and(sides>0).all()):
        raise ValueError('Finite positive fixed boxes required')
    x,y,t=poses.unbind(-1);extent=.5*(t.cos().abs()+t.sin().abs())
    wall=torch.stack((extent-x,x+extent-sides[:,None],extent-y,y+extent-sides[:,None]),-1).clamp_min(0.)
    per=wall.square().sum(-1);wall_energy=per.sum(1)
    i,j=torch.triu_indices(N,N,1,device=poses.device)
    dx=x[:,j]-x[:,i];dy=y[:,j]-y[:,i];a=t[:,i];b=t[:,j]
    penetration=torch.full_like(dx,torch.inf)
    for owner,other in((a,b),(b,a)):
        for offset in(0.,math.pi/2):
            phi=owner+offset;relative=phi-other
            radius=.5+.5*(relative.cos().abs()+relative.sin().abs())
            penetration=torch.minimum(penetration,radius-(dx*phi.cos()+dy*phi.sin()).abs())
    penetration=penetration.clamp_min(0.);pair_square=penetration.square()
    per.scatter_add_(1,i[None].expand(B,-1),.5*pair_square)
    per.scatter_add_(1,j[None].expand(B,-1),.5*pair_square)
    pair_energy=pair_square.sum(1)
    return dict(energy=wall_energy+pair_energy,per_square=per,wall_energy=wall_energy,pair_energy=pair_energy,
                max_wall=wall.amax((1,2)),max_pair=penetration.amax(1)if N>1 else torch.zeros(B,dtype=poses.dtype,device=poses.device))


def acceptance(current,proposal,temperature,uniform):
    """Exact native ratio rule, with explicit finite/zero-energy handling."""
    current,proposal,temperature,uniform=np.broadcast_arrays(
        np.asarray(current,float),np.asarray(proposal,float),np.asarray(temperature,float),np.asarray(uniform,float))
    if not(np.isfinite(current).all()and(current>=0).all()and np.isfinite(temperature).all()
           and(temperature>0).all()and np.isfinite(uniform).all()and(uniform>=0).all()and(uniform<1).all()):
        raise ValueError('Invalid current energy, temperature or uniform draw')
    valid=np.isfinite(proposal)&(proposal>=0)
    # Native floors energies and U at1e-300; no log(0/0) or invalid ratio.
    log_ratio=np.log(np.maximum(np.where(valid,proposal,np.inf),1e-300))-np.log(np.maximum(current,1e-300))
    threshold=-temperature*np.log(np.maximum(uniform,1e-300))
    accepted=valid&((proposal<current)|(log_ratio<threshold))
    return accepted,dict(log_ratio=log_ratio,threshold=threshold,uphill=valid&(proposal>current),
                         proposal_finite_nonnegative=valid)


def chain_design(source_keys):
    """Finite32-chain design: each temperature split exactly by amp and box."""
    if len(source_keys)!=3:raise ValueError('Exactly three reviewed335 sources required')
    rows=[]
    for temperature,count in((.3,8),(1.,12),(3.,12)):
        for amp_index,amplitude in enumerate((1.,1.5)):
            for box_index,side in enumerate((18.807,18.803)):
                for repeat in range(count//4):
                    source=source_keys[(repeat+amp_index+box_index)%3]
                    rows.append(dict(chain=len(rows),temperature=temperature,amplitude=amplitude,
                                     side=side,source_key=source))
    assert len(rows)==32
    return rows


def mutate(p,per_square,rng,amplitude,operator=None):
    """Apply a realized physical move to the accepted full-count pose."""
    p=np.asarray(p,dtype=np.float64);q=p.copy();load=np.maximum(np.asarray(per_square,float),0.)
    if p.ndim!=2 or p.shape[1]!=3 or len(load)!=len(p)or not np.isfinite(p).all():raise ValueError('Invalid mutation source')
    hot=bool(rng.random()<.5 and np.isfinite(load).all()and load.sum()>0)
    center=int(rng.choice(len(p),p=load/load.sum()))if hot else int(rng.integers(len(p)))
    operator=str(rng.choice(OPERATORS,p=WEIGHTS))if operator is None else operator
    if operator not in OPERATORS:raise ValueError('Unknown physical move')
    pivot=p[center,:2];distance=np.linalg.norm(p[:,:2]-pivot,axis=1)
    details=dict(operator=operator,center=center,center_selection='energy_weighted'if hot else'uniform',amplitude=float(amplitude))
    if operator=='shake':
        radius=float(1+2.5*rng.random());selected=np.flatnonzero(distance<radius)
        position_sigma=float(amplitude*(.05+.3*rng.random()));angle_sigma=float(amplitude*.15*rng.random())
        q[selected,:2]+=rng.normal(0,position_sigma,(len(selected),2));q[selected,2]+=rng.normal(0,angle_sigma,len(selected))
        details.update(radius=radius,position_sigma=position_sigma,angle_sigma=angle_sigma)
    elif operator=='cluster_rotation':
        radius=float(1+2.5*rng.random());selected=np.flatnonzero(distance<radius);angle=float(amplitude*.15*rng.normal())
        c,s=math.cos(angle),math.sin(angle);q[selected,:2]=(p[selected,:2]-pivot)@np.array([[c,s],[-s,c]])+pivot;q[selected,2]+=angle
        details.update(radius=radius,angle=angle,pivot=pivot.tolist())
    elif operator=='cluster_translation':
        radius=float(1+3*rng.random());selected=np.flatnonzero(distance<radius);shift=rng.normal(0,amplitude*.3,2)
        q[selected,:2]+=shift;details.update(radius=radius,shift=shift.tolist())
    else:
        horizontal=bool(rng.random()<.5);axis=0 if horizontal else 1;perpendicular=1-axis
        half=float(.5+.5*rng.random());direction=1 if rng.random()<.5 else-1
        cut=float(pivot[axis]+rng.random()-.5)
        selected=np.flatnonzero((abs(p[:,perpendicular]-pivot[perpendicular])<half)&((p[:,axis]-cut)*direction>0))
        forced=False
        if not len(selected):
            cut=float(pivot[axis]-.1*direction);forced=True
            selected=np.flatnonzero((abs(p[:,perpendicular]-pivot[perpendicular])<half)&((p[:,axis]-cut)*direction>0))
        shift=float(amplitude*.2*rng.normal());q[selected,axis]+=shift
        details.update(horizontal=horizontal,half_width=half,direction=direction,cut=cut,shift=shift,forced_cut_includes_center=forced)
    changed=np.flatnonzero(np.any(q!=p,axis=1))
    details.update(selected_ids=selected.tolist(),selected_count=len(selected),changed_ids=changed.tolist(),changed_count=len(changed),
                   maximum_position_step=float(np.linalg.norm(q[:,:2]-p[:,:2],axis=1).max()),
                   maximum_angle_step=float(abs(q[:,2]-p[:,2]).max()),jam_line_claimed=False)
    assert len(selected)>0 and q.shape==p.shape and np.isfinite(q).all()
    return q,details
