"""CUDA rectangular unit-square L-BFGS, with optional smooth SAT continuation.

Extends the existing independently implemented square-container kernel.
The shape remains an exact unit square; only its centre/angle may change.
Smoothing is used in exploration, never in final feasibility admission.
"""
import re
import cupy as cp
import numpy as np
import gpu_topology as square

src=square.CUDA.replace('alpha[','history_alpha[')
src=src.replace('double L,int nc','double W,double H,double tau,int nc')
src=src.replace('double*Ls,int*head','double*Ls,double*Ts,int*head')
src=src.replace('n,Ls[b],nc,','n,Ls[2*b],Ls[2*b+1],Ts[b],nc,')
src=src.replace('double L=Ls[b],E=','double W=Ls[2*b],H=Ls[2*b+1],tau=Ts[b],E=')
src=src.replace('n,L,nc,','n,W,H,tau,nc,')
src=src.replace('x+h-L,y+h-L','x+h-W,y+h-H')
# Preserve zero contact residual at exact zero for each smoothed absolute value.
src=src.replace('__device__ double sg(double x)', '__device__ double sg(double x)')
src=src.replace('double rad=.5*(1+fabs(cd)+fabs(sd))+2e-10,rd=.5*(-sd*sg(cd)+cd*sg(sd));',
'''double ac=tau>0?sqrt(cd*cd+tau*tau)-tau:fabs(cd),as=tau>0?sqrt(sd*sd+tau*tau)-tau:fabs(sd);
    double sc=tau>0?cd/sqrt(cd*cd+tau*tau):sg(cd),ss=tau>0?sd/sqrt(sd*sd+tau*tau):sg(sd);
    double rad=.5*(1+ac+as)+2e-10,rd=.5*(-sd*sc+cd*ss);''')
src=src.replace('double p=rad-fabs(z);','double az=tau>0?sqrt(z*z+tau*tau)-tau:fabs(z);double p=rad-az;')
src=src.replace('double sign=sg(z);','double sign=tau>0?z/sqrt(z*z+tau*tau):sg(z);')
mod=cp.RawModule(code=src,options=('--std=c++17',),name_expressions=['eval','lbfgs'])

def buffers(q,boxes,tau):
    q=cp.asarray(q,dtype=cp.float64);B,n,_=q.shape;boxes=np.asarray(boxes,dtype=float).reshape(B,2);nc=int(np.ceil((boxes.max()+6)/1.5))+1
    return q,B,n,nc,cp.asarray(boxes),cp.full(B,tau,cp.float64),cp.empty((B,nc*nc),cp.int32),cp.empty((B,n),cp.int32),cp.empty((B,n,2),cp.float64)

def energy(q,boxes,tau=0.):
    q,B,n,nc,ll,ts,h,l,cs=buffers(q,boxes,tau);g=cp.empty_like(q);out=cp.empty((B,2),cp.float64)
    mod.get_function('eval')((B,),(256,),(q,g,out,np.int32(n),np.int32(nc),ll,ts,h,l,cs));return cp.asnumpy(out),cp.asnumpy(g)

def quench(q,boxes,steps=1200,tau=0.):
    q,B,n,nc,ll,ts,h,l,cs=buffers(q,boxes,tau);M=8;work=cp.empty((B,5,n,3),cp.float64);hist=cp.empty((B,2,M,n,3),cp.float64);out=cp.empty((B,3),cp.float64)
    mod.get_function('lbfgs')((B,),(256,),(q,work,hist,out,np.int32(n),np.int32(nc),ll,ts,h,l,cs,np.int32(steps),np.int32(M)));return q,out

def check():
    rng=np.random.default_rng(230);q=rng.uniform(.4,2.8,(3,11,3));boxes=np.array([[3.3,2.9],[3.,3.],[4.,3.5]]);err=[]
    for tau in [0.,.002]:
        e,g=energy(q,boxes,tau)
        for i,k in [(0,0),(2,1),(7,2)]:
            p=q.copy();m=q.copy();p[0,i,k]+=1e-6;m[0,i,k]-=1e-6;fd=(energy(p,boxes,tau)[0][0,0]-energy(m,boxes,tau)[0][0,0])/2e-6;err.append(abs(fd-g[0,i,k]))
    e,g=energy(q[1:2],boxes[1:2],0);ee,gg=square.energy(q[1:2],[3.]);assert np.max(abs(ee-e))<1e-10 and np.max(abs(gg-g))<1e-10
    assert max(err)<2e-6,err
    return dict(max_gradient_error=max(err),square_endpoint_matches=True)

if __name__=='__main__':print(check())
