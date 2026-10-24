#!/usr/bin/env python3
"""Validate symmetric active-axis derivatives, including the coupled radius cusp."""
from pathlib import Path
import hashlib
import json
import math
import numpy as np
import review_gpu_tied_axis_gradient as original
from review_gpu_tied_axis_fix import fixed_evaluator


def evaluate(p,tau=0.):
    energy=0.;g=np.zeros_like(p)
    for i in range(2):
        j=1-i;dx,dy=p[j,:2]-p[i,:2]
        c,s=math.cos(p[i,2]),math.sin(p[i,2]);cj,sj=math.cos(p[j,2]),math.sin(p[j,2])
        cd,sd=c*cj+s*sj,c*sj-s*cj
        ac=math.sqrt(cd*cd+tau*tau)-tau if tau else abs(cd)
        ass=math.sqrt(sd*sd+tau*tau)-tau if tau else abs(sd)
        sc=cd/math.sqrt(cd*cd+tau*tau)if tau else original.sign(cd)
        ss=sd/math.sqrt(sd*sd+tau*tau)if tau else original.sign(sd)
        radius=.5*(1+ac+ass)+2e-10;rd=.5*(-sd*sc+cd*ss)
        ux=np.array([c,-s,cj,-sj]);uy=np.array([s,c,sj,cj]);z=dx*ux+dy*uy
        maximum=float(abs(z).max());active=np.flatnonzero(abs(z)==maximum)
        az=math.sqrt(maximum*maximum+tau*tau)-tau if tau else maximum
        penetration=radius-az
        if penetration<=0:continue
        weight=1./len(active);energy+=.25*penetration**2;ga=rd
        for axis in active:
            sg=z[axis]/math.sqrt(z[axis]*z[axis]+tau*tau)if tau else original.sign(z[axis])
            g[i,0]+=penetration*weight*sg*ux[axis];g[i,1]+=penetration*weight*sg*uy[axis]
            if axis<2:ga+=weight*sg*(-dx*uy[axis]+dy*ux[axis])
        g[i,2]-=penetration*ga
    return energy,g


def main():
    h=1e-6;results=[]
    for tau in(0.,.02):
        for common_angle in(0.,.31):
            for dy in(.2,.8):
                p=np.array([[2.,2.,0.],[2.9,2.+dy,0.]])
                center=p[:,:2].mean(0);c,s=math.cos(common_angle),math.sin(common_angle)
                p[:,:2]=(p[:,:2]-center)@np.array([[c,s],[-s,c]])+center;p[:,2]+=common_angle
                e,g=evaluate(p,tau);assert e==original.evaluate(p,tau)[0]
                plus=p.copy();minus=p.copy();plus[:,2]+=h;minus[:,2]-=h
                fd=(evaluate(plus,tau)[0]-evaluate(minus,tau)[0])/(2*h)
                tangent=np.column_stack((-(p[:,1]-center[1]),p[:,0]-center[0],np.ones(2)))
                assert abs(g[:,2].sum()-fd)<1e-8 and abs(np.sum(g*tangent))<1e-12
                results.append(dict(tau=tau,common_angle=common_angle,dy=dy,
                    coherent_derivative=float(g[:,2].sum()),coherent_fd=fd,
                    rigid_rotation_derivative=float(np.sum(g*tangent)),gradient=g.tolist()))
        regular=np.array([[2.,2.,.13],[2.9,2.2,.47]])
        a,ga=evaluate(regular,tau);b,gb=original.evaluate(regular,tau)
        assert a==b;np.testing.assert_array_equal(ga,gb)
    # Root's counterexample: coherent-direction agreement alone is not enough.
    p=np.array([[2.,2.,0.],[2.9,2.8,0.]]);perturbation=1e-8
    plus=p.copy();minus=p.copy();plus[1,2]+=perturbation;minus[1,2]-=perturbation
    endpoints=np.array([original.evaluate(plus)[1][:,2],original.evaluate(minus)[1][:,2]])
    symmetric=evaluate(p)[1][:,2];canonical=fixed_evaluator()[0](p)[1][:,2]
    vector=endpoints[1]-endpoints[0]
    def hull_distance(g):
        u=np.clip(float((g-endpoints[0])@vector/(vector@vector)),0.,1.)
        return float(np.linalg.norm(g-(endpoints[0]+u*vector)))
    assert hull_distance(symmetric)<1e-8 and hull_distance(canonical)>.04
    assert np.max(abs(symmetric-endpoints.mean(0)))<1e-8
    out=original.ROOT/'artifacts/full-gpu-objective-review-v1'
    proof=dict(cpu_emulation_only=True,all_controls_passed=True,
        coherent_control_is_necessary_but_insufficient=True,canonical_owner_rule_not_endorsed_as_complete_fix=True,
        exact_energy_unchanged=True,untied_gradients_bitwise_unchanged=True,
        active_axis_policy='Uniform weights over every exactly maximal absolute projection; radius uses existing rd, including sg(0)=0.',
        controls=results,coupled_cusp_counterexample=dict(coordinates=p.tolist(),
            one_sided_angle_gradient_limits=endpoints.tolist(),symmetric_angle_gradient=symmetric.tolist(),
            canonical_angle_gradient=canonical.tolist(),symmetric_distance_to_Clarke_segment=hull_distance(symmetric),
            canonical_distance_to_Clarke_segment=hull_distance(canonical)),
        source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    (out/'symmetric-tie-control.json').write_text(json.dumps(proof,indent=2)+'\n');print(json.dumps(proof),flush=True)


if __name__=='__main__':main()
