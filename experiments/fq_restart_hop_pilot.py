"""Paired persistent chains versus periodic hot-chain own-best resets."""
from __future__ import annotations
import argparse
import hashlib
import inspect
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[name] = '1'
import numpy as np
import torch
import fq_torch_hop_pilot as hop
import fq_fused_hop_pilot as fused
from fq_torch_hop import physical_energy, acceptance, mutate
from packer_hop_physical_energy import physical_energy as independent_energy

HOP_SHA = '2507a4260d1f7be8c67525a7ed4bbf401434cd1583f87049034faa04fdf97195'
CUDA_OPTIONS = fused.CUDA_OPTIONS


def design(case_n, reference_side, source_key):
    rows = []
    for arm in ('control','reset'):
        for pair in range(16):
            delta = (.002,.008)[pair//8]
            temperature = (.3,.3,.3,.3,1.,1.,3.,3.)[pair%8]
            rows.append(dict(chain=len(rows),pair=pair,arm=arm,n=int(case_n),
                delta=delta,side=float(reference_side)-delta,temperature=temperature,
                amplitude=(1.,1.5)[pair%2],source_key=source_key))
    return rows


def random_streams(seed, round_number):
    return [np.random.default_rng(np.random.SeedSequence([int(seed),int(round_number),b%16,41])) for b in range(32)]


def acceptance_uniforms(seed, round_number):
    values = np.random.default_rng(np.random.SeedSequence([int(seed),int(round_number),2718])).random(16)
    return np.r_[values,values]


def reset_mask(rows, rounds, cooling, initial, cooling_reset_done, last_periodic_round):
    periodic = bool(not initial and not cooling and rounds>0 and rounds%16==0 and last_periodic_round!=rounds)
    cooled = bool(not initial and cooling and not cooling_reset_done)
    mask = np.array([r['arm']=='reset' and r['temperature']>.3 and (periodic or cooled) for r in rows])
    return dict(mask=mask,periodic=periodic,cooling=cooled)


def temperature_schedule(base, absolute_deadline, decision_time):
    phase = 'cool' if decision_time >= absolute_deadline-150. else 'hot'
    return np.asarray(base)*(.1 if phase=='cool' else 1.),phase


class RestartPacketStore(hop.PacketStore):
    def __init__(self,root,batch,n,max_packets,max_bytes):
        super().__init__(root,batch,n,max_packets,max_bytes)
        # Six inherited pose arrays plus the exact pre-reset current pose.
        self.reserve = 2*(7*batch*n*3*8+1024**2+65536)
        if self.max_bytes<self.reserve: raise ValueError('Insufficient seven-pose packet budget')


def chain_design(source_keys):
    config = json.loads(Path('case-config.json').read_text())
    assert source_keys == [config['source_key']]
    return design(config['n'],config['reference_side'],source_keys[0])


def fused_quench(proposal,sides):
    cp,gpu,_ = fused.configure_gpu()
    assert proposal.dtype==sides.dtype==torch.float64 and proposal.shape[0]==32
    assert proposal.shape[1] in (453,693) and proposal.shape[2]==3
    assert sides.shape==(32,) and proposal.is_cuda and sides.is_cuda
    started=time.monotonic(); torch.cuda.synchronize()
    raw=cp.from_dlpack(proposal.detach()).copy()
    boxes=np.repeat(sides.detach().cpu().numpy()[:,None],2,axis=1)
    q,native=gpu.quench(raw,boxes,steps=2000,tau=0.)
    cp.cuda.get_current_stream().synchronize()
    result=torch.utils.dlpack.from_dlpack(q).clone();report=cp.asnumpy(native)
    assert result.shape==proposal.shape and report.shape==(32,3)
    return result,dict(solver='unchanged symmetric-tie FP64 quench',steps_requested=2000,tau=0.,
        compiler_options=list(CUDA_OPTIONS),seconds=time.monotonic()-started,native_report=report.tolist(),
        native_report_is_not_acceptance_energy=True,native_residual_may_describe_rejected_trial=True)


def replace_once(source,old,new):
    if source.count(old)!=1: raise ValueError('Pinned search delta count: '+old[:100])
    return source.replace(old,new,1)


def generated_search_source():
    assert hop.digest(hop.__file__)==HOP_SHA
    source=inspect.getsource(hop.search_main)
    replacements=[
        ("assert 0<float(config['search_seconds'])<=180","assert float(config['search_seconds'])==600"),
        ("assert preflight['passed']and preflight['parent_source_sha256']==PARENT_SHA",
         "assert preflight['passed']and preflight['backend']=='restart_fused_fp64'"),
        ("fixture=json.loads(Path('pilot-config.json').read_text());assert", "fixture=json.loads(Path('pilot-config.json').read_text());n=int(fixture['n']);assert"),
        ('assert current.shape==(32,335,3)','assert current.shape==(32,n,3)'),
        ("store=PacketStore('raw-hop',32,335,config['max_packets'],config['max_bytes'])",
         "store=PacketStore('raw-hop',32,n,config['max_packets'],config['max_bytes'])"),
        ("initial=True\n    while", "initial=True;cooling_reset_done=False;last_periodic_round=-1;storage_pause_seconds=0.\n    while"),
        ("        old=current.clone();old_best=best.clone();old_metrics=host_metrics(physical_energy(old,sides))", """        now=time.monotonic()
        if now<deadline-150. and (store.used+store.reserve>.6*store.max_bytes or len(store.entries)>=int(.6*store.max_packets)):
            pause=min(1.,deadline-150.-now);time.sleep(max(0.,pause));storage_pause_seconds+=max(0.,pause)
            continue
        pre_reset=current.clone();pre_reset_energy=current_metrics['energy'].copy()
        before_reset=reset_mask(design,rounds,now>=deadline-150.,initial,cooling_reset_done,last_periodic_round)
        if before_reset['periodic']:last_periodic_round=rounds
        if before_reset['cooling']:cooling_reset_done=True
        mask=torch.tensor(before_reset['mask'],device=device)
        current=torch.where(mask[:,None,None],best,current)
        current_metrics=host_metrics(physical_energy(current,sides))
        rngs=random_streams(int(config['seed']),rounds)
        old=current.clone();old_best=best.clone();old_metrics=host_metrics(physical_energy(old,sides))"""),
        ('arrays=dict(current_before=old_np,proposal_input=proposal,best_before=best_np,sides=sides.cpu().numpy(),',
         "arrays=dict(current_before_reset=pre_reset.cpu().numpy(),pre_reset_energy=pre_reset_energy,current_before=old_np,proposal_input=proposal,best_before=best_np,sides=sides.cpu().numpy(),"),
        ("metadata=dict(round=rounds,initialization=initial,design=design,moves=details,quench_radius=0.,fixed_side=True,",
         "metadata=dict(round=rounds,initialization=initial,design=design,moves=details,before_reset=before_reset,quench_radius=0.,fixed_side=True,"),
        (fused.OLD_BLOCK,"""        quenched,quench_record=fused_quench(proposal_tensor,sides)
        records=[quench_record]
        proposal_metrics=host_metrics(physical_energy(quenched,sides))
        completed=bool(torch.isfinite(quenched).all())and np.isfinite(proposal_metrics['energy']).all()"""),
        ('uniform=np.array([rng.random()for rng in rngs])','uniform=acceptance_uniforms(int(config[\'seed\']),rounds)'),
        ('        next_best_energy=choices.min(0)',"""        next_best_energy=choices.min(0)
        mh_next_energy=next_energy.copy()
        after_reset=reset_mask(design,rounds,temperature_phase=='cool',initial,cooling_reset_done,rounds)
        # A boundary-crossing quench began from its preboundary parent. Apply MH
        # at the recorded decision-time T, then reset before first cooled commit.
        if after_reset['cooling']:cooling_reset_done=True
        post_mask=torch.tensor(after_reset['mask'],device=device)
        next_current=torch.where(post_mask[:,None,None],next_best,next_current)
        next_energy=np.where(after_reset['mask'],next_best_energy,next_energy)"""),
        ("event=dict(round=rounds,initialization=initial,quench_completed=completed,outer_records=records,moves=details,",
         "event=dict(round=rounds,initialization=initial,quench_completed=completed,outer_records=records,moves=details,before_reset=before_reset,after_reset=after_reset,mh_next_energy=mh_next_energy,pre_reset_energy=pre_reset_energy,"),
        ("temperature_boundary='decision_time; search_180s_deadline_minus60s'",
         "temperature_boundary='decision_time; search_600s_deadline_minus150s'"),
        ("key=f\"baseT{row['temperature']}/{temperature_phase}/T{temperatures[b]}:{details[b]['operator']}\"",
         "key=f\"{row['arm']}/baseT{row['temperature']}/{temperature_phase}/T{temperatures[b]}:{details[b]['operator']}\""),
        ("zero_energy_raw_candidates=len(zero_records),verified=False)",
         "zero_energy_raw_candidates=len(zero_records),cooling_entered=cooling_reset_done,hot_storage_pause_seconds=storage_pause_seconds,verified=False)"),
        ("        if zero_records:stop_reason='zero_energy_candidate';break", "        # Keep the paired finite allocation; zero-energy states remain pending full gates."),
    ]
    for old,new in replacements: source=replace_once(source,old,new)
    source=source.replace("# Decision-time schedule is anchored to the parent's hard180s epoch.",
                          "# Decision-time schedule is anchored to the shared hard600s epoch.")
    compile(source,'<paired restart delta>','exec')
    return source


def search(deadline):
    namespace=dict(vars(hop))
    namespace.update(PacketStore=RestartPacketStore,chain_design=chain_design,fused_quench=fused_quench,
        random_streams=random_streams,acceptance_uniforms=acceptance_uniforms,reset_mask=reset_mask,
        temperature_schedule=temperature_schedule)
    exec(compile(generated_search_source(),'<paired restart delta>','exec'),namespace)
    namespace['search_main'](deadline)


def preflight():
    from full_structural_gpu_ties import check_cuda
    from full_structural_gpu_v2_preflight import preflight as full_preflight
    from fq_coherent_clusters import atom_npz
    started=time.monotonic();torch.set_num_threads(1);torch.set_num_interop_threads(1)
    assert torch.cuda.is_available() and 'T4' in torch.cuda.get_device_name(0)
    config=json.loads(Path('case-config.json').read_text());fixture=json.loads(Path('pilot-config.json').read_text())
    assert hop.digest('pilot-inputs.npz')==fixture['inputs_sha256']
    with np.load('pilot-inputs.npz',allow_pickle=False) as archive: p=archive[config['source_key']]
    assert p.shape==(config['n'],3) and hashlib.sha256(p.tobytes()).hexdigest()==fixture['arrays'][config['source_key']]['sha256']
    cp,gpu,audit=fused.configure_gpu();folder=Path('preflight');folder.mkdir()
    hop.atom_json(folder/'gradient-patch.json',audit)
    hop.atom_json(folder/'gradient-controls.json',dict(check_cuda(gpu),compiler_options=list(CUDA_OPTIONS)))
    actual=full_preflight(cp,gpu,{config['n']:p},{config['n']:[(config['source_key'],p)]},0,folder)
    assert actual['passed']
    rows=chain_design([config['source_key']]);sides=torch.tensor([r['side'] for r in rows],dtype=torch.float64,device='cuda')
    initial=np.stack([p.copy() for _ in rows]);tensor=torch.tensor(initial,dtype=torch.float64,device='cuda')
    before=hop.host_metrics(physical_energy(tensor,sides));rngs=random_streams(9482221,1)
    proposals=np.stack([mutate(initial[b],before['per_square'][b],rngs[b],rows[b]['amplitude'])[0] for b in range(32)])
    assert np.array_equal(proposals[:16],proposals[16:])
    value=torch.tensor(proposals,dtype=torch.float64,device='cuda');returned,report=fused_quench(value,sides)
    metrics=hop.host_metrics(physical_energy(returned,sides));q=returned.cpu().numpy()
    assert np.array_equal(value.cpu().numpy(),proposals) and np.isfinite(q).all()
    paired_output_equal=bool(np.array_equal(q[:16],q[16:]))
    paired_output_max_difference=float(np.max(abs(q[:16]-q[16:])))
    checks=[]
    for b in (0,7,15,16,23,31):
        energy=independent_energy(q[b],float(sides[b]))['energy'];error=abs(energy-metrics['energy'][b])
        assert error<=1e-11+1e-8*abs(energy)
        checks.append(dict(chain=b,energy=energy,error=error))
    u=acceptance_uniforms(9482221,1);temperatures=np.array([r['temperature'] for r in rows])
    accepted,_=acceptance(before['energy'],metrics['energy'],temperatures,u)
    scalar=np.array([(b<a)or(np.log(max(b,1e-300))-np.log(max(a,1e-300)) < -t*np.log(max(v,1e-300)))
        for a,b,t,v in zip(before['energy'],metrics['energy'],temperatures,u)])
    assert np.array_equal(accepted,scalar)
    assert 32/report['seconds']>=2.,'Actual 2000-step full-size interface too slow for finite pilot'
    atom_npz(folder/'interface-raw.npz',dict(input=proposals,output=q,sides=sides.cpu().numpy()))
    result=dict(passed=True,backend='restart_fused_fp64',n=config['n'],seconds=time.monotonic()-started,
        actual_size_full_controls=True,paired_input_bytes_equal=True,proposal_input_unchanged=True,
        paired_output_bytes_equal=paired_output_equal,paired_output_max_difference=paired_output_max_difference,
        paired_acceptance_equal=bool(np.array_equal(accepted[:16],accepted[16:])),scalar_acceptance_checked=True,
        physical_energy_checks=checks,quench_report=report,interface_poses_per_second=32/report['seconds'],
        generated_search_sha256=hashlib.sha256(generated_search_source().encode()).hexdigest(),
        cuda_options=list(CUDA_OPTIONS),raw_interface_sha256=hop.digest(folder/'interface-raw.npz'))
    hop.atom_json('preflight.json',result);print(json.dumps(result),flush=True)


def kill_tree(process):
    """Children inherit the outer owned group; stop a phase's descendants too."""
    parents={}
    for path in Path('/proc').glob('[0-9]*/stat'):
        try:
            text=path.read_text();tail=text[text.rfind(')')+2:].split()
            parents[int(path.parent.name)]=int(tail[1])
        except (OSError,ValueError,IndexError): pass
    descendants={process.pid}
    while True:
        new={pid for pid,parent in parents.items() if parent in descendants}-descendants
        if not new: break
        descendants.update(new)
    for pid in sorted(descendants-{process.pid},reverse=True):
        try: os.kill(pid,signal.SIGKILL)
        except ProcessLookupError: pass
    if process.poll() is None: process.kill()
    process.wait(timeout=2)


def run_phase(root,cases,phase,deadline):
    active={};records={};handles=[]
    try:
        for case in cases:
            n=case['n'];folder=root/f'case-{n}';log=(folder/(phase+'.log')).open('w');handles.append(log)
            env=dict(os.environ,CUDA_VISIBLE_DEVICES=str(case['device']))
            command=[sys.executable,'-u',str(Path(__file__).resolve()),'--phase',phase,'--case',str(n),'--deadline',str(deadline)]
            active[n]=subprocess.Popen(command,cwd=folder,env=env,stdout=log,stderr=subprocess.STDOUT)
        while active:
            for n,process in list(active.items()):
                forced=False
                if process.poll() is None and time.monotonic()>=deadline:
                    kill_tree(process);forced=True
                if process.poll() is not None:
                    records[str(n)]=dict(returncode=process.returncode,forced=forced,phase=phase)
                    del active[n]
            if active: time.sleep(.2)
    finally:
        for process in active.values(): kill_tree(process)
        for handle in handles: handle.close()
    return records


def recover_terminal():
    """Recover exact committed terminal state without rereading gigabytes."""
    if not Path('raw-index.json').exists():
        return dict(packets=0,completed=0,pending=0,recovered_final_archive_sha256=None)
    index=json.loads(Path('raw-index.json').read_text());entries=index['packets']
    completed=[entry for entry in entries if entry['status']=='completed']
    result=dict(packets=len(entries),completed=len(completed),pending=len(entries)-len(completed),
        total_bytes=index['total_bytes'],raw_index_sha256=hop.digest('raw-index.json'),
        recovery_scope='Terminal packet and all its members verified; earlier raw files remain SHA-bound by index and are not reread.',
        recovered_final_archive_sha256=None)
    if not completed: return result
    last=completed[-1];path=Path(last['path'])
    assert path.resolve().is_relative_to(Path.cwd()) and hop.digest(path)==last['sha256']
    assert path.stat().st_size==last['bytes']
    with np.load(path,allow_pickle=False) as archive:
        metadata=json.loads(archive['metadata_json'].tobytes())
        for name in archive.files:
            if name!='metadata_json':
                assert hashlib.sha256(archive[name].tobytes()).hexdigest()==metadata['array_sha256'][name]
        arrays={name:archive[name] for name in ('current_after','best_after','sides','next_energy','best_energy_after')}
    temporary=Path('final-current-best.incoming')
    with temporary.open('wb') as stream: np.savez(stream,**arrays)
    temporary.replace('final-current-best.npz')
    result.update(last_completed_packet=last,rounds_completed=int(metadata['round'])+int(not metadata['initialization']),
        recovered_final_archive_sha256=hop.digest('final-current-best.npz'))
    return result


def parent_main():
    started=time.monotonic();root=Path.cwd();config=json.loads(Path('restart-config.json').read_text())
    assert config['search_seconds']==600 and config['cooling_seconds']==150
    assert hop.digest('restart-inputs.npz')==config['inputs_sha256']
    with np.load('restart-inputs.npz',allow_pickle=False) as archive: bank={key:archive[key] for key in archive.files}
    cases=[dict(config['cases'][str(n)]) for n in (453,693)]
    binary=(root/config.get('binary_path','bin/fq')).resolve()
    assert binary.is_file();binary.chmod(0o500)
    assert hop.digest(binary)=='10ec7cf773ac0ebca3791d5cfb84e9ecbb10e3f0a9e43194330c80e1cfc9dc3d'
    for case in cases:
        folder=root/f"case-{case['n']}";folder.mkdir();key=case['source_key'];p=bank[key]
        assert p.shape==(case['n'],3) and np.isfinite(p).all()
        assert hashlib.sha256(p.tobytes()).hexdigest()==case['source_geometry_sha256']
        with (folder/'pilot-inputs.npz').open('wb') as stream: np.savez(stream,**{key:p})
        fixture=dict(n=case['n'],inputs_sha256=hop.digest(folder/'pilot-inputs.npz'),exploratory_sources=[key],
            arrays={key:dict(shape=list(p.shape),dtype=p.dtype.str,sha256=hashlib.sha256(p.tobytes()).hexdigest())})
        case.update(binary_path=str(binary),baseline_sha256=config['baseline']['sha256'])
        hop.atom_json(folder/'case-config.json',case);hop.atom_json(folder/'pilot-config.json',fixture)
        hop.atom_json(folder/'hop-config.json',dict(search_seconds=600,seed=int(config['seed'])+case['n'],
            max_packets=int(config['max_packets']),max_bytes=int(config['max_bytes'])))
    controls=run_phase(root,cases,'preflight',started+100)
    assert all(r['returncode']==0 for r in controls.values()),'Actual-size preflight failed'
    assert all(json.loads((root/f"case-{c['n']}"/'preflight.json').read_text())['passed'] for c in cases)
    print(json.dumps(dict(stage='both_actual_size_controls_passed',controls=controls)),flush=True)
    search_started=time.monotonic();deadline=search_started+600
    assert deadline<=started+705
    searches=run_phase(root,cases,'search',deadline)
    recoveries={}
    for case in cases:
        folder=root/f"case-{case['n']}";os.chdir(folder)
        try:
            recoveries[str(case['n'])]=recover_terminal()
            hop.atom_json('recovery.json',recoveries[str(case['n'])])
        finally: os.chdir(root)
    finish_deadline=min(time.monotonic()+120,started+830)
    finishes=run_phase(root,cases,'finish',finish_deadline)
    summaries={}
    for case in cases:
        folder=root/f"case-{case['n']}";names=('preflight.json','hop-status.json','pilot-summary.json','recovery.json','finish-summary.json')
        summaries[str(case['n'])]={name:json.loads((folder/name).read_text()) for name in names if (folder/name).exists()}
    unexpected=[dict(case=n,**row) for phase in (searches,finishes) for n,row in phase.items()
                if row['returncode']!=0 and not row['forced']]
    summary=dict(controls_passed=True,seconds=time.monotonic()-started,controls=controls,searches=searches,finishes=finishes,
        status='unexpected_child_failure' if unexpected else 'complete_or_bounded_partial',unexpected_child_failures=unexpected,
        search_seconds=600,case_summaries=summaries,no_submission=True,no_pointer_mutation=True,
        interpretation='Physical energy and native residuals are not certified portfolio gains.')
    hop.atom_json('pilot-summary.json',hop.json_finite(summary));print(json.dumps(hop.json_finite(summary)),flush=True)
    if unexpected: raise SystemExit(1)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--phase',choices=('preflight','search','finish'))
    parser.add_argument('--case',type=int);parser.add_argument('--deadline',type=float);args=parser.parse_args()
    if args.phase=='preflight': return preflight()
    if args.phase=='search': return search(args.deadline)
    if args.phase=='finish':
        from fq_restart_hop_finish import finish_case
        config=json.loads(Path('case-config.json').read_text())
        result=finish_case(Path.cwd(),config,args.deadline);hop.atom_json('finish-summary.json',result);return
    return parent_main()


if __name__=='__main__':main()
