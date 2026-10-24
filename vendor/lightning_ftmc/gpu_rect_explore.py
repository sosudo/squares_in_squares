"""T4 FP32 exploration; FP64 refinement and official metric remain mandatory."""
import numpy as np
import cupy as cp
import gpu_rect_optimizer as exact
source=exact.src.replace('double','float')
for old,new in [('fabs(','fabsf('),('sqrt(','sqrtf('),('cos(','cosf('),('sin(','sinf('),('floor(','floorf('),('fmax(','fmaxf('),('fmin(','fminf(')]:source=source.replace(old,new)
source=source.replace('mp<2e-11','mp<6e-6').replace('sy>1e-24','sy>1e-14').replace('yy>1e-30','yy>1e-20')
module=cp.RawModule(code=source,options=('--std=c++17',),name_expressions=['eval','lbfgs'])
def setup(q,boxes):
    q=cp.asarray(q,dtype=cp.float32);B,n,_=q.shape;boxes=np.asarray(boxes,np.float32).reshape(B,2);nc=int(np.ceil((boxes.max()+6)/1.5))+1
    return q,B,n,nc,cp.asarray(boxes),cp.zeros(B,cp.float32),cp.empty((B,nc*nc),cp.int32),cp.empty((B,n),cp.int32),cp.empty((B,n,2),cp.float32)
def energy(q,boxes):
    q,B,n,nc,bb,t,h,l,c=setup(q,boxes);out=cp.empty((B,2),cp.float32);g=cp.empty_like(q)
    module.get_function('eval')((B,),(256,),(q,g,out,np.int32(n),np.int32(nc),bb,t,h,l,c));return cp.asnumpy(out),cp.asnumpy(g)
def quench(q,boxes,steps=350):
    q,B,n,nc,bb,t,h,l,c=setup(q,boxes);M=8;work=cp.empty((B,5,n,3),cp.float32);hist=cp.empty((B,2,M,n,3),cp.float32);out=cp.empty((B,3),cp.float32)
    module.get_function('lbfgs')((B,),(256,),(q,work,hist,out,np.int32(n),np.int32(nc),bb,t,h,l,c,np.int32(steps),np.int32(M)));return q,out
def check():
    rng=np.random.default_rng(224);q=rng.uniform(.4,2.6,(2,9,3));boxes=np.array([[3.1,3.2],[3.2,3.1]])
    e,g=energy(q,boxes);ee,gg=exact.energy(q,boxes)
    assert np.max(abs(e-ee))<3e-4 and np.max(abs(g-gg))<3e-4
    return dict(fp32_energy_error=float(np.max(abs(e-ee))),fp32_gradient_error=float(np.max(abs(g-gg))),fp64=exact.check())
