"""Explicit FP32 explorer port of the pinned corrected FP64 CUDA optimizer.

The original FP64 text is never rewritten. Stop/curvature constants retain
their original magnitudes. Only hash-grid/radial screening uses promoted
rounded coordinates, to keep broad-phase coverage conservative.
"""
from __future__ import annotations
import hashlib
import math
import re
import numpy as np
from full_structural_gpu_ties import audit_patched

FP64_SHA = '8ccc1e355158401881545c054c53cc0e6ed1036aaec24856ca2d37b179247601'
OPTIONS = ('--std=c++17','--fmad=false')
FLOAT_LITERAL = re.compile(r'(?<![\w.])(?:\d+\.\d*|\.\d+|\d+[eE][+-]?\d+)(?:[eE][+-]?\d+)?(?![\w.])')


def sha_text(source):
    return hashlib.sha256(source.encode()).hexdigest()


def float_source(source):
    if sha_text(source) != FP64_SHA:
        raise ValueError('corrected_FP64_source_hash_mismatch')
    audit_patched(source)
    result = re.sub(r'\bdouble\b','float',source)
    result = FLOAT_LITERAL.sub(lambda match:match.group()+'f',result)
    for name in ('sqrt','sin','cos','fabs','fmin','fmax','floor'):
        result = re.sub(r'\b'+name+r'\(',name+'f(',result)
    replacements = {}
    for coordinate in ('q[3*i]','q[3*i+1]','x','y'):
        old = 'floorf(('+coordinate+'+3)/1.5f)'
        new = 'floor(((double)'+coordinate+'+3.0)/1.5)'
        if result.count(old) != 1:
            raise ValueError('unexpected_cell_index_source')
        result = result.replace(old,new,1); replacements[old] = new
    old = 'if(dx*dx+dy*dy>2.00000001f)continue;'
    new = ('double radial_dx=(double)q[3*j]-(double)x,radial_dy=(double)q[3*j+1]-(double)y;'
           'if(radial_dx*radial_dx+radial_dy*radial_dy>2.00000001)continue;')
    if result.count(old) != 1:
        raise ValueError('unexpected_radial_cutoff_source')
    result = result.replace(old,new,1); replacements[old] = new
    # All remaining double operations must belong to the declared screening
    # guards, never to reductions, gradients or optimizer state.
    remainder = result
    for replacement in replacements.values():
        remainder = remainder.replace(replacement,'')
    if re.search(r'\bdouble\b',remainder):
        raise ValueError('unapproved_FP64_explorer_math')
    if FLOAT_LITERAL.search(remainder):
        raise ValueError('unsuffixed_explorer_float_literal')
    thresholds = ('2e-11','1e-24','1e-30','1e-4')
    if any(value+'f' not in result for value in thresholds):
        raise ValueError('optimizer_threshold_changed')
    return result,dict(fp64_source_sha256=sha_text(source),fp32_source_sha256=sha_text(result),
        source_only_changes=['explicit float types/literals/math overloads','double cell/radial guards on exact rounded coordinates'],
        unchanged_threshold_magnitudes=list(thresholds),screening_replacements=replacements,
        compiler_options=list(OPTIONS),fast_math=False,
        lost_precision_note='FP32 may round away the2e-10 pair margin; it is exploration only. Final repair uses original FP64 boxes/source.')


def observational_source(source):
    """Separate untimed FP32 kernel; timed lbfgs remains byte-identical."""
    signature = '__global__ void lbfgs('
    begin = source.index(signature); end = source.rfind('\n}')
    kernel = source[begin:end].replace(signature,'__global__ void lbfgs_observed(',1)
    edits = {
        'int stored=0,last=0,its=0;':'int stored=0,last=0,its=0,accepted_count=0,zero_count=0,stop_reason=0;',
        'its=it;if(mp<2e-11f)break;':'its=it;if(mp<2e-11f){stop_reason=1;break;}',
        'if(!ok)break;':'if(!ok){stop_reason=2;break;}',
        'for(int k=tid;k<d;k+=blockDim.x){v[k]=trial[k]-q[k];direction[k]=gt[k]-g[k];}':
            'if(tid==0){accepted_count++;bool unchanged=true;for(int k=0;k<d;k++)if(trial[k]!=q[k])unchanged=false;if(unchanged)zero_count++;}__syncthreads();\n  for(int k=tid;k<d;k+=blockDim.x){v[k]=trial[k]-q[k];direction[k]=gt[k]-g[k];}',
        'if(tid==0){out[3*b]=E;out[3*b+1]=mp;out[3*b+2]=its;}':
            'float final_gn=sqrtf(dot(g,g,d,r));if(tid==0){out[8*b]=E;out[8*b+1]=mp;out[8*b+2]=its;out[8*b+3]=accepted_count;out[8*b+4]=zero_count;out[8*b+5]=stop_reason;out[8*b+6]=stored;out[8*b+7]=final_gn;}'
    }
    for old,new in edits.items():
        if kernel.count(old) != 1:
            raise ValueError('unexpected_observational_kernel_source')
        kernel = kernel.replace(old,new,1)
    return source[:end]+'\n'+kernel+source[end:]


class Solver:
    def __init__(self,cp,source,precision):
        if precision not in ('fp64','fp32'):
            raise ValueError('unsupported_precision')
        self.cp = cp; self.precision = precision
        if sha_text(source) != FP64_SHA:
            raise ValueError('corrected_FP64_source_hash_mismatch')
        audit_patched(source)
        self.dtype = cp.float64 if precision == 'fp64' else cp.float32
        self.source = source
        self.audit = dict(fp64_source_sha256=FP64_SHA,precision=precision,compiler_options=list(OPTIONS))
        expressions = ['eval','lbfgs']
        if precision == 'fp32':
            self.source,self.audit = float_source(source)
            compiled = observational_source(self.source); expressions.append('lbfgs_observed')
        else:
            compiled = source
        self.audit['compiled_source_sha256'] = sha_text(compiled)
        self.audit['observational_kernel_is_separate_from_timed_lbfgs'] = precision == 'fp32'
        self.compiled_source = compiled
        self.src = self.source
        self.module = cp.RawModule(code=compiled,options=OPTIONS,name_expressions=expressions)

    def _buffers(self,poses,boxes,tau):
        cp = self.cp; q = cp.array(poses,dtype=self.dtype,copy=True,order='C')
        if q.ndim != 3 or q.shape[2] != 3 or not bool(cp.isfinite(q).all()):
            raise ValueError('finite_full_count_poses_required')
        B,n,_ = q.shape; boxes = np.asarray(boxes,dtype=np.float64).reshape(B,2)
        if not np.isfinite(boxes).all() or not (boxes>0).all() or not math.isfinite(float(tau)) or tau < 0:
            raise ValueError('finite_positive_boxes_and_tau_required')
        ll = cp.asarray(boxes,dtype=self.dtype); ts = cp.full(B,tau,dtype=self.dtype)
        if not bool(cp.isfinite(ll).all()) or not bool((ll>0).all()):
            raise ValueError('rounded_boxes_nonfinite')
        nc = int(np.ceil((boxes.max()+6)/1.5))+1
        return q,B,n,nc,ll,ts,cp.empty((B,nc*nc),cp.int32),cp.empty((B,n),cp.int32),cp.empty((B,n,2),self.dtype)

    def energy(self,poses,boxes,tau=0.):
        cp = self.cp; q,B,n,nc,ll,ts,h,l,cs = self._buffers(poses,boxes,tau)
        g = cp.empty_like(q); out = cp.empty((B,2),self.dtype)
        self.module.get_function('eval')((B,),(256,),(q,g,out,np.int32(n),np.int32(nc),ll,ts,h,l,cs))
        return cp.asnumpy(out),cp.asnumpy(g)

    def quench(self,poses,boxes,steps,tau=0.,observed=False):
        if not isinstance(steps,int) or steps < 0:
            raise ValueError('finite_nonnegative_steps_required')
        if observed and self.precision != 'fp32':
            raise ValueError('original_FP64_kernel_is_not_instrumented')
        cp = self.cp; q,B,n,nc,ll,ts,h,l,cs = self._buffers(poses,boxes,tau); M = 8
        work = cp.empty((B,5,n,3),self.dtype); history = cp.empty((B,2,M,n,3),self.dtype)
        out = cp.empty((B,8 if observed else 3),self.dtype)
        name = 'lbfgs_observed' if observed else 'lbfgs'
        self.module.get_function(name)((B,),(256,),(q,work,history,out,np.int32(n),np.int32(nc),ll,ts,h,l,cs,np.int32(steps),np.int32(M)))
        return q,out

    def buffer_inventory(self):
        scalar = 'float64' if self.precision == 'fp64' else 'float32'
        return {name:scalar for name in ('poses','boxes','tau','work','history','native_output','trig','reductions')}|dict(head='int32',links='int32')
