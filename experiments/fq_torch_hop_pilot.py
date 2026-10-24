"""Bounded persistent infeasible chains; raw physical energy is not admission."""
from __future__ import annotations
import hashlib
import argparse
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import zipfile
for _name in('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[_name]='1'
import numpy as np
import torch
import fq_torch_alm_pilot as parent
from fq_torch_alm import LiftedBatch
from fq_torch_hop import physical_energy,acceptance,chain_design,mutate
from full_structural_gpu_moves import geometry_sha

PARENT_SHA='12d07fd1a294652432d42afc24e6fe4464079484c2cf12eca6f6e946d161665a'
CONTROL_MARKER='    # No optimization stage below is reachable before the live controls pass.'


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def atom_json(path,value):
    path=Path(path);tmp=path.with_suffix('.incoming')
    tmp.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n');tmp.replace(path)


def json_finite(value):
    if isinstance(value,np.ndarray):return json_finite(value.tolist())
    if isinstance(value,np.generic):return json_finite(value.item())
    if isinstance(value,float):return value if np.isfinite(value)else None
    if isinstance(value,dict):return{k:json_finite(v)for k,v in value.items()}
    if isinstance(value,(list,tuple)):return[json_finite(v)for v in value]
    return value


class PacketStore:
    """Reserve the complete packet BEFORE proposing; publish BEFORE commit."""
    def __init__(self,root,batch,n,max_packets,max_bytes):
        self.root=Path(root);self.root.mkdir(exist_ok=False);self.entries=[]
        self.max_packets=int(max_packets);self.max_bytes=int(max_bytes);self.used=0
        # Pending input and completed output coexist until index publication.
        self.reserve=2*(6*batch*n*3*8+1024**2+65536)
        if self.max_packets<1 or self.max_bytes<self.reserve:raise ValueError('Insufficient raw packet budget')

    def can_begin(self):return len(self.entries)<self.max_packets and self.used+self.reserve<=self.max_bytes

    def _publish(self,index,arrays,metadata,status):
        hashes={key:hashlib.sha256(np.ascontiguousarray(p).tobytes()).hexdigest()for key,p in arrays.items()}
        metadata=json_finite(dict(metadata,status=status,verified=False,array_sha256=hashes))
        encoded=json.dumps(metadata,allow_nan=False).encode();assert len(encoded)<=1024**2
        arrays=dict(arrays,metadata_json=np.frombuffer(encoded,dtype=np.uint8))
        stream=io.BytesIO()
        with zipfile.ZipFile(stream,'w',compression=zipfile.ZIP_STORED)as archive:
            for key,p in arrays.items():
                buf=io.BytesIO();np.save(buf,p,allow_pickle=False);archive.writestr(key+'.npy',buf.getvalue())
        data=stream.getvalue();assert len(data)<=self.reserve//2
        old=self.entries[index]['bytes']if index<len(self.entries)else 0
        old_path=Path(self.entries[index]['path'])if index<len(self.entries)else None
        assert self.used+len(data)<=self.max_bytes
        suffix='-input'if status=='pending_quench'else''
        path=self.root/f'packet-{index:04d}{suffix}.npz';assert not path.exists()
        temporary=path.with_suffix('.incoming')
        temporary.write_bytes(data);temporary.replace(path)
        entry=dict(index=index,path=str(path),sha256=hashlib.sha256(data).hexdigest(),bytes=len(data),status=status,verified=False)
        if index==len(self.entries):self.entries.append(entry)
        else:self.entries[index]=entry
        self.used+=len(data)-old
        atom_json('raw-index.json',dict(packets=self.entries,total_bytes=self.used,max_bytes=self.max_bytes,
            max_packets=self.max_packets,reserve_per_packet=self.reserve,verified=False))
        if old_path is not None and old_path!=path:old_path.unlink()
        return entry

    def begin(self,arrays,metadata):
        if not self.can_begin():raise RuntimeError('Packet budget must stop search before another proposal')
        index=len(self.entries);self._publish(index,arrays,metadata,'pending_quench');return index

    def complete(self,index,arrays,metadata):
        if index!=len(self.entries)-1 or self.entries[index]['status']!='pending_quench':raise ValueError('Unexpected packet completion')
        return self._publish(index,arrays,metadata,'completed')


def run_parent_preflight(root):
    """Reuse only the pinned, already-reviewed live-control prefix verbatim."""
    source=Path(parent.__file__).read_bytes();assert hashlib.sha256(source).hexdigest()==PARENT_SHA
    text=source.decode();assert text.count(CONTROL_MARKER)==1
    prefix=text[text.index('def main():'):text.index(CONTROL_MARKER)]
    prefix=prefix.replace('def main():','def existing_preflight():',1)
    prefix+='    return dict(passed=True,gates=gates,seconds=time.monotonic()-started)\n'
    namespace=dict(vars(parent));exec(compile(prefix,'<pinned existing ALM preflight>','exec'),namespace)
    directory=root/'preflight';directory.mkdir()
    for name in('pilot-config.json','pilot-inputs.npz'):shutil.copyfile(root/name,directory/name)
    os.chdir(directory)
    try:result=namespace['existing_preflight']()
    finally:os.chdir(root)
    result.update(parent_source_sha256=PARENT_SHA,executed_prefix_sha256=hashlib.sha256(prefix.encode()).hexdigest(),
                  exact_control_artifacts='preflight/')
    atom_json('preflight.json',result);return result


def host_metrics(metrics):
    return{key:value.detach().cpu().numpy()for key,value in metrics.items()}


def temperature_schedule(base,absolute_deadline,decision_time):
    phase = 'cool' if decision_time >= absolute_deadline - 60. else 'hot'
    return np.asarray(base)*(.1 if phase=='cool'else 1.),phase


def search_main(absolute_deadline):
    started=time.monotonic();root=Path.cwd();torch.set_num_threads(1);torch.set_num_interop_threads(1)
    assert torch.cuda.is_available();device=torch.device('cuda:0');assert'T4'in torch.cuda.get_device_name(device)
    config=json.loads(Path('hop-config.json').read_text());assert 0<float(config['search_seconds'])<=180
    preflight=json.loads(Path('preflight.json').read_text());assert preflight['passed']and preflight['parent_source_sha256']==PARENT_SHA
    fixture=json.loads(Path('pilot-config.json').read_text());assert digest('pilot-inputs.npz')==fixture['inputs_sha256']
    with np.load('pilot-inputs.npz',allow_pickle=False)as z:bank={k:z[k]for k in z.files}
    assert set(bank)==set(fixture['arrays'])
    for key,p in bank.items():
        row=fixture['arrays'][key]
        assert list(p.shape)==row['shape']and p.dtype.str==row['dtype']and hashlib.sha256(p.tobytes()).hexdigest()==row['sha256']
    design=chain_design(fixture['exploratory_sources']);atom_json('chain-design.json',design)
    current=torch.tensor(np.stack([bank[row['source_key']]for row in design]),dtype=torch.float64,device=device)
    assert current.shape==(32,335,3)
    sides=torch.tensor([row['side']for row in design],dtype=torch.float64,device=device)
    base_temperatures=np.array([row['temperature']for row in design]);rngs=[np.random.default_rng(int(config['seed'])+104729*b)for b in range(32)]
    store=PacketStore('raw-hop',32,335,config['max_packets'],config['max_bytes'])
    current_metrics=host_metrics(physical_energy(current,sides));best=current.clone();best_energy=current_metrics['energy'].copy()
    zero_records=[];counters={};rounds=0;attempted=0;quenches=0;stop_reason='deadline';search_started=time.monotonic()
    deadline=min(float(absolute_deadline),search_started+float(config['search_seconds']))
    status=dict(controls_passed=True,rounds_completed=0,rounds_attempted=0,completed_chain_quenches=0,
                per_temperature_operator={},current_energy=current_metrics['energy'],best_energy=best_energy,
                raw_packets=0,raw_bytes=0,zero_energy_raw_candidates=0,verified=False)

    def save_zero(poses,energy,label):
        folder=Path('zero-energy');folder.mkdir(exist_ok=True)
        for b in np.flatnonzero(energy==0):
            q=poses[b];identity=geometry_sha(q);path=folder/(identity+'.npz')
            if path.exists():continue
            temporary=path.with_suffix('.incoming')
            with temporary.open('wb')as stream:np.savez(stream,pose=q)
            temporary.replace(path)
            record=dict(path=str(path),sha256=digest(path),geometry_sha256=identity,chain=int(b),side=float(sides[b]),
                        origin=label,physical_energy=0.,verified=False,full_gate_pending=True)
            atom_json(path.with_suffix('.json'),record);zero_records.append(record)
            atom_json('zero-energy-index.json',zero_records)

    # Initial quench is explicit initialization, not a hidden Metropolis move.
    initial=True
    while time.monotonic()<deadline and store.can_begin():
        old=current.clone();old_best=best.clone();old_metrics=host_metrics(physical_energy(old,sides))
        assert np.allclose(old_metrics['energy'],current_metrics['energy'],rtol=1e-12,atol=1e-16)
        old_np=old.cpu().numpy();best_np=old_best.cpu().numpy();details=[]
        if initial:proposal=old_np.copy();details=[dict(operator='initial_quench',changed_count=0,selected_count=0)for _ in design]
        else:
            mutated=[]
            for b,row in enumerate(design):
                for resamples in range(4):
                    q,detail=mutate(old_np[b],old_metrics['per_square'][b],rngs[b],row['amplitude'])
                    if detail['changed_count']>0:break
                else:raise ValueError('Repeated actual zero-change move')
                detail['zero_change_resamples']=resamples;mutated.append(q);details.append(detail)
            proposal=np.stack(mutated)
        proposal_tensor=torch.tensor(proposal,dtype=torch.float64,device=device)
        input_metrics=host_metrics(physical_energy(proposal_tensor,sides));save_zero(proposal,input_metrics['energy'],'proposal_input')
        arrays=dict(current_before=old_np,proposal_input=proposal,best_before=best_np,sides=sides.cpu().numpy(),
                    base_temperature=base_temperatures,current_energy=old_metrics['energy'],input_energy=input_metrics['energy'],best_energy_before=best_energy)
        metadata=dict(round=rounds,initialization=initial,design=design,moves=details,quench_radius=0.,fixed_side=True,
                      energy_definition='sum_four_wall_penetration_squared + sum_all_unordered_pair_min_four_axis_penetration_squared',
                      physical_unit_shape=True,source_config_sha256=digest('hop-config.json'))
        packet=store.begin(arrays,metadata)
        state=LiftedBatch(proposal_tensor,sides.clone())
        records=state.stage(0.,True,outer=2,inner=24,tolerance=1e-9,deadline=lambda:time.monotonic()>=deadline)
        assert torch.equal(state.sides,sides)
        quenched=state.poses.detach().clone();proposal_metrics=host_metrics(physical_energy(quenched,sides))
        completed=bool(records)and(len(records)==2 or max(records[-1]['violation'])<1e-9)
        uniform=np.array([rng.random()for rng in rngs])
        # Decision-time schedule is anchored to the parent's hard180s epoch.
        decision_time=time.monotonic()
        temperatures,temperature_phase=temperature_schedule(base_temperatures,float(absolute_deadline),decision_time)
        accepted,rule=acceptance(old_metrics['energy'],proposal_metrics['energy'],temperatures,uniform)
        if initial:accepted[:]=True
        if not completed:accepted[:]=False
        next_current=torch.where(torch.tensor(accepted,device=device)[:,None,None],quenched,old)
        next_energy=np.where(accepted,proposal_metrics['energy'],old_metrics['energy'])
        # Best is over all observed physical input/quench states, independent of acceptance.
        choices=np.stack((best_energy,input_metrics['energy'],proposal_metrics['energy']))
        choice=choices.argmin(0);next_best=old_best.clone()
        for k,poses in((1,proposal_tensor),(2,quenched)):
            mask=torch.tensor(choice==k,device=device);next_best[mask]=poses[mask]
        next_best_energy=choices.min(0)
        proposal_np=quenched.cpu().numpy();save_zero(proposal_np,proposal_metrics['energy'],'proposal_quenched')
        uphill=accepted&rule['uphill']&~np.full(32,initial)
        event=dict(round=rounds,initialization=initial,quench_completed=completed,outer_records=records,moves=details,
            current_energy=old_metrics['energy'],input_energy=input_metrics['energy'],proposal_energy=proposal_metrics['energy'],
            next_energy=next_energy,best_energy=next_best_energy,best_origin_choice=choice,uniform=uniform,
            base_temperature=base_temperatures,temperature=temperatures,temperature_phase=temperature_phase,
            temperature_boundary='decision_time; search_180s_deadline_minus60s',
            search_deadline_monotonic=float(absolute_deadline),decision_time_monotonic=decision_time,
            decision_elapsed_seconds=decision_time-(float(absolute_deadline)-float(config['search_seconds'])),
            sides=sides.cpu().numpy(),accepted=accepted,accepted_uphill=uphill,**rule)
        arrays.update(proposal_quenched=proposal_np,current_after=next_current.cpu().numpy(),best_after=next_best.cpu().numpy(),
                      proposal_energy=proposal_metrics['energy'],next_energy=next_energy,best_energy_after=next_best_energy,
                      uniform=uniform,temperature=temperatures,accepted=accepted,accepted_uphill=uphill)
        entry=store.complete(packet,arrays,dict(metadata,event=event))
        # Packet and event publication precede in-memory state commitment.
        with open('hop-events.jsonl','a')as stream:
            stream.write(json.dumps(json_finite(dict(event,packet=entry)),allow_nan=False)+'\n');stream.flush()
        current=next_current;best=next_best;best_energy=next_best_energy
        current_metrics=host_metrics(physical_energy(current,sides))
        assert np.allclose(current_metrics['energy'],next_energy,rtol=1e-12,atol=1e-16)
        if completed:quenches+=32
        if not initial:
            attempted+=1;rounds+=int(completed)
            for b,row in enumerate(design):
                key=f"baseT{row['temperature']}/{temperature_phase}/T{temperatures[b]}:{details[b]['operator']}"
                count=counters.setdefault(key,dict(proposed=0,completed_quenches=0,accepted=0,accepted_uphill=0,selected_units=0,changed_units=0))
                count['proposed']+=1;count['completed_quenches']+=int(completed);count['accepted']+=int(accepted[b]);count['accepted_uphill']+=int(uphill[b])
                count['selected_units']+=details[b]['selected_count'];count['changed_units']+=details[b]['changed_count']
        initial=False
        status=dict(controls_passed=True,seconds=time.monotonic()-started,search_seconds=time.monotonic()-search_started,
                    rounds_completed=rounds,rounds_attempted=attempted,completed_chain_quenches=quenches,per_temperature_operator=counters,
                    current_energy=current_metrics['energy'],best_energy=best_energy,raw_packets=len(store.entries),raw_bytes=store.used,
                    zero_energy_raw_candidates=len(zero_records),verified=False)
        atom_json('hop-status.json',json_finite(status))
        print(json.dumps(dict(stage='hop',rounds=rounds,seconds=time.monotonic()-search_started,
                              best_energy=float(best_energy.min()),uphill=sum(x['accepted_uphill']for x in counters.values()))),flush=True)
        if zero_records:stop_reason='zero_energy_candidate';break
        if not completed:stop_reason='incomplete_quench_at_deadline';break
    if not store.can_begin()and stop_reason=='deadline':stop_reason='raw_packet_or_byte_cap'
    np.savez('final-current-best.npz',current=current.cpu().numpy(),best=best.cpu().numpy(),sides=sides.cpu().numpy(),
             current_energy=current_metrics['energy'],best_energy=best_energy)
    summary=dict(status,stop_reason=stop_reason,search_limit_seconds=float(config['search_seconds']),max_packets=store.max_packets,
                 max_bytes=store.max_bytes,final_archive_sha256=digest('final-current-best.npz'),controls_passed=preflight['passed'],
                 full_gate_pending=len(zero_records),certified_new_cases=0,native_finishing_performed=False,
                 scope='Persistent infeasible unit-pose chains. Physical floating energy is not a geometry certificate.')
    atom_json('pilot-summary.json',json_finite(summary));print(json.dumps(json_finite(summary)),flush=True)


def recover_completed_packets(index_path):
    """CPU-only recovery; a completed packet is the durable state-commit record."""
    if not Path(index_path).exists():return dict(packets=0,completed=0,pending=0,rounds_completed=0,completed_chain_quenches=0)
    index=json.loads(Path(index_path).read_text());last=None;completed=rounds=quenches=0;counters={}
    for entry in index['packets']:
        path=Path(entry['path']);assert digest(path)==entry['sha256']and path.stat().st_size==entry['bytes']
        if entry['status']!='completed':continue
        with np.load(path,allow_pickle=False)as z:
            metadata=json.loads(z['metadata_json'].tobytes());event=metadata['event']
            assert metadata['status']=='completed';completed+=1
            if event['quench_completed']:quenches+=len(metadata['design'])
            if not event['initialization']:
                rounds+=int(event['quench_completed'])
                for b,row in enumerate(metadata['design']):
                    move=event['moves'][b];key=f"baseT{row['temperature']}/{event['temperature_phase']}/T{event['temperature'][b]}:{move['operator']}"
                    count=counters.setdefault(key,dict(proposed=0,completed_quenches=0,accepted=0,accepted_uphill=0,selected_units=0,changed_units=0))
                    count['proposed']+=1;count['completed_quenches']+=int(event['quench_completed'])
                    count['accepted']+=int(event['accepted'][b]);count['accepted_uphill']+=int(event['accepted_uphill'][b])
                    count['selected_units']+=move['selected_count'];count['changed_units']+=move['changed_count']
        last=entry
    if last is not None:
        with np.load(last['path'],allow_pickle=False)as z:
            arrays={name:z[name]for name in('current_after','best_after','sides','next_energy','best_energy_after')}
            metadata=json.loads(z['metadata_json'].tobytes())
            for name,value in arrays.items():assert hashlib.sha256(value.tobytes()).hexdigest()==metadata['array_sha256'][name]
        with open('final-current-best.npz','wb')as stream:np.savez(stream,**arrays)
    indexed={Path(entry['path'])for entry in index['packets']}
    unindexed=[]
    for path in sorted(Path('raw-hop').glob('packet-*.npz')):
        if path not in indexed:
            with np.load(path,allow_pickle=False)as z:metadata=json.loads(z['metadata_json'].tobytes())
            unindexed.append(dict(path=str(path),sha256=digest(path),status=metadata['status'],verified=False))
    return dict(packets=len(index['packets']),completed=completed,pending=len(index['packets'])-completed,
                total_bytes=index['total_bytes'],rounds_completed=rounds,completed_chain_quenches=quenches,
                per_temperature_operator=counters,last_completed_packet=last,
                unindexed_packet_files=unindexed,
                recovered_final_archive_sha256=digest('final-current-best.npz')if last is not None else None)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--search-child',action='store_true')
    parser.add_argument('--deadline',type=float);args=parser.parse_args()
    if args.search_child:
        if args.deadline is None:raise ValueError('Absolute parent deadline required')
        return search_main(args.deadline)
    root=Path.cwd();started=time.monotonic();config=json.loads(Path('hop-config.json').read_text())
    assert 0<float(config['search_seconds'])<=180
    assert not Path('raw-index.json').exists()and not Path('pilot-summary.json').exists()
    # Only the pinned original prefix initializes Torch's interop threads here.
    preflight=run_parent_preflight(root)
    if time.monotonic()-started>100:raise TimeoutError('Control budget leaves insufficient bounded search time')
    search_started=time.monotonic();deadline=search_started+float(config['search_seconds'])
    # Inherit the worker process group: outer300s kill reaches this child too.
    process=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'--search-child','--deadline',str(deadline)])
    forced=False
    try:process.wait(timeout=max(.01,deadline-time.monotonic()))
    except subprocess.TimeoutExpired:
        forced=True;process.kill();process.wait(timeout=2.)
    # No CUDA work after the hard search bound; recover only persisted CPU bytes.
    recovery=recover_completed_packets('raw-index.json')
    previous=json.loads(Path('pilot-summary.json').read_text())if Path('pilot-summary.json').exists()else{}
    summary=dict(previous,controls_passed=preflight['passed'],seconds=time.monotonic()-started,
                 search_seconds=time.monotonic()-search_started,search_limit_seconds=float(config['search_seconds']),
                 search_child_returncode=process.returncode,hard_search_deadline_enforced=forced,
                 recovery=recovery,certified_new_cases=0,native_finishing_performed=False,
                 status='search_timeout_partial_raw_retained'if forced else('complete'if process.returncode==0 else'search_failed_partial_raw_retained'))
    atom_json('pilot-summary.json',json_finite(summary));print(json.dumps(json_finite(summary)),flush=True)
    if not forced and process.returncode!=0:raise SystemExit(process.returncode)


if __name__=='__main__':main()
