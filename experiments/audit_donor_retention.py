#!/usr/bin/env python3
"""Inventory exact historical poses omitted from pinned composition inputs.

No geometric validity is inferred from an archive name. Selected omissions
still require independent certification before their use in pair searches.
"""
import argparse
from collections import defaultdict
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import time

for variable in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[variable] = '1'
import numpy as np
from compose_gadgets import extents, read_baseline
from extract_broad_active_frontier import orient, geometry_sha


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def preferred_path(paths):
    def rank(s):
        p=Path(s)
        return ('/inputs/' in s, '/snapshot-' in s, '/source/' in s,
                not any(t in s for t in ('all-strict','complete/','final','donors','variants','gadgets')),len(s),s)
    return min(paths,key=rank)


def canonical_hash(p):
    hashes=[]
    for trans in (False,True):
        for sx,sy in ((1,1),(-1,1),(1,-1),(-1,-1)):
            q=orient(p,trans,sx,sy)
            q[:,2]=(q[:,2]+np.pi/4)%(np.pi/2)-np.pi/4
            q[q==0]=0.
            q=q[np.lexsort((q[:,2],q[:,1],q[:,0]))]
            hashes.append(geometry_sha(q))
    return min(hashes)


def parse_type(key,p):
    match=re.match(r'^(\d+)_(\d+)_(-?\d+)(?:__|$)',key)
    lo,hi=extents(p);span=hi.max(0)-lo.min(0)
    explicit=False
    if match:
        w,h,d=map(int,match.groups());explicit=True
        if w*h+d != len(p):return None
    else:
        w,h=np.floor(span+1e-9).astype(int);d=len(p)-int(w*h)
    if not (0<w<=31 and 0<h<=31 and 0<d<=63 and len(p)<=1000):return None
    f=float(max(span-[w,h]))
    if not 0<f<1:return None
    return dict(w=int(w),h=int(h),d=int(d),canonical_type=f'{min(w,h)}_{max(w,h)}_{d}',
                excess=f,explicit_type=explicit)


def include_baseline(baseline,path,geometries,types,covered_raw,covered_canonical):
    """Include both geometry and type coverage of the attached complete CSV.

    A baseline-only pose must also be available in the retained partner bank.
    Archive-only type enumeration otherwise mislabels complete square types
    as missing even though their geometries are already attached.
    """
    sha=digest(path)
    for n,p in baseline.items():
        g=geometry_sha(p);canonical=canonical_hash(p)
        covered_raw.add(g);covered_canonical.add(canonical)
        if g not in geometries:
            geometries[g]=dict(p=p,canonical_sha256=canonical,n=len(p),
                source_archive_sha256=sha,source_archive=str(path),source_key=f'puzzle_{n}')
        parsed=parse_type(f'puzzle_{n}',p)
        if parsed is None:continue
        token=(g,parsed['canonical_type'])
        if token not in types:
            types[token]=dict(**parsed,geometry_sha256=g,canonical_sha256=canonical,
                source=dict(archive_sha256=sha,archive=str(path),key=f'puzzle_{n}',format='csv'),
                origin_archives=set())


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--catalogue',type=Path,required=True)
    ap.add_argument('--descriptor',type=Path,required=True)
    ap.add_argument('--gpu-baseline',type=Path,required=True)
    ap.add_argument('--portfolio-report',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True)
    args=ap.parse_args();started=time.monotonic()
    args.out.mkdir(parents=True,exist_ok=False)
    catalogue=json.loads(args.catalogue.read_text());descriptor=json.loads(args.descriptor.read_text())
    archives={x['sha256']:x for x in catalogue['archives']}
    current={name:item['sha256'] for name,item in descriptor['gadgets'].items()}
    for name,sha in current.items():
        if sha not in archives:
            item=descriptor['gadgets'][name];p=Path(item.get('local_path',''))
            if not p.is_file() or digest(p)!=sha:raise ValueError(f'Missing current archive {name}:{sha}')
            archives[sha]=dict(sha256=sha,bytes=p.stat().st_size,paths=[str(p)])
    current_shas=set(current.values())
    geometries={};members=defaultdict(set);types={};archive_stats={};errors=[]
    ordered=sorted(archives,key=lambda sha:sha not in current_shas)
    for index,sha in enumerate(ordered):
        info=archives[sha];path=preferred_path(info['paths']);pose_count=0
        try:
            with np.load(path,allow_pickle=False) as z:
                for key in z.files:
                    p=z[key]
                    if p.ndim!=2 or p.shape[1]!=3 or len(p)<2 or not np.issubdtype(p.dtype,np.number):continue
                    p=np.asarray(p,dtype=float)
                    if not np.isfinite(p).all():continue
                    pose_count+=1;g=geometry_sha(p);members[sha].add(g)
                    if g not in geometries:
                        geometries[g]=dict(p=p,canonical_sha256=canonical_hash(p),n=len(p),
                            source_archive_sha256=sha,source_archive=path,source_key=key)
                    item=geometries[g]
                    parsed=parse_type(key,p)
                    if parsed:
                        token=(g,parsed['canonical_type'])
                        origin=dict(archive_sha256=sha,archive=path,key=key)
                        if token not in types:
                            types[token]=dict(**parsed,geometry_sha256=g,canonical_sha256=item['canonical_sha256'],
                                source=origin,origin_archives=set())
                        entry=types[token];entry['origin_archives'].add(sha)
                        if parsed['explicit_type'] and not entry['explicit_type']:
                            entry.update(parsed,source=origin)
        except Exception as exc:
            errors.append(dict(path=path,error=repr(exc)))
        archive_stats[sha]=dict(paths=info['paths'],representative_path=path,pose_arrays=pose_count,
                                unique_geometries=len(members[sha]))
        if (index+1)%250==0:print(json.dumps(dict(stage='inventory',archives=index+1,geometries=len(geometries))),flush=True)
    covered_raw=set().union(*(members[s] for s in current_shas))
    covered_canonical={geometries[g]['canonical_sha256'] for g in covered_raw}
    baseline=read_baseline(args.gpu_baseline)
    include_baseline(baseline,args.gpu_baseline,geometries,types,covered_raw,covered_canonical)
    current_types=set();current_entries=[];missing=[]
    for entry in types.values():
        represented=(entry['geometry_sha256'] in covered_raw or entry['canonical_sha256'] in covered_canonical)
        entry['represented']=represented
        if represented:
            current_types.add(entry['canonical_type']);current_entries.append(entry)
        else:missing.append(entry)
    # Scalar minima are used only to bound possible pair gains, never as pose identities.
    type_min={}
    for entry in types.values():
        t=entry['canonical_type']
        if t not in type_min or entry['excess']<type_min[t]['excess']:type_min[t]=entry
    partner=[]
    for e in type_min.values():
        w,h,d=map(int,e['canonical_type'].split('_'))
        partner.extend([(w,h,d,e['excess']),(h,w,d,e['excess'])] if w!=h else [(w,h,d,e['excess'])])
    pa=np.array(partner);pw,ph,pd,pf=pa.T;pd=pd.astype(int)
    report=json.loads(args.portfolio_report.read_text());assert report['valid']
    sides=np.full(1065,np.inf)
    for r in report['results']:sides[r['n']]=float(r.get('side_upper',r.get('side')))
    cache={}
    def potential(e):
        w,h,d=map(int,e['canonical_type'].split('_'));f=math.floor(e['excess']*1e7)/1e7
        token=(w,h,d,f)
        if token in cache:return cache[token]
        answer=0.;target=None
        for aw,ah in ((w,h),(h,w)):
            for mode in (0,1,2):
                width=aw+pw+(mode==1);height=ah+ph+(mode==2);surplus=d+pd;excess=np.maximum(f,pf)
                eligible=(width<=31)&(height<=31)&(surplus<=63)
                if not eligible.any():continue
                for k in range(max(aw,ah,2),32):
                    ns=k*k+surplus
                    mask=eligible&(width<=k)&(height<=k)&(ns<=1000)
                    if not mask.any():continue
                    chosen=ns[mask];gain=(sides[chosen]-(k+excess[mask]))/np.sqrt(chosen)
                    loc=int(np.argmax(gain))
                    if gain[loc]>answer:answer=float(gain[loc]);target=int(chosen[loc])
        cache[token]=(answer,target);return cache[token]
    for entry in missing:
        entry['novel_canonical_type']=entry['canonical_type'] not in current_types
        entry['pair_gain_upper_bound'],entry['pair_target']=potential(entry)
    missing.sort(key=lambda e:(-e['pair_gain_upper_bound'],-e['novel_canonical_type'],e['canonical_type'],e['geometry_sha256']))
    bank_rank=[]
    for sha,stats in archive_stats.items():
        omitted=[e for e in missing if sha in e['origin_archives']]
        if not omitted:continue
        bank_rank.append(dict(archive_sha256=sha,**stats,omitted_geometry_types=len(omitted),
            novel_types=sorted({e['canonical_type'] for e in omitted if e['novel_canonical_type']}),
            promising=len([e for e in omitted if e['pair_gain_upper_bound']>1e-9]),
            maximum_pair_gain_bound=max(e['pair_gain_upper_bound'] for e in omitted)))
    bank_rank.sort(key=lambda e:(-e['maximum_pair_gain_bound'],-len(e['novel_types']),-e['promising']))
    # Preserve source notices exactly; no relicensing or scalar-only deduplication.
    notices=args.out/'source-notices';notices.mkdir()
    notice_hashes={}
    for name,text in descriptor.get('source_notices',{}).items():
        destination=notices/name;destination.parent.mkdir(parents=True,exist_ok=True);destination.write_text(text)
        notice_hashes[name]=digest(destination)
    (args.out/'current-descriptor.json').write_bytes(args.descriptor.read_bytes())
    (args.out/'source.py').write_bytes(Path(__file__).read_bytes())
    current_bank={};seen=set()
    for e in current_entries:
        token=(e['canonical_sha256'],e['canonical_type'])
        if token in seen:continue
        seen.add(token);p=geometries[e['geometry_sha256']]['p'];key=f"{e['w']}_{e['h']}_{e['d']}__retained_{e['geometry_sha256']}"
        current_bank[key]=p
    np.savez_compressed(args.out/'current-typed-bank.npz',**current_bank)
    shortlist={};shortlist_records=[];seen=set()
    for e in missing:
        if e['pair_gain_upper_bound']<=1e-9:continue
        token=(e['canonical_sha256'],e['canonical_type'])
        if token in seen:continue
        seen.add(token);p=geometries[e['geometry_sha256']]['p']
        key=f"{e['w']}_{e['h']}_{e['d']}__omitted_{e['geometry_sha256']}"
        shortlist[key]=p;shortlist_records.append(dict(e,array_key=key,origin_archives=sorted(e['origin_archives'])))
    np.savez_compressed(args.out/'omitted-promising-unvalidated.npz',**shortlist)
    serial=[dict(e,origin_archives=sorted(e['origin_archives'])) for e in missing]
    (args.out/'omitted-poses.json').write_text(json.dumps(serial,indent=2)+'\n')
    (args.out/'shortlist.json').write_text(json.dumps(shortlist_records,indent=2)+'\n')
    result=dict(elapsed_seconds=time.monotonic()-started,catalogue_sha256=digest(args.catalogue),
        descriptor_sha256=digest(args.descriptor),portfolio_report_sha256=digest(args.portfolio_report),
        portfolio_sha256=report['sha256'],gpu_baseline_sha256=digest(args.gpu_baseline),
        historical_archive_paths=catalogue['total_paths'],unique_archives=len(archives),unique_pose_arrays=len(geometries),
        current_attachment_names=current,current_exact_geometries=len(covered_raw),current_canonical_types=len(current_types),
        omitted_geometry_type_combinations=len(missing),novel_types=sorted({e['canonical_type'] for e in missing if e['novel_canonical_type']}),
        promising_omissions=len(shortlist),source_notice_hashes=notice_hashes,archive_errors=errors,
        current_bank_sha256=digest(args.out/'current-typed-bank.npz'),shortlist_bank_sha256=digest(args.out/'omitted-promising-unvalidated.npz'),
        omitted_poses_sha256=digest(args.out/'omitted-poses.json'),shortlist_sha256=digest(args.out/'shortlist.json'),
        bank_rankings=bank_rank,identity_method='Exact binary64 array hash, plus exact hashes of sorted translated D4 transforms. '
            'No rounding or scalar-excess equality is used for identity; floating transform discrepancies may conservatively retain redundant poses.',
        validity_note='Shape/count/excess checks only in this inventory. Omitted poses are NOT certified here; full gates required before search use.',
        ranking_note='Scalar pair gains are optimistic ranking bounds only; they do not prove nonoverlap or a score improvement.')
    (args.out/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('source_notice_hashes','bank_rankings','archive_errors','current_attachment_names')}),flush=True)


if __name__=='__main__':main()
