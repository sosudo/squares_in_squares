#!/usr/bin/env python3
"""Freeze seven already-certified full-puzzle starts for held-box continuation."""
from __future__ import annotations
import argparse
import ast
import base64
import io
import json
import lzma
from pathlib import Path
import re
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'experiments')]
import numpy as np
import build_fq_remote_cpu_job as base
import fq_active_pilot as fq
import fq_full_round_cpu_search as worker
from analyze_fq_remote_cpu import raw_text_sha
from fq_variant_campaign import atomic_json,atomic_npz,geometry_sha

INVENTORY='artifacts/fq-full-round-independent-review-v1/expected-input-inventory.json'
WEIGHTS={'12_12_3':1,'17_17_10':1,'18_18_11':2}


def prepare_inputs(out):
    out.mkdir();reference={};donors={};records={};sources={};alternatives={key:[]for key in WEIGHTS}
    expected=json.loads((ROOT/INVENTORY).read_text())
    if len(expected)!=7 or len({r['geometry_sha256']for r in expected})!=7:
        raise ValueError('Expected the exact three originals and four controlled alternatives')
    for row in expected:
        path=ROOT/row['source_archive'];source_sha=fq.digest(path)
        with np.load(path,allow_pickle=False)as z:
            matches=[(name,z[name].copy())for name in z.files if geometry_sha(z[name])==row['geometry_sha256']]
        if len(matches)!=1:raise ValueError('Expected exactly one matching certified source geometry')
        name,p=matches[0];key=row['key'];n=row['n']
        if key not in WEIGHTS or p.shape!=(n,3)or not np.isfinite(p).all():raise ValueError('Unexpected source type')
        if row['role']=='immutable_current_original':
            proofpath=ROOT/row['certificate_manifest'];proof=json.loads(proofpath.read_text())
            if source_sha!=proof['input_sha256']or proof['selected'][str(n)]['geometry_sha256']!=row['geometry_sha256']:
                raise ValueError('Original certificate input identity differs')
            certificate=proof['input_certificates'][key];reference[key]=p
        else:
            proofpath=ROOT/row['certificate_file'];proof=json.loads(proofpath.read_text())
            if source_sha!=proof['stage_archive_sha256']or proof['geometry_sha256']!=row['geometry_sha256']:
                raise ValueError('Controlled stage and exact certificate differ')
            certificate=proof['certificate'];donors[key+'__frozen_'+row['geometry_sha256']]=p
            alternatives[key].append(row['geometry_sha256'])
        if (not certificate['valid']or not certificate['shared_official_gate']['valid']
            or certificate['ordinary_pandas_official_reason']!='ok'
            or any(not certificate[part]['valid']or certificate[part]['n']!=n
                   for part in ('independent_raw','independent_roundtrip'))
            or certificate['raw_csv_sha256']!=raw_text_sha(p)):
            raise ValueError('Exact existing full-gate certificate required')
        identity=key+'__'+row['geometry_sha256']
        records[identity]=dict(row,source_name=name,source_archive_sha256=source_sha,
            certificate_source=str(proofpath.relative_to(ROOT)),certificate_source_sha256=fq.digest(proofpath),
            certificate=certificate,excess=fq.bloat(p,*map(int,key.split('_')[:2])),certificate_reused=True)
        sources[str(path.relative_to(ROOT))]=source_sha;sources[str(proofpath.relative_to(ROOT))]=fq.digest(proofpath)
    if set(reference)!=set(WEIGHTS)or sorted(map(len,alternatives.values()))!=[1,1,2]:
        raise ValueError('Incomplete seven-pose inventory')
    atomic_npz(out/'reference.npz',reference);atomic_npz(out/'donors.npz',donors)
    atomic_json(out/'priorities.json',WEIGHTS);atomic_json(out/'pose_provenance.json',records)
    proof=dict(expected_inventory=INVENTORY,expected_inventory_sha256=fq.digest(ROOT/INVENTORY),
        poses=7,reference_poses=3,alternate_poses=4,source_hashes=sources,
        geometry_sha256_by_role={r['role']:[x['geometry_sha256']for x in expected if x['role']==r['role']]for r in expected},
        geometry_validation_repeated=False,
        files={p.name:fq.digest(p)for p in out.iterdir()if p.is_file()})
    atomic_json(out/'input_proof.json',proof)
    return proof,alternatives


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--slug',default='sos54352/squares-fq-cpu-held-full-v1');args=parser.parse_args()
    if args.out.exists():raise ValueError('Frozen output directory must be fresh')
    args.out.mkdir(parents=True);proof,alternatives=prepare_inputs(args.out/'inputs')
    data=base.sources_recursively(['experiments/fq_full_round_cpu_search.py','research/official_metric_v17.py'])
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
    config=dict(binary_sha256=ready_config['binary_sha256'],weights=WEIGHTS,seed=17147001,
        alternative_geometry_hashes=alternatives,
        input_hashes={name:base.sha(value)for name,value in data.items()if name.startswith('inputs/')},
        source_policy=dict(original_current_fraction=.25,immutable_control_fraction=.25,incumbent_fraction=.5),
        per_case_stage_seconds=worker.CAPS,workers=4,search_seconds=1200,whole_seconds=1500,server_timeout_seconds=1800,
        retention='All fully certified stages retained before the continuing-search band; native output/trace retained even on failed certification.',
        method='Selected-parent box held exactly during12-step quadratic rounding return; no round-compress; global rigid ALM45/polish100/flip16.')
    _,generated,matches=worker.build_runtime(config)
    config['generated_runtime_sha256']=base.sha(generated.encode());config['checked_ast_matches']=matches
    data['campaign_config.json']=json.dumps(config,indent=2).encode()
    data['provenance/generated_scheduler.py']=generated.encode()
    data['provenance/full_round_builder.py']=Path(__file__).read_bytes()
    data['provenance/input_builder.py']=Path(base.__file__).read_bytes()
    data['provenance/expected-input-inventory.json']=(ROOT/INVENTORY).read_bytes()
    for folder in ['fq-full-round-control-v1','fq-full-round-held-control-v1']:
        for name in ['manifest.json','control_report.json','supervisor.json']:
            path=ROOT/'artifacts'/folder/name
            if path.exists():data['provenance/'+folder+'/'+name]=path.read_bytes()
    for name in ['compressed-control-complete-review.json','held-control-complete-review.json']:
        data['provenance/'+name]=(ROOT/'artifacts/fq-full-round-independent-review-v1'/name).read_bytes()
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w',compression=zipfile.ZIP_STORED)as archive:
        for name,value in sorted(data.items()):
            if re.search(rb'KGAT_[A-Za-z0-9]{20,}',value):raise ValueError('Credentials forbidden in payload')
            if name.endswith('.py'):compile(value,name,'exec')
            archive.writestr(zipfile.ZipInfo(name,date_time=(2026,1,1,0,0,0)),value)
    raw=stream.getvalue();loader=(ROOT/'experiments/fq_full_round_cpu_loader.py').read_bytes()
    manifest=dict(binary_sha256=ready_config['binary_sha256'],ready_ref='sos54352/squares-fq-cpu-ready-10ec7cf773ac/1',
        ready_manifest_sha256='a9bc54f4684628dff1574d1b3306c26434796ba3da829bce9318715b94b67e25',
        ready_source_sha256=fq.digest(ready),payload_sha256=base.sha(raw),files={name:base.sha(value)for name,value in data.items()},
        loader_sha256=base.sha(loader),worker_seconds=1200,whole_seconds=1500,server_timeout_seconds=1800,
        cpu_workers=4,campaign=config,input_proof_sha256=fq.digest(args.out/'inputs/input_proof.json'))
    source='CONFIG='+repr(manifest)+'\nPAYLOAD='+repr(base64.b64encode(lzma.compress(raw,preset=6)).decode())+'\n'+loader.decode()
    compile(source,'search.py','exec')
    if len(source.encode())>=1_000_000:raise ValueError('Notebook exceeds1MB')
    (args.out/'search.py').write_text(source)
    metadata=dict(id=args.slug,title=args.slug.split('/')[-1].replace('-',' '),code_file='search.py',language='python',
        kernel_type='script',is_private=True,enable_gpu=False,enable_tpu=False,enable_internet=False,
        dataset_sources=[],competition_sources=[],kernel_sources=[manifest['ready_ref']])
    atomic_json(args.out/'kernel-metadata.json',metadata);atomic_json(args.out/'job_manifest.json',manifest)
    atomic_json(args.out/'generated_scheduler_audit.json',dict(source_sha256=config['generated_runtime_sha256'],matches=matches))
    report=dict(script_sha256=base.sha(source.encode()),script_bytes=len(source.encode()),payload_files=len(data),
        reference_poses=3,controlled_alternatives=4,workers=4,search_seconds=1200,whole_seconds=1500,server_timeout_seconds=1800)
    atomic_json(args.out/'build_report.json',report);print(json.dumps(report,indent=2))


if __name__=='__main__':main()
