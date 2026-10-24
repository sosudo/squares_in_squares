"""Twelve finite FP64 cold searches, with aligned clocks and bounded retention.

The numerical quench is the unchanged reviewed symmetric-tie implementation.
Only case/batch policy, wall clocks, retention guards and queue orchestration
are adapted. Floating physical energy never establishes feasibility.
"""
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
    os.environ[name]='1'
import numpy as np
import torch
import fq_restart_hop_pilot as prior
import fq_cold_transfer_pilot as cold
from fq_torch_hop import physical_energy,acceptance,mutate
from packer_hop_physical_energy import physical_energy as independent_energy

PRIOR_SHA='fd1b34f98fb4759309ce8accb535b62cfb7b374ce6c3be75cbbe647949b6f297'
COLD_SHA='46ee38d3b1e1bdb503abb6bb0efa809d92d0af85d9e6597fbf8849f42c9c8b2b'
CASES=(412,544,742,591,744,641,411,462,978,541,629,341)
QUEUES=((978,742,629,544,462,411),(744,641,591,541,412,341))
SEARCH_SECONDS=360.
COOLING_SECONDS=100.
RAW_BYTES=768*1024**2
PROTECTED_SEARCH_BYTES=128*1024**2
TOTAL_BYTES=12*1024**3
SEED=116240001
hop=prior.hop
fused=prior.fused
CUDA_OPTIONS=prior.CUDA_OPTIONS
replace_once=prior.replace_once
assert hop.digest(prior.__file__)==PRIOR_SHA and hop.digest(cold.__file__)==COLD_SHA


def case_config():
    return json.loads(Path('case-config.json').read_text())


def batch_size():
    value=int(case_config()['batch_size'])
    assert value in (32,64,128)
    return value


def design(n,reference_side,source_key,batch):
    assert n in CASES and batch in (32,64,128)
    return [dict(chain=b,arm='cold',n=n,delta=(.0005,.002)[b//(batch//2)],
        side=float(reference_side)-(.0005,.002)[b//(batch//2)],temperature=.3,
        amplitude=(1.,1.5)[b%2],source_key=source_key,case_seed=SEED+n,
        stream_chain=b,seed_recipe='SeedSequence([case_seed,round,chain,41]); acceptance domain2718')
        for b in range(batch)]


def chain_design(source_keys):
    c=case_config();assert source_keys==[c['source_key']]
    return design(c['n'],c['reference_side'],c['source_key'],batch_size())


def random_streams(seed,round_number):
    return [np.random.default_rng(np.random.SeedSequence([int(seed),int(round_number),b,41]))
        for b in range(batch_size())]


def acceptance_uniforms(seed,round_number):
    return np.random.default_rng(np.random.SeedSequence([int(seed),int(round_number),2718])).random(batch_size())


def temperature_schedule(base,deadline,decision_time):
    phase='cool' if decision_time>=deadline-COOLING_SECONDS else 'hot'
    return np.asarray(base)*(.1 if phase=='cool' else 1.),phase


def tree_bytes(root,exclude_raw=False):
    total=0
    for directory,dirs,names in os.walk(root):
        if exclude_raw and 'raw-hop' in dirs:dirs.remove('raw-hop')
        for name in names:
            try:total+=(Path(directory)/name).stat().st_size
            except FileNotFoundError:pass
    return total


class BoundedPacketStore(prior.RestartPacketStore):
    """Keep half the non-raw allowance free for terminal state and full gates."""
    def can_begin(self):
        self.protected_bytes=tree_bytes(Path.cwd(),exclude_raw=True)
        self.protected_limit_hit=self.protected_bytes>=PROTECTED_SEARCH_BYTES
        return not self.protected_limit_hit and super().can_begin()


def aligned_search_epoch(parent_deadline,seconds):
    """Publish the actual initialized child epoch; reserve twenty seconds to finish."""
    started=time.monotonic();deadline=started+seconds
    if deadline+20.>parent_deadline:
        raise TimeoutError('search initialization exceeded its fixed ten-second allowance')
    hop.atom_json('search-epoch.json',dict(started_monotonic=started,deadline_monotonic=deadline,
        parent_phase_deadline_monotonic=parent_deadline,search_seconds=seconds,
        cooling_start_monotonic=deadline-COOLING_SECONDS,finalization_reserve_seconds=20.,
        clock_scope='Initialized child and controller use the same monotonic clock.'))
    return started,deadline


def generated_search_source():
    source=prior.generated_search_source()
    replacements=[
        ("assert float(config['search_seconds'])==600", "assert float(config['search_seconds'])==SEARCH_SECONDS"),
        ('assert current.shape==(32,n,3)','B=batch_size();assert current.shape==(B,n,3)'),
        ('for b in range(32)]','for b in range(B)]'),
        ("store=PacketStore('raw-hop',32,n,config['max_packets'],config['max_bytes'])",
         "store=PacketStore('raw-hop',B,n,config['max_packets'],config['max_bytes'])"),
        ("zero_records=[];counters={};rounds=0;attempted=0;quenches=0;stop_reason='deadline';search_started=time.monotonic()\n    deadline=min(float(absolute_deadline),search_started+float(config['search_seconds']))",
         "zero_records=[];counters={};rounds=0;attempted=0;quenches=0;stop_reason='deadline'\n    search_started,deadline=aligned_search_epoch(float(absolute_deadline),float(config['search_seconds']))\n    absolute_deadline=deadline\n    tail_guard=max(2.,2.*float(preflight['quench_report']['seconds'])+1.)\n    if tail_guard>20.:raise TimeoutError('Measured quench exceeds reserved finalization budget')"),
        ('while time.monotonic()<deadline and store.can_begin():',
         'while time.monotonic()<deadline-tail_guard and store.can_begin():'),
        ('now<deadline-150.','now<deadline-COOLING_SECONDS'),
        ('pause=min(1.,deadline-150.-now)','pause=min(1.,deadline-COOLING_SECONDS-now)'),
        ('now>=deadline-150.','now>=deadline-COOLING_SECONDS'),
        ('np.full(32,initial)','np.full(B,initial)'),
        ('if completed:quenches+=32','if completed:quenches+=B'),
        ("temperature_boundary='decision_time; search_600s_deadline_minus150s'",
         "temperature_boundary='decision_time; initialized_child360s_deadline_minus100s'"),
        ('cooling_entered=cooling_reset_done',"cooling_entered=temperature_phase=='cool'"),
        ("if not store.can_begin()and stop_reason=='deadline':stop_reason='raw_packet_or_byte_cap'",
         "if not store.can_begin()and stop_reason=='deadline':stop_reason='protected_output_cap' if store.protected_limit_hit else 'raw_packet_or_byte_cap'"),
        ("np.savez('final-current-best.npz',current=current.cpu().numpy(),best=best.cpu().numpy(),sides=sides.cpu().numpy(),\n             current_energy=current_metrics['energy'],best_energy=best_energy)",
         "np.savez('final-current-best.npz',current_after=current.cpu().numpy(),best_after=best.cpu().numpy(),sides=sides.cpu().numpy(),\n             next_energy=current_metrics['energy'],best_energy_after=best_energy)"),
        ("scope='Persistent infeasible unit-pose chains. Physical floating energy is not a geometry certificate.'",
         "actual_search_epoch=json.loads(Path('search-epoch.json').read_text()),tail_guard_seconds=tail_guard,\n                 protected_output_bytes=tree_bytes(Path.cwd(),exclude_raw=True),\n                 scope='Persistent infeasible unit-pose chains. Physical floating energy is not a geometry certificate.'"),
    ]
    for old,new in replacements:source=replace_once(source,old,new)
    compile(source,'<sustained finite cold search>','exec')
    return source


def search(deadline):
    namespace=dict(vars(hop),PacketStore=BoundedPacketStore,chain_design=chain_design,
        fused_quench=fused_quench,random_streams=random_streams,acceptance_uniforms=acceptance_uniforms,
        reset_mask=cold.reset_mask,temperature_schedule=temperature_schedule,batch_size=batch_size,
        SEARCH_SECONDS=SEARCH_SECONDS,COOLING_SECONDS=COOLING_SECONDS,
        aligned_search_epoch=aligned_search_epoch,tree_bytes=tree_bytes)
    exec(compile(generated_search_source(),'<sustained finite cold search>','exec'),namespace)
    namespace['search_main'](deadline)


def install_counted_adapters():
    code=inspect.getsource(prior.fused_quench)
    code=replace_once(code,'proposal.shape[0]==32','proposal.shape[0]==batch_size()')
    code=replace_once(code,'proposal.shape[1] in (453,693)','proposal.shape[1] in CASES')
    code=replace_once(code,'sides.shape==(32,)','sides.shape==(batch_size(),)')
    code=replace_once(code,'report.shape==(32,3)','report.shape==(batch_size(),3)')
    sources={'fused_quench':code}
    # Already-reviewed independent cold preflight; expand only shape/policy guards.
    code=inspect.getsource(prior.preflight)
    replacements=[
        ('for b in range(32)','for b in range(batch_size())'),
        ('assert np.array_equal(proposals[:16],proposals[16:])',
         "assert len({hashlib.sha256(q.tobytes()).hexdigest() for q in proposals})==batch_size()"),
        ('paired_output_equal=bool(np.array_equal(q[:16],q[16:]))',
         'unique_output_count=len({hashlib.sha256(pose.tobytes()).hexdigest() for pose in q})'),
        ('    paired_output_max_difference=float(np.max(abs(q[:16]-q[16:])))\n',''),
        ('for b in (0,7,15,16,23,31):','for b in sorted({0,batch_size()//4-1,batch_size()//2-1,batch_size()//2,3*batch_size()//4-1,batch_size()-1}):'),
        ("assert 32/report['seconds']>=2.,'Actual 2000-step full-size interface too slow for finite pilot'",
         "assert report['seconds']<=9.5,'Actual batch quench exceeds twenty-second finalization reserve'"),
        ('paired_input_bytes_equal=True,proposal_input_unchanged=True,',
         'independent_input_count=batch_size(),proposal_input_unchanged=True,'),
        ('paired_output_bytes_equal=paired_output_equal,paired_output_max_difference=paired_output_max_difference,',
         'unique_output_count=unique_output_count,exploratory_unpaired=True,'),
        ('paired_acceptance_equal=bool(np.array_equal(accepted[:16],accepted[16:])),scalar_acceptance_checked=True,',
         'independent_acceptance_draws=True,scalar_acceptance_checked=True,'),
        ("interface_poses_per_second=32/report['seconds']","interface_poses_per_second=batch_size()/report['seconds']"),
    ]
    for old,new in replacements:code=replace_once(code,old,new)
    sources['preflight']=code
    for name,code in sources.items():exec(compile(code,'<sustained '+name+'>','exec'),globals())
    return {name:hashlib.sha256(code.encode()).hexdigest() for name,code in sources.items()}


ADAPTER_HASHES=install_counted_adapters()


def run_child(folder,phase,seconds,global_deadline,device):
    # The parent queue deadline already precedes the separate thirty-second
    # summary allowance. Do not subtract that same reserve a second time.
    deadline=min(time.monotonic()+seconds,global_deadline)
    if deadline-time.monotonic()<seconds-.01:
        return dict(phase=phase,status='skipped_insufficient_fixed_budget',returncode=None,forced=False)
    command=[sys.executable,'-u',str(Path(__file__).resolve()),'--phase',phase,'--deadline',str(deadline)]
    started=time.monotonic();forced=False
    with (folder/(phase+'.log')).open('w') as log:
        process=subprocess.Popen(command,cwd=folder,env=dict(os.environ,CUDA_VISIBLE_DEVICES=str(device)),stdout=log,stderr=subprocess.STDOUT)
        try:process.wait(timeout=max(.01,deadline-time.monotonic()))
        except subprocess.TimeoutExpired:prior.kill_tree(process);forced=True
        finally:
            if process.poll() is None:prior.kill_tree(process)
    return dict(phase=phase,returncode=process.returncode,forced=forced,seconds=time.monotonic()-started,
        phase_limit_seconds=seconds,status='complete' if process.returncode==0 else 'bounded_partial' if forced else 'failed')


class RecoveryDeadline(BaseException):
    pass


def bounded_recovery(folder):
    def expire(signum,frame):raise RecoveryDeadline()
    root=Path.cwd();begin=time.monotonic();old=signal.signal(signal.SIGALRM,expire)
    assert signal.getitimer(signal.ITIMER_REAL)[0]==0
    signal.setitimer(signal.ITIMER_REAL,3.)
    os.chdir(folder)
    try:
        result=prior.recover_terminal();result['recovery_status']='complete'
    except RecoveryDeadline:
        result=dict(completed=0,recovery_status='deadline_partial',raw_files_preserved=True)
    finally:
        signal.setitimer(signal.ITIMER_REAL,0);signal.signal(signal.SIGALRM,old);os.chdir(root)
    result['recovery_seconds']=time.monotonic()-begin
    hop.atom_json(folder/'recovery.json',result)
    return result


def queue_main(device,global_deadline):
    root=Path.cwd();config=json.loads(Path('sustained-config.json').read_text());records={}
    for n in QUEUES[device]:
        folder=root/f'case-{n}';row={};records[str(n)]=row
        if tree_bytes(root)>TOTAL_BYTES:
            row['status']='global_output_limit';break
        row['preflight']=run_child(folder,'preflight',45.,global_deadline,device)
        if row['preflight']['returncode']!=0:
            row['status']='failed_actual_shape_controls';hop.atom_json(f'queue-{device}.json',records);continue
        # Ten initialized-child seconds, 360 search seconds, twenty finalization seconds.
        row['search']=run_child(folder,'search',390.,global_deadline,device)
        row['recovery']=bounded_recovery(folder)
        if row['recovery'].get('completed',0)>0:
            row['finish']=run_child(folder,'finish',145.,global_deadline,device)
        else:row['finish']=dict(status='no_committed_state',returncode=None)
        row['status']='complete' if all(row[k].get('returncode')==0 for k in ('preflight','search','finish')) else 'bounded_partial'
        row['case_bytes']=tree_bytes(folder)
        assert row['case_bytes']<=1024**3,'Protected case output budget exceeded'
        hop.atom_json(f'queue-{device}.json',records)
        print(json.dumps(dict(device=device,n=n,**row)),flush=True)
    hop.atom_json(f'queue-{device}.json',records)


def parent_main():
    started=time.monotonic();root=Path.cwd();config=json.loads(Path('sustained-config.json').read_text())
    assert set(config['cases'])=={str(n) for n in CASES} and config['batch_size']==64
    assert config['search_seconds']==SEARCH_SECONDS and config['cooling_seconds']==COOLING_SECONDS
    assert config['cuts']==[.0005,.002] and config['temperature']==.3 and config['seed']==SEED
    assert config['amplitudes']==[1.,1.5]
    assert config['raw_bytes_per_case']==RAW_BYTES and config['output_bytes_total']==TOTAL_BYTES
    assert config['quench_steps']==2000 and config['cuda_options']==list(CUDA_OPTIONS)
    assert config['finish_workers_per_case']==2 and config['finish_native_seconds']==60 and config['finish_certificate_seconds']==8
    assert config['finish_slots_per_case']==4
    assert config['batch_decision']['production_precision']=='float64' and config['batch_decision']['row_equivalence_passed']
    assert hop.digest('sustained-inputs.npz')==config['inputs_sha256']
    with np.load('sustained-inputs.npz',allow_pickle=False) as archive:bank={key:archive[key].copy() for key in archive.files}
    binary=(root/'bin/fq').resolve();assert hop.digest(binary)=='10ec7cf773ac0ebca3791d5cfb84e9ecbb10e3f0a9e43194330c80e1cfc9dc3d';binary.chmod(0o500)
    for device,queue in enumerate(QUEUES):
        for n in queue:
            case=dict(config['cases'][str(n)]);key=case['source_key'];p=bank[key]
            assert p.shape==(n,3) and p.dtype==np.dtype('<f8') and np.isfinite(p).all()
            assert hashlib.sha256(p.tobytes()).hexdigest()==case['source_geometry_sha256']
            folder=root/f'case-{n}';folder.mkdir()
            with (folder/'pilot-inputs.npz').open('wb') as stream:np.savez(stream,**{key:p})
            fixture=dict(n=n,inputs_sha256=hop.digest(folder/'pilot-inputs.npz'),exploratory_sources=[key],
                arrays={key:dict(shape=list(p.shape),dtype=p.dtype.str,sha256=hashlib.sha256(p.tobytes()).hexdigest())})
            case.update(binary_path=str(binary),device=device,batch_size=config['batch_size'],baseline_sha256=config['baseline']['sha256'])
            hop.atom_json(folder/'case-config.json',case);hop.atom_json(folder/'pilot-config.json',fixture)
            hop.atom_json(folder/'hop-config.json',dict(search_seconds=SEARCH_SECONDS,seed=SEED+n,max_packets=2000,max_bytes=RAW_BYTES))
    deadline=started+3540.;active={};handles=[]
    try:
        for device in (0,1):
            log=(root/f'queue-{device}.log').open('w');handles.append(log)
            command=[sys.executable,'-u',str(Path(__file__).resolve()),'--queue',str(device),'--deadline',str(deadline)]
            active[device]=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT)
        completed={};storage_stop=False
        while active:
            if tree_bytes(root)>TOTAL_BYTES:storage_stop=True
            for device,process in list(active.items()):
                forced=False
                if process.poll() is None and (time.monotonic()>=deadline or storage_stop):prior.kill_tree(process);forced=True
                if process.poll() is not None:
                    completed[str(device)]=dict(returncode=process.returncode,forced=forced);del active[device]
            if active:time.sleep(2.)
    finally:
        for process in active.values():prior.kill_tree(process)
        for handle in handles:handle.close()
    cases={}
    for n in CASES:
        folder=root/f'case-{n}'
        cases[str(n)]={name:json.loads((folder/name).read_text()) for name in
            ('preflight.json','search-epoch.json','hop-status.json','pilot-summary.json','recovery.json','finish-summary.json') if (folder/name).exists()}
    queues={str(device):json.loads((root/f'queue-{device}.json').read_text())
        for device in (0,1) if (root/f'queue-{device}.json').exists()}
    executions={n:row for queue in queues.values() for n,row in queue.items()}
    complete=(set(executions)=={str(n) for n in CASES}
        and all(row['status']=='complete' for row in executions.values())
        and all('finish-summary.json' in row for row in cases.values())
        and all(row['returncode']==0 for row in completed.values()))
    summary=dict(status='complete' if complete else 'bounded_partial',case_execution=executions,
        controls_passed=all(r.get('preflight.json',{}).get('passed',False) for r in cases.values()),
        seconds=time.monotonic()-started,queue_results=completed,case_summaries=cases,global_storage_stop=storage_stop,
        output_bytes=tree_bytes(root),output_limit_bytes=TOTAL_BYTES,batch_size=config['batch_size'],
        planned_search_seconds_per_case=SEARCH_SECONDS,planned_cooling_seconds_per_case=COOLING_SECONDS,
        interpretation='Actual epochs/status/packet commits define coverage; raw energy is not a valid score.',
        no_submission=True,no_pointer_mutation=True)
    hop.atom_json('pilot-summary.json',hop.json_finite(summary));print(json.dumps(hop.json_finite(summary)),flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--phase',choices=('preflight','search','finish'))
    parser.add_argument('--queue',type=int,choices=(0,1));parser.add_argument('--deadline',type=float);args=parser.parse_args()
    if args.phase=='preflight':return preflight()
    if args.phase=='search':return search(args.deadline)
    if args.phase=='finish':
        from fq_sustained_hop_finish import finish_case
        result=finish_case(Path.cwd(),case_config(),args.deadline);hop.atom_json('finish-summary.json',result);return
    if args.queue is not None:return queue_main(args.queue,args.deadline)
    return parent_main()


if __name__=='__main__':main()
