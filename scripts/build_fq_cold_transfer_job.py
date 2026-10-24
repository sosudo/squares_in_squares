#!/usr/bin/env python3
"""Freeze the bounded 803/861 cold-transfer experiment; never launch it."""
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

ROOT=Path(__file__).resolve().parents[1]
PARENT=ROOT/'artifacts/fq-restart-hop-job-v2/search.py'
PARENT_SHA='d350aebf10c9bcd07eab3088fd33778cb2e9b55e114eb95bbf0b51a9883f070f'
BINARY_SHA='10ec7cf773ac0ebca3791d5cfb84e9ecbb10e3f0a9e43194330c80e1cfc9dc3d'
REMOVED_DATA=('pilot-inputs.npz','pilot-config.json','hop-config.json',
              'restart-inputs.npz','restart-config.json','restart-input-proof.json')
NEW_SOURCES=('experiments/fq_cold_transfer_pilot.py','experiments/fq_cold_hop_finish.py')


def sha(data):return hashlib.sha256(data).hexdigest()
def save(path,value):path.write_text(json.dumps(value,indent=2)+'\n')


def build(args):
    if args.out.exists():raise ValueError('Use a fresh source freeze directory')
    source,parent,files=unpack(PARENT,PARENT_SHA,'xz85')
    original={name:sha(data)for name,data in files.items()}
    removed={name:dict(sha256=sha(files[name]),bytes=len(files[name]))for name in REMOVED_DATA}
    for name in REMOVED_DATA:del files[name]
    assert sha(files['bin/fq'])==BINARY_SHA
    config_bytes=args.config.read_bytes();config=json.loads(config_bytes)
    proof_bytes=args.input_proof.read_bytes();proof=json.loads(proof_bytes)
    inputs=args.inputs.read_bytes()
    if sha(inputs)!=config['inputs_sha256'] or sha(inputs)!=proof['inputs_sha256']:
        raise ValueError('Input archive differs')
    if set(config['cases'])!={'803','861'}:raise ValueError('Expected authorized cases803/861')
    for device,n in enumerate((803,861)):
        case=config['cases'][str(n)];record=proof['cases'][str(n)]
        if not(case['n']==n and case['device']==device and case['source_key']==record['reference_key']
                and case['source_geometry_sha256']==record['reference_geometry_sha256']
                and case['reference_side']==record['reference_side']):
            raise ValueError('Case source binding differs')
    if not(config['seed']==105833501 and config['search_seconds']==600 and config['cooling_seconds']==150
            and config['quench_steps']==2000 and config['chains']==32 and config['temperature']==.3
            and config['cuts']==[.002,.008] and config['amplitudes']==[1.,1.5]
            and config['finish_native_seconds']==60 and config['finish_certificate_seconds']==8
            and config['finish_workers_per_case']==2 and config['finish_slots_per_case']==4
            and 0<config['max_packets']<=3000 and 0<config['max_bytes']<=6*1024**3
            and config['cuda_options']==['--std=c++17','--fmad=false']):
        raise ValueError('Unreviewed cold-transfer configuration')
    with np.load(io.BytesIO(inputs),allow_pickle=False)as z:
        if set(z.files)!=set(proof['arrays']):raise ValueError('Input inventory differs')
        for name in z.files:
            value=z[name];record=proof['arrays'][name]
            if not(list(value.shape)==record['shape'] and value.dtype.str==record['dtype']
                    and sha(value.tobytes())==record['sha256'] and np.isfinite(value).all()):
                raise ValueError('Input geometry differs')
    files.update({'cold-config.json':config_bytes,'cold-inputs.npz':inputs,'cold-input-proof.json':proof_bytes})
    preparation=(args.input_proof.parent/'prepare-cold-inputs.py').read_bytes()
    if sha(preparation)!=proof['cold_preparation_source_sha256']:raise ValueError('Cold input preparation source differs')
    files['provenance/prepare-cold-inputs.py']=preparation
    for name in NEW_SOURCES:files[name]=(ROOT/name).read_bytes()
    dependency_additions=add_local_import_closure(files,{})
    if add_local_import_closure(dict(files),{}):raise ValueError('Import closure incomplete')
    for name,data in files.items():
        if name.endswith('.py'):
            compile(data,name,'exec')
            for node in ast.walk(ast.parse(data)):
                modules=([a.name for a in node.names]if isinstance(node,ast.Import)
                    else[node.module]if isinstance(node,ast.ImportFrom)and node.module else[])
                for module in modules:
                    path=module.replace('.','/')+'.py'
                    paths=[str(Path(name).parent/path),'experiments/'+path,'scripts/'+path,'public_solver/'+path,path]
                    if not any(p in files for p in paths)and any((ROOT/p).is_file()for p in paths):
                        raise ValueError('Unfrozen local import: '+name+' -> '+module)
        if b'KGAT_'in data:raise ValueError('Credential-shaped bytes forbidden')
    for name,digest in original.items():
        if name not in REMOVED_DATA and sha(files[name])!=digest:
            raise ValueError('Reviewed numerical/source/native/notice bytes changed: '+name)
    supervisor=source.decode().split('\n',2)[2]
    replacements={"'experiments/fq_restart_hop_pilot.py'":"'experiments/fq_cold_transfer_pilot.py'",
                  'worker.wait(timeout=850)':'worker.wait(timeout=880)'}
    for old,new in replacements.items():
        if supervisor.count(old)!=1:raise ValueError('Ambiguous supervisor delta')
        supervisor=supervisor.replace(old,new,1)
    if supervisor.count('signal.alarm(895)')!=1:raise ValueError('Expected unchanged parent alarm')
    manifest=dict(kind='Persistent cold803/861 transfer; independent32-chain batches',
        parent_source_sha256=PARENT_SHA,native_binary_sha256=BINARY_SHA,
        original_file_inventory_sha256=sha(json.dumps(original,sort_keys=True,separators=(',',':')).encode()),
        original_file_count=len(original),preserved_original_file_count=len(original)-len(removed),
        replaced_inactive_root_data=removed,
        data_replacement_scope='Old immutable root fixtures are unused; new parent generates actual per-case pilot fixtures from cold inputs. All original source/native/license bytes remain exact.',
        files={name:sha(data)for name,data in files.items()},configuration=config,input_proof_sha256=sha(proof_bytes),
        builder_sha256=sha(Path(__file__).read_bytes()),transitive_dependency_additions=dependency_additions,
        supervisor_delta=replacements,worker_seconds=880,parent_alarm_seconds=895,whole_seconds=900,
        server_timeout_seconds=1200,devices_used=2,no_submission=True,
        native_dependency_license_count=parent['native_dependency_license_count'])
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w',compression=zipfile.ZIP_STORED)as z:
        for name,data in files.items():z.writestr(name,data)
    payload=base64.b85encode(lzma.compress(stream.getvalue(),preset=9)).decode()
    frozen='CONFIG='+repr(manifest)+'\nPAYLOAD='+repr(payload)+'\n'+supervisor
    compile(frozen,'search.py','exec')
    if len(frozen.encode())>=1_000_000:raise ValueError('Kaggle source limit exceeded: '+str(len(frozen.encode())))
    args.out.mkdir(parents=True);(args.out/'search.py').write_text(frozen)
    metadata=dict(id=args.slug,title=args.slug.split('/')[-1].replace('-',' '),code_file='search.py',language='python',
        kernel_type='script',is_private=True,enable_gpu=True,enable_tpu=False,enable_internet=False,
        dataset_sources=[],kernel_sources=[],competition_sources=[],machine_shape='NvidiaTeslaT4')
    report=dict(source_sha256=sha(frozen.encode()),source_bytes=len(frozen.encode()),payload_files=len(files),configuration=manifest,launched=False)
    save(args.out/'kernel-metadata.json',metadata);save(args.out/'build_report.json',report)
    print(json.dumps({k:v for k,v in report.items()if k!='configuration'},indent=2));return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('config','inputs','input-proof','out'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--slug',default='sos54352/squares-cold-transfer-803-861')
    build(p.parse_args())
