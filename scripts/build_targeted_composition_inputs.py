#!/usr/bin/env python3
"""Package exact targeted-FTMC variants and the audited finite partner selection.

This private CPU export copies every targeted pose and reconstructs the selected
partners byte-for-byte from a frozen notebook output and three inline arrays.
It changes no geometry and makes no new certificate or exhaustive-search claim.
"""
from __future__ import annotations
import argparse
import base64
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import zipfile
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'experiments'))
from attached_composition_inputs import validate_manifest
from build_consolidated_input_job import RUNTIME as ORIGINAL_RUNTIME


def sha(data):
    return hashlib.sha256(data).hexdigest()


SELECTION = r'''
        descriptor=json.loads((root/'proofs/portable_selection.json').read_text())
        partner_manifest=json.loads((root/'proofs/partner_manifest.json').read_text())
        arrays={};records=[];canonical=hashlib.sha256()
        def append(label,key,pose,source_sha,nominal_type):
            assert pose.dtype==np.float64 and pose.ndim==2 and pose.shape[1]==3
            assert len(pose) and np.isfinite(pose).all()
            name=f'{label}__{len(arrays):05d}__{key}'
            array_sha=hashlib.sha256(np.asarray(pose,dtype='<f8').tobytes()).hexdigest()
            arrays[name]=pose.copy()
            canonical.update((name+'\0'+array_sha+'\n').encode())
            records.append({'output_key':name,'source_label':label,'source_key':key,
                            'source_archive_sha256':source_sha,'array_sha256':array_sha,
                            'nominal_type':nominal_type,'squares':len(pose)})
        target=resolved['inputs']['targeted']
        with np.load(target['path'],allow_pickle=False)as source:
            assert len(source.files)==CONFIG['targeted_count']
            for key in source.files:
                fields=key.split('__',1)[0].split('_')
                assert len(fields)==3 and all(v.isdigit() for v in fields)
                nominal=list(map(int,fields));pose=np.asarray(source[key])
                assert len(pose)==nominal[0]*nominal[1]+nominal[2]
                append('targeted',key,pose,target['sha256'],nominal)
        partners={};partner_canonical=hashlib.sha256()
        with np.load(resolved['inputs']['partner_source']['path'],allow_pickle=False)as source:
            for record in descriptor['records']:
                if 'source_key'in record:
                    assert 'inline_f64_le_b64'not in record
                    pose=np.asarray(source[record['source_key']])
                else:
                    pose=np.frombuffer(base64.b64decode(record['inline_f64_le_b64']),dtype='<f8').reshape(record['shape']).copy()
                assert pose.dtype==np.float64 and list(pose.shape)==record['shape']
                digest_=hashlib.sha256(np.asarray(pose,dtype='<f8').tobytes()).hexdigest()
                assert digest_==record['array_sha256']
                key=record['output_key'];assert key not in partners
                partners[key]=pose
                partner_canonical.update((key+'\0'+digest_+'\n').encode())
                assert partner_manifest['records'][key]['geometry_sha256']==digest_
                assert partner_manifest['records'][key]['nominal_type']==record['nominal_type']
                append('partners',key,pose,descriptor['expected_local_archive_sha256'],record['nominal_type'])
        assert len(partners)==descriptor['poses']==CONFIG['partner_count']
        assert partner_canonical.hexdigest()==descriptor['expected_canonical_key_array_sha256']
        assert len(arrays)==CONFIG['consolidation_expected_arrays']
        assert canonical.hexdigest()==CONFIG['expected_canonical_sha256']
        for name in ('portable_selection.json','partner_manifest.json','typed_bank_handoff.json','targeted_report.json'):
            shutil.copyfile(root/'proofs'/name,working/name)
'''


def runtime():
    start = ORIGINAL_RUNTIME.index('        arrays={};records=[];canonical=hashlib.sha256()')
    end = ORIGINAL_RUNTIME.index("        archive=working/'composition_donors.npz'", start)
    value = ORIGINAL_RUNTIME[:start] + SELECTION + ORIGINAL_RUNTIME[end:]
    return value.replace('timeout=300', 'timeout=240').replace("'worker_seconds':300", "'worker_seconds':240")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--slug', required=True)
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--baseline-kernel', required=True)
    parser.add_argument('--partners', type=Path, default=ROOT/'artifacts/targeted-partners-v2')
    parser.add_argument('--handoff', type=Path, default=ROOT/'artifacts/targeted-ftmc-n65-analysis-v1/typed-bank-handoff.json')
    args = parser.parse_args()
    if args.out.exists():
        raise ValueError('Use a fresh output directory')
    descriptor = json.loads((args.partners/'portable_selection.json').read_text())
    partner_manifest = json.loads((args.partners/'manifest.json').read_text())
    handoff = json.loads(args.handoff.read_text())
    assert sha((args.partners/'manifest.json').read_bytes())==descriptor['selected_manifest_sha256']
    assert sha((args.partners/'source_notices.json').read_bytes())==descriptor['source_notices_sha256']
    assert sha(args.handoff.read_bytes())==partner_manifest['targeted_handoff_sha256']
    local={'baseline':args.baseline.resolve(), 'targeted':Path(handoff['path']),
           'partner_source':Path(partner_manifest['source_archive'])}
    attached={'schema_version':1,'baseline':{'kernel':args.baseline_kernel,'file':'submission.csv','sha256':sha(local['baseline'].read_bytes())},
              'gadgets':{'targeted':{'kernel':handoff['notebook']+'/'+str(handoff['version']),'file':'artifacts/campaign_gadgets.npz','sha256':handoff['sha256']},
                         'partner_source':{'kernel':descriptor['source_private_notebook'],'file':descriptor['source_file'],'sha256':descriptor['source_archive_sha256']}},
              'groups':{'all':['targeted','partner_source']}}
    kernels=validate_manifest(attached)
    for label,record in [('baseline',attached['baseline']),*attached['gadgets'].items()]:
        assert sha(local[label].read_bytes())==record['sha256']
    report_path=ROOT/handoff['proof_path'];assert sha(report_path.read_bytes())==handoff['proof_sha256']
    payload={'pipeline/attached_composition_inputs.py':(ROOT/'experiments/attached_composition_inputs.py').read_bytes(),
             'proofs/portable_selection.json':(args.partners/'portable_selection.json').read_bytes(),
             'proofs/partner_manifest.json':(args.partners/'manifest.json').read_bytes(),
             'proofs/typed_bank_handoff.json':args.handoff.read_bytes(),'proofs/targeted_report.json':report_path.read_bytes()}
    notices=json.loads((args.partners/'source_notices.json').read_text())
    notices['provenance/targeted7033-certificate-binding.json']=args.handoff.read_text()
    attached['source_notice_files']={}
    for index,(name,value)in enumerate(sorted(notices.items())):
        path=f'source_notices/{index:04d}.txt';data=value.encode();payload[path]=data
        attached['source_notice_files'][name]={'path':path,'sha256':sha(data)}
    records=[];canonical=hashlib.sha256()
    for label,path,expected in [('targeted',local['targeted'],handoff['sha256']),('partners',args.partners/'partners.npz',descriptor['expected_local_archive_sha256'])]:
        assert sha(path.read_bytes())==expected
        with np.load(path,allow_pickle=False)as bank:
            for key in bank.files:
                pose=bank[key];nominal=list(map(int,key.split('__',1)[0].split('_')))
                assert pose.dtype==np.float64 and pose.shape==(nominal[0]*nominal[1]+nominal[2],3)
                name=f'{label}__{len(records):05d}__{key}';digest_=sha(np.asarray(pose,dtype='<f8').tobytes())
                canonical.update((name+'\0'+digest_+'\n').encode())
                records.append({'output_key':name,'source_label':label,'source_key':key,'source_archive_sha256':expected,
                                'array_sha256':digest_,'nominal_type':nominal,'squares':len(pose)})
    count=handoff['poses']+descriptor['poses'];assert len(records)==count
    oriented=8*(count+1060);assert oriented*60543<=2**32
    config={'attached_inputs':attached,'embedded_sha256':{k:sha(v)for k,v in payload.items()},
            'baseline_sha256':attached['baseline']['sha256'],'consolidation_expected_arrays':count,
            'expected_canonical_sha256':canonical.hexdigest(),'targeted_count':handoff['poses'],'partner_count':descriptor['poses'],
            'conservative_oriented_bound':oriented,'max_encoded_identifier':oriented*60543-1,
            'deduplication':'None across targeted and partner banks. Partner selection retains the independently audited exact-type/byte aliases.',
            'partner_coverage':'All87 selected source identities, original51 aliases and417 canonical scalar-minimum families; finite geometry palette, no exhaustive claim.'}
    packed=io.BytesIO()
    with zipfile.ZipFile(packed,'w',compression=zipfile.ZIP_LZMA)as archive:
        for name,data in payload.items():archive.writestr(name,data)
    source='CONFIG = '+repr(config)+'\nPAYLOAD = '+repr(base64.b64encode(packed.getvalue()).decode())+'\n'+runtime()
    compile(source,'export.py','exec');assert len(source.encode())<1_000_000
    args.out.mkdir(parents=True);(args.out/'export.py').write_text(source)
    metadata={'id':args.slug,'title':args.slug.split('/')[-1].replace('-',' '),'code_file':'export.py','language':'python','kernel_type':'script',
              'is_private':True,'enable_gpu':False,'enable_tpu':False,'enable_internet':False,'dataset_sources':[],
              'competition_sources':[],'kernel_sources':kernels}
    for name,value in [('kernel-metadata.json',metadata),('job_manifest.json',config),('expected_records.json',records)]:
        (args.out/name).write_text(json.dumps(value,indent=2)+'\n')
    replay=args.out/'local-replay';replay.mkdir()
    with tempfile.TemporaryDirectory(prefix='targeted-mount-',dir=args.out)as temporary:
        mount=Path(temporary).resolve()
        for label,record in [('baseline',attached['baseline']),*attached['gadgets'].items()]:
            target=mount/label/Path(record['file']).name;target.parent.mkdir(parents=True);shutil.copyfile(local[label],target)
        env=os.environ.copy();env.update(COMPOSITION_INPUT_ROOT=str(mount),COMPOSITION_OUTPUT_ROOT=str(replay.resolve()),OPENBLAS_NUM_THREADS='1')
        subprocess.run([sys.executable,str((args.out/'export.py').resolve())],env=env,check=True,timeout=270)
    proof=json.loads((replay/'consolidation_report.json').read_text());assert proof['records']==records
    report={'source_sha256':sha(source.encode()),'source_bytes':len(source.encode()),'archive_sha256':proof['archive_sha256'],
            'canonical_sha256':canonical.hexdigest(),'arrays':count,'targeted_arrays':handoff['poses'],'partner_arrays':descriptor['poses'],
            'baseline_sha256':config['baseline_sha256'],'conservative_oriented_bound':oriented,'max_encoded_identifier':oriented*60543-1,
            'all_arrays_exact':True,'worker_seconds':240,'server_seconds':300,'launch_performed':False}
    (args.out/'build_report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))


if __name__=='__main__':
    main()
