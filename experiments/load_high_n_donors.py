"""Reconstruct and interval-certify a pinned public higher-n donor bank.

The descriptor records exact binary64 offsets, factors and converted angles.
Runtime x/y conversion uses Fraction's correctly-rounded binary64 conversion,
then individual scalar IEEE754 operations, avoiding NumPy/libm-version drift.
Every array must match its expected SHA256 before interval certification.
The resulting NPZ's actual hash is recorded for immutable remote attachment.
"""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor
from fractions import Fraction
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import struct
import sys
import time
import urllib.request
import zlib

import numpy as np

sys.set_int_max_str_digits(0)


def sha(data):return hashlib.sha256(data).hexdigest()
def file_sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def value(bits):return struct.unpack('>d',bytes.fromhex(bits))[0]
def vector(bits):return [value(v) for v in bits]
def array_sha(p):return sha(np.asarray(p,dtype='<f8').tobytes(order='C'))


def read_descriptor(path,expected_sha):
    data=Path(path).read_bytes()
    if str(path).endswith('.zlib'):data=zlib.decompress(data)
    if sha(data)!=expected_sha:raise ValueError('Pinned donor descriptor hash mismatch')
    d=json.loads(data)
    if d.get('schema_version')!=1 or d.get('source_repo')!='franciscouzo/square-packing':
        raise ValueError('Unsupported source descriptor')
    if not re.fullmatch('[0-9a-f]{40}',d['source_commit']):raise ValueError('Invalid source commit')
    return d


def download_sources(d,cache,workers):
    cache=Path(cache);cache.mkdir(parents=True,exist_ok=True)
    def one(item):
        key,source=item
        path=source['path']
        if not re.fullmatch(r'certificates/best/n[1-9][0-9]*\.cert',path):raise ValueError('Unexpected certificate path')
        target=cache/Path(path).name
        if target.exists():
            if file_sha(target)!=source['sha256']:raise ValueError('Existing cache certificate hash mismatch')
        else:
            url='https://raw.githubusercontent.com/franciscouzo/square-packing/'+d['source_commit']+'/'+path
            temporary=target.with_suffix('.cert.incoming');count=0;h=hashlib.sha256()
            with urllib.request.urlopen(url,timeout=60) as response,temporary.open('wb') as f:
                while chunk:=response.read(1024*1024):
                    count+=len(chunk)
                    if count>32*1024*1024:raise ValueError('Unexpectedly large public certificate')
                    h.update(chunk);f.write(chunk)
            if h.hexdigest()!=source['sha256']:
                temporary.unlink(missing_ok=True);raise ValueError('Downloaded certificate hash mismatch')
            temporary.replace(target)
        return key,target
    with ThreadPoolExecutor(max_workers=min(3,max(1,workers))) as pool:
        return dict(pool.map(one,d['sources'].items()))


def read_xy(path,expected_n):
    with Path(path).open() as f:
        lines=(r.split() for r in f if r.strip() and not r.lstrip().startswith('#'))
        if int(next(lines)[0])!=expected_n:raise ValueError('Certificate header count mismatch')
        rows=[(float(Fraction(row[0])),float(Fraction(row[1]))) for row in lines]
    if len(rows)!=expected_n:raise ValueError('Certificate row count mismatch')
    return rows


def reconstruct(d,paths):
    sources={key:read_xy(paths[key],rec['n']) for key,rec in d['sources'].items()}
    poses={};digests={};canonical=hashlib.sha256()
    for key,recipe in sorted(d['donors'].items()):
        skey=str(recipe['source_n']);source=d['sources'][skey]
        ids=[i for start,stop in recipe['source_square_id_ranges'] for i in range(start,stop)]
        if len(ids)!=recipe['rows'] or len(set(ids))!=len(ids) or not all(0<=i<source['n'] for i in ids):
            raise ValueError('Invalid crop source indices')
        original=vector(source['source_offset_bits']);crop=vector(recipe['crop_offset_bits'])
        legal=vector(recipe['legalize_offset_bits']);final=vector(recipe['final_offset_bits'])
        factor=value(recipe['dilation_factor_bits']);rows=[]
        for i in ids:
            x,y=sources[skey][i]
            # Separate scalar operations preserve each binary64 rounding step.
            x=x-original[0];y=y-original[1]
            x=x-crop[0];y=y-crop[1]
            x=x-legal[0];y=y-legal[1]
            x=x*factor;y=y*factor
            x=x-final[0];y=y-final[1]
            angle=value(source['angle_bits'][str(i)]) if str(i) in source['angle_bits'] else 0.
            rows.append((x,y,angle))
        p=np.asarray(rows,dtype='<f8');actual=array_sha(p)
        if actual!=recipe['array_sha256']:raise ValueError('Canonical donor array hash mismatch: '+key)
        poses[key]=p;digests[key]=actual
        canonical.update(key.encode()+b'\0');canonical.update(str(len(p)).encode()+b'\0')
        canonical.update(bytes.fromhex(actual))
    if canonical.hexdigest()!=d['canonical_pose_sha256']:raise ValueError('Canonical bank digest mismatch')
    return poses,digests,canonical.hexdigest()


def certify(poses,validator_path,expected_sha):
    if file_sha(validator_path)!=expected_sha:raise ValueError('Pinned interval validator hash mismatch')
    spec=importlib.util.spec_from_file_location('high_n_interval_validator',validator_path)
    module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
    results={}
    for key,p in poses.items():
        rows=[module.Square(*(format(float(v),'.17g') for v in row)) for row in p]
        rec=module.validate_puzzle(len(rows),rows)
        if not rec['valid']:raise ValueError('Reconstructed donor failed interval certification: '+key)
        results[key]=rec
        if len(results)%50==0:print(f'Interval-certified {len(results)}/{len(poses)} donor poses',flush=True)
    return results


def load_bank(descriptor,descriptor_sha256,cache,output,validator,report,workers=3):
    started=time.monotonic();d=read_descriptor(descriptor,descriptor_sha256)
    paths=download_sources(d,cache,workers)
    print(f'Hash-verified {len(paths)} pinned public certificates',flush=True)
    poses,digests,canonical=reconstruct(d,paths)
    certificates=certify(poses,validator,d['validator_sha256'])
    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    temporary=output.with_suffix(output.suffix+'.incoming')
    with temporary.open('wb') as f:np.savez_compressed(f,**poses)
    temporary.replace(output)
    result={'status':'complete','valid':True,'source_repo':d['source_repo'],'source_commit':d['source_commit'],
        'descriptor_sha256':descriptor_sha256,'source_certificates':len(paths),'donors':len(poses),
        'squares':sum(len(p) for p in poses.values()),'canonical_pose_sha256':canonical,
        'expected_canonical_pose_sha256':d['canonical_pose_sha256'],'all_array_hashes_match':True,
        'array_sha256':digests,'archive':str(output),'archive_sha256':file_sha(output),
        'validator_sha256':d['validator_sha256'],'invalid_count':0,'validation':certificates,
        'source_sha256':{key:rec['sha256'] for key,rec in d['sources'].items()},
        'elapsed_seconds':time.monotonic()-started,'licenses':d['licenses']}
    Path(report).write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ['array_sha256','validation','source_sha256','licenses']}),flush=True)
    return result


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--descriptor',type=Path,required=True)
    ap.add_argument('--descriptor-sha256',required=True)
    ap.add_argument('--cache',type=Path,default=Path('/tmp/high-n-certificates'))
    ap.add_argument('--output',type=Path,default=Path('high_n_donors.npz'))
    ap.add_argument('--report',type=Path,default=Path('high_n_donors.source_report.json'))
    ap.add_argument('--validator',type=Path,default=Path('scripts/validate_submission.py'))
    ap.add_argument('--workers',type=int,default=3)
    args=ap.parse_args();load_bank(args.descriptor,args.descriptor_sha256,args.cache,args.output,args.validator,args.report,args.workers)

if __name__=='__main__':main()
