"""Bounded actual-CUDA diagnostics only; never change the frozen adapter/search."""
from __future__ import annotations

import hashlib
import itertools
import math
from pathlib import Path
import time

import numpy as np
import full_structural_gpu_ties as ties


FIELDS = ['dx','dy','c','s','cj','sj','cd','sd','radius','radius_derivative',
          'selected_axis','selected_z','penetration','projection_sign',
          'gx_before','gy_before','ga_before','recomputed_z0','recomputed_z1',
          'recomputed_z2','recomputed_z3','tie_count','gx_after','gy_after',
          'ga_after','cumulative_pair_energy','fma_z0','fma_z1','fma_z2',
          'fma_z3','recomputed_selected_z','explicit_fma_sd']


def diagnostic_source(patched):
    """Instrument the actual full objective; retain uninstrumented comparisons."""
    ties.audit_patched(patched)
    source=patched[:patched.index('__global__ void lbfgs')]+'\n}\n'
    assert source.count('double*maxpen){')==1
    source=source.replace('double*maxpen){','double*maxpen,double*dbg){',1)
    assert source.count('double*cs){')==1
    source=source.replace('double*cs){','double*cs,double*dbg){',1)
    assert source.count('r,&mp);')==1
    source=source.replace('r,&mp);','r,&mp,dbg+b*n*n*32);',1)
    before='''    double *dr=dbg+(i*n+j)*32;
    dr[0]=dx;dr[1]=dy;dr[2]=c;dr[3]=s;dr[4]=cj;dr[5]=sj;
    dr[6]=cd;dr[7]=sd;dr[8]=rad;dr[9]=rd;dr[10]=a;dr[11]=z;
    dr[12]=p;dr[13]=sign;dr[14]=gx;dr[15]=gy;dr[16]=ga;
    for(int dk=0;dk<4;dk++){
     dr[17+dk]=dx*ux[dk]+dy*uy[dk];
     dr[26+dk]=fma(dx,ux[dk],dy*uy[dk]);
    }
'''
    after='''
    dr[21]=tie_count;dr[22]=gx;dr[23]=gy;dr[24]=ga;dr[25]=energy;
    dr[30]=dx*ux[a]+dy*uy[a];dr[31]=fma(c,sj,-s*cj);
'''
    assert source.count(ties.NEW_GRADIENT)==1
    return source.replace(ties.NEW_GRADIENT,before+ties.NEW_GRADIENT+after,1)


def _sha(source):return hashlib.sha256(source.encode()).hexdigest()


def _outputs(p,e,g):
    center=p[:,:2].mean(0)
    tangent=np.column_stack((-(p[:,1]-center[1]),p[:,0]-center[0],np.ones(2)))
    return dict(input=p.tolist(),input_hex=[[float(x).hex()for x in row]for row in p],
                energy=np.asarray(e).tolist(),gradient=np.asarray(g).tolist(),
                coherent_angle_gradient=float(g[0,:,2].sum()),
                rigid_rotation_gradient=float(np.sum(g[0]*tangent)))


def run(gpu):
    """No optimization. Compare two compiler modes and instrumented exact pairs."""
    cp=gpu.cp;began=time.monotonic();original_mod=gpu.mod
    patched,audit=ties.patch_cuda(gpu.src)if ties.MARKER not in gpu.src else(gpu.src,ties.audit_patched(gpu.src))
    diagnostic=diagnostic_source(patched);cases=[]
    try:
        for fmad in(True,False):
            options=('--std=c++17',)if fmad else('--std=c++17','--fmad=false')
            gpu.mod=cp.RawModule(code=patched,options=options,name_expressions=['eval','lbfgs'])
            probe=cp.RawModule(code=diagnostic,options=options,name_expressions=['eval'])
            for tau,angle,dy in itertools.product((0.,.02),(0.,.31),(.2,.8,.9)):
                p=ties._pair(angle,dy);boxes=np.array([[10.,10.]])
                e,g=gpu.energy(p[None],boxes,tau=tau)
                q,B,n,nc,ll,ts,heads,links,trigs=gpu.buffers(p[None],boxes,tau)
                debug=cp.full((B,n,n,32),cp.nan,dtype=cp.float64)
                dg=cp.empty_like(q);de=cp.empty((B,2),dtype=cp.float64)
                probe.get_function('eval')((B,),(256,),
                    (q,dg,de,np.int32(n),np.int32(nc),ll,ts,heads,links,trigs,debug))
                de,dg,debug=map(cp.asnumpy,(de,dg,debug))
                directed=[]
                for i,j in((0,1),(1,0)):
                    row=debug[0,i,j];values={name:float(x)for name,x in zip(FIELDS,row)}
                    values['projection_hex']={name:float(row[k]).hex()
                        for k,name in enumerate(FIELDS)if k in(7,9,11,17,18,19,20,30,31)}
                    values['actual_exact_membership']=[bool(abs(row[k])==abs(row[11]))for k in range(17,21)]
                    directed.append(dict(i=i,j=j,**values))
                cases.append(dict(fmad=fmad,tau=tau,common_angle=angle,local_dy=dy,
                    actual=_outputs(p,e,g),instrumented=_outputs(p,de,dg),
                    instrumentation_max_gradient_difference=float(np.max(abs(g-dg))),
                    instrumentation_max_energy_difference=float(np.max(abs(e-de))),
                    directed_pairs=directed))
        cp.cuda.get_current_stream().synchronize()
    finally:gpu.mod=original_mod
    return dict(kind='actual CUDA exact-tie diagnostic; no optimization',
        device=int(cp.cuda.runtime.getDevice()),seconds=time.monotonic()-began,
        adapter_sha256=hashlib.sha256(Path(ties.__file__).read_bytes()).hexdigest(),
        diagnostic_module_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        source_audit=audit,patched_source_sha256=_sha(patched),
        instrumented_source_sha256=_sha(diagnostic),fields=FIELDS,cases=cases)
