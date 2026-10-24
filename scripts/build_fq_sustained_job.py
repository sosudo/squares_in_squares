#!/usr/bin/env python3
"""Freeze the approved twelve-case FP64 campaign; never launch it."""
from __future__ import annotations
import argparse
import ast
import base64
import hashlib
import io
import json
import lzma
from pathlib import Path
import zipfile
import numpy as np
from build_fq_fused_hop_job import unpack, add_local_import_closure

ROOT = Path(__file__).resolve().parents[1]
PARENT = ROOT/'artifacts/fq-cold-transfer-job-v1/search.py'
PARENT_SHA = '34ea1497cf6e24560eff8da939b3288b08029519640ba1eb8907acc1353d1292'
BINARY_SHA = '10ec7cf773ac0ebca3791d5cfb84e9ecbb10e3f0a9e43194330c80e1cfc9dc3d'
BASELINE_SHA = '77072a68f862fc166264825aa19a1eb867692bf280ca531965499fab2e6baea0'
CASES = (412,544,742,591,744,641,411,462,978,541,629,341)
REMOVED_DATA = ('cold-config.json','cold-inputs.npz','cold-input-proof.json')
NEW_SOURCES = {
    'experiments/fq_sustained_cold_pilot.py': '5b06d48ccac0c9fb1828d80793ddaedd3cb67e8bf4b66f3925b7633d46634c19',
    'experiments/fq_sustained_hop_finish.py': 'e4dd34a61e8d03d512e4ecb29cfdc0bba5ed9dc2a71e898742384cbe4db0387e',
}


def sha(data): return hashlib.sha256(data).hexdigest()
def save(path,value): path.write_text(json.dumps(value,indent=2)+'\n')


def validate_inputs(folder):
    config_bytes=(folder/'sustained-config.json').read_bytes()
    proof_bytes=(folder/'sustained-input-proof.json').read_bytes()
    inputs=(folder/'sustained-inputs.npz').read_bytes()
    config=json.loads(config_bytes);proof=json.loads(proof_bytes)
    if not (sha(inputs)==config['inputs_sha256']==proof['inputs_sha256']
            and config['baseline']['sha256']==proof['baseline']['sha256']==BASELINE_SHA
            and set(config['cases'])==set(proof['cases'])=={str(n) for n in CASES}):
        raise ValueError('Expected exact current twelve-case input binding')
    expected=dict(batch_size=64,search_seconds=360,cooling_seconds=100,cuts=[.0005,.002],temperature=.3,
        amplitudes=[1.,1.5],seed=116240001,raw_bytes_per_case=768*1024**2,output_bytes_total=12*1024**3,
        quench_steps=2000,cuda_options=['--std=c++17','--fmad=false'],finish_workers_per_case=2,
        finish_native_seconds=60,finish_certificate_seconds=8,finish_slots_per_case=4,
        preflight_seconds=45,search_initialization_seconds=10,search_finalization_seconds=20,
        recovery_seconds=3,finish_phase_seconds=145,parent_queue_seconds=3540,parent_summary_seconds=30,
        whole_seconds=3600,server_seconds=4200,matched_reference_controls_repeated_remotely=False)
    if any(config.get(k)!=v for k,v in expected.items()):
        raise ValueError('Unreviewed sustained campaign policy')
    decision=config['batch_decision']
    if not (decision==proof['batch_decision'] and decision['batch_size']==64
            and decision['production_precision']=='float64' and decision['row_equivalence_passed']
            and decision['independent_report_sha256']=='81a09aef42e7ac1ea0c3887a6800f01d3151653680b4d6a2267b7ffb7b30706c'):
        raise ValueError('Exact independent FP64 occupancy decision required')
    with np.load(io.BytesIO(inputs),allow_pickle=False) as archive:
        if set(archive.files)!=set(proof['arrays']) or len(archive.files)!=24:
            raise ValueError('All twelve original and translated poses required')
        for name in archive.files:
            value=archive[name];record=proof['arrays'][name]
            if not (value.dtype.str==record['dtype']=='<f8' and list(value.shape)==record['shape']
                    and sha(value.tobytes())==record['sha256'] and np.isfinite(value).all()):
                raise ValueError('Exact input array differs')
        for n in CASES:
            case=config['cases'][str(n)];record=proof['cases'][str(n)]['source']
            if not (case['n']==n and case['source_key']==record['reference_key']
                    and case['source_geometry_sha256']==record['reference_geometry_sha256']
                    and case['reference_side']==record['original_case_official']['side']
                    and archive[case['source_key']].shape==(n,3)):
                raise ValueError('Case geometry/count/side binding differs')
            if n in (411,544) and not proof['cases'][str(n)]['current_original_equals_control_output']:
                raise ValueError('Current control winners must be included')
    additions={'sustained-config.json':config_bytes,'sustained-inputs.npz':inputs,
               'sustained-input-proof.json':proof_bytes}
    preparation=(folder/'prepare-sustained-inputs.py').read_bytes()
    if sha(preparation)!=proof['preparation_source_sha256']:
        raise ValueError('Input preparer changed')
    additions['provenance/prepare-sustained-inputs.py']=preparation
    old_builder=(ROOT/'scripts/build_fq_restart_hop_job.py').read_bytes()
    if sha(old_builder)!=proof['frozen_input_builder_sha256']:
        raise ValueError('Input preparation dependency changed')
    additions['provenance/sustained-input-builder.py']=old_builder
    for name,record in proof['evidence'].items():
        if Path(name).name!=name: raise ValueError('Evidence filename must be local')
        data=(folder/'evidence'/name).read_bytes()
        if sha(data)!=record['sha256']: raise ValueError('Input evidence changed')
        additions['provenance/sustained-evidence/'+name]=data
    for name in ('portfolio-pointer.json','restart-input-proof.json','preparation-receipt.json'):
        additions['provenance/sustained-'+name]=(folder/name).read_bytes()
    pointer=json.loads(additions['provenance/sustained-portfolio-pointer.json'])
    if pointer['raw']['sha256']!=BASELINE_SHA: raise ValueError('Frozen portfolio pointer differs')
    return config,proof,additions


def build(args):
    if args.out.exists(): raise ValueError('Fresh output directory required')
    source,parent,files=unpack(PARENT,PARENT_SHA,'xz85')
    original={name:sha(data) for name,data in files.items()}
    removed={name:dict(sha256=sha(files[name]),bytes=len(files[name])) for name in REMOVED_DATA}
    for name in REMOVED_DATA: del files[name]
    if sha(files['bin/fq'])!=BINARY_SHA: raise ValueError('Native solver differs')
    config,proof,additions=validate_inputs(args.inputs)
    files.update(additions)
    for name,expected in NEW_SOURCES.items():
        data=(ROOT/name).read_bytes()
        if sha(data)!=expected: raise ValueError('Unfrozen new source: '+name)
        files[name]=data
    dependency_additions=add_local_import_closure(files,{})
    if add_local_import_closure(dict(files),{}): raise ValueError('Incomplete import closure')
    for name,data in files.items():
        if name.endswith('.py'):
            compile(data,name,'exec')
            # Evidence-only preparers are retained verbatim, never imported by the runtime.
            if name.startswith('provenance/'): continue
            for node in ast.walk(ast.parse(data)):
                modules=([a.name for a in node.names] if isinstance(node,ast.Import)
                    else [node.module] if isinstance(node,ast.ImportFrom) and node.module else [])
                for module in modules:
                    path=module.replace('.','/')+'.py'
                    paths=[str(Path(name).parent/path),'experiments/'+path,'scripts/'+path,'public_solver/'+path,path]
                    if not any(p in files for p in paths) and any((ROOT/p).is_file() for p in paths):
                        raise ValueError('Unfrozen local import: '+name+' -> '+module)
        if b'KGAT_' in data: raise ValueError('Credential-shaped bytes forbidden')
    for name,digest in original.items():
        if name not in REMOVED_DATA and sha(files[name])!=digest:
            raise ValueError('Reviewed parent source/native/notice changed: '+name)
    supervisor=source.decode().split('\n',2)[2]
    replacements={"'experiments/fq_cold_transfer_pilot.py'":"'experiments/fq_sustained_cold_pilot.py'",
                  'worker.wait(timeout=880)':'worker.wait(timeout=3570)',
                  'signal.alarm(895)':'signal.alarm(3595)'}
    for old,new in replacements.items():
        if supervisor.count(old)!=1: raise ValueError('Ambiguous supervisor delta')
        supervisor=supervisor.replace(old,new,1)
    manifest=dict(kind='Twelve independent FP64 cold case searches; two fixed device queues',
        parent_source_sha256=PARENT_SHA,native_binary_sha256=BINARY_SHA,
        original_file_count=len(original),preserved_original_file_count=len(original)-len(removed),
        original_file_inventory_sha256=sha(json.dumps(original,sort_keys=True,separators=(',',':')).encode()),
        replaced_inactive_root_data=removed,files={name:sha(data) for name,data in files.items()},
        configuration=config,input_proof_sha256=sha(additions['sustained-input-proof.json']),
        builder_sha256=sha(Path(__file__).read_bytes()),transitive_dependency_additions=dependency_additions,
        supervisor_delta=replacements,worker_seconds=3570,parent_alarm_seconds=3595,whole_seconds=3600,
        server_timeout_seconds=4200,devices_used=2,raw_global_bytes=9*1024**3,protected_global_bytes=3*1024**3,
        native_dependency_license_count=parent['native_dependency_license_count'],no_submission=True)
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w',compression=zipfile.ZIP_STORED) as archive:
        for name,data in files.items(): archive.writestr(name,data)
    payload=base64.b85encode(lzma.compress(stream.getvalue(),preset=9)).decode()
    frozen='CONFIG='+repr(manifest)+'\nPAYLOAD='+repr(payload)+'\n'+supervisor
    compile(frozen,'search.py','exec')
    if len(frozen.encode())>=1_000_000:
        raise ValueError('Exact source exceeds1MB: '+str(len(frozen.encode()))+'; preserve this input set and use authorized immutable private fixtures')
    args.out.mkdir(parents=True);(args.out/'search.py').write_text(frozen)
    metadata=dict(id=args.slug,title=args.slug.split('/')[-1].replace('-',' '),code_file='search.py',language='python',
        kernel_type='script',is_private=True,enable_gpu=True,enable_tpu=False,enable_internet=False,
        dataset_sources=[],kernel_sources=[],competition_sources=[],machine_shape='NvidiaTeslaT4')
    report=dict(source_sha256=sha(frozen.encode()),source_bytes=len(frozen.encode()),payload_files=len(files),
                configuration=manifest,launched=False)
    save(args.out/'kernel-metadata.json',metadata);save(args.out/'build_report.json',report)
    print(json.dumps({k:v for k,v in report.items() if k!='configuration'},indent=2))
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--slug',default='sos54352/squares-sustained-cold-12case')
    build(parser.parse_args())
