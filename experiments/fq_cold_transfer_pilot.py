"""Exploratory independent cold chains on two new full-packing cases.

Only orchestration, case design and finishing allocation differ from the
reviewed restart pilot. The corrected CUDA objective and physical acceptance
remain unchanged. No reset or paired comparison is performed.
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
from fq_torch_hop import physical_energy,acceptance,mutate
from packer_hop_physical_energy import physical_energy as independent_energy

PRIOR_SHA='fd1b34f98fb4759309ce8accb535b62cfb7b374ce6c3be75cbbe647949b6f297'
SEED=105833501
CASES=(803,861)
hop=prior.hop
fused=prior.fused
CUDA_OPTIONS=prior.CUDA_OPTIONS
assert hop.digest(prior.__file__)==PRIOR_SHA
replace_once=prior.replace_once
recover_terminal=prior.recover_terminal
kill_tree=prior.kill_tree


def design(case_n,reference_side,source_key):
    rows=[]
    for chain in range(32):
        delta=(.002,.008)[chain//16]
        rows.append(dict(chain=chain,arm='cold',n=int(case_n),delta=delta,
            side=float(reference_side)-delta,temperature=.3,
            amplitude=(1.,1.5)[chain%2],source_key=source_key,
            case_seed=SEED+int(case_n),stream_chain=chain,
            seed_recipe='SeedSequence([case_seed,round,chain,41]); independent acceptance domain2718'))
    return rows


def random_streams(seed,round_number):
    return [np.random.default_rng(np.random.SeedSequence([int(seed),int(round_number),b,41])) for b in range(32)]


def acceptance_uniforms(seed,round_number):
    return np.random.default_rng(np.random.SeedSequence([int(seed),int(round_number),2718])).random(32)


def reset_mask(rows,rounds,cooling,initial,cooling_reset_done,last_periodic_round):
    """Inactive compatibility hook; every chain is persistent in every phase."""
    return dict(mask=np.zeros(len(rows),dtype=bool),periodic=False,cooling=False)


def chain_design(source_keys):
    config=json.loads(Path('case-config.json').read_text())
    assert source_keys==[config['source_key']]
    return design(config['n'],config['reference_side'],source_keys[0])


def generated_search_source():
    source=prior.generated_search_source()
    source=replace_once(source,'cooling_entered=cooling_reset_done',
        "cooling_entered=temperature_phase=='cool'")
    return source


def search(deadline):
    namespace=dict(vars(hop))
    namespace.update(PacketStore=prior.RestartPacketStore,chain_design=chain_design,
        fused_quench=fused_quench,random_streams=random_streams,
        acceptance_uniforms=acceptance_uniforms,reset_mask=reset_mask,
        temperature_schedule=prior.temperature_schedule)
    source=generated_search_source()
    exec(compile(source,'<independent cold transfer search>','exec'),namespace)
    namespace['search_main'](deadline)


def _install_counted_adapters():
    sources={}
    code=inspect.getsource(prior.fused_quench)
    code=replace_once(code,'in (453,693)','in (803,861)')
    sources['fused_quench']=code
    code=inspect.getsource(prior.preflight)
    code=replace_once(code,'assert np.array_equal(proposals[:16],proposals[16:])',
        "assert len({hashlib.sha256(q.tobytes()).hexdigest() for q in proposals})==32")
    code=replace_once(code,'paired_output_equal=bool(np.array_equal(q[:16],q[16:]))',
        'unique_output_count=len({hashlib.sha256(pose.tobytes()).hexdigest() for pose in q})')
    code=replace_once(code,'    paired_output_max_difference=float(np.max(abs(q[:16]-q[16:])))\n','')
    code=replace_once(code,'paired_input_bytes_equal=True,proposal_input_unchanged=True,',
        'independent_input_count=32,proposal_input_unchanged=True,')
    code=replace_once(code,'paired_output_bytes_equal=paired_output_equal,paired_output_max_difference=paired_output_max_difference,',
        'unique_output_count=unique_output_count,exploratory_unpaired=True,')
    code=replace_once(code,"paired_acceptance_equal=bool(np.array_equal(accepted[:16],accepted[16:])),scalar_acceptance_checked=True,",
        'independent_acceptance_draws=True,scalar_acceptance_checked=True,')
    sources['preflight']=code
    sources['run_phase']=inspect.getsource(prior.run_phase)
    code=inspect.getsource(prior.parent_main)
    code=replace_once(code,"Path('restart-config.json')","Path('cold-config.json')")
    code=replace_once(code,"assert config['search_seconds']==600 and config['cooling_seconds']==150",
        """assert config['search_seconds']==600 and config['cooling_seconds']==150 and config['seed']==SEED
    assert config['chains']==32 and config['temperature']==.3
    assert config['cuts']==[.002,.008] and config['amplitudes']==[1.,1.5]
    assert config['quench_steps']==2000 and config['cuda_options']==list(CUDA_OPTIONS)
    assert config['finish_native_seconds']==60 and config['finish_certificate_seconds']==8
    assert config['finish_workers_per_case']==2 and config['finish_slots_per_case']==4""")
    code=code.replace("'restart-inputs.npz'","'cold-inputs.npz'")
    assert code.count("'cold-inputs.npz'")==2
    code=replace_once(code,'for n in (453,693)','for n in CASES')
    code=replace_once(code,'finish_deadline=min(time.monotonic()+120,started+830)',
        'finish_deadline=min(time.monotonic()+150,started+855)')
    sources['parent_main']=code
    for name,source in sources.items():
        exec(compile(source,'<cold transfer '+name+'>','exec'),globals())
    return {name:hashlib.sha256(source.encode()).hexdigest() for name,source in sources.items()}


ADAPTER_HASHES=_install_counted_adapters()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase',choices=('preflight','search','finish'))
    parser.add_argument('--case',type=int);parser.add_argument('--deadline',type=float)
    args=parser.parse_args()
    if args.phase=='preflight':return preflight()
    if args.phase=='search':return search(args.deadline)
    if args.phase=='finish':
        from fq_cold_hop_finish import finish_case
        config=json.loads(Path('case-config.json').read_text())
        result=finish_case(Path.cwd(),config,args.deadline)
        hop.atom_json('finish-summary.json',result);return
    return parent_main()


if __name__=='__main__':main()
