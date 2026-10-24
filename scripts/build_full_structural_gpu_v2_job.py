#!/usr/bin/env python3
"""Freeze the corrected full-packing GPU ablation; never launch or submit."""
import argparse
import ast
import base64
import io
import json
from pathlib import Path
import sys
import zipfile
import numpy as np

from build_full_structural_gpu_job import ROOT,sha,npz_bytes,local_sources
sys.path.insert(0,str(ROOT/'experiments'))
from full_structural_gpu_moves import geometry_sha
from compose_gadgets import side


def checked(path,expected=None):
    data=Path(path).read_bytes()
    if expected is not None:assert sha(data)==expected,str(path)
    return data


def load_arrays(data):
    with np.load(io.BytesIO(data),allow_pickle=False)as z:return {k:z[k]for k in z.files}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--held',type=Path)
    args=parser.parse_args();assert not args.out.exists()
    old=ROOT/'artifacts/full-structural-gpu-essential-v1/outputs'
    refs=load_arrays(checked(old/'prepared_references.npz','d4e3fb24ba77ce583c0c23568c45e18bb7460f30e01c078d5bc6c0bf419a87a3'))
    variants=load_arrays(checked(old/'prepared_variants.npz','d93744b78975215c1fd61fcf5e518c35c4a835d452e772303349ec781940db97'))
    assert len(variants)==65 and {n:sum(len(p)==n for p in variants.values())for n in(299,335)}=={299:32,335:33}
    previous_source=checked(ROOT/'artifacts/full-structural-gpu-job-v4/search.py','b79e6d174215379ad8033e8ae2d4b986bcca34f5355bdcc1564c82f6118683bf')
    values={node.targets[0].id:ast.literal_eval(node.value)for node in ast.parse(previous_source).body
            if isinstance(node,ast.Assign)and isinstance(node.targets[0],ast.Name)and node.targets[0].id in('CONFIG','PAYLOAD')}
    with zipfile.ZipFile(io.BytesIO(base64.b64decode(values['PAYLOAD'])))as z:
        original_proof=json.loads(z.read('prepared_provenance.json'))
    proofs={r['key']:dict(kind='v1-certified-structural',proof=r)for r in original_proof['selected']}
    for name,p in variants.items():assert name.endswith(geometry_sha(p))and proofs[name]['proof']['certificate']['valid']
    origins={'original_v1_source_sha256':sha(previous_source),'original_v1_variant_archive_sha256':sha(checked(old/'prepared_variants.npz'))}
    extra=ROOT/'artifacts/fq-n147-structural-v1/diversity-handoff'
    n147_summary=json.loads(checked(extra/'summary.json'))
    n147_proofs=json.loads(checked(extra/'proofs.json','6c498ef7e32217f998f884f9ac342e15a20b349f69a1b81cce158b0fb8ff48ea'))
    n147_bank=load_arrays(checked(extra/'donors.npz','9c802152965b352567be7c2570f5862ef67de81758de5e736f0785d75bb60b1a'))
    reference147=load_arrays(checked(ROOT/n147_summary['original_seed_archive'],n147_summary['original_seed_sha256']))['147']
    refs['147']=reference147
    for r in n147_proofs:
        name=r['archive_key'];p=n147_bank[name]
        assert len(p)==147 and geometry_sha(p)==r['geometry_sha256']and r['source_record']['certificate']['valid']
        variants[name]=p;proofs[name]=dict(kind='n147-structural',proof=r)
    origins['n147_summary']=n147_summary
    rounded=ROOT/'artifacts/fq-full-round-control-v1/remote-certified'
    rounded_summary=json.loads(checked(rounded/'summary.json'))
    rounded_bank=load_arrays(checked(rounded/'donors.npz',rounded_summary['donors_sha256']))
    rounded_proofs=json.loads(checked(rounded/'provenance.json',rounded_summary['provenance_sha256']))
    for name,p in rounded_bank.items():
        if len(p)!=335:continue
        r=rounded_proofs[name][0]['record']
        assert geometry_sha(p)==r['geometry_sha256']and r['certificate']['valid']
        variants[name]=p;proofs[name]=dict(kind='compressed-rounded335',proof=rounded_proofs[name])
    origins['rounded_summary']=rounded_summary
    if args.held:
        hs=json.loads(checked(args.held/'summary.json'))
        hb=load_arrays(checked(args.held/'donors.npz',hs['donors_sha256']))
        hp=json.loads(checked(args.held/'provenance.json',hs['provenance_sha256']))
        assert len(hb)==3 and {len(p)for p in hb.values()}=={147,299,335}
        for name,p in hb.items():
            r=hp[name][0]['record'];assert r['certificate']['valid']and geometry_sha(p)==r['geometry_sha256']
            assert name not in variants;variants[name]=p;proofs[name]=dict(kind='held-box-rounded',proof=hp[name])
        origins['held_summary']=hs
    pointer_path=ROOT/'artifacts/current-best-portfolio.json';pointer=json.loads(checked(pointer_path))
    baseline=pointer['raw'];checked(baseline['path'],baseline['sha256'])
    report=json.loads(checked(baseline['official_report'],baseline['official_report_sha256']))
    assert report['valid']and report['sha256']==baseline['sha256']
    reference_sides={str(r['n']):float(r['side'])for r in report['results']if r['n']in(147,299,335)}
    for n,p in refs.items():assert p.shape==(int(n),3)and abs(side(p)-reference_sides[n])<1e-9
    source_order={n:sorted(k for k,p in variants.items()if len(p)==int(n))for n in refs}
    data=local_sources(['experiments/full_structural_gpu_v2_worker.py','experiments/full_structural_gpu_v2_preflight.py',
                       'scripts/score_official.py','scripts/validate_submission.py','research/official_metric_v17.py'])
    public_dir=ROOT/'vendor/lightning_ftmc';public=json.loads(checked(public_dir/'SOURCE_MANIFEST.json'))
    for name,expected in public['files'].items():data['public_solver/'+name]=checked(public_dir/name,expected)
    data['public_solver/SOURCE_MANIFEST.json']=checked(public_dir/'SOURCE_MANIFEST.json')
    data['prepared_references.npz']=npz_bytes(refs);data['prepared_variants.npz']=npz_bytes(variants)
    data['prepared_provenance.json']=json.dumps(dict(proofs=proofs,origins=origins,
        current_references=original_proof['current_references'],baseline=baseline,
        source_pointer_sha256=sha(checked(pointer_path)),reference147_source=n147_summary)).encode()
    config=dict(search_seconds=1200,certification_seconds=150,replicas=32,paired_seed=14937101,
        cuda_options=['--std=c++17','--fmad=false'],
        family_cycle=[299,335,299,335,147],source_order=source_order,reference_sides=reference_sides,
        references_sha256=sha(data['prepared_references.npz']),variants_sha256=sha(data['prepared_variants.npz']),
        raw_byte_limit=2*1024**3,maximum_steps_per_cuda_call=400,
        arms={'0':'exact SAT','1':'smooth absolute values .02 then .005; common exact SAT target'},
        contraction_depths=[.00001,.0002,.002,.01,.02],loose_slack=[.015,.04,.08],
        gradient_fix='Symmetric average over exactly maximal projection axes; original energy formula; FMA disabled to preserve duplicate-axis arithmetic',
        current_reference_share=.25,raw_retention='All exact dispatched input and returned stage bytes; UNVERIFIED',
        certification='Bounded postrun selection; every admitted pose has unchanged full official and interval gates',
        possible_partial_drain=True,baseline=baseline)
    data['prepared_config.json']=json.dumps(config).encode()
    runtime=checked(ROOT/'experiments/full_structural_gpu_v2_runtime.py')
    manifest=dict(kind='Full-packing corrected-gradient throughput ablation',slug='sos54352/squares-full-packing-structural-repair-v2',
        devices=[0,1],preflight_seconds=150,search_seconds=1200,certification_seconds=150,
        wall_seconds=1500,server_timeout_seconds=1800,configuration=config,
        variants=len(variants),variant_counts={n:len(names)for n,names in source_order.items()},
        baseline=baseline,origins=origins,public_source=public['source'],public_version=public['version'],
        public_license='Apache-2.0, inherited notices retained',runtime_sha256=sha(runtime),
        builder_sha256=sha(Path(__file__).read_bytes()),embedded_sha256={k:sha(v)for k,v in data.items()})
    for name,blob in data.items():
        if name.endswith('.py'):compile(blob,name,'exec')
        if b'KGAT_'in blob:raise ValueError('Credential-shaped payload forbidden')
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9)as z:
        for name,blob in data.items():z.writestr(name,blob)
    script='# Private corrected full-packing search; no credentials.\nCONFIG='+repr(manifest)+'\nPAYLOAD='+repr(base64.b64encode(stream.getvalue()).decode())+'\n'+runtime.decode()
    compile(script,'search.py','exec');assert len(script.encode())<1_000_000
    args.out.mkdir(parents=True)
    metadata=dict(id=manifest['slug'],title='Squares Full Packing Structural Repair V2',code_file='search.py',language='python',
        kernel_type='script',is_private=True,enable_gpu=True,enable_internet=False,enable_tpu=False,
        dataset_sources=[],kernel_sources=[],competition_sources=['squares-in-squares'],machine_shape='NvidiaTeslaT4')
    for name,value in [('job_manifest.json',manifest),('kernel-metadata.json',metadata),('prepared_config.json',config)]:
        (args.out/name).write_text(json.dumps(value,indent=2)+'\n')
    (args.out/'search.py').write_text(script)
    print(json.dumps(dict(out=str(args.out),source_sha256=sha(script.encode()),source_bytes=len(script.encode()),
                         variants=len(variants),counts=manifest['variant_counts'],launched=False)))


if __name__=='__main__':main()
