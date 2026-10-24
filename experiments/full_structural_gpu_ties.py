"""One audited generated-CUDA correction and mandatory live directional controls.

Upstream files and frozen v1 remain unchanged. Only derivatives at exactly tied
active SAT projection axes are averaged; energy and the untied branch stay intact.
"""
from __future__ import annotations
import hashlib
import itertools
import math
from pathlib import Path
import time
import numpy as np

EXPECTED_SOURCE_SHA256='65e2d062fd43be4c97a41619e0f62590466573397f4d3de9222235586bc41a3e'
MARKER='// SYMMETRIC_EXACT_ACTIVE_AXES_V1'
OLD_GRADIENT='''    gx+=p*sign*ux[a];gy+=p*sign*uy[a];
    ga-=p*(rd+(a<2?sign*(-dx*uy[a]+dy*ux[a]):0));'''
NEW_GRADIENT='''    // SYMMETRIC_EXACT_ACTIVE_AXES_V1
    int tie_count=0;
    for(int k=0;k<4;k++){
     double tie_z=dx*ux[k]+dy*uy[k];
     if(fabs(tie_z)==fabs(z))tie_count++;
    }
    if(tie_count<2){
     gx+=p*sign*ux[a];gy+=p*sign*uy[a];
     ga-=p*(rd+(a<2?sign*(-dx*uy[a]+dy*ux[a]):0));
    }else{
     double tie_x=0,tie_y=0,tie_angle=0;
     for(int k=0;k<4;k++){
      double tie_z=dx*ux[k]+dy*uy[k];
      if(fabs(tie_z)!=fabs(z))continue;
      double tie_sign=tau>0?tie_z/sqrt(tie_z*tie_z+tau*tau):sg(tie_z);
      tie_x+=tie_sign*ux[k];tie_y+=tie_sign*uy[k];
      if(k<2)tie_angle+=tie_sign*(-dx*uy[k]+dy*ux[k]);
     }
     gx+=p*(tie_x/tie_count);gy+=p*(tie_y/tie_count);
     ga-=p*(rd+tie_angle/tie_count);
    }'''


def _sha(value):return hashlib.sha256(value.encode()).hexdigest()


def patch_cuda(source):
    """Refuse source drift/double adaptation; return a new string and audit."""
    if not isinstance(source,str):raise TypeError('CUDA source must be text')
    before=_sha(source)
    if before!=EXPECTED_SOURCE_SHA256:raise ValueError('Pinned rectangular CUDA source hash mismatch')
    if MARKER in source or source.count(OLD_GRADIENT)!=1:
        raise ValueError('Unexpected active-axis derivative source structure')
    changed=source.replace(OLD_GRADIENT,NEW_GRADIENT,1)
    assert changed.count(MARKER)==1
    audit={'adapter':'symmetric_exact_active_axes_v1','original_sha256':before,
        'patched_sha256':_sha(changed),'replacement_count':1,
        'old_block_sha256':_sha(OLD_GRADIENT),'new_block_sha256':_sha(NEW_GRADIENT),
        'tie_rule':'Uniform weights over all exactly maximal absolute projections; no near-tie tolerance.',
        'radius_rule':'Existing rd applied once per directed square; exact parallel sg(0)=0 retained.',
        'energy_changed':False,'untied_gradient_operations_changed':False,
        'upstream_files_modified':False,'adapter_file_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    return changed,audit


def audit_patched(source):
    if not isinstance(source,str)or source.count(NEW_GRADIENT)!=1 or source.count(MARKER)!=1:
        raise ValueError('Expected exactly one symmetric generated-CUDA block')
    original=source.replace(NEW_GRADIENT,OLD_GRADIENT,1)
    if _sha(original)!=EXPECTED_SOURCE_SHA256:raise ValueError('Patched CUDA is not the pinned one-block adaptation')
    return {'original_sha256':_sha(original),'patched_sha256':_sha(source),'replacement_count':1}


def _hull_distance(point,vertices):
    """Distance to a <=4-point angular-gradient hull, including degenerate edges."""
    point=np.asarray(point,float);vertices=np.asarray(vertices,float)
    best=min(float(np.linalg.norm(point-v))for v in vertices)
    for a,b in itertools.combinations(vertices,2):
        delta=b-a;norm=float(delta@delta)
        if norm:best=min(best,float(np.linalg.norm(point-(a+np.clip((point-a)@delta/norm,0,1)*delta))))
    for triangle in itertools.combinations(vertices,3):
        triangle=np.array(triangle);matrix=np.vstack((triangle.T,np.ones(3)))
        weights=np.linalg.lstsq(matrix,np.r_[point,1.],rcond=None)[0]
        if weights.min()>=-1e-9 and abs(weights.sum()-1)<1e-9:
            best=min(best,float(np.linalg.norm(weights@triangle-point)))
    return best


def _pair(common_angle,dy):
    p=np.array([[2.,2.,0.],[2.9,2.+dy,0.]])
    center=p[:,:2].mean(0);c,s=math.cos(common_angle),math.sin(common_angle)
    p[:,:2]=(p[:,:2]-center)@np.array([[c,s],[-s,c]])+center
    p[:,2]=common_angle
    return p


def directional_checks(energy):
    """Backend-independent protocol; live check_cuda supplies actual GPU.energy.

    Unequal projection controls have differentiable coherent-angle directions.
    Four-axis corners use limiting-gradient hulls, never central FD as an oracle.
    """
    began=time.monotonic();records=[];h=1e-6;relative_h=1e-7
    def evaluate(p,tau):
        e,g=energy(p[None].copy(),np.array([[10.,10.]]),tau=tau)
        e=np.asarray(e,float);g=np.asarray(g,float)
        assert e.shape==(1,2)and g.shape==(1,2,3)
        assert np.isfinite(e).all()and np.isfinite(g).all()
        return float(e[0,0]),g[0]
    for tau,angle,dy in itertools.product((0.,.02),(0.,.31),(.2,.8)):
        p=_pair(angle,dy);e,g=evaluate(p,tau)
        plus=p.copy();minus=p.copy();plus[:,2]+=h;minus[:,2]-=h
        coherent_fd=(evaluate(plus,tau)[0]-evaluate(minus,tau)[0])/(2*h)
        coherent=float(g[:,2].sum());assert abs(coherent-coherent_fd)<5e-7
        center=p[:,:2].mean(0)
        tangent=np.column_stack((-(p[:,1]-center[1]),p[:,0]-center[0],np.ones(2)))
        rigid=float(np.sum(g*tangent));assert abs(rigid)<2e-9
        reverse_e,reverse_g=evaluate(p[::-1],tau)
        permutation_error=float(np.max(abs(g-reverse_g[::-1])))
        assert abs(e-reverse_e)<1e-12 and permutation_error<2e-9
        plus=p.copy();minus=p.copy();plus[1,2]+=relative_h;minus[1,2]-=relative_h
        limits=np.array([evaluate(plus,tau)[1][:,2],evaluate(minus,tau)[1][:,2]])
        hull_error=_hull_distance(g[:,2],limits)
        midpoint_error=float(np.linalg.norm(g[:,2]-limits.mean(0)))
        assert hull_error<2e-6 and midpoint_error<2e-6
        records.append({'tau':tau,'common_angle':angle,'local_dy':dy,'energy':e,
            'coherent_gradient':coherent,'coherent_finite_difference':coherent_fd,
            'rigid_rotation_gradient':rigid,'row_permutation_error':permutation_error,
            'angular_gradient':g[:,2].tolist(),'nearby_one_sided_gradients':limits.tolist(),
            'nearby_segment_distance':hull_error,'nearby_midpoint_error':midpoint_error})
    corners=[]
    for tau,angle in itertools.product((0.,.02),(0.,.31)):
        p=_pair(angle,.9);e,g=evaluate(p,tau);center=p[:,:2].mean(0)
        tangent=np.column_stack((-(p[:,1]-center[1]),p[:,0]-center[0],np.ones(2)))
        rigid=float(np.sum(g*tangent));assert abs(rigid)<2e-9
        reverse_e,reverse_g=evaluate(p[::-1],tau)
        permutation_error=float(np.max(abs(g-reverse_g[::-1])))
        assert abs(e-reverse_e)<1e-12 and permutation_error<2e-9
        nearby=[]
        for square,sgn in itertools.product((0,1),(-1,1)):
            shifted=p.copy();shifted[square,2]+=sgn*relative_h
            nearby.append(evaluate(shifted,tau)[1][:,2])
        hull_error=_hull_distance(g[:,2],nearby);assert hull_error<2e-6
        corners.append({'tau':tau,'common_angle':angle,'angular_gradient':g[:,2].tolist(),
            'nearby_smooth_gradients':np.array(nearby).tolist(),'nearby_hull_distance':hull_error,
            'rigid_rotation_gradient':rigid,'row_permutation_error':permutation_error,
            'coherent_central_fd_used':False})
    # A genuinely untied regular case must remain an ordinary gradient.
    untied=[];p=np.array([[2.,2.,.13],[2.9,2.2,.47]])
    for tau in(0.,.02):
        _,g=evaluate(p,tau);errors=[]
        for i,k in itertools.product(range(2),range(3)):
            plus=p.copy();minus=p.copy();plus[i,k]+=h;minus[i,k]-=h
            fd=(evaluate(plus,tau)[0]-evaluate(minus,tau)[0])/(2*h)
            errors.append(abs(fd-g[i,k]))
        assert max(errors)<5e-7
        untied.append({'tau':tau,'maximum_finite_difference_error':max(errors)})
    return {'passed':True,'seconds':time.monotonic()-began,'coherent_controls':records,
        'corner_controls':corners,'untied_controls':untied,
        'one_sided_angle_step':relative_h,'coherent_fd_step':h,
        'scope':'Numerical actual-backend directional/permutation/nearby-gradient controls; no global convergence or optimum claim.'}


def check_cuda(gpu):
    """Mandatory live CUDA check AFTER replacing gpu.src and gpu.mod."""
    audit=audit_patched(gpu.src)
    cp=gpu.cp
    assert cp.cuda.runtime.getDeviceCount()>0
    device=int(cp.cuda.runtime.getDevice())
    cp.cuda.get_current_stream().synchronize()
    result=directional_checks(gpu.energy)
    cp.cuda.get_current_stream().synchronize()
    return {**result,'execution_backend':'actual gpu.energy CUDA',
            'device':device,'source_audit':audit}
