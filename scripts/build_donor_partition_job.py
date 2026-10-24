#!/usr/bin/env python3
"""Consolidate a declared exact donor partition into one private CPU attachment."""
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

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'experiments'))
from attached_composition_inputs import validate_manifest
from build_consolidated_input_job import RUNTIME as ORIGINAL_RUNTIME


def sha(data):return hashlib.sha256(data).hexdigest()


def runtime():
    old="""        arrays={};records=[];canonical=hashlib.sha256()"""
    new="""        arrays={};records=[];canonical=hashlib.sha256();excluded={} """
    value=ORIGINAL_RUNTIME
    assert value.count(old)==1;value=value.replace(old,new)
    old="""                for key in source.files:
                    pose=np.asarray(source[key])"""
    new="""                for key in source.files:
                    prefixes=CONFIG['exclude_prefixes'].get(label,[])
                    if any(key.startswith(prefix)for prefix in prefixes):
                        excluded.setdefault(label,[]).append(key)
                        continue
                    pose=np.asarray(source[key])"""
    assert value.count(old)==1;value=value.replace(old,new)
    old="""        assert len(arrays)==CONFIG['consolidation_expected_arrays']"""
    new="""        assert len(arrays)==CONFIG['consolidation_expected_arrays']
        assert {k:len(v)for k,v in excluded.items()}==CONFIG['expected_excluded_counts']
        assert canonical.hexdigest()==CONFIG['expected_canonical_sha256']
        (working/'excluded_arrays.json').write_text(json.dumps(excluded,indent=2)+'\\n')"""
    assert value.count(old)==1;value=value.replace(old,new)
    return value.replace('timeout=300','timeout=240').replace("'worker_seconds':300","'worker_seconds':240")


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--slug',required=True)
    parser.add_argument('--expected-arrays',type=int,required=True)
    args=parser.parse_args()
    if args.out.exists():raise ValueError('Use a fresh partition export directory')
    supplied=json.loads(args.manifest.read_text());attached=supplied['attached_inputs']
    kernels=validate_manifest(attached);payload={};local={}
    for label,record in [('baseline',attached['baseline']),*attached['gadgets'].items()]:
        path=Path(record.get('local_path',record.get('local_cache','')))
        if not path.is_file()or sha(path.read_bytes())!=record['sha256']:raise ValueError('Frozen local input mismatch: '+label)
        local[label]=path.resolve()
        record.pop('local_cache',None)
        if 'local_path'in record:
            record.pop('local_path');record['embedded_path']='inputs/'+label+'.npz'
            payload[record['embedded_path']]=path.read_bytes()
    payload['pipeline/attached_composition_inputs.py']=(ROOT/'experiments/attached_composition_inputs.py').read_bytes()
    records=[];canonical=hashlib.sha256();excluded={}
    for label in attached['gadgets']:
        with np.load(local[label],allow_pickle=False)as bank:
            for key in bank.files:
                if any(key.startswith(p)for p in supplied['exclude_prefixes'].get(label,[])):
                    excluded.setdefault(label,[]).append(key);continue
                array=bank[key]
                if array.dtype!=np.float64 or array.ndim!=2 or array.shape[1]!=3 or not len(array)or not np.isfinite(array).all():
                    raise ValueError('Invalid exact source array')
                output=f'{label}__{len(records):05d}__{key}';digest=sha(np.asarray(array,dtype='<f8').tobytes())
                canonical.update((output+'\0'+digest+'\n').encode())
                records.append({'output_key':output,'source_label':label,'source_key':key,'source_archive_sha256':attached['gadgets'][label]['sha256'],
                                'array_sha256':digest,'squares':len(array)})
    if len(records)!=args.expected_arrays or {k:len(v)for k,v in excluded.items()}!=supplied['expected_excluded_counts']:
        raise ValueError('Exact partition counts differ')
    notices=attached.pop('source_notices',{});attached['source_notice_files']={}
    for index,(name,text)in enumerate(sorted(notices.items())):
        path=f'source_notices/{index:04d}.txt';data=text.encode();payload[path]=data
        attached['source_notice_files'][name]={'path':path,'sha256':sha(data)}
    config={'attached_inputs':attached,'embedded_sha256':{k:sha(v)for k,v in payload.items()},
            'baseline_sha256':attached['baseline']['sha256'],'consolidation_expected_arrays':len(records),
            'expected_canonical_sha256':canonical.hexdigest(),'exclude_prefixes':supplied['exclude_prefixes'],
            'expected_excluded_counts':supplied['expected_excluded_counts'],'source_plan_sha256':sha(args.manifest.read_bytes()),
            'deduplication':'None. Array values, row order and every source alias remain distinct.',
            'original_control_preserved':supplied['original_control_preserved']}
    archive=io.BytesIO()
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_LZMA)as z:
        for name,data in payload.items():z.writestr(name,data)
    source='CONFIG = '+repr(config)+'\nPAYLOAD = '+repr(base64.b64encode(archive.getvalue()).decode())+'\n'+runtime()
    compile(source,'export.py','exec')
    if len(source.encode())>=1_000_000:raise ValueError(f'Partition export source exceeds limit: {len(source.encode())}')
    args.out.mkdir(parents=True);(args.out/'export.py').write_text(source)
    metadata={'id':args.slug,'title':args.slug.split('/')[-1].replace('-',' '),'code_file':'export.py','language':'python','kernel_type':'script',
              'is_private':True,'enable_gpu':False,'enable_tpu':False,'enable_internet':False,'dataset_sources':[],
              'competition_sources':[],'kernel_sources':kernels}
    (args.out/'kernel-metadata.json').write_text(json.dumps(metadata,indent=2)+'\n')
    (args.out/'partition_manifest.json').write_text(json.dumps(config,indent=2)+'\n')
    (args.out/'expected_records.json').write_text(json.dumps(records,indent=2)+'\n')
    replay=args.out/'local-replay';replay.mkdir()
    with tempfile.TemporaryDirectory(prefix='partition-mount-',dir=args.out)as temporary:
        mount=Path(temporary).resolve()
        for label,record in [('baseline',attached['baseline']),*attached['gadgets'].items()]:
            if 'kernel'in record:
                path=mount/label/Path(record['file']).name;path.parent.mkdir(parents=True)
                shutil.copyfile(local[label],path)
        env=os.environ.copy();env.update(COMPOSITION_INPUT_ROOT=str(mount),COMPOSITION_OUTPUT_ROOT=str(replay.resolve()),OPENBLAS_NUM_THREADS='1')
        subprocess.run([sys.executable,str((args.out/'export.py').resolve())],env=env,check=True,timeout=270)
    proof=json.loads((replay/'consolidation_report.json').read_text())
    assert proof['records']==records and proof['canonical_array_digest']==canonical.hexdigest()
    report={'source_sha256':sha(source.encode()),'source_bytes':len(source.encode()),'arrays':len(records),
            'canonical_sha256':canonical.hexdigest(),'archive_sha256':proof['archive_sha256'],
            'excluded_counts':{k:len(v)for k,v in excluded.items()},'all_local_arrays_exact':True,
            'source_notices_preserved':True,'worker_seconds':240,'server_seconds':300,'launch_performed':False}
    (args.out/'build_report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))


if __name__=='__main__':main()
