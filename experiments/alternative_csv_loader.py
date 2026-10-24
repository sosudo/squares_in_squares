"""Restore a hash-bound alternative-packing bank from its public CSV sources.

Only exact expected source CSV bytes and per-array digests are accepted. Public
notebook URLs may later change; a changed source fails closed instead of being
silently substituted. Versioned dataset mirrors are preferred when available.
This module never submits or launches notebook jobs.
"""
from __future__ import annotations
import argparse
import csv
from concurrent.futures import ThreadPoolExecutor
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import sys
import time
import urllib.request
import zlib

import numpy as np


def digest(path):
    with Path(path).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def array_sha(p):return hashlib.sha256(np.asarray(p,dtype='<f8').tobytes()).hexdigest()
def val(bits):return struct.unpack('>d',bytes.fromhex(bits))[0]


def load_descriptor(path,expected_sha):
    data=Path(path).read_bytes()
    if str(path).endswith('.zlib'):data=zlib.decompress(data)
    if hashlib.sha256(data).hexdigest()!=expected_sha:raise ValueError('Descriptor SHA mismatch')
    d=json.loads(data)
    if d.get('schema_version')!=1:raise ValueError('Unsupported descriptor')
    return d


def source_paths(d,cache,download=False):
    cache=Path(cache)
    if download:cache.mkdir(parents=True,exist_ok=True)
    def one(item):
        sid,source=item
        if not download:
            path=Path(source['local_path'])
        else:
            path=cache/(sid+'.csv')
            if not path.exists():
                url=source['download_url']
                if not url.startswith('https://www.kaggle.com/api/v1/'):
                    raise ValueError('Unexpected public source URL')
                temporary=path.with_suffix('.csv.incoming');count=0
                with urllib.request.urlopen(url,timeout=90)as r,temporary.open('wb')as f:
                    while chunk:=r.read(1024*1024):
                        count+=len(chunk)
                        if count>64*1024*1024:raise ValueError('Unexpected source size')
                        f.write(chunk)
                if digest(temporary)!=source['sha256']:
                    temporary.unlink(missing_ok=True);raise ValueError('Public output changed; exact source hash is unavailable')
                temporary.replace(path)
        if digest(path)!=source['sha256']:raise ValueError('Frozen source CSV SHA mismatch')
        return sid,path
    with ThreadPoolExecutor(max_workers=3)as pool:return dict(pool.map(one,d['sources'].items()))


def reconstruct(d,paths,embedded=None):
    embedded=embedded or {}
    wanted={sid:set()for sid in d['sources']}
    for rec in d['donors'].values():wanted[rec['source_id']].add(rec['source_n'])
    raw={}
    for sid,path in paths.items():
        sizes=wanted[sid];groups={n:[None]*n for n in sizes}
        with Path(path).open(encoding='utf-8-sig',newline='')as f:
            for row in csv.DictReader(f):
                n=int(float(row['n']))
                if n not in sizes:continue
                k=int(row['square_id'])
                if not 0<=k<n or groups[n][k]is not None:raise ValueError('Bad source square IDs')
                groups[n][k]=(float(row['x']),float(row['y']),float(row['angle']))
        if any(any(row is None for row in rows)for rows in groups.values()):raise ValueError('Missing source rows')
        if digest(path)!=d['sources'][sid]['sha256']:raise ValueError('Source changed while loading')
        raw[sid]=groups
    poses={};canonical=hashlib.sha256();hashes={}
    for key,rec in sorted(d['donors'].items()):
        if key in embedded:
            p=np.asarray(embedded[key],dtype='<f8')
        else:
            recipe=rec['recipe'];a=list(map(val,recipe['normalization_offset_bits']))
            b=list(map(val,recipe['final_offset_bits']));factor=val(recipe['dilation_factor_bits']);rows=[]
            for x,y,angle in raw[rec['source_id']][rec['source_n']]:
                x=x-a[0];y=y-a[1]
                x=x*factor;y=y*factor
                x=x-b[0];y=y-b[1]
                rows.append((x,y,angle))
            p=np.asarray(rows,dtype='<f8')
        actual=array_sha(p)
        if actual!=rec['array_sha256']:raise ValueError('Reconstructed array SHA mismatch: '+key)
        poses[key]=p;hashes[key]=actual
        canonical.update(key.encode()+b'\0');canonical.update(str(len(p)).encode()+b'\0')
        canonical.update(bytes.fromhex(actual))
    if canonical.hexdigest()!=d['canonical_pose_sha256']:raise ValueError('Canonical bank SHA mismatch')
    return poses,hashes,canonical.hexdigest()


def certify(poses,path,expected):
    if digest(path)!=expected:raise ValueError('Validator SHA mismatch')
    spec=importlib.util.spec_from_file_location('alternative_interval_validator',path)
    module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
    result={}
    for key,p in poses.items():
        rows=[module.Square(*(format(float(v),'.17g')for v in row))for row in p]
        rec=module.validate_puzzle(len(rows),rows)
        if not rec['valid']:raise ValueError('Alternative pose failed interval certification: '+key)
        result[key]=rec
        if len(result)%50==0:print(f'Interval-certified {len(result)}/{len(poses)} alternative poses',flush=True)
    return result


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--descriptor',type=Path,required=True);ap.add_argument('--descriptor-sha256',required=True)
    ap.add_argument('--download',action='store_true',help='Fetch exact public CSVs; default uses already frozen local files')
    ap.add_argument('--cache',type=Path,default=Path('/tmp/alternative-public-csvs'))
    ap.add_argument('--output',type=Path,default=Path('alternative_donors.npz'))
    ap.add_argument('--report',type=Path,default=Path('alternative_donors.source_report.json'))
    ap.add_argument('--validator',type=Path,default=Path('scripts/validate_submission.py'))
    ap.add_argument('--embedded-poses',type=Path)
    ap.add_argument('--embedded-sha256')
    args=ap.parse_args();started=time.monotonic();d=load_descriptor(args.descriptor,args.descriptor_sha256)
    embedded={}
    if args.embedded_poses:
        if not args.embedded_sha256 or digest(args.embedded_poses)!=args.embedded_sha256:
            raise ValueError('Frozen embedded pose archive SHA mismatch')
        with np.load(args.embedded_poses,allow_pickle=False)as z:
            for key in z.files:
                if key not in d['donors']or array_sha(z[key])!=d['donors'][key]['array_sha256']:
                    raise ValueError('Frozen embedded pose does not match the original certified bank')
                embedded[key]=z[key]
    needed={rec['source_id']for key,rec in d['donors'].items()if key not in embedded}
    download_descriptor={**d,'sources':{sid:rec for sid,rec in d['sources'].items()if sid in needed}}
    paths=source_paths(download_descriptor,args.cache,args.download);poses,hashes,canonical=reconstruct(d,paths,embedded)
    certificates=certify(poses,args.validator,d['validator_sha256'])
    args.output.parent.mkdir(parents=True,exist_ok=True)
    tmp=args.output.with_suffix(args.output.suffix+'.incoming')
    with tmp.open('wb')as f:np.savez_compressed(f,**poses)
    tmp.replace(args.output)
    report={'status':'complete','valid':True,'archive_sha256':digest(args.output),
        'descriptor_sha256':args.descriptor_sha256,'donors':len(poses),'squares':sum(len(p)for p in poses.values()),
        'canonical_pose_sha256':canonical,'all_array_hashes_match':True,'array_sha256':hashes,
        'source_sha256':{sid:s['sha256']for sid,s in d['sources'].items()},
        'verified_remote_or_local_csv_sha256':{sid:d['sources'][sid]['sha256']for sid in paths},
        'embedded_pose_count':len(embedded),'fetched_csv_count':len(paths),
        'embedded_archive_sha256':args.embedded_sha256 if embedded else None,
        'validator_sha256':d['validator_sha256'],'invalid_count':0,'validation':certificates,
        'elapsed_seconds':time.monotonic()-started,
        'meaning':'Validated alternative donor geometry only; no new competition score claim.'}
    args.report.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items()if k not in ['array_sha256','source_sha256','validation']}),flush=True)

if __name__=='__main__':
    try:main()
    except Exception as e:
        print(json.dumps({'status':'blocked','error_type':type(e).__name__,'reason':'Exact source, array or interval validation failed; no substitution permitted.'}))
        raise SystemExit(1)
