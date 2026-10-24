#!/usr/bin/env python3
"""Losslessly export frozen float64 donor banks through bounded private CPU parts."""
from __future__ import annotations
import argparse
import base64
import hashlib
import io
import json
import lzma
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import zipfile
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = r'''
import base64,hashlib,io,json,lzma,os,signal,time,zipfile
from pathlib import Path
os.environ['OPENBLAS_NUM_THREADS']='1'
os.environ['OMP_NUM_THREADS']='1'
import numpy as np
started=time.monotonic()
def expired(signum,frame):raise TimeoutError('Exact donor export exceeded180 seconds')
signal.signal(signal.SIGALRM,expired);signal.alarm(180)
compressed=base64.b85decode(PAYLOAD)
assert hashlib.sha256(compressed).hexdigest()==CONFIG['compressed_sha256']
decoder=lzma.LZMADecompressor(memlimit=128*1024*1024)
raw=decoder.decompress(compressed,max_length=CONFIG['raw_bytes']+1)
assert decoder.eof and not decoder.unused_data and len(raw)==CONFIG['raw_bytes']
assert hashlib.sha256(raw).hexdigest()==CONFIG['raw_sha256']
with zipfile.ZipFile(io.BytesIO(raw))as archive:
    assert set(archive.namelist())==set(CONFIG['files'])
    data={name:archive.read(name)for name in archive.namelist()}
    for name,value in data.items():assert hashlib.sha256(value).hexdigest()==CONFIG['files'][name]
index=json.loads(data['index.json']);blob=data['poses.bin'];arrays={};offset=0;canonical=hashlib.sha256()
for record in index['arrays']:
    assert record['dtype']=='<f8' and record['shape'][1]==3
    size=record['shape'][0]*3*8
    value=blob[offset:offset+size];offset+=size
    assert len(value)==size and hashlib.sha256(value).hexdigest()==record['sha256']
    pose=np.frombuffer(value,dtype='<f8').reshape(record['shape']).copy()
    assert np.isfinite(pose).all() and len(pose)>0
    w,h,d=record['nominal_type'];assert len(pose)==w*h+d
    assert record['output_key']not in arrays
    arrays[record['output_key']]=pose
    canonical.update((record['output_key']+'\0'+record['sha256']+'\n').encode())
assert offset==len(blob) and len(arrays)==CONFIG['arrays']
assert canonical.hexdigest()==CONFIG['canonical_sha256']
output=Path('donor_part.npz');assert not output.exists()
np.savez_compressed(output,**arrays)
with np.load(output,allow_pickle=False)as restored:
    assert restored.files==list(arrays)
    for record in index['arrays']:
        assert hashlib.sha256(np.asarray(restored[record['output_key']],dtype='<f8').tobytes()).hexdigest()==record['sha256']
for name,value in data.items():
    if name=='poses.bin':continue
    path=Path('provenance')/name
    assert path.resolve().is_relative_to(Path('provenance').resolve())
    path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(value)
report={'status':'complete','arrays':len(arrays),'archive_sha256':hashlib.sha256(output.read_bytes()).hexdigest(),
        'canonical_sha256':canonical.hexdigest(),'seconds':time.monotonic()-started,
        'exact_array_reconstruction':True,'fresh_geometry_evaluations':0,
        'certificate_policy':'Frozen source certificates reused only after every exact array hash matches.',
        'configuration':CONFIG,'competition_submission_performed':False}
Path('part_report.json').write_text(json.dumps(report,indent=2)+'\n')
signal.alarm(0);print(json.dumps({k:v for k,v in report.items()if k!='configuration'}),flush=True)
'''

def sha(data): return hashlib.sha256(data).hexdigest()


def package(records, sources, notices):
    index={'arrays':[{k:v for k,v in record.items()if k!='bytes'}for record in records],
           'source_bindings':sources,'deduplication':'None; all source array bytes and order retained.'}
    data={'index.json':json.dumps(index,separators=(',',':')).encode(),
          'poses.bin':b''.join(record['bytes']for record in records)}
    data.update(notices)
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w',compression=zipfile.ZIP_STORED)as archive:
        for name,value in data.items():archive.writestr(name,value)
    raw=stream.getvalue();packed=lzma.compress(raw,preset=6)
    canonical=hashlib.sha256()
    for record in records:canonical.update((record['output_key']+'\0'+record['sha256']+'\n').encode())
    config={'format':'exact_float64_concatenation_v1','raw_bytes':len(raw),'raw_sha256':sha(raw),
            'compressed_sha256':sha(packed),'files':{k:sha(v)for k,v in data.items()},
            'arrays':len(records),'canonical_sha256':canonical.hexdigest(),
            'worker_wall_seconds':180,'server_timeout_seconds':300}
    source='CONFIG='+repr(config)+'\nPAYLOAD='+repr(base64.b85encode(packed).decode())+'\n'+RUNTIME
    compile(source,'export.py','exec')
    return source,config,index


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bank',type=Path,action='append',required=True)
    parser.add_argument('--label',action='append',required=True)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--owner',default='sos54352')
    parser.add_argument('--notice-file',type=Path,action='append',default=[])
    args=parser.parse_args()
    if len(args.bank)!=len(args.label)or args.out.exists():raise ValueError('Fresh output and one label per bank required')
    notices={f'notices/{p.name}':p.read_bytes()for p in (ROOT/'vendor/fq/LICENSE',ROOT/'vendor/fq/NOTICE',ROOT/'vendor/fq/SOURCE_MANIFEST.json')}
    for index,path in enumerate(args.notice_file):
        notices[f'notices/inherited-{index:03d}-{path.name}']=path.read_bytes()
    records=[];sources={}
    for label,path in zip(args.label,args.bank):
        if not re.fullmatch('[a-z][a-z0-9_]*',label):raise ValueError('Unsafe bank label')
        provenance={str(p):sha(p.read_bytes())for p in sorted(path.parent.glob('*.json'))}
        sources[label]={'archive_path':str(path),'archive_sha256':sha(path.read_bytes()),'proof_files':provenance}
        with np.load(path,allow_pickle=False)as bank:
            for key in bank.files:
                original=bank[key]
                if original.dtype!=np.dtype('float64'):raise ValueError('Expected original float64 array')
                pose=np.ascontiguousarray(original,dtype='<f8');match=re.match(r'(\d+)_(\d+)_(\d+)',key)
                if not match or pose.ndim!=2 or pose.shape[1]!=3 or not np.isfinite(pose).all():raise ValueError('Invalid typed array')
                typ=list(map(int,match.groups()))
                if len(pose)!=typ[0]*typ[1]+typ[2]:raise ValueError('Nominal type/count differs')
                raw=pose.tobytes();output=f'{label}__{len(records):05d}__{key}'
                records.append({'output_key':output,'source_label':label,'source_key':key,'nominal_type':typ,
                                'shape':list(pose.shape),'dtype':'<f8','sha256':sha(raw),'bytes':raw})
    # Split whole arrays only, with a conservative source margin. No float math.
    pending=[records];parts=[]
    while pending:
        group=pending.pop(0);source,config,index=package(group,sources,notices)
        if len(source.encode())>950000:
            if len(group)<2:raise ValueError('One array cannot fit')
            middle=len(group)//2;pending[:0]=[group[:middle],group[middle:]];continue
        parts.append((source,config,index))
    args.out.mkdir(parents=True);reports=[]
    for number,(source,config,index)in enumerate(parts):
        folder=args.out/f'part-{number:02d}';folder.mkdir()
        slug=f'{args.owner}/squares-donor-part-{config["canonical_sha256"][:12]}'
        (folder/'export.py').write_text(source)
        metadata={'id':slug,'title':slug.split('/')[-1].replace('-',' '),'code_file':'export.py','language':'python',
                  'kernel_type':'script','is_private':True,'enable_gpu':False,'enable_tpu':False,'enable_internet':False,
                  'kernel_sources':[],'dataset_sources':[],'competition_sources':[]}
        (folder/'kernel-metadata.json').write_text(json.dumps(metadata,indent=2)+'\n')
        (folder/'part_index.json').write_text(json.dumps(index,indent=2)+'\n')
        local=folder/'local-replay';local.mkdir()
        subprocess.run([sys.executable,str((folder/'export.py').resolve())],cwd=local,check=True)
        report=json.loads((local/'part_report.json').read_text())
        report.update(source_sha256=sha(source.encode()),source_bytes=len(source.encode()),ref=slug,version=1,
                      folder=str(folder),local_archive=str(local/'donor_part.npz'))
        (folder/'build_report.json').write_text(json.dumps(report,indent=2)+'\n');reports.append(report)
    assert sum(x['arrays']for x in reports)==len(records)
    (args.out/'parts_manifest.json').write_text(json.dumps({'sources':sources,'total_arrays':len(records),'parts':reports},indent=2)+'\n')
    print(json.dumps({'output':str(args.out),'parts':len(reports),'arrays':len(records),
                      'source_bytes':[x['source_bytes']for x in reports],'launch_performed':False}))


if __name__=='__main__':main()
