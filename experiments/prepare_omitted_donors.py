#!/usr/bin/env python3
"""Certify a diverse exact-omission shortlist and bound compatible partner types."""
import argparse
from collections import defaultdict
import json
import math
import os
from pathlib import Path
import time

for variable in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[variable]='1'
import numpy as np
from audit_donor_retention import digest,parse_type
from extract_broad_active_frontier import orient,geometry_sha
from fq_capacity_probe import full_certificate


def bucket(p,w,h):
    result=[]
    for transpose in ((False,True) if w==h else (w>h,)):
        for sx,sy in ((1,1),(-1,1),(1,-1),(-1,-1)):
            q=orient(p,transpose,sx,sy)
            q[:,2]=(q[:,2]+np.pi/4)%(np.pi/2)-np.pi/4
            q=np.round(q,6);q[q==0]=0.
            q=q[np.lexsort((q[:,2],q[:,1],q[:,0]))]
            result.append(geometry_sha(q))
    return min(result)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--inventory',type=Path,required=True)
    ap.add_argument('--portfolio-report',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--limit',type=int,default=160)
    args=ap.parse_args();started=time.monotonic()
    args.out.mkdir(parents=True,exist_ok=False)
    inv=json.loads((args.inventory/'report.json').read_text())
    assert digest(args.inventory/'omitted-promising-unvalidated.npz')==inv['shortlist_bank_sha256']
    assert digest(args.inventory/'current-typed-bank.npz')==inv['current_bank_sha256']
    entries=json.loads((args.inventory/'shortlist.json').read_text())
    all_missing=json.loads((args.inventory/'omitted-poses.json').read_text())
    current={};current_buckets=set();current_by_type=defaultdict(list)
    with np.load(args.inventory/'current-typed-bank.npz') as archive:
        for key in archive.files:
            p=archive[key];e=parse_type(key,p)
            if e is None:continue
            b=bucket(p,e['w'],e['h']);current_buckets.add((e['canonical_type'],b))
            current[key]=p;current_by_type[e['canonical_type']].append(dict(e,key=key,bucket=b))
    missing_arrays={}
    with np.load(args.inventory/'omitted-promising-unvalidated.npz') as archive:
        for key in archive.files:missing_arrays[key]=archive[key]
    for e in entries:
        e['bucket']=bucket(missing_arrays[e['array_key']],e['w'],e['h'])
        e['near_current_bucket']=(e['canonical_type'],e['bucket']) in current_buckets
    # Rounded buckets affect bounded sampling only; they never establish identity.
    chosen=[];seen=set();per_type=defaultdict(int)
    for e in entries:
        if not e['novel_canonical_type']:continue
        token=(e['canonical_type'],e['bucket'])
        if token in seen:continue
        seen.add(token);chosen.append(e);per_type[e['canonical_type']]+=1
    for e in entries:
        token=(e['canonical_type'],e['bucket'])
        if token in seen or e['near_current_bucket'] or per_type[e['canonical_type']]>=6:continue
        seen.add(token);chosen.append(e);per_type[e['canonical_type']]+=1
        if len(chosen)>=args.limit:break
    # Audit novel types even if no scalar two-block opportunity was found.
    novel_best={}
    for e in all_missing:
        if e['novel_canonical_type'] and (e['canonical_type'] not in novel_best or e['excess']<novel_best[e['canonical_type']]['excess']):
            novel_best[e['canonical_type']]=e
    for typ,e in novel_best.items():
        if any(c['canonical_type']==typ for c in chosen):continue
        source=e['source']
        assert digest(source['archive'])==source['archive_sha256']
        with np.load(source['archive']) as archive:p=archive[source['key']]
        key=f"{e['w']}_{e['h']}_{e['d']}__omitted_{e['geometry_sha256']}"
        missing_arrays[key]=p;e=dict(e,array_key=key,bucket=bucket(p,e['w'],e['h']),near_current_bucket=False)
        chosen.append(e)
    valid={};search={};checks=[]
    for index,e in enumerate(chosen):
        p=missing_arrays[e['array_key']]
        assert geometry_sha(p)==e['geometry_sha256']
        certificate=full_certificate(p)
        check=dict(e,certificate=certificate)
        if certificate['valid']:
            valid[e['array_key']]=p
            if e['pair_gain_upper_bound']>1e-9:search[e['array_key']]=p
        checks.append(check)
        if (index+1)%20==0:print(json.dumps(dict(stage='certify',checked=index+1,valid=len(valid),search=len(search))),flush=True)
    np.savez_compressed(args.out/'all-validated-missing.npz',**valid)
    np.savez_compressed(args.out/'search-missing.npz',**search)
    # Keep every current canonical type with a scalar opportunity, then sample
    # three distinct retained geometries per type for the bounded exact search.
    types=sorted(current_by_type)
    summaries=[]
    for typ in types:
        w,h,d=map(int,typ.split('_'));f=min(e['excess']for e in current_by_type[typ])
        summaries.extend([(w,h,d,f,typ),(h,w,d,f,typ)] if w!=h else [(w,h,d,f,typ)])
    pw=np.array([x[0]for x in summaries]);ph=np.array([x[1]for x in summaries]);pd=np.array([x[2]for x in summaries]);pf=np.array([x[3]for x in summaries])
    report=json.loads(args.portfolio_report.read_text());assert report['valid']
    sides=np.full(1065,np.inf)
    for row in report['results']:sides[row['n']]=float(row.get('side_upper',row.get('side')))
    useful=set()
    for check in checks:
        if check['array_key'] not in search:continue
        w,h,d=check['w'],check['h'],check['d'];f=check['excess'];good=np.zeros(len(summaries),dtype=bool)
        for aw,ah in ((w,h),(h,w)):
            for mode in (0,1,2):
                width=aw+pw+(mode==1);height=ah+ph+(mode==2);sd=d+pd;ex=np.maximum(f,pf)
                for k in range(max(aw,ah,2),32):
                    ns=k*k+sd;mask=(width<=k)&(height<=k)&(sd<=63)&(ns<=1000)
                    if mask.any():good[mask]|=(sides[ns[mask]]-(k+ex[mask]))/np.sqrt(ns[mask])>1e-9
        useful.update(summaries[i][4]for i in np.flatnonzero(good))
    partners={};partner_records=[]
    for typ in sorted(useful):
        seen_buckets=set()
        for e in sorted(current_by_type[typ],key=lambda e:e['excess']):
            if e['bucket'] in seen_buckets:continue
            seen_buckets.add(e['bucket']);partners[e['key']]=current[e['key']];partner_records.append(e)
            if len(seen_buckets)>=3:break
    np.savez_compressed(args.out/'retained-partners.npz',**partners)
    (args.out/'checks.json').write_text(json.dumps(checks,indent=2)+'\n')
    (args.out/'partner-records.json').write_text(json.dumps(partner_records,indent=2)+'\n')
    result=dict(elapsed_seconds=time.monotonic()-started,inventory_report_sha256=digest(args.inventory/'report.json'),
        portfolio_report_sha256=digest(args.portfolio_report),portfolio_sha256=report['sha256'],
        checked=len(checks),valid=len(valid),rejected=len(checks)-len(valid),search_missing=len(search),
        strict_novel_types=sorted({c['canonical_type']for c in checks if c['novel_canonical_type']and c['certificate']['valid']}),
        retained_partner_types=len(useful),retained_partner_poses=len(partners),
        all_validated_sha256=digest(args.out/'all-validated-missing.npz'),search_missing_sha256=digest(args.out/'search-missing.npz'),
        retained_partners_sha256=digest(args.out/'retained-partners.npz'),checks_sha256=digest(args.out/'checks.json'),
        selection='All promising novel types, then up to six 1e-6-rounded geometric buckets per type, preferring buckets absent from current inputs. '
                  'Rounded buckets are a sampling heuristic, not an identity claim. All exact omissions remain in the inventory.',
        partner_sampling='At most three distinct current buckets per scalar-feasible canonical type; exact pair coverage is bounded to this selected set.',
        no_submission=True)
    (args.out/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    (args.out/'source.py').write_bytes(Path(__file__).read_bytes())
    print(json.dumps(result),flush=True)


if __name__=='__main__':main()
