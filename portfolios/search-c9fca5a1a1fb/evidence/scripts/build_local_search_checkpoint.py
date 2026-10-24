#!/usr/bin/env python3
"""Freeze a LOCAL-only exact portfolio checkpoint and selected proof ancestry.

No network, native solver, geometry gate, canonical write or export/queue call.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import lzma
from pathlib import Path
import shutil
import time
import numpy as np
from local_checkpoint_bytes import make_patch,apply_patch,sha

ROOT=Path(__file__).resolve().parents[1]
PARENT_SHA='f1b5c18e95fa637e93795102f892a160b972ad1fa13789b2e7d737b5b44a1494'
TARGETS={'raw':'9d18b33ca0efb4c55c0afac2c159f413676d76aae37fb3cbcc6ec93a43975396',
         'safe':'c9fca5a1a1fbf55bba5e3ed093cc5412b92845fb01809c3fbc61362bb01d3097',
         'roundtrip':'fc5c2882e8443fb51d2c9f3f681494d7f5e418032cadbfa1669983fb8be2234e'}
CAMPAIGNS={'sustained':('artifacts/fq-sustained-analysis-v1',96),
           'public35_alternative':('artifacts/fq-public35-alternative-finish-v1',24),
           'fresh_current_alm':('artifacts/fq-fresh-current-alm-finish-v1',24)}


def json_bytes(value):return (json.dumps(value,indent=2,allow_nan=False)+'\n').encode()
def build(args):
    start=time.monotonic();out=args.out
    if out.exists():raise ValueError('Fresh checkpoint path required')
    pointer_bytes=(ROOT/'artifacts/current-best-portfolio.json').read_bytes();pointer=json.loads(pointer_bytes)
    if any(pointer[k]['sha256']!=v for k,v in TARGETS.items()):raise ValueError('Wait for exact adopted canonical target')
    parent=args.parent.read_bytes()
    if sha(parent)!=PARENT_SHA:raise ValueError('Exact f1b5 parent CSV required')
    parent_recipe=ROOT/'portfolios/candidate-f1b5c18e95fa'
    pm=json.loads((parent_recipe/'export_manifest.json').read_bytes())
    if pm['csv_sha256']!=PARENT_SHA:raise ValueError('Parent recipe target differs')
    out.mkdir(parents=True);inventory={};evidence={}
    def store(relative,data):
        path=out/relative;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
        inventory[relative]=dict(sha256=sha(data),bytes=len(data));return relative
    def retain(source):
        source=Path(source);source=source if source.is_absolute()else ROOT/source
        if source.is_symlink()or not source.is_file():raise ValueError('Missing or symlink evidence:'+str(source))
        name=source.relative_to(ROOT).as_posix()
        if name in evidence:return
        data=source.read_bytes();relative='evidence/'+name
        compressed=source.suffix in ('.json','.csv','.log','.stdout','.stderr','.in','.out')and len(data)>64*1024
        payload=lzma.compress(data,preset=6)if compressed else data
        if compressed:relative+='.xz'
        store(relative,payload)
        evidence[name]=dict(stored_path=relative,sha256=sha(data),bytes=len(data),compression='xz'if compressed else 'none')
    # Freeze exact adopted proof bytes together; no later pointer read.
    store('canonical-pointer.json',pointer_bytes)
    for key in ('raw','safe','roundtrip'):
        for field in ('official_report',):retain(pointer[key][field])
    retain(pointer['canonical_proof']);retain(pointer['independent_report']['path'])
    retain('artifacts/submission-sustained-alternatives-fresh-v1-safe.transport-transform.json')
    retain('artifacts/submissions/authorization-policy.json')
    targets={}
    for label,expected in TARGETS.items():
        target=Path(pointer[label]['path']).read_bytes()
        if sha(target)!=expected:raise ValueError('Canonical target changed:'+label)
        patch,record=make_patch(parent,target)
        if apply_patch(parent,patch,record)!=target:raise ValueError('Exact restoration failed')
        try:apply_patch(parent[:-1]+bytes([parent[-1]^1]),patch,record)
        except ValueError:pass
        else:raise ValueError('Wrong-parent negative failed')
        filename='patches/'+label+'.bytes.xz';store(filename,patch)
        targets[label]=dict(record,patch_file=filename,output_file=label+'.csv',
            official_score=pointer[label]['score'],original_path=pointer[label]['path'])
    store('restore.py',(ROOT/'scripts/local_checkpoint_bytes.py').read_bytes())
    retain(Path(__file__));retain('scripts/local_checkpoint_bytes.py');retain('tests/test_local_checkpoint_bytes.py')
    banks={};candidate_files={}
    for label,(folder,count)in CAMPAIGNS.items():
        base=ROOT/folder
        for source in sorted(base.iterdir()):
            if source.is_file()and source.name!='candidates-live.json':retain(source)
        candidate_files[label]=dict(path=folder+'/candidates.json',sha256=sha((base/'candidates.json').read_bytes()))
        path=base/'certified.npz';arrays={}
        with np.load(path,allow_pickle=False)as archive:
            if len(archive.files)!=count:raise ValueError('All certified geometries required:'+label)
            for name in archive.files:
                a=archive[name]
                if a.dtype.str!='<f8'or a.ndim!=2 or a.shape[1]!=3:raise ValueError('Unexpected certified bank schema')
                arrays[name]=dict(dtype=a.dtype.str,shape=list(a.shape),sha256=sha(a.tobytes()))
        banks[label]=dict(path=folder+'/certified.npz',sha256=sha(path.read_bytes()),arrays=arrays,poses=len(arrays))
        if label!='sustained':
            # Full native input/output/certification text and exact selected,
            # returned and certified arrays are small and independently useful.
            for directory in ('inputs','source','trials'):
                for source in sorted((base/directory).rglob('*')):
                    if source.is_file():retain(source)
    extra_files=[
        'artifacts/fq-sustained-cold-job-v1/search.py',
        'artifacts/fq-sustained-cold-job-v1/build_report.json',
        'artifacts/fq-sustained-cold-job-v1/remote-source-proof.json',
        'artifacts/fq-sustained-cold-job-v1/completion-status-proof.json',
        'artifacts/fq-sustained-cold-job-v1/independent_packaging_finisher_review.json',
        'artifacts/fq-sustained-driver-review-v1/independent-driver-review.json',
        'artifacts/fq-sustained-extracted-v1/extraction-receipt.json',
        'artifacts/fq-sustained-extractor-results-v1/download-receipt.json',
        'artifacts/fq-sustained-five-independent-review-v1/review.json',
        'artifacts/fq-sustained-five-independent-review-v1/review.py',
        'artifacts/public35-alternative-independent-review-v1/review.json',
        'artifacts/public35-alternative-independent-review-v1/review.py',
        'artifacts/current-fresh-alm-exposure-v2/independent_runner_review.json',
        'experiments/analyze_fq_sustained_cold.py','scripts/unpack_fq_sustained_output.py']
    for name in extra_files:retain(name)
    # The completed analysis proof explicitly names the actual extraction,
    # remote completion/source and independent-review receipts. Do not invent
    # a separate extractor completion file that this chain never produced.
    gpu_completion=json.loads((ROOT/'artifacts/fq-sustained-analysis-v1/completion-proof.json').read_bytes())
    for name,expected in gpu_completion['files'].items():
        if sha((ROOT/name).read_bytes())!=expected:raise ValueError('GPU completion ancestry differs:'+name)
        retain(name)
    extraction=json.loads((ROOT/'artifacts/fq-sustained-extracted-v1/extraction-receipt.json').read_bytes())
    retain(extraction['inventory']['path'])
    extracted=ROOT/'artifacts/fq-sustained-extracted-v1/outputs'
    # Keep the exact new run's manifest/config/inputs and explicit MIT sources;
    # no ancestor recipe manifest is copied recursively.
    names=['job_manifest.json','sustained-config.json','sustained-input-proof.json','sustained-inputs.npz',
           'pilot-summary.json','supervisor-summary.json','queue-0.json','queue-1.json']
    for prefix in ('vendor/fq','public_solver'):
        for name in ('LICENSE','NOTICE'):
            names.append(prefix+'/'+name)
    names+=['vendor/fq/SOURCE_MANIFEST.json','vendor/fq/Cargo.lock','vendor/fq/Cargo.toml',
            'vendor/fq/src/fq.rs','vendor/fq/src/ldl.rs','vendor/fq/src/lpipm.rs',
            'public_solver/gpu_topology.py','public_solver/gpu_rect_optimizer.py']
    for name in names:retain(extracted/name)
    for folder in sorted(extracted.glob('case-*')):
        for source in sorted(folder.iterdir()):
            if source.is_file()and source.suffix=='.json':retain(source)
        for directory in ('preflight/preflight_entries','finish'):
            for source in sorted((folder/directory).rglob('*')):
                if source.is_file():retain(source)
        for name in ('preflight/preflight_packing_records.json','preflight/preflight_packings.npz','preflight/preflight.json'):
            retain(folder/name)
    # Existing inherited notices stay accessible through the exact parent
    # recipe chain; main MIT and native source copies are explicit above.
    parent_refs={}
    for name in ('export_manifest.json','incremental_loader.py','completion-proof.json','current-best-portfolio.json'):
        p=parent_recipe/name;parent_refs[p.relative_to(ROOT).as_posix()]=dict(sha256=sha(p.read_bytes()),bytes=p.stat().st_size)
    manifest=dict(schema_version=1,kind='local_only_exact_byte_checkpoint',parent_csv_sha256=PARENT_SHA,
        parent_csv_bytes=len(parent),parent_local_recipe='portfolios/candidate-f1b5c18e95fa',parent_recipe_references=parent_refs,
        parent_notebook_reference_only='sos54352/squares-portfolio-f1b5c18e95fa-incremental/1',
        targets=targets,canonical_pointer_sha256=sha(pointer_bytes),candidate_files=candidate_files,
        certified_banks=banks,certified_geometry_count=sum(b['poses']for b in banks.values()),
        evidence=evidence,files=inventory,
        no_numerical_transform=True,no_new_geometry_certification=True,no_optimization=True,
        no_remote_export=True,no_queue=True,no_submission=True,eligible_under_user_policy=False,
        user_submission_threshold='22.24',policy_sha256=pointer['authorization_policy']['sha256'],
        provenance_scope='Exact compact local checkpoint. All144 certified poses and three candidateJSONs retained; original proofs reused. Large raw UNVERIFIED archives remain in immutable source/remote outputs referenced by exact receipts, not duplicated.',
        source_notice_policy='Inherited notices referenced through exact committed parent recipe/hash chain, with new campaign notices/inputs and explicit MIT solver/native source/license copies retained.',
        evidence_compression='XZ is a lossless byte-storage wrapper only; original bytes/SHA and stored bytes/SHA are recorded.',
        seconds=time.monotonic()-start)
    (out/'manifest.json').write_bytes(json_bytes(manifest))
    proof=dict(status='local_exact_replay_passed_pending_independent_review',manifest_sha256=sha((out/'manifest.json').read_bytes()),
        target_hashes=TARGETS,parent_sha256=PARENT_SHA,wrong_parent_rejected_for_all_targets=True,
        certified_pose_count=manifest['certified_geometry_count'],evidence_files=len(evidence),
        total_checkpoint_bytes=sum(p.stat().st_size for p in out.rglob('*')if p.is_file()),seconds=time.monotonic()-start,
        no_network=True,no_remote_export=True,no_submission=True)
    (out/'local-proof.json').write_bytes(json_bytes(proof));print(json.dumps(proof,indent=2),flush=True)
    return proof


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--parent',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    build(parser.parse_args())
