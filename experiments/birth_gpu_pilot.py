"""One finite, two-GPU staged single-square-birth pilot; no submissions."""
from __future__ import annotations
import time
STARTED=time.monotonic()
import os
for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='1'
import argparse,hashlib,json,math,signal,subprocess,sys,zipfile
from pathlib import Path
import numpy as np

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):
    p=Path(p);tmp=p.with_suffix(p.suffix+'.incoming');tmp.write_text(json.dumps(x,indent=2,allow_nan=False)+'\n');tmp.replace(p)
def archive(p,**arrays):
    p=Path(p);tmp=p.with_suffix('.incoming.npz');np.savez_compressed(tmp,**arrays);tmp.replace(p)

def publish_stage(folder,cycle,stage,poses,sizes,sides,record):
    """Commit each returned stage before another quench can begin."""
    assert poses.ndim==3 and poses.shape[-1]==3 and sizes.shape==sides.shape==(len(poses),)
    assert np.isfinite(poses).all()and np.isfinite(sizes).all()and ((sizes>0)&(sizes<=1)).all()
    packet=Path(folder)/f'cycle-{cycle:02d}-stage-{stage:02d}.npz'
    archive(packet,poses=poses,birth_sizes=sizes,sides=sides)
    result=dict(record,stage=stage,birth_sizes=sizes.tolist(),eligible_for_finish=bool((sizes==1.).all()),
        verified=False,all_existing_unit_sizes=1.,birth_row=poses.shape[1]-1,
        raw_packet=packet.name,raw_packet_sha256=sha(packet))
    save(packet.with_suffix('.json'),result)
    return result

def stop_groups(children):
    """Each registered arm owns a group containing every native descendant."""
    stopped=[]
    for process in children:
        live=process.poll()is None
        try:os.killpg(process.pid,signal.SIGKILL)
        except ProcessLookupError:pass
        try:process.wait(timeout=2.)
        except subprocess.TimeoutExpired:raise RuntimeError('Arm group did not terminate')
        stopped.append(dict(pid=process.pid,forced=live,returncode=process.returncode))
    return stopped

def configuration(root):
    config=json.loads((root/'birth-config.json').read_text());proof=json.loads((root/'input-proof.json').read_text())
    assert config['inputs_sha256']==proof['inputs_sha256']==sha(root/'birth-inputs.npz')
    assert config['design_sha256']==proof['design_sha256']==sha(root/'chain-design.json')
    assert config['chains']==32 and config['search_seconds']==300 and config['maximum_cycles']==32
    assert config['quench_steps_per_growth_stage']==1200 and config['whole_seconds']==600
    assert config['finish_slots_per_case']==4 and config['finish_workers_per_case']==2
    assert config['no_cross_size_metropolis']and config['fresh_optimizer_history_every_growth_stage']
    design=json.loads((root/'chain-design.json').read_text())
    with np.load(root/'birth-inputs.npz',allow_pickle=False)as z:bank={k:z[k].copy()for k in z.files}
    for key,p in bank.items():
        r=proof['arrays'][key]
        assert list(p.shape)==r['shape']and p.dtype.str==r['dtype']and hashlib.sha256(p.tobytes()).hexdigest()==r['geometry_sha256']
    return config,proof,design,bank

def arm(args):
    import cupy as cp
    from birth_cuda import Solver
    from birth_gpu_preflight import live_preflight
    from birth_finish import finish
    root=Path.cwd();config,proof,designs,bank=configuration(root)
    n=args.case;assert n in (498,587)and args.device==(0 if n==498 else 1)
    rows=designs[str(n)];assert len(rows)==32 and all(r['n']==n and r['chain']==i for i,r in enumerate(rows))
    out=root/'outputs'/f'case-{n}';out.mkdir(parents=True,exist_ok=False)
    cp.cuda.Device(args.device).use();solver=Solver(cp,root/'vendor/lightning_ftmc/gpu_topology.py')
    initial=np.stack([np.vstack((bank[r['source_key']],r['birth_pose']))for r in rows]);sides=np.array([r['fixed_side']for r in rows])
    assert initial.shape==(32,n,3)and np.isfinite(initial).all()
    archive(out/'initial-unverified.npz',poses=initial,sides=sides,birth_sizes=np.full(32,.05))
    save(out/'chain-design.json',rows)
    preflight=live_preflight(solver,initial,sides,args.device,out)
    save(out/'preflight.json',preflight)
    print(json.dumps(dict(stage='birth_preflight',n=n,passed=True,seconds=preflight['seconds'])),flush=True)
    while not(root/'search-go.json').exists():
        if time.monotonic()>=args.deadline-150.:raise RuntimeError('No bounded paired preflight release')
        time.sleep(.1)
    go=json.loads((root/'search-go.json').read_text());deadline=min(go['search_deadline'],args.deadline-145.)
    rng=np.random.default_rng(config['seed']+n);full_states=[];full_energy=[];cycles=[]
    growthdir=out/'growth-unverified';growthdir.mkdir()
    for cycle in range(config['maximum_cycles']):
        if time.monotonic()>=deadline:break
        q=initial.copy();scale=config['restart_center_jitter'][cycle%4];angle=config['restart_angle_jitter'][cycle%4]
        if cycle:
            q[:,:,:2]+=rng.normal(0,scale,q[:,:,:2].shape);q[:,:,2]+=rng.normal(0,angle,q[:,:,2].shape)
            # A new angle/center start, never a cross-size acceptance comparison.
            q[:,-1,:2]+=rng.normal(0,.04*(1+cycle%3),(32,2))
        archive(growthdir/f'cycle-{cycle:02d}-start.npz',poses=q,sides=sides,birth_sizes=np.full(32,.05))
        stages=[];stage_arrays={};finished=False;began=time.monotonic()
        for stage in range(12):
            if time.monotonic()>=deadline:break
            sizes=np.array([r['growth_schedule'][stage]for r in rows]);before=solver.energy(q,sides,sizes)[0]
            q,native=solver.quench(q,sides,sizes,steps=1200)
            after=solver.energy(q,sides,sizes)[0]
            assert np.isfinite(q).all()and np.isfinite(after).all()
            stage_record=dict(stage=stage,birth_sizes=sizes.tolist(),fresh_optimizer_history=True,
                energy_before=before[:,0].tolist(),energy_after=after[:,0].tolist(),max_overlap=after[:,1].tolist(),
                native_report=native.tolist())
            stages.append(publish_stage(growthdir,cycle,stage,q,sizes,sides,stage_record))
            # Only the final common size1 stage enters the candidate pool.
            if stage==11:
                assert(sizes==1.).all();full_states.append(q.copy());full_energy.append(after[:,0].copy());finished=True
        if stages:
            save(growthdir/f'cycle-{cycle:02d}.json',dict(cycle=cycle,source='Exact certified scaffold plus screened small birth; later jitter may overlap.',
                stages=stages,raw_geometry_status='UNVERIFIED proposals, mixed sizes unless explicit size1'))
        cycles.append(dict(cycle=cycle,finished_all_lambda1=finished,stages=len(stages),seconds=time.monotonic()-began,
            center_jitter=scale,angle_jitter=angle,full_lambda1_batches=len(full_states)))
        archive(out/'full-lambda1-states.npz',**{f'cycle_{i:02d}':p for i,p in enumerate(full_states)},
                energies=np.asarray(full_energy),sides=sides,birth_size=np.array(1.))
        save(out/'search-heartbeat.json',dict(n=n,cycles=cycles,full_batches=len(full_states),last_stage_count=len(stages)))
        print(json.dumps(dict(stage='birth_cycle',n=n,cycle=cycle,stages=len(stages),full=finished,
            min_full_energy=float(np.min(full_energy[-1]))if full_energy else None)),flush=True)
        assert sum(p.nbytes for p in full_states)<=config['maximum_full_state_bytes_per_case']
        if not finished:break
    if full_states:
        case=config['cases'][str(n)];summary=finish(out/'finish',full_states,full_energy,rows,
            dict(n=n,reference_side=case['reference_side']),root/'bin/fq',min(args.deadline,time.monotonic()+140.))
    else:summary=dict(slots=0,certified=0,status='no_completed_full_lambda1_state')
    result=dict(status='complete',n=n,cycles=cycles,full_lambda1_batches=len(full_states),finish=summary,
        actual_seconds=time.monotonic()-STARTED,preflight_sha256=sha(out/'preflight.json'),
        full_states_sha256=sha(out/'full-lambda1-states.npz')if full_states else None,
        no_submission=True,no_canonical_mutation=True)
    save(out/'summary.json',result);print(json.dumps(dict(stage='birth_arm_complete',**result)),flush=True)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--case',type=int);parser.add_argument('--device',type=int)
    parser.add_argument('--deadline',type=float);args=parser.parse_args()
    if args.case is not None:return arm(args)
    root=Path.cwd();configuration(root);(root/'outputs').mkdir(exist_ok=False)
    deadline=STARTED+570.;children=[];began=time.monotonic()
    try:
        for device,n in enumerate((498,587)):
            children.append(subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'--case',str(n),'--device',str(device),'--deadline',str(deadline)],start_new_session=True))
            save(root/'arm-groups.json',dict(parent_pid=os.getpid(),groups=[p.pid for p in children]))
        # Both actual preflights must pass before either search starts.
        while time.monotonic()<min(deadline-450.,began+75.):
            if any(p.poll()is not None for p in children):break
            paths=[root/'outputs'/f'case-{n}'/'preflight.json'for n in(498,587)]
            if all(p.exists()and json.loads(p.read_text()).get('passed')for p in paths):
                save(root/'search-go.json',dict(search_deadline=min(time.monotonic()+300.,deadline-145.),
                    preflight_sha256=[sha(p)for p in paths],search_seconds=300));break
            time.sleep(.2)
        if not(root/'search-go.json').exists():raise RuntimeError('Paired actual CUDA preflight failed or timed out')
        while any(p.poll()is None for p in children)and time.monotonic()<deadline:time.sleep(.2)
        stopped=stop_groups(children)
        result=dict(status='complete'if all(p.poll()==0 for p in children)else'bounded_partial',
            returncodes=[p.poll()for p in children],seconds=time.monotonic()-STARTED,whole_cap=600,
            search_seconds=300,devices=[0,1],stopped_groups=stopped,outputs_frozen_before_hashing=True,
            no_submission=True,no_canonical_mutation=True)
        save(root/'completion.json',result)
        inventory={p.relative_to(root).as_posix():dict(sha256=sha(p),bytes=p.stat().st_size)
            for p in(root/'outputs').rglob('*')if p.is_file()}
        save(root/'output-manifest.json',inventory)
        with zipfile.ZipFile(root/'birth-results.zip','w',compression=zipfile.ZIP_STORED)as z:
            for name in sorted(inventory):z.write(root/name,name)
            z.write(root/'completion.json','completion.json');z.write(root/'output-manifest.json','output-manifest.json')
        result['aggregate_sha256']=sha(root/'birth-results.zip');result['aggregate_bytes']=(root/'birth-results.zip').stat().st_size
        save(root/'completion.json',result);print(json.dumps(dict(stage='birth_job_complete',**result)),flush=True)
    finally:
        stop_groups(children)

if __name__=='__main__':main()
