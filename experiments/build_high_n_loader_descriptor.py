"""Bind compact source-backed reconstruction recipes to the certified donor arrays."""
import argparse
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import struct
import sys
import zlib

import numpy as np
from scipy.spatial import cKDTree
from compose_gadgets import extents, normalize

sys.set_int_max_str_digits(0)


def sha_bytes(data):return hashlib.sha256(data).hexdigest()
def bits(x):return struct.pack('>d',float(x)).hex()
def vector_bits(x):return [bits(v) for v in x]
def array_sha(p):return sha_bytes(np.asarray(p,dtype='<f8').tobytes(order='C'))


def ranges(ids):
    out=[]
    for i in ids:
        if out and i==out[-1][1]:out[-1][1]+=1
        else:out.append([i,i+1])
    return out


def load_raw(path):
    with path.open() as f:
        lines=[r.split() for r in f if r.strip() and not r.lstrip().startswith('#')]
    n=int(lines[0][0]);p=np.array([(float(Fraction(x)),float(Fraction(y)),2*math.atan(float(Fraction(t))))
                                for x,y,t in lines[1:]],dtype=float)
    if p.shape!=(n,3):raise ValueError(path.name)
    return p


def record_legalize(p):
    p=p.copy();lo,_=extents(p);offset=lo.min(axis=0);p[:,:2]-=offset
    pairs=cKDTree(p[:,:2]).query_pairs(1.5,output_type='ndarray');factor=1.
    if len(pairs):
        i,j=pairs.T;delta=p[j,:2]-p[i,:2];a,b=p[i,2],p[j,2]
        projection=np.maximum.reduce([np.abs(delta[:,0]*np.cos(t)+delta[:,1]*np.sin(t))
                                      for t in (a,a+math.pi/2,b,b+math.pi/2)])
        radius=.5*(1+np.abs(np.cos(a-b))+np.abs(np.sin(a-b)))
        factor=max(1.,float(np.max((radius+2e-9)/np.maximum(projection,1e-30))))
        if factor>1.000001:raise ValueError('Large overlap')
        p[:,:2]*=factor
    lo,_=extents(p);final=lo.min(axis=0);p[:,:2]-=final
    return p,offset,factor,final


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--bank',type=Path,default=Path('artifacts/high-n-donors'))
    ap.add_argument('--catalogue',type=Path,default=Path('/tmp/squares-research/couzo'))
    ap.add_argument('--validator',type=Path,default=Path('scripts/validate_submission.py'))
    args=ap.parse_args();manifest=json.loads((args.bank/'manifest.json').read_text())
    records=manifest['donors'];source_rows={};sources={};recipes={}
    with np.load(args.bank/'donors.npz',allow_pickle=False) as z:
        for key,meta in records.items():
            n=meta['source_n'];skey=str(n)
            if n not in source_rows:
                path=args.catalogue/meta['certificate'];data=path.read_bytes()
                if sha_bytes(data)!=meta['certificate_sha256']:raise ValueError('Certificate changed')
                raw=load_raw(path);lo,_=extents(raw);offset=lo.min(axis=0)
                source_rows[n]=(raw,offset)
                sources[skey]={'path':meta['certificate'],'sha256':meta['certificate_sha256'],
                    'n':n,'source_offset_bits':vector_bits(offset),'angle_bits':{},
                    'credit':meta['credit'],'source_repository':meta['source_repository']}
            raw,source_offset=source_rows[n];ids=meta['source_square_ids']
            q=raw[ids].copy();q[:,:2]-=source_offset
            lo,_=extents(q);crop_offset=lo.min(axis=0);q[:,:2]-=crop_offset
            actual,legal_offset,factor,final_offset=record_legalize(q)
            expected=z[key]
            if not np.array_equal(actual,expected):raise ValueError('Recipe does not exactly reconstruct '+key)
            for i in ids:
                if raw[i,2]!=0:sources[skey]['angle_bits'][str(i)]=bits(raw[i,2])
            recipes[key]={'source_n':n,'source_square_id_ranges':ranges(ids),'rows':len(ids),
                'crop_offset_bits':vector_bits(crop_offset),'legalize_offset_bits':vector_bits(legal_offset),
                'dilation_factor_bits':bits(factor),'final_offset_bits':vector_bits(final_offset),
                'array_sha256':array_sha(expected)}
    canonical=hashlib.sha256()
    for key,rec in sorted(recipes.items()):
        canonical.update(key.encode()+b'\0');canonical.update(str(rec['rows']).encode()+b'\0')
        canonical.update(bytes.fromhex(rec['array_sha256']))
    licenses={p.name:p.read_text() for p in Path('vendor/notices/high-n-donors').glob('LICENSE-*.txt')}
    descriptor={'schema_version':1,'source_repo':'franciscouzo/square-packing',
        'source_commit':manifest['catalogue_commit'],'source_manifest_sha256':manifest['manifest_sha256'],
        'sources':sources,'donors':recipes,'licenses':licenses,'canonical_pose_sha256':canonical.hexdigest(),
        'validator_sha256':sha_bytes(args.validator.read_bytes()),
        'note':'IEEE754 scalar recipes exactly reproduce original binary64 arrays; no runtime trig required.'}
    data=json.dumps(descriptor,separators=(',',':'),sort_keys=True).encode()
    compressed=zlib.compress(data,9)
    (args.bank/'loader_descriptor.json').write_bytes(data)
    (args.bank/'loader_descriptor.json.zlib').write_bytes(compressed)
    summary={'sources':len(sources),'donors':len(recipes),'descriptor_bytes':len(data),
             'compressed_bytes':len(compressed),'descriptor_sha256':sha_bytes(data),
             'compressed_sha256':sha_bytes(compressed),'canonical_pose_sha256':canonical.hexdigest(),
             'validator_sha256':descriptor['validator_sha256']}
    (args.bank/'loader_descriptor.summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary),flush=True)

if __name__=='__main__':main()
