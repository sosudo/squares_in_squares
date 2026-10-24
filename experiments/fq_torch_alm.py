"""Minimal independent FP64 batched lifted ALM; no admission logic.

Geometry/PHR equations follow Evan Daniel's MIT FQ, commit659ee62e4a9d39542a1146e8b011cc3ab6407ede.
Every raw result remains unverified until the unchanged full geometry gates.
"""
import math
import numpy as np
import torch
from fq_torch_objective import near_pairs,rounded_offsets


def independent_lbfgs(x,evaluate,valid,steps=40,history=7,max_step=.05,tolerance=1e-9,backtracks=18):
    """Independent two-loop directions/Armijo searches, including failures."""
    x=x.detach().clone();B,D=x.shape;device=x.device
    if not bool(valid(x).all()):raise ValueError('Initial state violates trial domain')
    f,g=evaluate(x);f=f.detach();g=g.detach()
    if not bool(torch.isfinite(f).all()and torch.isfinite(g).all()):raise ValueError('Initial objective is nonfinite')
    S=torch.zeros((B,history,D),dtype=x.dtype,device=device);Y=torch.zeros_like(S)
    curvature=torch.ones((B,history),dtype=x.dtype,device=device)
    head=torch.zeros(B,dtype=torch.long,device=device);count=head.clone();ids=torch.arange(B,device=device)
    accepted_count=head.clone();failed_count=head.clone();trials_count=head.clone()
    for iteration in range(steps):
        active=torch.isfinite(f)&torch.isfinite(g).all(1)&(g.abs().amax(1)>tolerance)
        if not bool(active.any()):break
        q=g.clone();alphas=[];indices=[];masks=[]
        for j in range(history):
            index=(head-1-j)%history;mask=j<count
            alpha=torch.where(mask,(S[ids,index]*q).sum(1)/curvature[ids,index],0.)
            q=q-alpha[:,None]*Y[ids,index];alphas.append(alpha);indices.append(index);masks.append(mask)
        last=(head-1)%history
        gamma=torch.where(count>0,curvature[ids,last]/Y[ids,last].square().sum(1).clamp_min(1e-30),1.).clamp(1e-8,1e8)
        direction=q*gamma[:,None]
        for j in reversed(range(history)):
            index=indices[j];beta=torch.where(masks[j],(Y[ids,index]*direction).sum(1)/curvature[ids,index],0.)
            direction=direction+S[ids,index]*(alphas[j]-beta)[:,None]
        direction=-direction
        slope=(g*direction).sum(1)
        fallback=(~torch.isfinite(direction).all(1))|(slope>=0)
        direction=torch.where(fallback[:,None],-g,direction);slope=(g*direction).sum(1)
        step=torch.minimum(torch.ones_like(f),max_step/direction.abs().amax(1).clamp_min(1e-30))
        accepted=torch.zeros(B,dtype=torch.bool,device=device)
        next_x=x.clone();next_f=f.clone();next_g=g.clone()
        for attempt in range(backtracks):
            pending=active&~accepted
            if not bool(pending.any()):break
            trial=x+step[:,None]*direction
            safe=valid(trial)&torch.isfinite(trial).all(1)&pending
            # Unsafe candidates never reach the objective, even in padded rows.
            evaluated=torch.where(safe[:,None],trial,x)
            tf,tg=evaluate(evaluated);tf=tf.detach();tg=tg.detach()
            good=safe&torch.isfinite(tf)&torch.isfinite(tg).all(1)&(tf<=f+1e-4*step*slope)
            next_x=torch.where(good[:,None],trial,next_x)
            next_f=torch.where(good,tf,next_f);next_g=torch.where(good[:,None],tg,next_g)
            trials_count+=pending.long();accepted|=good
            step=torch.where(pending&~good,step*.5,step)
        delta=next_x-x;change=next_g-g;ys=(delta*change).sum(1)
        usable=accepted&(ys>1e-12*torch.linalg.vector_norm(delta,dim=1)*torch.linalg.vector_norm(change,dim=1))&(ys>1e-25)
        update_ids=ids[usable];slots=head[usable]
        S[update_ids,slots]=delta[usable];Y[update_ids,slots]=change[usable];curvature[update_ids,slots]=ys[usable]
        head=torch.where(usable,(head+1)%history,head);count=torch.where(usable,(count+1).clamp_max(history),count)
        accepted_count+=accepted.long();failed_count+=(active&~accepted).long()
        x,f,g=next_x,next_f,next_g
        if not bool(accepted.any()):break
    return x,dict(value=f,gradient=g,accepted_steps=accepted_count,failed_lines=failed_count,
                  trial_evaluations=trials_count,history_count=count,history_head=head,
                  history_s=S,history_y=Y,history_curvature=curvature)


def initialize_lines(poses,pairs,radius):
    B=poses.shape[0];ids=torch.arange(B,device=poses.device)[:,None]
    i,j=pairs[...,0],pairs[...,1];a,b=poses[ids,i],poses[ids,j]
    delta=b[...,:2]-a[...,:2]
    angles=torch.stack((a[...,2],a[...,2]+math.pi/2,b[...,2],b[...,2]+math.pi/2,
                        torch.atan2(delta[...,1],delta[...,0])),dim=-1)
    u=torch.stack((angles.cos(),angles.sin()),dim=-1)
    angles=angles+torch.where((delta[:,:,None]*u).sum(-1)<0,math.pi,0.)
    u=torch.stack((angles.cos(),angles.sin()),dim=-1)
    offsets=rounded_offsets(poses,radius)
    first=offsets[ids,i]-.5*delta[:,:,None];second=offsets[ids,j]+.5*delta[:,:,None]
    hi=(first[:,:,None]*u[:,:,:,None]).sum(-1).amax(-1)
    lo=(second[:,:,None]*u[:,:,:,None]).sum(-1).amin(-1)
    best=(lo-hi).argmax(-1,keepdim=True)
    phi=angles.gather(-1,best).squeeze(-1);d=((lo+hi)*.5).gather(-1,best).squeeze(-1)
    return torch.stack((phi,d),dim=-1)


class LiftedBatch:
    """Per-replica sparse state; lists change only at accepted outer boundaries."""
    def __init__(self,poses,sides,skin=.3,mu0=10.):
        if poses.dtype!=torch.float64 or not torch.isfinite(poses).all():raise ValueError('Finite FP64 poses required')
        if sides.dtype!=torch.float64 or sides.shape!=(len(poses),)or not torch.isfinite(sides).all():raise ValueError('Finite FP64 side per replica required')
        self.B,self.N,_=poses.shape;self.device=poses.device;self.skin=skin
        self.poses=poses.detach().clone();self.sides=sides.detach().clone()
        self.wall_lambda=torch.zeros((self.B,self.N,4,4),dtype=poses.dtype,device=self.device)
        self.mu=torch.full((self.B,),mu0,dtype=poses.dtype,device=self.device)
        self.pair_ids=None;self.lines=None;self.pair_lambda=None;self.mask=None
        self.rebuild(0.)

    def rebuild(self,radius):
        """Transport identical pair IDs exactly; initialize only new pairs."""
        lists=[near_pairs(p,self.skin)for p in self.poses.detach().cpu().numpy()]
        P=max(1,max(map(len,lists)));pairs=torch.zeros((self.B,P,2),dtype=torch.long,device=self.device)
        mask=torch.zeros((self.B,P),dtype=torch.bool,device=self.device)
        for b,ids in enumerate(lists):
            pairs[b,:len(ids)]=torch.as_tensor(ids,device=self.device);mask[b,:len(ids)]=True
        lines=initialize_lines(self.poses,pairs,radius)
        lam=torch.zeros((self.B,P,8),dtype=self.poses.dtype,device=self.device)
        retained=new=removed=0
        if self.pair_ids is not None:
            old_ids=self.pair_ids.detach().cpu().tolist();old_masks=self.mask.detach().cpu().tolist()
            for b,ids in enumerate(lists):
                old={tuple(ij):k for k,ij in enumerate(old_ids[b])if old_masks[b][k]}
                old_index=[];new_index=[]
                for k,ij in enumerate(ids):
                    source=old.get(tuple(ij))
                    if source is not None:old_index.append(source);new_index.append(k)
                if old_index:
                    lines[b,new_index]=self.lines[b,old_index];lam[b,new_index]=self.pair_lambda[b,old_index]
                retained+=len(old_index);new+=len(ids)-len(old_index);removed+=len(old)-len(old_index)
        else:new=sum(map(len,lists))
        self.pair_ids=pairs;self.mask=mask;self.lines=lines.masked_fill(~mask[...,None],0.)
        self.pair_lambda=lam;self.reference=self.poses.detach().clone()
        return dict(retained=retained,new=new,removed=removed,pair_counts=mask.sum(1).cpu().tolist(),padded_pairs=P)

    def pack(self):return torch.cat((self.poses.flatten(1),self.sides[:,None],self.lines.flatten(1)),1)

    def unpack(self,x):
        self.poses=x[:,:3*self.N].reshape(self.B,self.N,3).detach().clone()
        self.sides=x[:,3*self.N].detach().clone()
        self.lines=x[:,3*self.N+1:].reshape(self.B,-1,2).detach().clone()

    def valid(self,x):
        p=x[:,:3*self.N].reshape(self.B,self.N,3)
        displacement=torch.linalg.vector_norm(p[...,:2]-self.reference[...,:2],dim=-1).amax(1)
        return torch.isfinite(x).all(1)&(2*displacement<self.skin-1e-9)&(x[:,3*self.N]>0.)

    def constraints(self,x,radius,fixed):
        p=x[:,:3*self.N].reshape(self.B,self.N,3);s=x[:,3*self.N]
        if fixed:s=s.detach()
        line=x[:,3*self.N+1:].reshape(self.B,-1,2)
        offsets=rounded_offsets(p,radius);corners=p[:,:,:2,None].transpose(-1,-2)+offsets
        cx,cy=corners[...,0],corners[...,1]
        wall=torch.stack((-cx+radius,cx-s[:,None,None]+radius,-cy+radius,cy-s[:,None,None]+radius),-1)
        ids=torch.arange(self.B,device=self.device)[:,None];i,j=self.pair_ids[...,0],self.pair_ids[...,1]
        half=.5*(p[ids,i,:2]-p[ids,j,:2]);u=torch.stack((line[...,0].cos(),line[...,0].sin()),-1)
        first=((half[:,:,None]+offsets[ids,i])*u[:,:,None]).sum(-1)-line[...,1,None]+radius
        second=line[...,1,None]-((-half[:,:,None]+offsets[ids,j])*u[:,:,None]).sum(-1)+radius
        return wall,torch.cat((first,second),-1)

    def value_grad(self,x,radius,fixed):
        x=x.detach().requires_grad_();wall,pair=self.constraints(x,radius,fixed)
        wm=self.mu[:,None,None,None];pm=self.mu[:,None,None]
        wt=.5*wm*torch.relu(wall+self.wall_lambda/wm).square()-self.wall_lambda.square()/(2*wm)
        pt=.5*pm*torch.relu(pair+self.pair_lambda/pm).square()-self.pair_lambda.square()/(2*pm)
        value=(x[:,3*self.N]*0 if fixed else x[:,3*self.N])+wt.flatten(1).sum(1)+(pt*self.mask[...,None]).flatten(1).sum(1)
        gradient=torch.autograd.grad(value.sum(),x)[0]
        return value.detach(),gradient.detach()

    def stage(self,radius,fixed=True,outer=6,inner=40,mu0=10.,tolerance=1e-8,callback=None,deadline=None):
        # A physical shape/held-side stage is a new objective, explicitly
        # restarted. Within it, every pair-list rebuild transports state.
        self.mu.fill_(mu0);self.wall_lambda.zero_();self.pair_lambda.zero_()
        previous=torch.full_like(self.mu,float('inf'));records=[]
        for iteration in range(outer):
            if deadline is not None and deadline():break
            mapping=self.rebuild(radius);x=self.pack()
            x,solver=independent_lbfgs(x,lambda q:self.value_grad(q,radius,fixed),self.valid,
                                      steps=inner,tolerance=tolerance)
            self.unpack(x);wall,pair=self.constraints(x,radius,fixed)
            violation=torch.maximum(wall.flatten(1).amax(1),pair.masked_fill(~self.mask[...,None],-torch.inf).flatten(1).amax(1)).clamp_min(0.)
            record=dict(iteration=iteration,radius=radius,fixed_side=fixed,mu=self.mu.cpu().tolist(),
                        violation=violation.cpu().tolist(),accepted_steps=solver['accepted_steps'].cpu().tolist(),
                        failed_lines=solver['failed_lines'].cpu().tolist(),pair_mapping=mapping,
                        sides=self.sides.cpu().tolist(),verified=False)
            records.append(record)
            # Raw stage callback happens before objective/multiplier changes.
            if callback is not None:callback(self.poses.detach().clone(),record)
            self.wall_lambda=(self.wall_lambda+self.mu[:,None,None,None]*wall).clamp_min(0.)
            self.pair_lambda=torch.where(self.mask[...,None],(self.pair_lambda+self.mu[:,None,None]*pair).clamp_min(0.),0.)
            increase=violation>.25*previous
            self.mu=torch.where(increase,(10*self.mu).clamp_max(1e6),self.mu);previous=violation.detach()
            if bool((violation<tolerance).all()):break
        return records
