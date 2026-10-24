"""Retain geometry-distinct near-best public packings as alternative donors.

This reads only already downloaded, hash-bound public CSVs. It does not submit,
launch jobs, download new sources, or replace the current portfolio. Whole-pose
D4/translation equivalence removes precision copies; relative wall phase and
individual square angles remain in every retained pose. Independent interval
certification decides admission, not a source's claimed leaderboard score.
"""
from __future__ import annotations
import argparse
from collections import Counter,defaultdict
import hashlib
import json
import math
from pathlib import Path
import struct
import sys
import time

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

from compose_gadgets import extents,normalize,legalize,orientations,read_baseline,side
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from validate_submission import Square,validate_puzzle


def digest(path):
    with Path(path).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()

def array_sha(p):return hashlib.sha256(np.asarray(p,dtype='<f8').tobytes(order='C')).hexdigest()
def bits(v):return struct.pack('>d',float(v)).hex()
def vbits(a):return [bits(v)for v in a]


def geometry_fingerprint(oriented):
    hashes=[]
    for q in oriented:
        a=np.column_stack((q[:,:2],np.cos(4*q[:,2]),np.sin(4*q[:,2])))
        a=np.round(a,3);a[a==0]=0
        a=a[np.lexsort((a[:,3],a[:,2],a[:,1],a[:,0]))]
        hashes.append(hashlib.sha256(a.tobytes()).hexdigest())
    return min(hashes)


def compare(oriented,reference,precision_tol=2e-4,angle_tol=2e-5):
    q,tree=reference;novelty=math.inf
    for p in oriented:
        distances,ids=tree.query(p[:,:2],k=1)
        angular=np.abs(np.sin(2*(p[:,2]-q[ids,2])))
        if distances.max()<=precision_tol and angular.max()<=angle_tol:
            return True,0.
        score=float(np.sqrt(np.mean(distances**2))+.2*np.sqrt(np.mean(angular**2)))
        novelty=min(novelty,score)
    return False,novelty


def pose_reference(p):
    p=normalize(p);return p,cKDTree(p[:,:2])


def source_ledger(root):
    allowed={'additional-public','public','public-v24','public-lightning18','additional-dataset-v11'}
    ledger=[]
    for meta in sorted(root.rglob('*.source.json')):
        if not any(part in allowed for part in meta.parts):continue
        csv=Path(str(meta).removesuffix('.source.json')+'.csv')
        if not csv.exists():continue
        rec=json.loads(meta.read_text());actual=digest(csv)
        if actual!=rec['sha256']:raise ValueError('A frozen public CSV changed: '+csv.name)
        ref=rec.get('notebook')or rec.get('dataset')
        if not ref:raise ValueError('Public source reference is missing')
        kind='dataset' if 'dataset' in rec else 'notebook'
        if kind=='dataset':
            if ref.startswith(('cdeotte/','lightningv08/')):license='CC0 dataset compilation; inherited source credits remain'
            elif ref.startswith('dariushafshar/'):license='CC BY 4.0 dataset compilation; inherited source terms remain'
            elif ref.startswith('kmmmvs/'):license='Mixed source terms; full notices retained in vendor/notices/kmmmvs-v24/'
            else:raise ValueError('Unreviewed dataset license')
        else:license='Public Kaggle notebook Apache-2.0 notice; inherited source terms remain'
        version=rec.get('version')
        if (version is None and ref=='kmmmvs/squares-in-squares-best-packings'
                and actual=='aa8d390849d0ff5a8acacc36ad62f232ab76a11acdb8402a79e29167f6d1d920'):version=22
        if (version is None and ref=='cdeotte/squares-in-squares-22-315-data'
                and actual=='7a9fb4638f6de775d01a8300cbe3616b5c21052fdb5229a0d6bd4c9f67989725'):version=2
        ledger.append({'id':actual[:16],'path':str(csv.resolve()),'sha256':actual,'reference':ref,
            'kind':kind,'version':version,'metadata':str(meta.resolve()),'metadata_sha256':digest(meta),
            'download_provenance':rec,'license':license,
            'license_evidence':'research/ftmc_strategy.md for the official public-notebook notice; vendor/notices/ for inherited records'})
    # Identical outputs can appear in many notebooks. Prefer the explicitly
    # versioned dataset's provenance and licensing without relabeling a mirror
    # notebook with that dataset's version number.
    groups=defaultdict(list)
    for row in ledger:groups[row['sha256']].append(row)
    canonical=[]
    for group in groups.values():
        group.sort(key=lambda r:(r['kind']!='dataset',r['version']is None,r['reference']))
        chosen=group[0]
        chosen['identical_csv_mirrors']=[r for r in group[1:]]
        if chosen['kind']=='dataset' and chosen['version']is not None:
            filename=chosen['download_provenance'].get('filename','submission.csv')
            chosen['portable_download_url']='https://www.kaggle.com/api/v1/datasets/download/'+chosen['reference']+'/'+filename+'?datasetVersionNumber='+str(chosen['version'])
            chosen['portable_version_pin']='explicit dataset version plus exact CSV SHA-256'
        else:
            chosen['portable_download_url']=chosen['download_provenance']['url']
            chosen['portable_version_pin']='hash-bound public output; reject any changed bytes, never silently accept a newer output'
        canonical.append(chosen)
    ledger=canonical
    # Recent versioned datasets provide good quality without suppressing older layouts.
    ledger.sort(key=lambda r:(r['kind']!='dataset',-(r['version']or 0),r['reference']))
    return ledger


def legalize_recipe(raw):
    p=raw.copy();lo,_=extents(p);initial=lo.min(axis=0);p[:,:2]-=initial
    pairs=cKDTree(p[:,:2]).query_pairs(1.5,output_type='ndarray');factor=1.
    if len(pairs):
        i,j=pairs.T;delta=p[j,:2]-p[i,:2];a,b=p[i,2],p[j,2]
        projection=np.maximum.reduce([np.abs(delta[:,0]*np.cos(t)+delta[:,1]*np.sin(t))
                                     for t in (a,a+math.pi/2,b,b+math.pi/2)])
        radius=.5*(1+np.abs(np.cos(a-b))+np.abs(np.sin(a-b)))
        factor=max(1.,float(np.max((radius+2e-9)/np.maximum(projection,1e-30))))
        if factor>1.000001:return None,None
        p[:,:2]*=factor
    lo,_=extents(p);final=lo.min(axis=0);p[:,:2]-=final
    return p,{'normalization_offset_bits':vbits(initial),'dilation_factor_bits':bits(factor),
              'final_offset_bits':vbits(final),'rounding_clearance':2e-9}


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--baseline',type=Path,required=True)
    ap.add_argument('--artifacts',type=Path,default=Path('artifacts'))
    ap.add_argument('--output',type=Path,default=Path('artifacts/alternative-public-donors'))
    ap.add_argument('--limit',type=int,default=320)
    ap.add_argument('--max-side-gap',type=float,default=.15)
    ap.add_argument('--per-n-pool',type=int,default=5)
    args=ap.parse_args();started=time.monotonic()
    if args.output.exists():raise ValueError('Choose a fresh output directory; previous archives stay immutable')
    args.output.mkdir(parents=True)
    baseline=read_baseline(args.baseline);base_sides={n:side(p)for n,p in baseline.items()}
    references={n:pose_reference(p)for n,p in baseline.items()}
    known={n:{geometry_fingerprint([q for q,_ in orientations(p)])}for n,p in baseline.items()}
    fixtures=defaultdict(list)
    fixture_path=Path('artifacts/public/gadgets_39_and_baselines.npz')
    with np.load(fixture_path,allow_pickle=False)as z:
        for key in z.files:
            q=np.asarray(z[key])
            if q.ndim==2 and q.shape[1]==3:fixtures[len(q)].append(pose_reference(q))
    ledger=source_ledger(args.artifacts);pools=defaultdict(list);counts=Counter();source_stats={}
    for si,source in enumerate(ledger):
        local=Counter();path=Path(source['path'])
        df=pd.read_csv(path,usecols=['n','square_id','x','y','angle'],float_precision='round_trip')
        for n,g in df.groupby('n',sort=True):
            counts['groups']+=1;local['groups']+=1
            if not float(n).is_integer() or not 1<=int(n)<=1000:counts['bad_n']+=1;continue
            n=int(n);g=g.sort_values('square_id')
            if len(g)!=n or not np.array_equal(g.square_id.to_numpy(),np.arange(n)):
                counts['bad_ids_or_count']+=1;continue
            p=g[['x','y','angle']].to_numpy(dtype=float)
            if not np.isfinite(p).all():counts['nonfinite']+=1;continue
            length=side(p);gap=length-base_sides[n]
            if length<math.sqrt(n)-1e-8:counts['area_bogus']+=1;continue
            if gap>args.max_side_gap:counts['too_far_from_frontier']+=1;continue
            folded=(p[:,2]+math.pi/4)%(math.pi/2)-math.pi/4
            tilted=int(np.sum(np.abs(folded)>.003))
            if tilted<4:counts['grid_or_trivial']+=1;continue
            oriented=[q for q,_ in orientations(p)];fp=geometry_fingerprint(oriented)
            if fp in known[n]:counts['coarse_duplicate']+=1;continue
            same,novelty=compare(oriented,references[n])
            if same:counts['baseline_precision_duplicate']+=1;known[n].add(fp);continue
            if any(compare(oriented,ref)[0]for ref in fixtures.get(n,[])):
                counts['known_ftmc_fixture']+=1;known[n].add(fp);continue
            duplicate=None
            for j,old in enumerate(pools[n]):
                if compare(oriented,old['pose_reference'])[0]:duplicate=j;break
            if duplicate is not None:
                counts['alternative_precision_duplicate']+=1;known[n].add(fp);continue
            rank=novelty/(.025+max(0.,gap))*(1.4 if n>324 else 1.)
            entry={'source_id':source['id'],'source_n':n,'raw_pose':p,'raw_side':length,
                   'baseline_side':base_sides[n],'side_gap':gap,'tilted_squares':tilted,'novelty':novelty,
                   'ranking_score':rank,'fingerprint':fp,'pose_reference':pose_reference(p)}
            pool=pools[n];pool.append(entry);pool.sort(key=lambda r:-r['ranking_score'])
            if len(pool)>args.per_n_pool:pool.pop()
            known[n].add(fp);local['new_geometry']+=1;counts['new_geometry']+=1
        if digest(path)!=source['sha256']:raise ValueError('Source changed during inspection')
        source_stats[source['id']]=dict(local)
        print(json.dumps({'stage':'scan','sources':si+1,'total_sources':len(ledger),
            'geometry_candidates':sum(len(v)for v in pools.values()),'source':source['reference'],
            'seconds':time.monotonic()-started}),flush=True)
    first=sorted((pool[0]for pool in pools.values()if pool),key=lambda r:-r['ranking_score'])
    first=first[:min(len(first),int(args.limit*.75))]
    first_ids={(r['source_id'],r['source_n'])for r in first}
    rest=sorted((r for pool in pools.values()for r in pool
                 if (r['source_id'],r['source_n'])not in first_ids),key=lambda r:-r['ranking_score'])
    ordered=first+rest;chosen={};records={};invalid=[];per_n=Counter();per_source=Counter();validation={}
    for entry in ordered:
        n=entry['source_n'];sid=entry['source_id']
        if per_n[n]>=2 or per_source[sid]>=max(64,args.limit//4):continue
        q,recipe=legalize_recipe(entry['raw_pose'])
        if q is None:invalid.append({'source_id':sid,'n':n,'reason':'Material overlap; not a rounding-only repair'});continue
        if side(q)>base_sides[n]+args.max_side_gap+1e-6:continue
        rows=[Square(*(format(float(v),'.17g')for v in row))for row in q]
        cert=validate_puzzle(n,rows)
        if not cert['valid']:invalid.append({'source_id':sid,'n':n,'certificate':cert});continue
        key=f'alt_n{n}_s{sid}'
        if key in chosen:continue
        chosen[key]=q;validation[key]=cert;per_n[n]+=1;per_source[sid]+=1
        records[key]={k:v for k,v in entry.items()if k not in ['raw_pose','pose_reference']}
        records[key].update(recipe=recipe,array_sha256=array_sha(q),exported_side=side(q))
        if len(chosen)%25==0:print(json.dumps({'stage':'certify','accepted':len(chosen),
            'rejected':len(invalid),'seconds':time.monotonic()-started}),flush=True)
        if len(chosen)>=args.limit:break
    archive=args.output/'donors.npz';np.savez_compressed(archive,**chosen)
    canonical=hashlib.sha256()
    for key,p in sorted(chosen.items()):
        canonical.update(key.encode()+b'\0');canonical.update(str(len(p)).encode()+b'\0')
        canonical.update(bytes.fromhex(array_sha(p)))
    report={'baseline':str(args.baseline.resolve()),'baseline_sha256':digest(args.baseline),
        'archive_sha256':digest(archive),'canonical_pose_sha256':canonical.hexdigest(),
        'donors':len(chosen),'squares':sum(len(p)for p in chosen.values()),'valid':True,
        'source_files':ledger,'source_stats':source_stats,'selection_counts':dict(counts),
        'puzzle_counts':dict(per_n),'source_counts':dict(per_source),'max_side_gap':args.max_side_gap,
        'precision_duplicate_center_tolerance':2e-4,'precision_duplicate_angle_sine_tolerance':2e-5,
        'fixture_archive':str(fixture_path),'fixture_archive_sha256':digest(fixture_path),
        'known_ftmc_fixtures_excluded':True,'donor_records':records,'validation':validation,
        'rejected':invalid,'elapsed_seconds':time.monotonic()-started,
        'validator_sha256':digest(Path('scripts/validate_submission.py')),
        'meaning':'Alternative near-best public full-puzzle layouts for donor cropping. No leaderboard gain claim.'}
    (args.output/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    compact={k:v for k,v in report.items()if k not in ['source_files','source_stats','donor_records','validation','rejected']}
    (args.output/'summary.json').write_text(json.dumps(compact,indent=2)+'\n')
    print(json.dumps(compact),flush=True)

if __name__=='__main__':main()
