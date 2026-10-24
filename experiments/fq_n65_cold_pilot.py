"""One finite n65 persistent-cold pilot; unchanged corrected rigid quench."""
from __future__ import annotations
import argparse
import hashlib
import inspect
import json
import os
from pathlib import Path
import time
for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[name]='1'
import numpy as np
import torch
import fq_restart_hop_pilot as prior
from fq_torch_hop import physical_energy,acceptance,mutate
from packer_hop_physical_energy import physical_energy as independent_energy

PRIOR_SHA='fd1b34f98fb4759309ce8accb535b62cfb7b374ce6c3be75cbbe647949b6f297'
SEED=116506501
hop=prior.hop
fused=prior.fused
CUDA_OPTIONS=prior.CUDA_OPTIONS
assert hop.digest(prior.__file__)==PRIOR_SHA
replace_once=prior.replace_once
recover_terminal=prior.recover_terminal


def design(reference_side,source_keys):
    assert len(source_keys)==16 and len(set(source_keys))==16
    return [dict(chain=16*j+i,arm='cold',n=65,delta=delta,
        side=float(reference_side)-delta,temperature=.3,amplitude=1.,
        source_key=key,source_group=i,case_seed=SEED+65,stream_chain=16*j+i,
        seed_recipe='SeedSequence([case_seed,round,chain,41]); independent acceptance domain2718')
        for j,delta in enumerate((.0005,.002)) for i,key in enumerate(source_keys)]


def random_streams(seed,round_number):
    return [np.random.default_rng(np.random.SeedSequence([int(seed),int(round_number),b,41])) for b in range(32)]


def acceptance_uniforms(seed,round_number):
    return np.random.default_rng(np.random.SeedSequence([int(seed),int(round_number),2718])).random(32)


def reset_mask(rows,rounds,cooling,initial,cooling_reset_done,last_periodic_round):
    return dict(mask=np.zeros(len(rows),dtype=bool),periodic=False,cooling=False)


def temperature_schedule(base,absolute_deadline,decision_time):
    phase='cool' if decision_time>=absolute_deadline-100. else 'hot'
    return np.asarray(base)*(.1 if phase=='cool' else 1.),phase


def chain_design(source_keys):
    config=json.loads(Path('case-config.json').read_text())
    assert source_keys==config['source_keys'] and config['n']==65
    return design(config['reference_side'],source_keys)


def generated_search_source():
    source=prior.generated_search_source()
    # All occurrences are the reviewed search epoch, reserve/cooling boundary,
    # and reporting strings. The numerical quench/acceptance remains unchanged.
    assert source.count('600')==3 and source.count('150.')==3
    source=source.replace('600','300').replace('150.','100.')
    source=replace_once(source,"search_300s_deadline_minus150s","search_300s_deadline_minus100s")
    source=replace_once(source,'cooling_entered=cooling_reset_done',"cooling_entered=temperature_phase=='cool'")
    return source


def search(deadline):
    namespace=dict(vars(hop))
    namespace.update(PacketStore=prior.RestartPacketStore,chain_design=chain_design,
        fused_quench=fused_quench,random_streams=random_streams,
        acceptance_uniforms=acceptance_uniforms,reset_mask=reset_mask,
        temperature_schedule=temperature_schedule)
    exec(compile(generated_search_source(),'<n65 finite cold search>','exec'),namespace)
    namespace['search_main'](deadline)


def _install_counted_adapters():
    sources={}
    sources['fused_quench']=replace_once(inspect.getsource(prior.fused_quench),'in (453,693)','in (65,)')
    code=inspect.getsource(prior.preflight)
    code=replace_once(code,"with np.load('pilot-inputs.npz',allow_pickle=False) as archive: p=archive[config['source_key']]",
        "with np.load('pilot-inputs.npz',allow_pickle=False) as archive: bank={k:archive[k].copy() for k in archive.files}\n    p=bank[config['source_key']]")
    code=replace_once(code,"rows=chain_design([config['source_key']])","rows=chain_design(config['source_keys'])")
    code=replace_once(code,'initial=np.stack([p.copy() for _ in rows])',"initial=np.stack([bank[r['source_key']].copy() for r in rows])")
    code=replace_once(code,'assert np.array_equal(proposals[:16],proposals[16:])',
        'assert len({hashlib.sha256(q.tobytes()).hexdigest() for q in proposals})==32')
    code=replace_once(code,'paired_output_equal=bool(np.array_equal(q[:16],q[16:]))',
        'unique_output_count=len({hashlib.sha256(pose.tobytes()).hexdigest() for pose in q})')
    code=replace_once(code,'    paired_output_max_difference=float(np.max(abs(q[:16]-q[16:])))\n','')
    code=replace_once(code,'paired_input_bytes_equal=True,proposal_input_unchanged=True,',
        'independent_input_count=32,proposal_input_unchanged=True,')
    code=replace_once(code,'paired_output_bytes_equal=paired_output_equal,paired_output_max_difference=paired_output_max_difference,',
        'unique_output_count=unique_output_count,exploratory_unpaired=True,')
    code=replace_once(code,'paired_acceptance_equal=bool(np.array_equal(accepted[:16],accepted[16:])),scalar_acceptance_checked=True,',
        'independent_acceptance_draws=True,scalar_acceptance_checked=True,')
    sources['preflight']=code
    # This function dispatches __file__, so compile into this module's live
    # globals; the old module's subprocess launcher must not be called directly.
    sources['run_phase']=inspect.getsource(prior.run_phase)
    for name,source in sources.items():
        exec(compile(source,'<n65 cold '+name+'>','exec'),globals())
    return {name:hashlib.sha256(source.encode()).hexdigest() for name,source in sources.items()}


# Names used by the exact copied phase launcher.
import subprocess,sys
kill_tree=prior.kill_tree
ADAPTER_HASHES=_install_counted_adapters()


def parent_main():
    started=time.monotonic();root=Path.cwd()
    config=json.loads(Path('n65-cold-config.json').read_text())
    assert config['seed']==SEED and config['search_seconds']==300 and config['cooling_seconds']==100
    assert config['quench_steps']==2000 and config['chains']==32 and config['temperature']==.3
    assert config['cuts']==[.0005,.002] and config['amplitudes']==[1.]
    assert config['finish_workers_per_case']==4 and config['finish_slots_per_case']==8
    assert config['finish_native_seconds']==60 and config['finish_certificate_seconds']==8
    assert config['cuda_options']==list(CUDA_OPTIONS) and set(config['cases'])=={'65'}
    assert 0<config['max_packets']<=2000 and 0<config['max_bytes']<=2*1024**3
    proof=json.loads(Path('n65-cold-input-proof.json').read_text())
    assert hop.digest('n65-cold-inputs.npz')==config['inputs_sha256']==proof['inputs_sha256']
    with np.load('n65-cold-inputs.npz',allow_pickle=False) as archive:bank={key:archive[key].copy() for key in archive.files}
    assert set(bank)==set(proof['arrays'])
    for key,p in bank.items():
        record=proof['arrays'][key]
        assert p.shape==(65,3) and np.isfinite(p).all()
        assert list(p.shape)==record['shape'] and p.dtype.str==record['dtype']
        assert hashlib.sha256(p.tobytes()).hexdigest()==record['sha256']
    case=dict(config['cases']['65']);assert case['n']==65 and case['device']==0
    assert len(case['source_keys'])==16 and len(set(case['source_keys']))==16
    assert set(case['source_keys'])<set(bank) and case['source_key'] in bank
    assert case['source_key'] not in case['source_keys']
    assert hashlib.sha256(bank[case['source_key']].tobytes()).hexdigest()==case['source_geometry_sha256']
    binary=(root/config.get('binary_path','bin/fq')).resolve();binary.chmod(0o500)
    assert hop.digest(binary)=='10ec7cf773ac0ebca3791d5cfb84e9ecbb10e3f0a9e43194330c80e1cfc9dc3d'
    folder=root/'case-65';folder.mkdir()
    with (folder/'pilot-inputs.npz').open('wb') as stream:np.savez(stream,**bank)
    fixture=dict(n=65,inputs_sha256=hop.digest(folder/'pilot-inputs.npz'),
        exploratory_sources=case['source_keys'],arrays=proof['arrays'])
    case.update(binary_path=str(binary),baseline_sha256=config['baseline']['sha256'])
    hop.atom_json(folder/'case-config.json',case);hop.atom_json(folder/'pilot-config.json',fixture)
    hop.atom_json(folder/'hop-config.json',dict(search_seconds=300,seed=SEED+65,
        max_packets=config['max_packets'],max_bytes=config['max_bytes']))
    controls=run_phase(root,[case],'preflight',started+80)
    assert controls['65']['returncode']==0 and json.loads((folder/'preflight.json').read_text())['passed']
    print(json.dumps(dict(stage='actual_n65_tie_lastunit_controls_passed',controls=controls)),flush=True)
    deadline=time.monotonic()+300
    assert deadline<=started+385
    searches=run_phase(root,[case],'search',deadline)
    os.chdir(folder)
    try:
        recovery=recover_terminal();hop.atom_json('recovery.json',recovery)
    finally:os.chdir(root)
    finishes=run_phase(root,[case],'finish',min(time.monotonic()+165,started+550))
    names=('preflight.json','hop-status.json','pilot-summary.json','recovery.json','finish-summary.json')
    outputs={name:json.loads((folder/name).read_text()) for name in names if (folder/name).exists()}
    unexpected=[dict(case=n,**r) for phase in (searches,finishes) for n,r in phase.items() if r['returncode']!=0 and not r['forced']]
    summary=dict(controls_passed=True,seconds=time.monotonic()-started,controls=controls,
        searches=searches,finishes=finishes,case_summaries={'65':outputs},
        status='unexpected_child_failure' if unexpected else 'complete_or_bounded_partial',
        unexpected_child_failures=unexpected,search_seconds=300,
        devices_used=1,devices_allocated=2,no_submission=True,no_pointer_mutation=True,
        interpretation='Unverified physical energy is not a feasible packing or a score.')
    hop.atom_json('pilot-summary.json',hop.json_finite(summary));print(json.dumps(hop.json_finite(summary)),flush=True)
    if unexpected:raise SystemExit(1)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--phase',choices=('preflight','search','finish'))
    p.add_argument('--case',type=int);p.add_argument('--deadline',type=float);args=p.parse_args()
    if args.phase=='preflight':return preflight()
    if args.phase=='search':return search(args.deadline)
    if args.phase=='finish':
        from fq_n65_cold_finish import finish_case
        result=finish_case(Path.cwd(),json.loads(Path('case-config.json').read_text()),args.deadline)
        hop.atom_json('finish-summary.json',result);return
    return parent_main()


if __name__=='__main__':main()
