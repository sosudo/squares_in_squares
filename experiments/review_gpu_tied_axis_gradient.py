#!/usr/bin/env python3
"""CPU-faithful two-square control for the frozen CUDA active-axis tie rule.

No optimizer is run. The coherent-angle direction keeps relative angles fixed,
so it is differentiable even when individual-angle partials have a cusp.
"""
from pathlib import Path
import hashlib
import json
import math
import numpy as np

ROOT=Path(__file__).resolve().parents[1]


def sign(x):return float(x>1e-12)-float(x<-1e-12)


def evaluate(p,tau=0.):
    energy=0.;g=np.zeros_like(p)
    for i in range(2):
        j=1-i;dx,dy=p[j,:2]-p[i,:2]
        c,s=math.cos(p[i,2]),math.sin(p[i,2]);cj,sj=math.cos(p[j,2]),math.sin(p[j,2])
        cd,sd=c*cj+s*sj,c*sj-s*cj
        ac=math.sqrt(cd*cd+tau*tau)-tau if tau else abs(cd)
        ass=math.sqrt(sd*sd+tau*tau)-tau if tau else abs(sd)
        sc=cd/math.sqrt(cd*cd+tau*tau)if tau else sign(cd)
        ss=sd/math.sqrt(sd*sd+tau*tau)if tau else sign(sd)
        radius=.5*(1+ac+ass)+2e-10;rd=.5*(-sd*sc+cd*ss)
        ux=[c,-s,cj,-sj];uy=[s,c,sj,cj];axis=0;z=dx*ux[0]+dy*uy[0]
        for k in range(1,4):
            v=dx*ux[k]+dy*uy[k]
            if abs(v)>abs(z):axis=k;z=v
        az=math.sqrt(z*z+tau*tau)-tau if tau else abs(z)
        penetration=radius-az
        if penetration<=0:continue
        sg=z/math.sqrt(z*z+tau*tau)if tau else sign(z)
        energy+=.25*penetration**2
        g[i,0]+=penetration*sg*ux[axis];g[i,1]+=penetration*sg*uy[axis]
        g[i,2]-=penetration*(rd+(sg*(-dx*uy[axis]+dy*ux[axis])if axis<2 else 0.))
    return energy,g


def run():
    source=ROOT/'vendor/lightning_ftmc/gpu_topology.py';rect=ROOT/'vendor/lightning_ftmc/gpu_rect_optimizer.py'
    text=source.read_text()
    assert 'if(fabs(v)>fabs(z)){a=k;z=v;}'in text
    assert 'ga-=p*(rd+(a<2?sign*(-dx*uy[a]+dy*ux[a]):0));'in text
    h=1e-6;records=[]
    for tau in(0.,.02):
        regular=np.array([[2.,2.,.13],[2.9,2.2,.47]])
        energy,gradient=evaluate(regular,tau);errors=[]
        for i in range(2):
            for k in range(3):
                plus=regular.copy();minus=regular.copy();plus[i,k]+=h;minus[i,k]-=h
                derivative=(evaluate(plus,tau)[0]-evaluate(minus,tau)[0])/(2*h)
                errors.append(abs(derivative-gradient[i,k]))
        assert max(errors)<1e-8
        p=np.array([[2.,2.,0.],[2.9,2.2,0.]])
        energy,g=evaluate(p,tau);plus=p.copy();minus=p.copy();plus[:,2]+=h;minus[:,2]-=h
        coherent_fd=(evaluate(plus,tau)[0]-evaluate(minus,tau)[0])/(2*h)
        coherent_native=float(g[:,2].sum())
        assert abs(coherent_native-2*coherent_fd)<1e-8 and abs(coherent_native-coherent_fd)>.01
        # Rotate both centers and angles together: unit-square overlap and
        # pair energy are exactly invariant, so the directional derivative is0.
        center=p[:,:2].mean(0);tangent=np.column_stack((-(p[:,1]-center[1]),p[:,0]-center[0],np.ones(2)))
        rigid_native=float(np.sum(g*tangent))
        def rotated(a):
            q=p.copy();c,s=math.cos(a),math.sin(a)
            q[:,:2]=(p[:,:2]-center)@np.array([[c,s],[-s,c]])+center;q[:,2]+=a;return q
        rigid_fd=(evaluate(rotated(h),tau)[0]-evaluate(rotated(-h),tau)[0])/(2*h)
        assert abs(rigid_fd)<1e-8 and abs(rigid_native)>.01
        records.append(dict(tau=tau,energy=energy,non_tie_max_gradient_error=max(errors),
            coherent_angle_native=coherent_native,coherent_angle_finite_difference=coherent_fd,
            rigid_rotation_native=rigid_native,rigid_rotation_finite_difference=rigid_fd,
            coordinates=p.tolist()))
    out=ROOT/'artifacts/full-gpu-objective-review-v1';out.mkdir(exist_ok=False)
    result=dict(cpu_emulation_only=True,gpu_execution_performed=False,optimization_performed=False,
        finding='Directed first-axis ties assign the full projection-angle derivative to both square owners; '
                'this is not a valid coherent-direction derivative. Untied controls agree.',
        source_hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest()for p in(source,rect,Path(__file__))},
        controls=records)
    (out/'tied-axis-gradient-control.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result),flush=True)


if __name__=='__main__':run()
