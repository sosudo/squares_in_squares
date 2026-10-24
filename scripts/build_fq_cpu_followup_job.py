#!/usr/bin/env python3
"""Freeze the controlled40/.6 and64/.3 two-lane continuation of8x20+12."""
from __future__ import annotations
import argparse
import ast
import base64
import io
import json
import lzma
from pathlib import Path
import re
import shutil
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'experiments')]
import build_fq_remote_cpu_job as base
import fq_active_pilot as fq
import fq_productive_campaign as productive
from fq_variant_campaign import atomic_json

SOURCES=[
    ('artifacts/fq-remote-cpu-minima-v1/best_bank.npz','ef78f8119597fc5be01af55565fd097d35a1289bb4d8fc4a6a755620530f4f16'),
    ('artifacts/fq-remote-cpu-analysis-v1/near_reference_donors.npz','10f00a2903c43c05fb8da7ec26ed7c56ec290108046064bdb41c93334f12a273'),
    ('artifacts/fq-bottleneck-final-handoff-v1/donors.npz','826806dab055cf8265477ccc2fbff1589e2a20fd5d1a0f2c35f0696ba438e6eb'),
]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--slug',default='sos54352/squares-fq-cpu-new-basin-v2')
    parser.add_argument('--certified-inputs',type=Path)
    parser.add_argument('--input-proof-sha')
    args=parser.parse_args()
    if args.out.exists():raise ValueError('Frozen output directory must be fresh')
    args.out.mkdir(parents=True)
    if args.certified_inputs:
        path=args.certified_inputs/'input_proof.json'
        if not args.input_proof_sha or fq.digest(path)!=args.input_proof_sha:
            raise ValueError('Exact previous input proof hash required')
        proof=json.loads(path.read_text())
        if proof['sources']!=[dict(path=p,sha256=s)for p,s in SOURCES]:
            raise ValueError('Previous certified sources differ')
        for name,expected in proof['files'].items():
            source=args.certified_inputs/name
            if not source.resolve().is_relative_to(args.certified_inputs.resolve())or fq.digest(source)!=expected:
                raise ValueError('Previous certified input bytes changed')
        records=json.loads((args.certified_inputs/'pose_provenance.json').read_text())
        if not records or not all(row['certificate']['valid']for row in records.values()):
            raise ValueError('Every reused selected input needs its complete valid certificate')
        shutil.copytree(args.certified_inputs,args.out/'inputs')
        weights=json.loads((args.out/'inputs/priorities.json').read_text())
    else:
        if args.input_proof_sha:raise ValueError('Input proof requires its certified directory')
        proof,weights=base.prepare_inputs(args.out/'inputs',{(8,20,12):1},SOURCES,8)
    minimum=proof['reference_records']['8_20_12']
    if minimum['geometry_sha256']!='1cb865a90232308f6becb125dd4687fb3ab37f7b35e7d7ca93a387435b41a0f9':
        raise ValueError('Expected the exact newly certified8x20 minimum')
    data=base.sources_recursively(['experiments/fq_cpu_followup_search.py','research/official_metric_v17.py'])
    ready=ROOT/'artifacts/fq-cpu-readiness-job-v2/readiness.py'
    if fq.digest(ready)!='a43315643e2e1475212d3cffbdea88e278100493e29dae2a60cb2448c0d48170':
        raise ValueError('Frozen readiness source changed')
    tree=ast.parse(ready.read_bytes());ready_config=ast.literal_eval(tree.body[0].value)
    raw=lzma.decompress(base64.b64decode(ast.literal_eval(tree.body[1].value)))
    if base.sha(raw)!=ready_config['payload_sha256']:raise ValueError('Readiness payload changed')
    with zipfile.ZipFile(io.BytesIO(raw))as archive:
        for name,expected in ready_config['files'].items():
            if name.startswith(('vendor/','provenance/')):
                value=archive.read(name)
                if base.sha(value)!=expected:raise ValueError('Source/license provenance changed')
                data[name]=value
    for path in (args.out/'inputs').iterdir():data['inputs/'+path.name]=path.read_bytes()
    _,generated=productive.fixed.build_runtime()
    data['provenance/generated_scheduler.py']=generated.encode()
    data['provenance/followup_builder.py']=Path(__file__).read_bytes()
    data['provenance/input_builder.py']=Path(base.__file__).read_bytes()
    for folder in ['fq-cpu-followup-controls-v1','fq-cpu-large-followup-controls-v1']:
        for filename in ['manifest.json','control_report.json','supervisor.json']:
            path=ROOT/'artifacts'/folder/filename
            data['provenance/'+folder+'/'+filename]=path.read_bytes()
    for name in ['fq_cpu_followup_controls.py','fq_cpu_large_followup_control.py']:
        data['provenance/'+name]=(ROOT/'experiments'/name).read_bytes()
    common=dict(binary_sha256=ready_config['binary_sha256'],weights=weights,
        generated_runtime_sha256=base.sha(generated.encode()),workers=2,search_seconds=1200,
        input_hashes={name:base.sha(value)for name,value in data.items()if name.startswith('inputs/')},
        immutable_start_fraction=.25,whole_trial_seconds=20,local_stage_seconds=12,
        release=['--loosen','1','--outer','45','--pit','100','--flip-top','16'],
        retention='Every strict stage retained before release; .002 band only restricts continuing search.')
    lanes={
        'productive':dict(common,lane='productive',policy='productive40_060',seed=14124001),
        'large':dict(common,lane='large',policy='connected64_030',seed=15124001),
    }
    for lane,config in lanes.items():data['lanes/'+lane+'.json']=json.dumps(config,indent=2).encode()
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w',compression=zipfile.ZIP_STORED)as archive:
        for name,value in sorted(data.items()):
            if re.search(rb'KGAT_[A-Za-z0-9]{20,}',value):raise ValueError('Credentials forbidden in payload')
            if name.endswith('.py'):compile(value,name,'exec')
            archive.writestr(zipfile.ZipInfo(name,date_time=(2026,1,1,0,0,0)),value)
    raw=stream.getvalue();packed=lzma.compress(raw,preset=6)
    loader=(ROOT/'experiments/fq_cpu_followup_loader.py').read_bytes()
    config=dict(binary_sha256=ready_config['binary_sha256'],ready_ref='sos54352/squares-fq-cpu-ready-10ec7cf773ac/1',
        ready_manifest_sha256='a9bc54f4684628dff1574d1b3306c26434796ba3da829bce9318715b94b67e25',
        ready_source_sha256=fq.digest(ready),payload_sha256=base.sha(raw),files={name:base.sha(value)for name,value in data.items()},
        loader_sha256=base.sha(loader),worker_seconds=1200,whole_seconds=1260,server_timeout_seconds=1500,
        cpu_workers=4,lanes=lanes,input_proof_sha256=fq.digest(args.out/'inputs/input_proof.json'))
    source='CONFIG='+repr(config)+'\nPAYLOAD='+repr(base64.b64encode(packed).decode())+'\n'+loader.decode()
    compile(source,'search.py','exec')
    if len(source.encode())>=1_000_000:raise ValueError('Notebook exceeds1MB')
    (args.out/'search.py').write_text(source)
    metadata=dict(id=args.slug,title=args.slug.split('/')[-1].replace('-',' '),code_file='search.py',language='python',
        kernel_type='script',is_private=True,enable_gpu=False,enable_tpu=False,enable_internet=False,
        dataset_sources=[],competition_sources=[],kernel_sources=[config['ready_ref']])
    atomic_json(args.out/'kernel-metadata.json',metadata);atomic_json(args.out/'job_manifest.json',config)
    report=dict(script_sha256=base.sha(source.encode()),script_bytes=len(source.encode()),payload_files=len(data),
        input_variants=proof['selected_variants'],reference_types=len(proof['reference_records']),
        reused_exact_input_proof_sha256=args.input_proof_sha,
        per_lane_workers=2,total_workers=4,search_seconds=1200,whole_seconds=1260,server_timeout_seconds=1500)
    atomic_json(args.out/'build_report.json',report)
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
