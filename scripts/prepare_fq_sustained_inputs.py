#!/usr/bin/env python3
"""Freeze twelve current references and existing evidence; no optimizer/gates."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import types
import numpy as np
import build_fq_restart_hop_job as builder

ROOT=Path(__file__).resolve().parents[1]
CASES=(412,544,742,591,744,641,411,462,978,541,629,341)
RAW_SHA='77072a68f862fc166264825aa19a1eb867692bf280ca531965499fab2e6baea0'
BUILDER_SHA='42207fe5db2dd6156128f6f917f91e6d607ff9d37767a6a71f7bc010ca829b03'
OCCUPANCY_SHA='81a09aef42e7ac1ea0c3887a6800f01d3151653680b4d6a2267b7ffb7b30706c'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def save(path,value):Path(path).write_text(json.dumps(value,indent=2)+'\n')


def prepare(out):
    assert not out.exists() and sha(builder.__file__)==BUILDER_SHA
    pointer=json.loads((ROOT/'artifacts/current-best-portfolio.json').read_text())
    assert pointer['raw']['sha256']==RAW_SHA
    function=types.FunctionType(builder.prepare_inputs.__code__,dict(vars(builder),CASES=CASES))
    function(ROOT/'artifacts/current-best-portfolio.json',out)
    proof=json.loads((out/'restart-input-proof.json').read_text())
    old=json.loads((out/'restart-config.json').read_text())
    assert old['baseline']['sha256']==RAW_SHA
    occupancy_path=ROOT/'artifacts/fq-mixed-precision-review-v1/independent-occupancy-analysis.json'
    assert sha(occupancy_path)==OCCUPANCY_SHA
    occupancy=json.loads(occupancy_path.read_text());assert occupancy['fp64_controls_passed']
    row=next(r for r in occupancy['occupancy'] if r['batch']==64)
    assert row['all_duplicate_input_rows_and_labels_verified']
    controls_path=ROOT/'artifacts/fq-sustained-reference-controls-v1/results.json'
    controls=json.loads(controls_path.read_text());assert {r['n'] for r in controls}==set(CASES)
    assert all(r['status']=='certified' for r in controls)
    bindings={}
    with np.load(out/'restart-inputs.npz',allow_pickle=False) as archive:
        for n in CASES:
            control=next(r for r in controls if r['n']==n)
            original=archive[f'original_{n}'];bound=proof['cases'][str(n)]
            matched_output=hashlib.sha256(original.tobytes()).hexdigest()==control['geometry_sha256']
            if n in (411,544):assert matched_output
            bindings[str(n)]=dict(source=bound,control_slot=control['slot'],
                control_native_input_sha256=control['input_sha256'],control_native_output_sha256=control['native_output_sha256'],
                control_output_geometry_sha256=control['geometry_sha256'],control_certificate=control['certificate'],
                control_worst_certified_side=control['worst_certified_side'],
                current_original_equals_control_output=matched_output,
                comparison_scope='Original baseline control completed once. Winning411/544 control outputs were merged before this freeze; controls are not rerun remotely.')
    evidence=out/'evidence';evidence.mkdir()
    sources=[occupancy_path,ROOT/'artifacts/fq-mixed-precision-results-v1/completion-proof.json',
        ROOT/'artifacts/fq-sustained-cohort-v1/selection.json',controls_path,
        ROOT/'artifacts/fq-sustained-reference-controls-v1/execution-manifest.json',
        ROOT/'artifacts/fq-sustained-reference-controls-v1/summary.json',
        ROOT/'artifacts/fq-sustained-reference-controls-review-v1.json']
    pins={}
    for i,path in enumerate(sources):
        name=f'{i:02d}-{path.name}';shutil.copyfile(path,evidence/name)
        pins[name]=dict(original_path=str(path.relative_to(ROOT)),sha256=sha(path))
    shutil.copyfile(__file__,out/'prepare-sustained-inputs.py')
    shutil.copyfile(out/'restart-inputs.npz',out/'sustained-inputs.npz')
    decision=dict(batch_size=64,production_precision='float64',row_equivalence_passed=True,
        row_equivalence_scope='Initial FP64 energy/gradient and exact source-row duplication; endpoints are NOT bitwise equal.',
        independent_report_sha256=OCCUPANCY_SHA,actual_fixture='n803_early',
        measured_combined_rows_per_second=row['solver_plus_dense_rows_per_second'],
        combined_speedup_over_B32=occupancy['throughput_gain_combined_B64_vs_B32'],
        endpoint_quality_scope='No demonstrated systematic median loss on one actual fixture, compared with repeatedB32 variation. Not a search-benefit or twelve-case generalization proof.',
        choice='B64:28.5percent more combinedthroughput than32;128 adds7.5percent at about2x dense memory. Every actualcase still requires controls.')
    cases={str(n):{k:v for k,v in old['cases'][str(n)].items() if k!='device'} for n in CASES}
    config=dict(cases=cases,inputs_sha256=sha(out/'sustained-inputs.npz'),baseline=old['baseline'],batch_size=64,
        batch_decision=decision,search_seconds=360,cooling_seconds=100,cuts=[.0005,.002],temperature=.3,
        amplitudes=[1.,1.5],seed=116240001,raw_bytes_per_case=768*1024**2,output_bytes_total=12*1024**3,
        quench_steps=2000,cuda_options=['--std=c++17','--fmad=false'],finish_workers_per_case=2,
        finish_native_seconds=60,finish_certificate_seconds=8,finish_slots_per_case=4,
        preflight_seconds=45,search_initialization_seconds=10,search_finalization_seconds=20,
        recovery_seconds=3,finish_phase_seconds=145,parent_queue_seconds=3540,parent_summary_seconds=30,
        whole_seconds=3600,server_seconds=4200,matched_reference_controls_repeated_remotely=False)
    save(out/'sustained-config.json',config)
    fullproof=dict(original_preparation=proof,inputs_sha256=config['inputs_sha256'],arrays=proof['arrays'],
        cases=bindings,baseline=old['baseline'],batch_decision=decision,evidence=pins,
        preparation_source_sha256=sha(__file__),frozen_input_builder_sha256=BUILDER_SHA,
        canonical_baseline_rechecked_after_preparation=json.loads((ROOT/'artifacts/current-best-portfolio.json').read_text())['raw']['sha256']==RAW_SHA,
        no_new_geometry_certification=True,no_optimization=True,no_submission=True)
    assert fullproof['canonical_baseline_rechecked_after_preparation']
    save(out/'sustained-input-proof.json',fullproof)
    report=dict(inputs_sha256=config['inputs_sha256'],config_sha256=sha(out/'sustained-config.json'),
        proof_sha256=sha(out/'sustained-input-proof.json'),arrays=24,cases=12,baseline_raw_sha256=RAW_SHA,batch_size=64)
    save(out/'preparation-receipt.json',report)
    for path in out.rglob('*'):
        if path.is_file():path.chmod(0o444)
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',type=Path,required=True)
    prepare(parser.parse_args().out.resolve())
