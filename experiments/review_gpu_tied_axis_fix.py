#!/usr/bin/env python3
"""Validate pair-consistent tie ownership in the CPU faithful objective control."""
import hashlib
import inspect
import json
import math
from pathlib import Path
import numpy as np
import review_gpu_tied_axis_gradient as old


def fixed_evaluator():
    source=inspect.getsource(old.evaluate)
    before="axis=0;z=dx*ux[0]+dy*uy[0]"
    after="axis=0 if i<j else 2;z=dx*ux[axis]+dy*uy[axis]"
    assert source.count(before)==1 and source.count('for k in range(1,4):')==1
    source=source.replace(before,after).replace('for k in range(1,4):','for k in ((1,2,3)if i<j else(3,0,1)):')
    namespace=dict(math=math,np=np,sign=old.sign);exec(compile(source,'pair-consistent-control','exec'),namespace)
    return namespace['evaluate'],source


def main():
    evaluate,code=fixed_evaluator();results=[];h=1e-6
    for tau in(0.,.02):
        for angle in(0.,.31):
            c,s=math.cos(angle),math.sin(angle);rotation=np.array([[c,s],[-s,c]])
            p=np.array([[2.,2.,0.],[2.9,2.2,0.]]);center=p[:,:2].mean(0)
            p[:,:2]=(p[:,:2]-center)@rotation+center;p[:,2]+=angle
            e,g=evaluate(p,tau);old_e,_=old.evaluate(p,tau);assert e==old_e
            plus=p.copy();minus=p.copy();plus[:,2]+=h;minus[:,2]-=h
            coherent_fd=(evaluate(plus,tau)[0]-evaluate(minus,tau)[0])/(2*h)
            tangent=np.column_stack((-(p[:,1]-center[1]),p[:,0]-center[0],np.ones(2)))
            assert abs(g[:,2].sum()-coherent_fd)<1e-8
            assert abs(np.sum(g*tangent))<1e-12
            results.append(dict(tau=tau,common_angle=angle,energy_unchanged=True,
                coherent_native=float(g[:,2].sum()),coherent_finite_difference=coherent_fd,
                rigid_rotation_derivative=float(np.sum(g*tangent))))
        regular=np.array([[2.,2.,.13],[2.9,2.2,.47]])
        a,ga=evaluate(regular,tau);b,gb=old.evaluate(regular,tau)
        assert a==b;np.testing.assert_array_equal(ga,gb)
    out=old.ROOT/'artifacts/full-gpu-objective-review-v1'
    (out/'pair-consistent-evaluator.py').write_text(code)
    proof=dict(cpu_emulation_only=True,all_controls_passed=True,controls=results,
        changed_rule='For i<j select local axes0,1,2,3; for i>j select2,3,0,1. Strict greater-than comparisons retain the first physical owner consistently.',
        exact_energy_unchanged=True,untied_gradient_bitwise_unchanged=True,
        original_control_sha256=hashlib.sha256(Path(old.__file__).read_bytes()).hexdigest(),
        fixed_evaluator_sha256=hashlib.sha256(code.encode()).hexdigest(),
        source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    (out/'pair-consistent-fix-control.json').write_text(json.dumps(proof,indent=2)+'\n');print(json.dumps(proof),flush=True)


if __name__=='__main__':main()
