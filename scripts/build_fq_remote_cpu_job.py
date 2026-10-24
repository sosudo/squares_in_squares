#!/usr/bin/env python3
"""Freeze complementary certified FQ inputs and one private CPU search job."""
from __future__ import annotations
import argparse
import ast
import base64
from collections import defaultdict
import hashlib
import io
import json
import lzma
from pathlib import Path
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'experiments'),str(ROOT/'scripts')]
import numpy as np
import fq_active_pilot as fq
from fq_capacity_probe import full_certificate
from fq_multiscale_campaign import diversity_bucket
from fq_variant_campaign import geometry_sha,atomic_json,atomic_npz
import fq_productive_campaign as productive

PRIMARY={(5,18,11):2,(8,20,12):2,(6,22,16):2,(10,23,14):2}
SOURCES=[
 ('artifacts/fq-bottleneck-final-handoff-v1/reference.npz','82aaa6f013bba306a25c3ecdafa8b13a841ea4fa22288d4e2ae9a3dc8696268d'),
 ('artifacts/fq-bottleneck-final-handoff-v1/donors.npz','826806dab055cf8265477ccc2fbff1589e2a20fd5d1a0f2c35f0696ba438e6eb'),
 ('artifacts/fq-local-soft-v1/all-strict/best_bank.npz','9443c4cb997cefd81f4b5f73ec52f2a38a54eaf851865dcfdbdf7c5d9bc4e1d8'),
 ('artifacts/fq-local-soft-v1/all-strict/donors.npz','c2aeea8fd99ac4c6b5b8c983fb9ac61b0be30672da1560f94ba03ec518033c7e'),
 ('artifacts/fq-combined-top3-v1/final-verified/best_bank.npz','006dbc3100df8231c328a1da6d441bfea55e771ed9cba5964ca3e155deb01deb'),
 ('artifacts/fq-combined-top3-v1/final-verified/donors.npz','d9642cf08b1e6a8c8885b2e2f9dac1fd993c2a33d5ebb4c430c244980a3bef2c'),
]


def sha(value):return hashlib.sha256(value).hexdigest()


def sources_recursively(names):
    answer={};pending=list(names)
    while pending:
        name=pending.pop()
        if name in answer:continue
        data=(ROOT/name).read_bytes();answer[name]=data
        if not name.endswith('.py'):continue
        for node in ast.walk(ast.parse(data)):
            modules=([node.module]if isinstance(node,ast.ImportFrom)and node.level==0 else
                [part.name for part in node.names]if isinstance(node,ast.Import)else [])
            for module in modules:
                if not module:continue
                for directory in ('experiments','scripts'):
                    candidate=directory+'/'+module.replace('.','/')+'.py'
                    if (ROOT/candidate).is_file():pending.append(candidate);break
    return answer


def prepare_inputs(out,families,sources,max_variants):
    out.mkdir();groups=defaultdict(dict);manifest=[]
    for relative,expected in sources:
        path=ROOT/relative
        if fq.digest(path)!=expected:raise ValueError('Exact source archive changed: '+relative)
        manifest.append(dict(path=relative,sha256=expected))
        with np.load(path,allow_pickle=False)as z:
            for name in z.files:
                key=name.split('__')[0];w,h,d=map(int,key.split('_'));family=(min(w,h),max(w,h),d)
                if family not in families:continue
                original=np.asarray(z[name],dtype=float)
                if original.shape!=(w*h+d,3)or not np.isfinite(original).all():raise ValueError('Invalid original donor')
                p=original.copy()
                if w>h:p[:,:2]=p[:,[1,0]];p[:,2]=-p[:,2]
                identity=geometry_sha(p);value=fq.bloat(p,*family[:2])
                groups[family].setdefault(identity,dict(pose=p,excess=value,source_archive=relative,
                    source_archive_sha256=expected,source_name=name,source_geometry_sha256=geometry_sha(original),
                    canonical_transformation='reflect_xy_angle_negated'if w>h else'identity'))
        if fq.digest(path)!=expected:raise ValueError('Source changed during selection')
    if set(groups)!=set(families):raise ValueError('Missing requested family')
    reference={};donors={};records={};reference_records={};rejected=[]
    for family,candidates in sorted(groups.items()):
        ranked=sorted(candidates.values(),key=lambda r:(r['excess'],geometry_sha(r['pose'])))
        minimum=ranked[0]['excess'];buckets={}
        for entry in ranked:
            if entry['excess']<=minimum+.005:buckets.setdefault(diversity_bucket(entry['pose']),entry)
        diverse=sorted(buckets.values(),key=lambda r:(r['excess'],geometry_sha(r['pose'])))
        positions=np.linspace(0,len(diverse)-1,min(max_variants,len(diverse)),dtype=int)
        selected=[diverse[i]for i in positions]
        # Always include the exact orientation-fair minimum before diversifying.
        if geometry_sha(selected[0]['pose'])!=geometry_sha(ranked[0]['pose']):raise ValueError('Minimum missing from compact bank')
        for rank,entry in enumerate(selected):
            for transpose in (False,True):
                small,large,d=family;w,h=(large,small)if transpose else(small,large)
                key=f'{w}_{h}_{d}';p=entry['pose'].copy()
                if transpose:p[:,:2]=p[:,[1,0]];p[:,2]=-p[:,2]
                certificate=full_certificate(p);identity=geometry_sha(p)
                info={k:v for k,v in entry.items()if k!='pose'}
                info.update(key=key,geometry_sha256=identity,excess=fq.bloat(p,w,h),
                    canonical_to_requested='reflect_xy_angle_negated'if transpose else'identity',
                    certificate=certificate,diversity_bucket=diversity_bucket(p))
                if not certificate['valid']:
                    rejected.append(info)
                    if rank==0:raise ValueError('Newest family reference failed the full gate: '+key)
                    continue
                name=key+'__frozen_'+identity;donors[name]=p;records[name]=info
                if rank==0:reference[key]=p;reference_records[key]=info
    priorities={key:families[tuple(sorted(map(int,key.split('_')[:2])))+(int(key.split('_')[2]),)]for key in reference}
    atomic_npz(out/'reference.npz',reference);atomic_npz(out/'donors.npz',donors)
    atomic_json(out/'priorities.json',priorities);atomic_json(out/'pose_provenance.json',records)
    proof=dict(sources=manifest,canonical_families=[list(x)for x in sorted(families)],reference_records=reference_records,
        rejected=rejected,selected_variants=len(donors),max_variants_per_orientation=max_variants,
        selection='Exact family minima plus deterministic spread across distinct rounded diversity buckets within.005 excess; complete source archives preserved at their original immutable locations.',
        files={name:fq.digest(out/name)for name in ('reference.npz','donors.npz','priorities.json','pose_provenance.json')})
    atomic_json(out/'input_proof.json',proof)
    return proof,priorities


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--slug',default='sos54352/squares-fq-cpu-complementary-v1')
    parser.add_argument('--extra-spec',type=Path);parser.add_argument('--max-variants',type=int,default=6)
    args=parser.parse_args()
    if args.out.exists():raise ValueError('Use a fresh frozen job directory')
    args.out.mkdir(parents=True);families=dict(PRIMARY);sources=list(SOURCES)
    if args.extra_spec:
        extra=json.loads(args.extra_spec.read_text());sources.extend((r['path'],r['sha256'])for r in extra['sources'])
        families.update({tuple(row['family']):row['weight']for row in extra['families']})
    proof,weights=prepare_inputs(args.out/'inputs',families,sources,args.max_variants)
    data=sources_recursively(['experiments/fq_remote_cpu_search.py','research/official_metric_v17.py'])
    ready=ROOT/'artifacts/fq-cpu-readiness-job-v2/readiness.py';tree=ast.parse(ready.read_bytes())
    ready_config=ast.literal_eval(tree.body[0].value);raw=lzma.decompress(base64.b64decode(ast.literal_eval(tree.body[1].value)))
    if sha(raw)!=ready_config['payload_sha256']:raise ValueError('Verified readiness source package changed')
    with zipfile.ZipFile(io.BytesIO(raw))as archive:
        for name,expected in ready_config['files'].items():
            if not name.startswith(('vendor/','provenance/')):continue
            value=archive.read(name)
            if sha(value)!=expected:raise ValueError('Native source/license provenance changed')
            data[name]=value
    for path in (args.out/'inputs').iterdir():data['inputs/'+path.name]=path.read_bytes()
    _,generated=productive.fixed.build_runtime();data['provenance/generated_scheduler.py']=generated.encode()
    campaign=dict(binary_sha256=ready_config['binary_sha256'],seed=12124001,weights=weights,
        generated_runtime_sha256=sha(generated.encode()),input_hashes={name:sha(value)for name,value in data.items()if name.startswith('inputs/')},
        method='productive40/.6 circle and contact; original ALM45 release; fixed25percent immutable starts',
        strict_retention='Every full-gated stage retained before release; original .002 search band applies only to continuing search.',
        whole_stage_cap_seconds=20,local_stage_cap_seconds=12,search_seconds=1140,workers=4)
    data['campaign_config.json']=json.dumps(campaign,indent=2).encode()
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w',compression=zipfile.ZIP_STORED)as archive:
        for name,value in sorted(data.items()):
            if b'KGAT_'in value:raise ValueError('Credentials forbidden in private search source')
            if name.endswith('.py'):compile(value,name,'exec')
            archive.writestr(zipfile.ZipInfo(name,date_time=(2026,1,1,0,0,0)),value)
    raw=stream.getvalue();packed=lzma.compress(raw,preset=6)
    loader=(ROOT/'experiments/fq_remote_cpu_loader.py').read_bytes()
    config=dict(binary_sha256=ready_config['binary_sha256'],ready_ref='sos54352/squares-fq-cpu-ready-10ec7cf773ac/1',
        ready_manifest_sha256='a9bc54f4684628dff1574d1b3306c26434796ba3da829bce9318715b94b67e25',
        ready_source_sha256=sha(ready.read_bytes()),payload_sha256=sha(raw),files={name:sha(value)for name,value in data.items()},
        loader_sha256=sha(loader),worker_seconds=1200,server_timeout_seconds=1500,cpu_workers=4,
        input_proof_sha256=sha((args.out/'inputs/input_proof.json').read_bytes()))
    source='CONFIG='+repr(config)+'\nPAYLOAD='+repr(base64.b64encode(packed).decode())+'\n'+loader.decode()
    compile(source,'search.py','exec')
    if len(source.encode())>=1_000_000:raise ValueError('Source exceeds Kaggle1MB')
    (args.out/'search.py').write_text(source)
    metadata=dict(id=args.slug,title=args.slug.split('/')[-1].replace('-',' '),code_file='search.py',language='python',
        kernel_type='script',is_private=True,enable_gpu=False,enable_tpu=False,enable_internet=False,
        dataset_sources=[],competition_sources=[],kernel_sources=[config['ready_ref']])
    atomic_json(args.out/'kernel-metadata.json',metadata);atomic_json(args.out/'job_manifest.json',config)
    report=dict(script_sha256=sha(source.encode()),script_bytes=len(source.encode()),payload_files=len(data),
        input_variants=proof['selected_variants'],reference_types=len(proof['reference_records']),server_timeout_seconds=1500)
    atomic_json(args.out/'build_report.json',report);print(json.dumps(report,indent=2))


if __name__=='__main__':main()
