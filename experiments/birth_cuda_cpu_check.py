"""Execute the exact proposed CUDA objective as a one-thread CPU reference.

This checks shared mathematical source, not CUDA compilation/synchronization.
Actual GPU controls remain mandatory before any search allocation.
"""
from __future__ import annotations
import ctypes
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import numpy as np
import torch
from birth_cuda import OBJECTIVE,mixed_cuda_source
from birth_continuation import mixed_energy,numpy_oracle

PREFIX=r'''
#include <cmath>
#include <algorithm>
#include <vector>
using std::min; using std::max;
#define __device__
struct Index { int x; };
Index threadIdx={0},blockDim={1};
void __syncthreads(){}
int atomicExch(int*ptr,int value){int old=*ptr;*ptr=value;return old;}
double sg(double x){return (x>0)-(x<0);}
'''
SUFFIX=r'''
extern "C" void evaluate(double*q,double*g,int n,double L,double birth,double*out){
 int nc=int(ceil((L+6)/1.5))+1;
 std::vector<int> head(nc*nc),next(n);
 std::vector<double> cs(2*n),r(2);
 double mp;
 out[0]=objective(q,g,n,L,birth,nc,head.data(),next.data(),cs.data(),r.data(),&mp);
 out[1]=mp;
}
'''

def check(out):
    torch.set_num_threads(1);root=Path(__file__).resolve().parents[1]
    out=Path(out);out.mkdir(exist_ok=False)
    source=PREFIX+OBJECTIVE+SUFFIX;(out/'exact-objective.cpp').write_text(source)
    subprocess.run(['g++','-O2','-std=c++17','-fno-fast-math','-ffp-contract=off','-shared','-fPIC',
                    str(out/'exact-objective.cpp'),'-o',str(out/'exact-objective.so')],check=True,timeout=20,capture_output=True)
    library=ctypes.CDLL(str((out/'exact-objective.so').resolve()));fn=library.evaluate
    pointer=np.ctypeslib.ndpointer(dtype=np.float64,flags='C_CONTIGUOUS')
    fn.argtypes=[pointer,pointer,ctypes.c_int,ctypes.c_double,ctypes.c_double,pointer]
    fixtures=[np.array([[1.,1.,0.],[1.5,1.3,0.]]),np.array([[1.,1.,0.],[1.8,1.8,0.]]),
              np.array([[1.,1.,.31],[1.5,1.3,.31]]),
              np.array([[.42,.71,.13],[1.1,.9,.57],[1.8,.45,-.27],[1.49,1.49,.37]])]
    rng=np.random.default_rng(776501)
    fixtures.extend(rng.uniform(.1,3.,(n,3))for n in (5,17,257))
    records=[]
    for i,p in enumerate(fixtures):
        for size in (.05,.2,.61,1.):
            L=4.;p=np.ascontiguousarray(p);g=np.empty_like(p);e=np.empty(2);fn(p,g,len(p),L,size,e)
            q=torch.tensor(p[None],dtype=torch.float64,requires_grad=True)
            value=mixed_energy(q,torch.tensor([[L,L]],dtype=torch.float64),size)['energy'].sum();value.backward()
            error=float(np.max(abs(g-q.grad.detach().numpy()[0])))
            energy_error=abs(e[0]-float(value.detach()))
            assert energy_error<1e-9 and error<1e-8,(i,size,energy_error,error,g,q.grad)
            oracle_error=None
            if len(p)<30:
                oracle_error=abs(e[0]-numpy_oracle(p,[L,L],size)['energy']);assert oracle_error<1e-11
            records.append(dict(fixture=i,n=len(p),birth_size=size,energy=float(e[0]),energy_error=energy_error,
                                maximum_gradient_error=error,independent_corner_oracle_error=oracle_error))
    # Largest actual sizes ensure all rows, including the last inserted row,
    # are traversed beyond block-size boundaries in the shared objective text.
    for n in (498,587):
        p=np.column_stack((np.arange(n)%25+.6,np.arange(n)//25+.6,np.zeros(n)))
        p[-1]=p[-2]+[.2,.1,.13]
        for size in (.05,.6,1.):
            g=np.empty_like(p);e=np.empty(2);fn(p,g,n,30.,size,e)
            q=torch.tensor(p[None],dtype=torch.float64,requires_grad=True)
            value=mixed_energy(q,torch.tensor([[30.,30.]],dtype=torch.float64),size)['energy'].sum();value.backward()
            error=float(np.max(abs(g-q.grad.detach().numpy()[0])))
            assert abs(e[0]-float(value.detach()))<1e-10 and error<1e-8
            assert np.linalg.norm(g[-1])>0
            records.append(dict(n=n,birth_size=size,energy=float(e[0]),maximum_gradient_error=error,last_row_gradient_nonzero=True))
    cuda,audit=mixed_cuda_source(root/'vendor/lightning_ftmc/gpu_topology.py')
    report=dict(passed=True,records=records,cpu_cpp_source_sha256=hashlib.sha256(source.encode()).hexdigest(),
                mixed_cuda_audit=audit,scope='Exact objective text in one-thread host emulation; not a substitute for live CUDA gates.')
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(passed=True,cases=len(records),maximum_gradient_error=max(r['maximum_gradient_error']for r in records))),flush=True)
    return report

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,required=True)
    check(parser.parse_args().out)
