"""Mandatory actual-device mixed-size controls before finite birth search."""
from __future__ import annotations
import math,time
from pathlib import Path
import numpy as np
import torch
from birth_continuation import mixed_energy,numpy_oracle,unit_reference
from fq_capacity_probe import full_certificate
from compose_gadgets import legalize


def live_preflight(solver,initial,sides,device,out):
    torch.set_num_threads(1);torch.cuda.set_device(device);cp=solver.cp
    start=time.monotonic();records=[]
    assert 'T4' in torch.cuda.get_device_name(device)
    def compare(p,L,size,label,gradient=True):
        e,g=solver.energy(np.asarray(p)[None],[L],size)
        q=torch.tensor(np.asarray(p)[None],dtype=torch.float64,requires_grad=gradient)
        value=mixed_energy(q,torch.tensor([[L,L]],dtype=torch.float64),size)['energy'].sum()
        err=abs(float(value.detach())-e[0,0]);assert err<1e-8+1e-10*abs(e[0,0])
        ge=None
        if gradient:
            value.backward();ge=float(np.max(abs(g[0]-q.grad.detach().numpy()[0])))
            assert ge<2e-7+2e-9*float(np.max(abs(g)))
        if len(p)<=8:assert abs(e[0,0]-numpy_oracle(p,[L,L],size)['energy'])<1e-10
        records.append(dict(label=label,n=len(p),birth_size=size,energy=float(e[0,0]),energy_error=err,maximum_gradient_error=ge))
        return e,g
    # Unequal parallel tie regression, all-unit corner tie, radial/cell boundary.
    fixtures=[(np.array([[1.,1.,0.],[1.5,1.3,0.]]),4.,.2,'unequal_parallel_tie'),
              (np.array([[1.,1.,0.],[1.8,1.8,0.]]),4.,1.,'unit_corner_tie'),
              (np.array([[1.49,1.49,math.pi/4],[2.89,1.49,math.pi/4]]),4.,1.,'radial_cell_boundary'),
              (np.array([[.42,.71,.13],[1.1,.9,.57],[1.8,.45,-.27],[1.49,1.49,.37]]),2.2,.61,'untied_fd')]
    for p,L,size,label in fixtures:compare(p,L,size,label)
    # Actual numerical central differences only on a differentiable fixture.
    p,L,size,_=fixtures[-1];_,g=solver.energy(p[None],[L],size);fd=[]
    for i,k in ((0,0),(0,2),(2,1),(3,0),(3,2)):
        plus=p.copy();minus=p.copy();plus[i,k]+=1e-6;minus[i,k]-=1e-6
        value=(solver.energy(plus[None],[L],size)[0][0,0]-solver.energy(minus[None],[L],size)[0][0,0])/2e-6
        fd.append(abs(value-g[0,i,k]));assert fd[-1]<5e-7
    n=initial.shape[1];assert n in (498,587)and initial.shape==(32,n,3)and len(sides)==32
    for index in (0,15,31):
        for size in (.05,.5,1.):compare(initial[index],float(sides[index]),size,f'actual_{n}_chain{index}')
    # Deliberate last-row overlap and wall violations beyond CUDA block size256.
    last=initial[0].copy();last[-1]=last[0]+[.1,.1,.13]
    e,g=compare(last,float(sides[0]),.6,'actual_last_row_collision')
    assert e[0,0]>.001 and np.linalg.norm(g[0,-1])>1e-5
    wall=initial[0].copy();wall[-1]=[-.2,-.3,.27]
    e,g=compare(wall,float(sides[0]),.05,'actual_last_row_wall');assert e[0,1]>.2
    # Every initial small birth must actually fit; old units remain side1.
    tiny,tiny_g=solver.energy(initial,sides,.05)
    assert tiny.shape==(32,2)and np.isfinite(tiny).all()and np.max(tiny[:,1])<1e-8
    # Nontrivial live optimization, not only an already-fitting size1 fixture.
    q=np.array([[.55,.55,0.],[2.17,.55,0.],[.55,2.17,0.],[2.17,2.17,0.],[1.36,1.36,math.pi/4]])
    old=q.copy();before=solver.energy(q[None],[2.72],1.)[0][0,0];assert before>.001
    growth=[]
    for size in (.05,.2,.4,.6,.8,1.):
        q,info=solver.quench(q[None],[2.72],size,steps=1200);q=q[0]
        exact=solver.energy(q[None],[2.72],size)[0]
        growth.append(dict(size=size,energy=float(exact[0,0]),max_overlap=float(exact[0,1]),fresh_history=True))
    assert solver.energy(q[None],[2.72],1.)[0][0,1]<2e-8
    movement=float(np.linalg.norm(q[:4,:2]-old[:4,:2],axis=1).max());assert movement>.02
    repaired=legalize(q.copy(),clearance=2e-9);assert repaired is not None
    certificate=full_certificate(repaired);assert certificate['valid']
    np.savez_compressed(out/'growth-control.npz',initial=old,returned=q,certified=repaired)
    # An actual32-chain stage launches after all detailed controls, then fresh
    # evaluation verifies finite full-count storage and untouched input bytes.
    saved=initial.copy();smoke,info=solver.quench(initial,sides,np.full(32,.2),steps=30)
    assert np.array_equal(saved,initial)and smoke.shape==initial.shape and np.isfinite(smoke).all()
    after=solver.energy(smoke,sides,.2)[0];assert np.isfinite(after).all()
    cp.cuda.get_current_stream().synchronize()
    result=dict(passed=True,device=device,device_name=torch.cuda.get_device_name(device),seconds=time.monotonic()-start,
        actual_n=n,actual_chains=32,records=records,maximum_untied_fd_error=max(fd),
        initial_tiny_max_overlap=float(tiny[:,1].max()),growth_stages=growth,
        existing_unit_center_movement=movement,growth_final_certificate=certificate,
        source_audit=solver.audit,proposal_input_unchanged=True,
        all_unit_lambda1_identity_checked=True,actual_last_index_and_neighbor_controls=True,
        scope='Actual CUDA mathematical/storage/finite-growth controls; no production convergence or feasibility claim.')
    return result
