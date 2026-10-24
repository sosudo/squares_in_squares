"""Mine public n>1000 exact certificates for new bounded rectangle donors.

Only source categories with verified public MIT notices are admitted here:
Mishapolk and TheSnakeFang. Canonical certificate bytes are checked against
Couzo's pinned manifest; all inherited credit/provenance is retained. Crops
are subsets, never scaled squares. Floating export is independently legalized
and any full-puzzle improvement still requires interval certification.
"""
from __future__ import annotations
import argparse
from collections import Counter
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
import time

import numpy as np
from scipy.spatial import cKDTree
from compose_gadgets import extents, normalize, legalize, read_baseline

sys.set_int_max_str_digits(0)
CATEGORIES = {'Mishapolk public certificate': 'Mishapolk/square-packing-records',
              'snakefang': 'TheSnakeFang/squarepack-certs'}


def sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def read_certificate(path):
    with Path(path).open() as f:
        lines=(line.split() for line in f if line.strip() and not line.lstrip().startswith('#'))
        header=next(lines);n=int(header[0]);bound=float(Fraction(header[1]))
        p=np.array([(float(Fraction(x)),float(Fraction(y)),2*math.atan(float(Fraction(t))))
                    for x,y,t in lines],dtype=float)
    if p.shape!=(n,3):raise ValueError(f'Certificate count mismatch: {path.name}')
    return n,bound,normalize(p)


def components(p):
    a=(p[:,2]+math.pi/4)%(math.pi/2)-math.pi/4
    ids=np.flatnonzero(np.abs(a)>.003)
    if not len(ids):return []
    parent=np.arange(len(ids))
    def find(i):
        while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
        return i
    for i,j in cKDTree(p[ids,:2]).query_pairs(1.65):
        i,j=find(i),find(j)
        if i!=j:parent[i]=j
    groups={}
    for i,k in enumerate(ids):groups.setdefault(find(i),[]).append(int(k))
    return [np.array(g,dtype=int) for g in groups.values() if len(g)>=3]


def fingerprint(p,decimals=4):
    hashes=[]
    for swap in (False,True):
        q=p.copy()
        if swap:q[:,:2]=q[:,[1,0]];q[:,2]=math.pi/2-q[:,2]
        for sx,sy in ((1,1),(-1,1),(1,-1),(-1,-1)):
            r=q.copy();r[:,0]*=sx;r[:,1]*=sy;r[:,2]*=sx*sy
            r[:,:2]-=r[:,:2].min(axis=0)
            # cos/sin(4 theta) identify a square's orientation without the
            # discontinuity at +/-45 degrees in a wrapped-angle fingerprint.
            r=np.column_stack((r[:,:2],np.cos(4*r[:,2]),np.sin(4*r[:,2])))
            r=np.round(r,decimals);r[r==0]=0
            r=r[np.lexsort((r[:,3],r[:,2],r[:,1],r[:,0]))]
            hashes.append(hashlib.sha256(r.tobytes()).hexdigest())
    return min(hashes)


def crop_windows(p,indices):
    lo,hi=extents(p);c_lo=lo[indices].min(axis=0);c_hi=hi[indices].max(axis=0)
    c=(c_lo+c_hi)/2
    starts=[]
    for width in (8.,12.,16.,24.,31.9):
        for anchor in (c_lo-1.001,c_hi+1.001-width,c-width/2):
            starts.append((anchor,np.array([width,width])))
    # Also tightly retain a small connected tilted component and its fill.
    if np.max(c_hi-c_lo)<30:
        starts.append((c_lo-1.01,c_hi-c_lo+2.02))
    seen=set()
    for start,wh in starts:
        mask=np.all(lo>=start-1e-10,axis=1)&np.all(hi<=start+wh+1e-10,axis=1)
        ids=np.flatnonzero(mask)
        if len(ids)<10 or len(ids)>1050:continue
        key=ids.tobytes()
        if key in seen:continue
        seen.add(key)
        q=normalize(p[ids]);a,b=extents(q);spans=b.max(axis=0)
        w,h=np.floor(spans+1e-9).astype(int)
        d=len(q)-int(w*h)
        if w<2 or h<2 or max(w,h)>31 or not 0<d<=63:continue
        f=float(np.max(spans-[w,h]))
        if not 1e-7<f<.999999:continue
        yield q,{'window_start':start.tolist(),'window_shape':wh.tolist(),'source_square_ids':ids.tolist(),
                 'nominal_width':int(w),'nominal_height':int(h),'surplus':d,'bloat':f}


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--catalogue',type=Path,default=Path('/tmp/squares-research/couzo'))
    ap.add_argument('--baseline',type=Path,required=True)
    ap.add_argument('--output',type=Path,default=Path('artifacts/high-n-donors'))
    ap.add_argument('--max-n',type=int,default=5000)
    ap.add_argument('--limit',type=int,default=240)
    args=ap.parse_args();started=time.monotonic();args.output.mkdir(parents=True,exist_ok=True)
    manifest_path=args.catalogue/'certificates/best/manifest.json'
    manifest=json.loads(manifest_path.read_text())['witnesses']
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=args.catalogue,text=True).strip()
    base=read_baseline(args.baseline)
    known=set()
    for p in base.values():
        for ids in components(p):known.add((len(ids),fingerprint(p[ids])))
    candidates=[];inventory=[];new_motifs=set();seen_poses=set();categories=Counter()
    selected=[(int(n),r) for n,r in manifest.items() if 1000<int(n)<=args.max_n and
              r.get('provenance',{}).get('category') in CATEGORIES]
    for index,(n,rec) in enumerate(sorted(selected)):
        path=args.catalogue/rec['certificate']
        if sha(path)!=rec['certificate_sha256']:raise ValueError(f'Certificate hash mismatch n={n}')
        actual,bound,p=read_certificate(path)
        if actual!=n:raise ValueError('Manifest count mismatch')
        category=rec['provenance']['category'];categories[category]+=1
        cs=components(p);novel=[]
        for ids in cs:
            f=(len(ids),fingerprint(p[ids]))
            if f not in known:novel.append(ids);new_motifs.add(f)
        inventory.append({'n':n,'bound':bound,'tilted_components':len(cs),'novel_components':len(novel),
                          'component_sizes':[len(ids) for ids in cs],
                          'certificate':rec['certificate'],'certificate_sha256':rec['certificate_sha256'],
                          'source_repository':CATEGORIES[category],'credit':rec['credit']})
        for ids in novel:
            for q,crop in crop_windows(p,ids):
                fp=fingerprint(q)
                if fp in seen_poses:continue
                seen_poses.add(fp)
                # Prefer lower bloat and positive surplus; keep the source link.
                merit=crop['bloat']/(crop['surplus']**.5)
                candidates.append((merit,q,{'source_n':n,'certificate':rec['certificate'],
                    'certificate_sha256':rec['certificate_sha256'],'credit':rec['credit'],
                    'source_repository':CATEGORIES[category],'manifest_record':rec,
                    'tilted_component_ids':ids.tolist(),**crop}))
        if (index+1)%20==0:print(json.dumps({'processed':index+1,'novel_component_families':len(new_motifs),
                  'rectangle_candidates':len(candidates),'seconds':time.monotonic()-started}),flush=True)
    # Bound the experiment and retain diversity across source counts.
    chosen=[];per_source=Counter()
    for merit,p,meta in sorted(candidates,key=lambda r:r[0]):
        n=meta['source_n']
        if per_source[n]>=4:continue
        q=legalize(p)
        if q is None:continue
        key=f'n{n}_crop{per_source[n]}'
        chosen.append((key,q,{**meta,'merit':merit}));per_source[n]+=1
        if len(chosen)>=args.limit:break
    archive=args.output/'donors.npz';np.savez_compressed(archive,**{key:p for key,p,_ in chosen})
    # Retain shape/separator variants for a separately budgeted broader
    # composer, instead of throwing them away because of one scalar ranking.
    all_archive=args.output/'all_crops.npz'
    np.savez_compressed(all_archive,**{f'crop_{i}':p for i,(_,p,_) in enumerate(candidates)})
    (args.output/'all_crops.provenance.json').write_text(json.dumps({f'crop_{i}':meta
         for i,(_,_,meta) in enumerate(candidates)},indent=2)+'\n')
    report={'catalogue_repository':'https://github.com/franciscouzo/square-packing','catalogue_commit':commit,
            'manifest_sha256':sha(manifest_path),'baseline':str(args.baseline.resolve()),
            'baseline_sha256':sha(args.baseline),'source_certificates':len(selected),'categories':dict(categories),
            'known_baseline_component_families':len(known),'novel_component_families':len(new_motifs),
            'candidate_crops':len(candidates),'exported_donors':len(chosen),'archive_sha256':sha(archive),
            'all_crops_archive_sha256':sha(all_archive),
            'inventory':inventory,'donors':{key:meta for key,_,meta in chosen},
            'elapsed_seconds':time.monotonic()-started,'rounding_dilation_clearance':2e-9,
            'note':'Novelty is approximate geometric clustering at 1e-4, not a new mathematical record claim.'}
    (args.output/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ['inventory','donors']}),flush=True)

if __name__=='__main__':main()
