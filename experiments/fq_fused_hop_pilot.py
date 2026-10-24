"""Reviewed persistent hop protocol with the unchanged corrected FP64 quench."""
from __future__ import annotations
import hashlib
import inspect
import json
import os
from pathlib import Path
import time
import numpy as np
import torch
import fq_torch_hop_pilot as hop
from fq_torch_hop import physical_energy,acceptance,chain_design,mutate
from packer_hop_physical_energy import physical_energy as independent_energy

HOP_SHA='2507a4260d1f7be8c67525a7ed4bbf401434cd1583f87049034faa04fdf97195'
TIES_SHA='3c373cb2338eab652d076e1d072cc5f146ab34300fd170a8d1794692aa7ea14a'
CUDA_OPTIONS=('--std=c++17','--fmad=false')
OLD_BLOCK="""        state=LiftedBatch(proposal_tensor,sides.clone())
        records=state.stage(0.,True,outer=2,inner=24,tolerance=1e-9,deadline=lambda:time.monotonic()>=deadline)
        assert torch.equal(state.sides,sides)
        quenched=state.poses.detach().clone();proposal_metrics=host_metrics(physical_energy(quenched,sides))
        completed=bool(records)and(len(records)==2 or max(records[-1]['violation'])<1e-9)"""
NEW_BLOCK="""        quenched,quench_record=fused_quench(proposal_tensor,sides)
        records=[quench_record]
        proposal_metrics=host_metrics(physical_energy(quenched,sides))
        completed=bool(torch.isfinite(quenched).all())and np.isfinite(proposal_metrics['energy']).all()"""
_GPU=None


def configure_gpu():
    global _GPU
    if _GPU is not None:return _GPU
    import cupy as cp
    import gpu_rect_optimizer as gpu
    import full_structural_gpu_ties as ties
    assert hop.digest(ties.__file__)==TIES_SHA
    cp.cuda.Device(0).use()
    gpu.src,audit=ties.patch_cuda(gpu.src)
    gpu.mod=cp.RawModule(code=gpu.src,options=CUDA_OPTIONS,name_expressions=['eval','lbfgs'])
    audit['compiler_options']=list(CUDA_OPTIONS)
    _GPU=(cp,gpu,audit)
    return _GPU


def fused_quench(proposal,sides):
    """DLPack COPY isolates the in-place public quench from the saved proposal."""
    cp,gpu,audit=configure_gpu()
    assert proposal.dtype==sides.dtype==torch.float64 and proposal.shape==(32,335,3)
    assert sides.shape==(32,) and proposal.is_cuda and sides.is_cuda
    started=time.monotonic();torch.cuda.synchronize()
    q=cp.from_dlpack(proposal.detach()).copy()
    boxes=np.repeat(sides.detach().cpu().numpy()[:,None],2,axis=1)
    q,native=gpu.quench(q,boxes,steps=400,tau=0.)
    cp.cuda.get_current_stream().synchronize()
    result=torch.utils.dlpack.from_dlpack(q).clone()
    report=cp.asnumpy(native)
    assert result.shape==proposal.shape and report.shape==(32,3)
    return result,dict(solver='unchanged symmetric-tie FP64 rectangular L-BFGS',
        steps_requested=400,tau=0.,compiler_options=list(CUDA_OPTIONS),seconds=time.monotonic()-started,
        native_report=report.tolist(),native_report_is_not_acceptance_energy=True,
        native_residual_may_describe_rejected_line_search_trial=True,
        acceptance_energy='Fresh unchanged Torch dense unordered-pair plus four-wall physical energy',
        quench_completion='Returned finite batch; no convergence claim')


def generated_search_source():
    assert hop.digest(hop.__file__)==HOP_SHA
    source=inspect.getsource(hop.search_main)
    assert source.count(OLD_BLOCK)==1
    source=source.replace(OLD_BLOCK,NEW_BLOCK)
    old="assert preflight['passed']and preflight['parent_source_sha256']==PARENT_SHA"
    new="assert preflight['passed']and preflight['backend']=='corrected_fused_fp64'and preflight['cuda_options']==list(CUDA_OPTIONS)"
    assert source.count(old)==1
    return source.replace(old,new)


def live_preflight(root):
    """Old full335 controls plus a small actual interface/retention smoke."""
    from full_structural_gpu_ties import check_cuda
    from full_structural_gpu_v2_preflight import preflight as old_preflight
    began=time.monotonic();torch.set_num_threads(1);torch.set_num_interop_threads(1)
    assert torch.cuda.is_available()and'T4'in torch.cuda.get_device_name(0)
    cp,gpu,audit=configure_gpu();folder=root/'fused-preflight';folder.mkdir()
    hop.atom_json(folder/'gradient-patch.json',audit)
    hop.atom_json(folder/'gradient-controls.json',dict(check_cuda(gpu),compiler_options=list(CUDA_OPTIONS)))
    fixture=json.loads((root/'pilot-config.json').read_text())
    assert hop.digest(root/'pilot-inputs.npz')==fixture['inputs_sha256']
    with np.load(root/'pilot-inputs.npz',allow_pickle=False)as z:bank={k:z[k]for k in z.files}
    for key,p in bank.items():
        row=fixture['arrays'][key]
        assert list(p.shape)==row['shape']and p.dtype.str==row['dtype']and hashlib.sha256(p.tobytes()).hexdigest()==row['sha256']
    keys=fixture['exploratory_sources'];assert len(keys)==3 and all(bank[k].shape==(335,3)for k in keys)
    controls=old_preflight(cp,gpu,{335:bank[keys[0]]},{335:[(k,bank[k])for k in keys[1:]]},0,folder)
    assert controls['passed']
    design=chain_design(keys);sides=torch.tensor([r['side']for r in design],dtype=torch.float64,device='cuda')
    initial=np.stack([bank[r['source_key']]for r in design]);current=initial.copy()
    rng=np.random.default_rng(7258931);packets=[];timings=[];oracle=[]
    smoke=folder/'smoke';smoke.mkdir();old_cwd=Path.cwd();os.chdir(smoke)
    try:
        store=hop.PacketStore('packets',32,335,3,64*1024**2)
        for iteration in range(3):
            old=torch.tensor(current,dtype=torch.float64,device='cuda')
            before=hop.host_metrics(physical_energy(old,sides));proposals=[];moves=[]
            for i,row in enumerate(design):
                q,move=mutate(current[i],before['per_square'][i],rng,row['amplitude'])
                proposals.append(q);moves.append(move)
            proposal=np.stack(proposals);tensor=torch.tensor(proposal,dtype=torch.float64,device='cuda')
            index=store.begin(dict(current_before=current,proposal_input=proposal),dict(iteration=iteration,moves=moves,verified=False))
            start=time.monotonic();quenched,native=fused_quench(tensor,sides)
            metrics=hop.host_metrics(physical_energy(quenched,sides));host=quenched.cpu().numpy()
            timings.append(time.monotonic()-start)
            assert np.array_equal(tensor.cpu().numpy(),proposal),'Native quench mutated the saved input'
            assert np.isfinite(host).all()and np.isfinite(metrics['energy']).all()
            for i in (0,15,31):
                value=independent_energy(host[i],float(sides[i]))['energy'];error=abs(value-metrics['energy'][i])
                assert error<=1e-11+1e-8*abs(value)
                oracle.append(dict(iteration=iteration,chain=i,error=error,energy=value))
            temperature=np.array([r['temperature']for r in design]);uniform=rng.random(32)
            accepted,rule=acceptance(before['energy'],metrics['energy'],temperature,uniform)
            scalar=np.array([(b<a)or(np.log(max(b,1e-300))-np.log(max(a,1e-300)) < -t*np.log(max(u,1e-300)))
                for a,b,t,u in zip(before['energy'],metrics['energy'],temperature,uniform)])
            assert np.array_equal(accepted,scalar)
            after=np.where(accepted[:,None,None],host,current)
            entry=store.complete(index,dict(current_before=current,proposal_input=proposal,proposal_quenched=host,current_after=after),
                dict(iteration=iteration,moves=moves,accepted=accepted.tolist(),uniform=uniform.tolist(),temperature=temperature.tolist(),native=native))
            with np.load(entry['path'],allow_pickle=False)as z:
                meta=json.loads(z['metadata_json'].tobytes())
                for key in ('current_before','proposal_input','proposal_quenched','current_after'):
                    assert hashlib.sha256(z[key].tobytes()).hexdigest()==meta['array_sha256'][key]
                assert np.array_equal(z['current_after'],after)
            packets.append(entry);current=after.copy()
        # This is a throughput gate, not evidence of geometric convergence.
        rate=96/sum(timings);assert rate>=20.,f'Fused interface remains too slow: {rate} poses/s'
        hop.atom_json('smoke.json',dict(passed=True,poses=96,seconds=sum(timings),poses_per_second=rate,
            per_call_seconds=timings,independent_physical_energy_checks=oracle,packets=packets,
            original_proposal_unchanged=True,ratio_acceptance_matches_scalar=True,verified=False))
    finally:os.chdir(old_cwd)
    result=dict(passed=True,backend='corrected_fused_fp64',cuda_options=list(CUDA_OPTIONS),
        seconds=time.monotonic()-began,quench_steps=400,full335_controls=True,
        adapter_sha256=hop.digest(__file__),hop_source_sha256=HOP_SHA,
        generated_search_sha256=hashlib.sha256(generated_search_source().encode()).hexdigest(),
        smoke_sha256=hop.digest(smoke/'smoke.json'),throughput_poses_per_second=rate)
    hop.atom_json('preflight.json',result);print(json.dumps(dict(stage='fused_live_preflight',**result)),flush=True)
    return result


def main():
    source=generated_search_source()
    namespace=dict(vars(hop));namespace.update(__file__=__file__,fused_quench=fused_quench,CUDA_OPTIONS=CUDA_OPTIONS,
        run_parent_preflight=live_preflight)
    exec(compile(source,'<pinned fused quench hop delta>','exec'),namespace)
    # Reuse the exact reviewed process bound/recovery code, spawning this adapter.
    exec(compile(inspect.getsource(hop.main),'<unchanged hop supervisor>','exec'),namespace)
    namespace['main']()


if __name__=='__main__':main()
