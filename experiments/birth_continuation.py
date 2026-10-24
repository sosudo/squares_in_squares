"""Proposal-only exact-square size continuation; no competition metric changes.

Only the final row may have side lambda in (0,1]. All other rows remain exact
unit squares. Intermediates are not packings for admission. Each growth stage
starts a fresh optimizer, energy and history; no cross-size acceptance rule.
"""
from __future__ import annotations
import math
import numpy as np
import torch


def _directional_mixed_surrogate(dx,dy,ai,aj,si,sj):
    """Exact limiting gradients from ghost-angle approaches in both directions.

    Applying amin/abs autograd separately is invalid at parallel unequal-size
    axes: some tied axes are never locally active. Rank exact active axes by
    their one-sided depth derivative first. Forward values remain exact.
    The last square is always j in these unordered mixed pairs.
    """
    ci,ss_i=ai.cos(),ai.sin();cj,ss_j=aj.cos(),aj.sin()
    delta=ai-aj;co,sn=delta.cos(),delta.sin()
    raw=torch.stack((dx*ci+dy*ss_i,-dx*ss_i+dy*ci,dx*cj+dy*ss_j,-dx*ss_j+dy*cj),-1)
    C=co.abs()+sn.abs();ri=.5*si+.5*sj*C;rj=.5*sj+.5*si*C
    radius=torch.stack((ri,ri,rj,rj),-1)
    exact_depth=radius-raw.abs();minimum=exact_depth.amin(-1)
    answer=[]
    for direction in (-1.,1.):
        # delta=ai-aj, hence only the j/ghost angle changes with -direction.
        co_dot=sn*direction;sn_dot=-co*direction
        co_sign=torch.where(co!=0,co.sign(),co_dot.sign()).detach()
        sn_sign=torch.where(sn!=0,sn.sign(),sn_dot.sign()).detach()
        Cdot=co_sign*co_dot+sn_sign*sn_dot
        zero=torch.zeros_like(dx)
        raw_dot=torch.stack((zero,zero,(-dx*ss_j+dy*cj)*direction,
                             (-dx*cj-dy*ss_j)*direction),-1)
        raw_sign=torch.where(raw!=0,raw.sign(),raw_dot.sign()).detach()
        radius_dot=torch.stack((.5*sj*Cdot,.5*sj*Cdot,.5*si*Cdot,.5*si*Cdot),-1)
        depth_dot=radius_dot-raw_sign*raw_dot
        active=exact_depth.detach()==minimum.detach()[...,None]
        best=torch.where(active,depth_dot.detach(),torch.inf).amin(-1)
        selected=(active & (depth_dot.detach()==best[...,None])).to(dx.dtype)
        def limit_abs(value,sign):return value.abs().detach()+(value-value.detach())*sign
        Clim=limit_abs(co,co_sign)+limit_abs(sn,sn_sign)
        ril=.5*si+.5*sj*Clim;rjl=.5*sj+.5*si*Clim
        depthlim=torch.stack((ril,ril,rjl,rjl),-1)-limit_abs(raw,raw_sign)
        selected_depth=(depthlim*selected).sum(-1)/selected.sum(-1)
        answer.append(selected_depth.clamp_min(0.).square())
    return (answer[0]+answer[1])*.5


def mixed_energy(poses, boxes, birth_size):
    """Dense FP64 four-axis SAT and walls, differentiable in center/angle.

    Exact tied active axes receive equal weights (torch.amin). Returns a
    numerical overlap objective, never a feasibility certificate.
    """
    if poses.dtype != torch.float64 or poses.ndim != 3 or poses.shape[-1] != 3:
        raise ValueError('FP64 batch,n,3 poses required')
    B,N,_ = poses.shape
    if N < 2 or boxes.shape != (B,2) or boxes.dtype != torch.float64:
        raise ValueError('FP64 positive rectangle per chain required')
    if not math.isfinite(float(birth_size)) or not 0 < birth_size <= 1:
        raise ValueError('Only a positive at-most-unit birth size is permitted')
    if not bool(torch.isfinite(poses).all() and torch.isfinite(boxes).all() and (boxes > 0).all()):
        raise ValueError('Finite poses and positive boxes required')
    size = torch.ones(N,dtype=poses.dtype,device=poses.device)
    size[-1] = birth_size
    x,y,a = poses.unbind(-1); c,s = a.cos(),a.sin()
    half = .5*size[None,:]*(c.abs()+s.abs())
    wall = torch.stack((half-x,x+half-boxes[:,0,None],half-y,y+half-boxes[:,1,None]),-1).clamp_min(0.)
    ii,jj = torch.triu_indices(N,N,1,device=poses.device)
    dx,dy = x[:,jj]-x[:,ii],y[:,jj]-y[:,ii]
    delta = a[:,ii]-a[:,jj]
    C = delta.cos().abs()+delta.sin().abs()
    ri = .5*size[ii][None,:]+.5*size[jj][None,:]*C
    rj = .5*size[jj][None,:]+.5*size[ii][None,:]*C
    pen = torch.stack((ri-(dx*c[:,ii]+dy*s[:,ii]).abs(),
                       ri-(-dx*s[:,ii]+dy*c[:,ii]).abs(),
                       rj-(dx*c[:,jj]+dy*s[:,jj]).abs(),
                       rj-(-dx*s[:,jj]+dy*c[:,jj]).abs()),-1).amin(-1).clamp_min(0.)
    pair_energy=pen.square().sum(1)
    if birth_size<1.:
        mixed=jj==N-1
        exact_mixed=pen[:,mixed].square().sum(1)
        surrogate=_directional_mixed_surrogate(dx[:,mixed],dy[:,mixed],a[:,ii[mixed]],a[:,jj[mixed]],1.,birth_size).sum(1)
        pair_energy=pair_energy+(surrogate-surrogate.detach())-(exact_mixed-exact_mixed.detach())
    return dict(energy=wall.square().sum((1,2))+pair_energy,
                max_pair=pen.amax(1),max_wall=wall.amax((1,2)),
                sizes=size,wall_energy=wall.square().sum((1,2)),pair_energy=pair_energy)


def numpy_oracle(p,box,birth_size):
    """Independent corner-projection reference, all pairs and all four walls."""
    p = np.asarray(p,dtype=np.float64); box = np.asarray(box,dtype=np.float64)
    if p.ndim != 2 or p.shape[1] != 3 or len(p)<2 or box.shape != (2,) or not np.isfinite(p).all():
        raise ValueError('Invalid reference geometry')
    if not np.isfinite(box).all() or min(box)<=0 or not 0 < birth_size <= 1:
        raise ValueError('Invalid sizes or box')
    sizes=np.ones(len(p)); sizes[-1]=birth_size
    unit=np.array([[-.5,-.5],[-.5,.5],[.5,.5],[.5,-.5]])
    corners=[]
    for row,size in zip(p,sizes):
        c,s=math.cos(row[2]),math.sin(row[2]); R=np.array([[c,-s],[s,c]])
        corners.append(size*unit@R.T+row[:2])
    corner=np.asarray(corners); w=np.maximum(0.,np.stack((-corner[:,:,0].min(1),corner[:,:,0].max(1)-box[0],
                                                       -corner[:,:,1].min(1),corner[:,:,1].max(1)-box[1]),-1))
    pair=0.; maximum=0.
    for i in range(len(p)):
        for j in range(i+1,len(p)):
            depths=[]
            for k in (i,j):
                c,s=math.cos(p[k,2]),math.sin(p[k,2])
                for axis in (np.array([c,s]),np.array([-s,c])):
                    a=corner[i]@axis; b=corner[j]@axis
                    # SAT interval distance uses centers/radii; interval
                    # intersection length is incorrect for contained shapes.
                    depths.append((a.max()-a.min()+b.max()-b.min())/2-
                                  abs((a.max()+a.min()-b.max()-b.min())/2))
            depth=max(0.,min(depths)); pair+=depth*depth; maximum=max(maximum,depth)
    return dict(energy=float(pair+(w*w).sum()),pair_energy=float(pair),wall_energy=float((w*w).sum()),
                max_pair=maximum,max_wall=float(w.max(initial=0)),unit_sizes=sizes.tolist())


def unit_reference(poses,boxes):
    """Independent unit-only formula; equal tied-axis weights, no size branch."""
    x,y,a=poses.unbind(-1); c,s=a.cos(),a.sin(); N=poses.shape[1]
    half=.5*(c.abs()+s.abs())
    wall=torch.stack((half-x,x+half-boxes[:,0,None],half-y,y+half-boxes[:,1,None]),-1).clamp_min(0.)
    i,j=torch.triu_indices(N,N,1,device=poses.device)
    dx,dy=x[:,j]-x[:,i],y[:,j]-y[:,i]
    delta=a[:,i]-a[:,j]; radius=.5+.5*(delta.cos().abs()+delta.sin().abs())
    projection=torch.stack(((dx*c[:,i]+dy*s[:,i]).abs(),(-dx*s[:,i]+dy*c[:,i]).abs(),
                            (dx*c[:,j]+dy*s[:,j]).abs(),(-dx*s[:,j]+dy*c[:,j]).abs()),-1)
    pen=(radius-projection.amax(-1)).clamp_min(0.)
    return wall.square().sum((1,2))+pen.square().sum(1)


def cpu_quench(p,box,birth_size,steps=300):
    """Fresh finite scipy L-BFGS history for precisely one fixed-size stage."""
    from scipy.optimize import minimize
    p=np.asarray(p,dtype=np.float64); boxes=torch.tensor(np.asarray(box)[None,:],dtype=torch.float64)
    def evaluate(flat):
        q=torch.tensor(flat.reshape(1,len(p),3),dtype=torch.float64,requires_grad=True)
        e=mixed_energy(q,boxes,birth_size)['energy'].sum(); e.backward()
        return float(e.detach()),q.grad.detach().numpy().reshape(-1).copy()
    result=minimize(evaluate,p.ravel(),jac=True,method='L-BFGS-B',
                    options=dict(maxiter=steps,maxls=50,ftol=1e-30,gtol=1e-12,maxcor=12))
    return result.x.reshape(p.shape),dict(success=bool(result.success),message=str(result.message),
        iterations=int(result.nit),evaluations=int(result.nfev),energy=float(result.fun),fresh_history=True)
