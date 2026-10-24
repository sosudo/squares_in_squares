#!/usr/bin/env python3
"""Freeze the reviewed full-packing GPU pilot, without launching a notebook."""
import argparse
import ast
import base64
import hashlib
import io
import json
from pathlib import Path
import sys
import zipfile
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'experiments'))
from full_structural_gpu_moves import geometry_sha
from compose_gadgets import side


def sha(data):return hashlib.sha256(data).hexdigest()


def npz_bytes(arrays):
    stream=io.BytesIO();np.savez_compressed(stream,**arrays);return stream.getvalue()


def local_sources(names):
    result={};pending=list(names)
    while pending:
        name=pending.pop()
        if name in result:continue
        data=(ROOT/name).read_bytes();result[name]=data
        if not name.endswith('.py'):continue
        for node in ast.walk(ast.parse(data)):
            modules=([node.module]if isinstance(node,ast.ImportFrom)and not node.level else
                     [a.name for a in node.names]if isinstance(node,ast.Import)else [])
            for module in modules:
                if not module:continue
                for directory in ('experiments','scripts'):
                    candidate=directory+'/'+module.replace('.','/')+'.py'
                    if(ROOT/candidate).is_file():pending.append(candidate);break
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--handoff',type=Path,default=ROOT/'artifacts/fq-full-structural-handoff-v1')
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--slug',default='sos54352/squares-full-structural-gpu-pilot')
    parser.add_argument('--seconds',type=int,default=600)
    parser.add_argument('--replicas',type=int,default=32)
    args=parser.parse_args()
    if args.out.exists()or not 30<=args.seconds<=600 or not 16<=args.replicas<=64:raise ValueError('New output and approved bounds required')
    handoff=json.loads((args.handoff/'manifest.json').read_text())
    for name,expected in handoff['hashes'].items():
        if sha((args.handoff/name).read_bytes())!=expected:raise ValueError('Immutable handoff changed: '+name)
    provenance=json.loads((args.handoff/'provenance.json').read_text());by_name={r['key']:r for r in provenance}
    raw_path=ROOT/'artifacts/merged-omitted-donor-pair-v1.csv'
    report_path=ROOT/'artifacts/merged-omitted-donor-pair-v1-official.json'
    baseline_report=json.loads(report_path.read_text())
    baseline_sha=sha(raw_path.read_bytes())
    assert baseline_report['valid']and baseline_report['sha256']==baseline_sha
    assert baseline_sha=='b9374e881450748a04a86e39b84c69ba8607ceb1e95a303caeb93f38d9174354'
    reference_sides={r['n']:float(r['side'])for r in baseline_report['results']if r['n']in(299,335)}
    with np.load(args.handoff/'current-reference.npz',allow_pickle=False)as z:
        refs={k:z[k]for k in z.files if int(k)in reference_sides}
    assert set(refs)=={'299','335'}
    for n,p in refs.items():
        proof=handoff['current_references'][n]
        assert proof['certificate']['valid']and geometry_sha(p)==proof['geometry_sha256']
    variants={};selected=[]
    with np.load(args.handoff/'variants.npz',allow_pickle=False)as z:
        for name in z.files:
            p=z[name];n=len(p)
            if n not in reference_sides or side(p)>reference_sides[n]+.005:continue
            proof=by_name[name]
            assert proof['certificate']['valid']and name.endswith(geometry_sha(p))
            record=Path(proof['record_path'])
            if not record.is_absolute():record=ROOT/record
            assert sha(record.read_bytes())==proof['record_sha256']
            rr=json.loads(record.read_text());assert rr['geometry_sha256']==geometry_sha(p)
            assert abs(rr['reference_side']-reference_sides[n])<1e-12
            variants[name]=p;selected.append(proof)
    assert all(any(len(p)==n for p in variants.values())for n in reference_sides)
    data=local_sources(['experiments/full_structural_gpu_worker.py','experiments/full_structural_gpu_moves.py',
                        'scripts/score_official.py','scripts/validate_submission.py','research/official_metric_v17.py'])
    vendor=ROOT/'vendor/lightning_ftmc';public=json.loads((vendor/'SOURCE_MANIFEST.json').read_text())
    for name,expected in public['files'].items():
        blob=(vendor/name).read_bytes();assert sha(blob)==expected;data['public_solver/'+name]=blob
    data['public_solver/SOURCE_MANIFEST.json']=(vendor/'SOURCE_MANIFEST.json').read_bytes()
    data['prepared_references.npz']=npz_bytes(refs);data['prepared_variants.npz']=npz_bytes(variants)
    data['prepared_provenance.json']=json.dumps(dict(selected=selected,current_references=handoff['current_references'],
        source_handoff_manifest_sha256=sha((args.handoff/'manifest.json').read_bytes()))).encode()
    config=dict(search_seconds=args.seconds,replicas=args.replicas,reference_sides=reference_sides,
                variants_sha256=sha(data['prepared_variants.npz']),references_sha256=sha(data['prepared_references.npz']),
                device_seeds={'0':14927001,'1':14927001},arms={'0':'exact full-N SAT','1':'smooth .02→.005 then exact full-N SAT'},
                mutation_modes=['identity','column_slide','bend','hinge'],amplitudes=[.03,.08,.18,.30],
                paired_source_operator_seeds=True,loose_slack=[.015,.04,.08],target_depths=[.000002,.00001,.00005,.0002],
                maximum_steps_per_cuda_call=400,retain_every_certified_intermediate=True,
                all_upright_start_coordinates_preserved=True,refill_used=False,
                final_gate='Fresh tau0 residual, small-clearance repair, official raw/17g/default-pandas and independent raw/default-pandas intervals')
    data['prepared_config.json']=json.dumps(config).encode()
    runtime=(ROOT/'experiments/full_structural_gpu_runtime.py').read_bytes()
    manifest=dict(kind='Whole-packing structural GPU pilot',slug=args.slug,devices=[0,1],search_seconds=args.seconds,
                  preflight_seconds=150,grace_seconds=60,wall_seconds=900,server_timeout_seconds=1200,
                  baseline_sha256=baseline_sha,baseline_report_sha256=sha(report_path.read_bytes()),
                  source_handoff_manifest_sha256=sha((args.handoff/'manifest.json').read_bytes()),
                  public_source=public['source'],public_version=public['version'],public_license='Apache-2.0, inherited notices retained',
                  runtime_sha256=sha(runtime),builder_sha256=sha(Path(__file__).read_bytes()),
                  variants=len(variants),variant_counts={n:sum(len(p)==n for p in variants.values())for n in reference_sides},
                  configuration=config,embedded_sha256={k:sha(v)for k,v in data.items()})
    for name,blob in data.items():
        if name.endswith('.py'):compile(blob,name,'exec')
        if b'KGAT_'in blob:raise ValueError('Credential-shaped payload forbidden')
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9)as archive:
        for name,blob in data.items():archive.writestr(name,blob)
    script='# Private full-packing GPU pilot; no credentials.\nCONFIG='+repr(manifest)+'\nPAYLOAD='+repr(base64.b64encode(stream.getvalue()).decode())+'\n'+runtime.decode()
    compile(script,'search.py','exec')
    if len(script.encode())>=1_000_000:raise ValueError('Notebook source exceeds Kaggle source limit')
    args.out.mkdir(parents=True)
    metadata=dict(id=args.slug,title='Squares Full Packing Structural Repair Pilot',code_file='search.py',language='python',
                  kernel_type='script',is_private=True,enable_gpu=True,enable_internet=False,enable_tpu=False,
                  dataset_sources=[],kernel_sources=[],competition_sources=['squares-in-squares'],machine_shape='NvidiaTeslaT4')
    for name,value in [('job_manifest.json',manifest),('kernel-metadata.json',metadata)]:
        (args.out/name).write_text(json.dumps(value,indent=2)+'\n')
    (args.out/'search.py').write_text(script)
    print(json.dumps(dict(out=str(args.out),source_bytes=len(script.encode()),source_sha256=sha(script.encode()),
                          variants=len(variants),launched=False)))


if __name__=='__main__':main()
