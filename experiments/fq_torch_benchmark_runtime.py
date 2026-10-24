"""Objective fidelity and synchronized timing only; no optimization steps."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import time
for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[name]='1'
import numpy as np
import torch
from fq_torch_objective import objective, constraints, guard_pair_list


def digest(data):return hashlib.sha256(data).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cpu-control-only',action='store_true')
    args=parser.parse_args();started=time.monotonic()
    torch.set_num_threads(1);torch.set_num_interop_threads(1)
    config=json.loads(Path('controls.json').read_text())
    data=Path('controls.npz').read_bytes();assert digest(data)==config['archive_sha256']
    with np.load('controls.npz',allow_pickle=False)as z:arrays={name:z[name]for name in z.files}
    assert set(arrays)==set(config['arrays'])
    for name,p in arrays.items():
        expected=config['arrays'][name]
        assert list(p.shape)==expected['shape']and p.dtype.str==expected['dtype']
        assert digest(p.tobytes())==expected['sha256']
    if args.cpu_control_only:device=torch.device('cpu');hardware='local CPU control only'
    else:
        assert torch.cuda.is_available();device=torch.device('cuda:0')
        hardware=torch.cuda.get_device_name(device);assert 'T4'in hardware
        torch.backends.cuda.matmul.allow_tf32=False
        torch.backends.cudnn.allow_tf32=False
    def sync():
        if device.type=='cuda':torch.cuda.synchronize(device)
    rows=[];gate_rows=[]
    def write(phase):
        report=dict(phase=phase,hardware=hardware,torch_version=torch.__version__,device=str(device),
                    seconds=time.monotonic()-started,control_archive_sha256=config['archive_sha256'],
                    gates=gate_rows,benchmarks=rows,no_optimization=True,no_submission=True)
        temporary=Path('benchmark-report.incoming');temporary.write_text(json.dumps(report,indent=2)+'\n')
        temporary.replace('benchmark-report.json')
    def prepare(case,dtype,batch):
        prefix=case['prefix'];get=lambda suffix:arrays[prefix+suffix]
        poses=get('_poses');n=case['n'];pairs=get('_pairs')
        assert poses.shape==(n,3)and pairs.shape==(case['pairs'],2)
        assert pairs.min()>=0 and pairs.max()<n
        make=lambda a:torch.tensor(a,dtype=dtype,device=device).unsqueeze(0).repeat((batch,)+(1,)*a.ndim)
        p=make(poses).requires_grad_();s=make(get('_side')).requires_grad_();lines=make(get('_lines')).requires_grad_()
        return(p,s,lines,torch.tensor(pairs,dtype=torch.long,device=device),make(get('_wall_lambda')),make(get('_pair_lambda')))
    def run(t,case):
        value=objective(*t,case['mu'],radius=case['radius'])
        gradients=torch.autograd.grad(value.sum(),t[:3])
        return value,gradients
    def check(t,case,dtype):
        value,gradients=run(t,case);sync()
        actual=value.detach().cpu().numpy();grad=np.concatenate([g.detach().cpu().numpy().reshape(len(actual),-1)for g in gradients],axis=1)
        prefix=case['prefix'];native=arrays[prefix+'_native_gradient'];native_value=float(arrays[prefix+'_native_value'])
        assert grad.shape==(len(actual),3*case['n']+1+2*case['pairs'])
        assert np.isfinite(grad).all()and np.isfinite(actual).all()
        if dtype==torch.float64:
            assert np.allclose(actual,native_value,rtol=1e-10,atol=1e-8)
            assert np.allclose(grad,native[None],rtol=1e-10,atol=1e-8)
        else:
            cpu=arrays[prefix+'_cpu32_gradient'];cpu_value=float(arrays[prefix+'_cpu32_value'])
            assert np.allclose(actual,cpu_value,rtol=3e-5,atol=.002)
            assert np.allclose(grad,cpu[None],rtol=3e-5,atol=.004)
            assert np.allclose(actual,native_value,rtol=1e-4,atol=.003)
            assert np.allclose(grad,native[None],rtol=1e-4,atol=.01)
        return dict(max_native_energy_error=float(np.abs(actual-native_value).max()),
                    max_native_gradient_error=float(np.abs(grad-native[None]).max()),
                    actual_pose_shape=list(t[0].shape),actual_line_shape=list(t[2].shape),
                    gradient_elements_per_replica=grad.shape[1])
    # All actual CUDA/native controls precede timings, including both precisions.
    for case in config['cases']:
        reference=arrays[case['prefix']+'_reference'];trial=arrays[case['prefix']+'_poses']
        guard_pair_list(reference,trial,.3)
        bad=reference.copy();bad[0,0]+=.151
        try:guard_pair_list(reference,bad,.3)
        except ValueError:pass
        else:raise AssertionError('Expired pair-list trial accepted')
        device_reference=torch.tensor(reference,dtype=torch.float64,device=device)
        def device_guard(candidate):
            delta=torch.tensor(candidate,dtype=torch.float64,device=device)[:,:2]-device_reference[:,:2]
            maximum=float(torch.linalg.vector_norm(delta,dim=1).max())
            if 2*maximum>=.3-1e-9:raise ValueError('Device displacement bound exceeded')
            return maximum
        device_guard(trial)
        try:device_guard(bad)
        except ValueError:pass
        else:raise AssertionError('Device accepted expired pair-list trial')
        for dtype in(torch.float64,torch.float32):
            t=prepare(case,dtype,1);result=check(t,case,dtype)
            gate_rows.append(dict(n=case['n'],radius=case['radius'],dtype=str(dtype),movement_bound_rejection=True,**result))
        write('fidelity-controls')
    print(json.dumps(dict(stage='all_native_objective_gates_passed',gates=len(gate_rows),hardware=hardware)),flush=True)
    for case in config['cases']:
        for dtype in(torch.float64,torch.float32):
            for batch in(1,8,32):
                if time.monotonic()-started>110:raise TimeoutError('Bounded benchmark incomplete')
                t=prepare(case,dtype,batch);result=check(t,case,dtype)
                for _ in range(3):run(t,case)
                sync()
                if device.type=='cuda':
                    torch.cuda.empty_cache();torch.cuda.reset_peak_memory_stats(device)
                    base_allocated=torch.cuda.memory_allocated(device)
                else:base_allocated=None
                timings=[]
                for _ in range(7):
                    sync();at=time.perf_counter();run(t,case);sync();timings.append(time.perf_counter()-at)
                memory={}if device.type!='cuda'else dict(base_allocated_bytes=base_allocated,
                    peak_allocated_bytes=torch.cuda.max_memory_allocated(device),peak_reserved_bytes=torch.cuda.max_memory_reserved(device))
                rows.append(dict(n=case['n'],pairs=case['pairs'],radius=case['radius'],dtype=str(dtype),batch=batch,
                                 forward_backward_seconds=timings,median_seconds=float(np.median(timings)),
                                 replicas_per_second=batch/float(np.median(timings)),**memory,**result))
                del t;write('benchmark')
    assert len(rows)==36
    write('complete');print(json.dumps(dict(stage='complete',settings=len(rows),seconds=time.monotonic()-started)),flush=True)


if __name__=='__main__':main()
