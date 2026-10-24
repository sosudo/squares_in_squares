"""Mandatory actual-CUDA precision/coverage controls for a finite diagnostic."""
from __future__ import annotations
import math
import numpy as np
from full_structural_gpu_ties import check_cuda, _pair, _hull_distance


def physical_metrics(torch,poses,boxes):
    from fq_torch_hop import physical_energy
    if not np.array_equal(boxes[:,0],boxes[:,1]):
        raise ValueError('square_original_boxes_required')
    p = torch.as_tensor(poses,dtype=torch.float64,device='cuda') if isinstance(poses,np.ndarray) else torch.utils.dlpack.from_dlpack(poses)
    if p.dtype != torch.float64 or not p.is_cuda:
        raise ValueError('physical_oracle_requires_FP64_CUDA')
    sides = torch.as_tensor(boxes[:,0].copy(),dtype=torch.float64,device='cuda')
    values = physical_energy(p,sides); torch.cuda.synchronize()
    return {key:value.detach().cpu().numpy() for key,value in values.items() if key != 'per_square'}


def rounded_coverage(pose,box):
    """Dense exact-unit SAT versus declared promoted broad-phase guards."""
    n = len(pose); i,j = np.triu_indices(n,1); delta = pose[j,:2]-pose[i,:2]
    a,b = pose[i,2],pose[j,2]
    proj = np.maximum.reduce([abs(delta[:,0]*np.cos(t)+delta[:,1]*np.sin(t)) for t in (a,a+math.pi/2,b,b+math.pi/2)])
    radius = .5*(1+abs(np.cos(a-b))+abs(np.sin(a-b)))
    overlap = proj < radius
    nc = int(np.ceil((max(box)+6)/1.5))+1
    cells = np.floor((pose[:,:2]+3)/1.5).astype(np.int64).clip(0,nc-1)
    covered = (abs(cells[i]-cells[j]).max(1)<=1)&((delta*delta).sum(1)<=2.00000001)
    missing = int(np.count_nonzero(overlap&~covered))
    if missing:
        raise AssertionError('rounded_exact_unit_broadphase_missed_overlap')
    return dict(n=n,dense_pairs=len(i),overlaps=int(overlap.sum()),missing=missing)


def isolated_last_index_case(n):
    """Full count with one isolated cross-cell pair; no force cancellation."""
    width=int(math.ceil(math.sqrt(n)));ids=np.arange(n)
    q=np.zeros((1,n,3),dtype=np.float64)
    q[0,:,0]=10+3*(ids%width);q[0,:,1]=10+3*(ids//width)
    q[0,0]=[4.49999,5.,.13];q[0,-1]=[4.70001,5.1,.37]
    side=float(12+3*width)
    return q,np.array([[side,side]],dtype=np.float64)


def run_fp64(cp,torch,fp64,fixtures,retain=None):
    report=dict(ties=check_cuda(fp64),full_count=[],passed=True)
    for fixture in fixtures:
        q=fixture['poses'][[0,15,31]].copy();box=fixture['boxes'][[0,15,31]].copy()
        e,g=fp64.energy(q,box);oracle=physical_metrics(torch,q,box)
        expected=2*oracle['wall_energy']+.5*oracle['pair_energy'];K=len(q[0])*(len(q[0])-1)/2; margin=2e-10
        tolerance=margin*np.sqrt(K*oracle['pair_energy'])+.5*margin*margin*K+1e-10*np.maximum(1.,expected)
        assert np.all(abs(e[:,0]-expected)<=tolerance) and np.isfinite(g).all()
        negative,negative_box=isolated_last_index_case(q.shape[1])
        ne,ng=fp64.energy(negative,negative_box);no=physical_metrics(torch,negative,negative_box)
        target=2*no['wall_energy']+.5*no['pair_energy']
        bound=margin*np.sqrt(K*no['pair_energy'])+.5*margin*margin*K+1e-10*np.maximum(1.,target)
        assert ne[0,1]>.1 and np.linalg.norm(ng[0,-1])>.01 and np.all(abs(ne[:,0]-target)<=bound)
        coverage=[rounded_coverage(p,b) for p,b in zip(q,box)]
        z,native=fp64.quench(q[:1],box[:1],0);host=cp.asnumpy(z);assert np.array_equal(host,q[:1])
        if retain is not None:
            retain('fp64-independent-'+fixture['key'],dict(input=q,boxes=box,energy=e,gradient=g,negative=negative,
                negative_boxes=negative_box,negative_energy=ne,negative_gradient=ng,zero_output=host,zero_native=cp.asnumpy(native)),dict(verified=False,fp32_dependency=False))
        report['full_count'].append(dict(key=fixture['key'],n=q.shape[1],dense_oracle_error=(e[:,0]-expected).tolist(),coverage=coverage,
            last_index_penetration=float(ne[0,1]),last_index_gradient_norm=float(np.linalg.norm(ng[0,-1])),zero_steps_unchanged=True))
    try:
        fp64.energy(np.array([[[np.nan,1.,0.]]]),[[3.,3.]])
    except ValueError:
        report['nonfinite_input_rejected_before_objective']=True
    else:
        raise AssertionError('FP64_nonfinite_input_not_rejected')
    return report


def run(cp,torch,fp64,fp32,fixtures,retain=None,fp64_report=None):
    def save(label,arrays):
        if retain is not None:
            retain('control-'+label,arrays,dict(verified=False,scope='Numerical diagnostic control only.'))
    report = dict(fp64_ties=fp64_report if fp64_report is not None else check_cuda(fp64),fp32_ties=[],untied=[],full_count=[],negative=[],zero_update=[])
    eps = np.finfo(np.float32).eps
    for theta in (0.,.31):
        for dy in (.2,.8,.9):
            for tau in (0.,.02):
                p = _pair(theta,dy).astype(np.float32).astype(np.float64)
                box = np.array([[10.,10.]],dtype=np.float32).astype(np.float64)
                et,gt = fp32.energy(p[None],box,tau); er,gr = fp64.energy(p[None],box,float(np.float32(tau)))
                ep,gp = fp32.energy(p[::-1][None],box,tau)
                assert np.isfinite(et).all() and np.isfinite(gt).all()
                assert abs(float(et[0,0]-er[0,0])) < 5e-5
                permutation = float(abs(gt[0]-gp[0,::-1]).max()); assert permutation < 2e-5
                tangent = np.column_stack((-p[:,1],p[:,0],np.ones(2)))
                rigid = abs(float((gt[0]*tangent).sum()))
                rigid_bound = 128*eps*max(1.,float(abs(gt[0]*tangent).sum()))
                assert rigid <= rigid_bound
                h = 2e-4; nearby=[]
                for unit,sign in ((0,1),(0,-1),(1,1),(1,-1)):
                    q=p.copy();q[unit,2]+=sign*h;nearby.append(q)
                _,ng = fp64.energy(np.array(nearby),np.repeat(box,4,0),float(np.float32(tau)))
                hull = _hull_distance(gt[0,:,2],ng[:,:,2]); assert hull < 8e-4
                coherent_error = None
                if dy != .9:
                    plus=p.copy();minus=p.copy();plus[:,2]+=.001;minus[:,2]-=.001
                    fd=(fp32.energy(plus[None],box,tau)[0][0,0]-fp32.energy(minus[None],box,tau)[0][0,0])/.002
                    coherent_error=abs(float(fd-gt[0,:,2].sum()));assert coherent_error < 3e-3
                report['fp32_ties'].append(dict(theta=theta,dy=dy,tau=tau,rounded_energy_error=float(et[0,0]-er[0,0]),
                    permutation_error=permutation,rigid_residual=rigid,rigid_bound=rigid_bound,
                    nearby_angular_hull_distance=hull,coherent_fd_error=coherent_error))
                save(f'tie-{theta}-{dy}-{tau}',dict(poses=p,boxes=box,fp32_energy=et,fp32_gradient=gt,fp64_energy=er,fp64_gradient=gr,nearby_gradients=ng))
    rng=np.random.default_rng(581903)
    p=rng.uniform(.5,2.4,(2,11,3));p[:,:,2]*=.2;boxes=np.array([[3.,3.],[3.2,3.2]])
    rounded=p.astype(np.float32).astype(np.float64);rounded_boxes=boxes.astype(np.float32).astype(np.float64)
    for tau in (0.,.02):
        e,g=fp32.energy(rounded,rounded_boxes,tau);er,gr=fp64.energy(rounded,rounded_boxes,float(np.float32(tau)))
        ge=float(abs(g-gr).max());ee=float(abs(e[:,0]-er[:,0]).max())
        assert ge<8e-4 and ee<8e-4
        fd_errors=[]
        for unit,axis in ((0,0),(2,1),(7,2)):
            plus=rounded.copy();minus=rounded.copy();plus[0,unit,axis]+=.002;minus[0,unit,axis]-=.002
            fd=(fp32.energy(plus,rounded_boxes,tau)[0][0,0]-fp32.energy(minus,rounded_boxes,tau)[0][0,0])/.004
            fd_errors.append(abs(float(fd-g[0,unit,axis])))
        assert max(fd_errors)<.015
        report['untied'].append(dict(tau=tau,rounded_energy_error=ee,rounded_gradient_error=ge,fd_errors=fd_errors))
        save(f'untied-{tau}',dict(poses=rounded,boxes=rounded_boxes,fp32_energy=e,fp32_gradient=g,fp64_energy=er,fp64_gradient=gr))
    # A wall-only case separates wall derivatives from pair-gradient checks.
    wall=np.array([[[.2,.7,.31]]]);box=np.array([[3.,3.]])
    e,g=fp32.energy(wall,box);er,gr=fp64.energy(wall.astype(np.float32).astype(float),box)
    assert abs(e-er).max()<2e-5 and abs(g-gr).max()<2e-5
    report['wall']=dict(energy_error=float(abs(e-er).max()),gradient_error=float(abs(g-gr).max()))
    radial=np.array([[[5.,5.,math.pi/4],[5.+math.sqrt(2)-2e-5,5.,math.pi/4]]],dtype=np.float32).astype(np.float64)
    radial_box=np.array([[10.,10.]])
    re,rg=fp32.energy(radial,radial_box);rr,rrg=fp64.energy(radial,radial_box)
    assert re[0,0]>0 and rr[0,0]>0
    report['radial_boundary']=dict(fp32_energy=float(re[0,0]),rounded_fp64_energy=float(rr[0,0]),coverage=rounded_coverage(radial[0],radial_box[0]))
    save('radial-boundary',dict(poses=radial,boxes=radial_box,fp32_energy=re,fp32_gradient=rg,fp64_energy=rr,fp64_gradient=rrg))
    for fixture in fixtures:
        q=fixture['poses'][[0,15,31]].copy();box=fixture['boxes'][[0,15,31]].copy()
        rounded=q.astype(np.float32).astype(np.float64);rb=box.astype(np.float32).astype(np.float64)
        e,g=fp32.energy(rounded,rb);er,gr=fp64.energy(rounded,rb)
        assert np.isfinite(e).all() and np.isfinite(g).all() and np.isfinite(er).all() and np.isfinite(gr).all()
        oracle=physical_metrics(torch,rounded,rb)
        expected=2*oracle['wall_energy']+.5*oracle['pair_energy']
        K=len(q[0])*(len(q[0])-1)/2; margin=2e-10
        tolerance=margin*np.sqrt(K*oracle['pair_energy'])+.5*margin*margin*K+1e-10*np.maximum(1.,expected)
        assert np.all(abs(er[:,0]-expected)<=tolerance)
        assert np.all(abs(e[:,0]-er[:,0])<5e-4*np.maximum(1.,abs(er[:,0])))
        coverage=[rounded_coverage(p,b) for p,b in zip(rounded,rb)]
        # Last-index collision crosses a hash-cell boundary in both dtypes.
        negative,negative_box=isolated_last_index_case(q.shape[1]);negative=negative.astype(np.float32).astype(np.float64)
        ne,ng=fp32.energy(negative,negative_box);nr,nrg=fp64.energy(negative,negative_box)
        assert ne[0,1]>.1 and np.linalg.norm(ng[0,-1])>.01 and abs(ne[0,0]-nr[0,0])<5e-4*max(1.,nr[0,0])
        rounded_coverage(negative[0],negative_box[0])
        for solver in (fp64,fp32):
            before=q[:1].astype(np.float64 if solver.precision=='fp64' else np.float32)
            saved=before.copy();z,native=solver.quench(before,box[:1],0)
            host=cp.asnumpy(z);assert np.array_equal(host,before) and np.array_equal(before,saved)
            save(f'zero-{fixture["key"]}-{solver.precision}',dict(input=before,output=host,native=cp.asnumpy(native),boxes=box[:1]))
            report['zero_update'].append(dict(key=fixture['key'],precision=solver.precision,steps=0,full_count=host.shape[1],unchanged=True))
        # Small bounded full-N repair checks return counts/finite outputs and descent.
        fixed,native=fp32.quench(negative,negative_box,40,observed=True);cp.cuda.get_current_stream().synchronize()
        after,_=fp32.energy(fixed,negative_box);assert fixed.shape==negative.shape and np.isfinite(cp.asnumpy(fixed)).all() and after[0,0]<ne[0,0]-min(1e-4,.01*float(ne[0,0]))
        report['negative'].append(dict(key=fixture['key'],last_index_penetration=float(ne[0,1]),last_index_gradient_norm=float(np.linalg.norm(ng[0,-1])),
            observed_fp32_native=cp.asnumpy(native).tolist(),repair_before=float(ne[0,0]),repair_after=float(after[0,0])))
        save(f'full-{fixture["key"]}',dict(poses=rounded,boxes=rb,fp32_energy=e,fp32_gradient=g,fp64_energy=er,fp64_gradient=gr,
            negative_input=negative,negative_boxes=negative_box,negative_output=cp.asnumpy(fixed),observed_native=cp.asnumpy(native)))
        report['full_count'].append(dict(key=fixture['key'],n=q.shape[1],rounded_input_native_energy_error=(e[:,0]-er[:,0]).tolist(),
            original_vs_rounded_energy=(fp64.energy(q,box)[0][:,0]-er[:,0]).tolist(),coverage=coverage,all_gradients_finite=bool(np.isfinite(g).all())))
    bad=np.array([[[np.nan,1.,0.]]]);rejected=[]
    for solver in (fp64,fp32):
        try:
            solver.energy(bad,[[3.,3.]])
        except ValueError:
            rejected.append(solver.precision)
        else:
            raise AssertionError('nonfinite_input_was_not_rejected')
    assert np.isnan(bad[0,0,0]);report['nonfinite_rejected_before_objective']=rejected
    report['passed']=True
    report['observational_fp32_native_columns']=['E','last_trial_maxpen_may_be_stale','last_iteration_index','accepted_steps','accepted_exact_noop_steps','stop_reason_0budget_1residual_2linesearch','stored_history','accepted_gradient_norm']
    report['numeric_control_tolerances_are_not_optimizer_thresholds']=True
    report['scope']='Actual CUDA precision-specific numerical/rounded-input/coverage controls; tolerance changes do not alter optimizer thresholds. No score or convergence claim.'
    return report
