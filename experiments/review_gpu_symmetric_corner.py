#!/usr/bin/env python3
"""Corner ties: invariance and limiting-gradient hull, not invalid cusp FD tests."""
import os
for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='1'
from pathlib import Path
import hashlib
import json
import math
import warnings
import numpy as np
from scipy.optimize import linprog
from review_gpu_symmetric_ties import evaluate
import review_gpu_tied_axis_gradient as original


def main():
    results=[]
    for tau in(0.,.02):
        for angle in(0.,.31):
            c,s=math.cos(angle),math.sin(angle);p=np.array([[2.,2.,0.],[2.9,2.9,0.]])
            center=p[:,:2].mean(0);p[:,:2]=(p[:,:2]-center)@np.array([[c,s],[-s,c]])+center;p[:,2]+=angle
            energy,g=evaluate(p,tau);assert energy==original.evaluate(p,tau)[0]
            permutation_error=float(abs(evaluate(p[::-1],tau)[1][::-1]-g).max());assert permutation_error<1e-12
            d=p[1,:2]-p[0,:2];projections=np.array([d[0]*c+d[1]*s,-d[0]*s+d[1]*c]*2)
            tied=int(np.sum(abs(projections)==abs(projections).max()))
            if angle==0:assert tied==4
            tangent=np.column_stack((-(p[:,1]-center[1]),p[:,0]-center[0],np.ones(2)))
            rigid_derivative=float(np.sum(g*tangent));assert abs(rigid_derivative)<1e-12
            limits=[]
            for da,db in((1.,.3),(-1.,-.3),(.3,1.),(-.3,-1.)):
                q=p.copy();q[0,2]+=1e-9*da;q[1,2]+=1e-9*db
                limits.append(original.evaluate(q,tau)[1].ravel())
            G=np.array(limits).T;target=g.ravel();tolerance=1e-7
            with warnings.catch_warnings():
                warnings.simplefilter('ignore')
                fit=linprog(np.zeros(4),A_ub=np.r_[G,-G],b_ub=np.r_[target+tolerance,-target+tolerance],
                    A_eq=np.ones((1,4)),b_eq=[1.],bounds=[(0.,1.)]*4,method='highs',
                    options={'threads':1,'primal_feasibility_tolerance':1e-9,'dual_feasibility_tolerance':1e-9})
            assert fit.success
            hull_residual=float(abs(G@fit.x-target).max());assert hull_residual<=tolerance+1e-9
            results.append(dict(tau=tau,common_angle=angle,actual_exact_tied_axes=tied,
                gradient=g.tolist(),row_permutation_error=permutation_error,
                rigid_rotation_derivative=rigid_derivative,nearby_smooth_gradients=np.array(limits).tolist(),
                nonnegative_hull_weights=fit.x.tolist(),hull_fit_max_error=hull_residual,
                note='Coherent-angle-only energy has a cusp; no central-FD equality is asserted for that direction.'))
    proof=dict(cpu_only=True,all_controls_passed=True,controls=results,
        source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    out=original.ROOT/'artifacts/full-gpu-objective-review-v1/symmetric-corner-control.json'
    out.write_text(json.dumps(proof,indent=2)+'\n');print(json.dumps(proof),flush=True)


if __name__=='__main__':main()
