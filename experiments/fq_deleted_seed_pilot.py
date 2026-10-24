"""Explore every one-square deletion of a distinct neighboring packing.

This finite one-worker pilot can cross a topology that same-seed kicks miss.
It retains all certified alternative poses and separates them from actual
improvements against the target's frozen official side. --seconds is a
scheduling deadline; run this pilot under an external whole-process timeout.
"""
import argparse
import json
import math
from pathlib import Path
import shutil
import sys
import time
import numpy as np
import pandas as pd
import fq_active_pilot as fq
from fq_capacity_probe import full_certificate
from fq_variant_campaign import atomic_json, atomic_npz, geometry_sha


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline',type=Path,required=True)
    parser.add_argument('--report',type=Path,required=True)
    parser.add_argument('--source-n',type=int,required=True)
    parser.add_argument('--binary',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--seconds',type=float,default=190)
    args=parser.parse_args()
    assert 3<=args.source_n<=150 and 20<=args.seconds<=240
    start=time.monotonic(); deadline=start+args.seconds-5
    report=json.loads(args.report.read_text())
    assert (report['valid'] and report['sha256']==fq.digest(args.baseline)
            and report['metric_sha256']==fq.OFFICIAL_SHA256
            and report['puzzles']==1000 and report['invalid_count']==0)
    n=args.source_n-1; w=math.isqrt(n); key=f'{w}_{w}_{n-w*w}'
    reference=next(x for x in report['results'] if x['n']==n)
    target_side=float(reference['side'])
    frame=pd.read_csv(args.baseline,float_precision='round_trip')
    source=frame[frame.n==args.source_n].sort_values('square_id')[['x','y','angle']].to_numpy(float)
    proof=full_certificate(source); assert proof['valid']
    args.out.mkdir(exist_ok=False); (args.out/'trials').mkdir();(args.out/'source').mkdir()
    binary=(args.out/'fq').resolve();shutil.copy2(args.binary,binary);binary.chmod(0o500)
    assert fq.digest(binary)==fq.digest(args.binary)
    paths=[Path(__file__),Path(fq.__file__),Path(__file__).parent/'fq_capacity_probe.py']
    for p in paths:shutil.copy2(p,args.out/'source'/p.name)
    atomic_npz(args.out/'source-pose.npz',{str(args.source_n):source})
    atomic_json(args.out/'manifest.json',{'baseline':str(args.baseline),'baseline_sha256':fq.digest(args.baseline),
        'report_sha256':fq.digest(args.report),'source_n':args.source_n,'target_n':n,'target_side':target_side,
        'source_certificate':proof,'binary_sha256':fq.digest(binary),'seconds':args.seconds,'workers':1,
        'source_hashes':{str(p):fq.digest(p) for p in paths},'methods':['polish-all-deletions','kick-best-distinct-deletions']})
    records=[];donors={};candidates={};starts=[]
    # Deterministic, spatially spread order; every square is visited at most once.
    order=list(range(len(source))); order.sort(key=lambda i:((i*37)%len(source),i))
    jobs=[(i,'polish',np.delete(source,i,axis=0)) for i in order]
    idx=0
    summary={'elapsed_seconds':time.monotonic()-start,'trials':0,'certified_variants':0,
             'improved_cases':0,'minimum_candidate_side':None,'reference_side':target_side}
    atomic_npz(args.out/'donors.npz',donors)
    atomic_json(args.out/'candidates.json',candidates)
    atomic_json(args.out/'results.json',records)
    while jobs and time.monotonic()<deadline-2:
        removed,mode,p=jobs.pop(0);seed=660100+idx;idx+=1
        try:
            r,donor=fq.trial((key,p,mode,str(binary),str((args.out/'trials').resolve()),seed,8.,deadline))
        except Exception as exc:
            r={'key':key,'mode':mode,'seed':seed,'status':'worker-error','error_type':type(exc).__name__}
            donor=None
        r.update(removed_original_index=removed,source_n=args.source_n,source_geometry_sha256=geometry_sha(p))
        if donor is not None:
            name,q=donor;donors[name]=q
            after=w+fq.bloat(q,w,w);r['target_side_gain']=target_side-after
            if mode=='polish':starts.append((after,removed,q))
            if after<target_side-1e-8:
                cert=full_certificate(q)
                if cert['valid'] and float(cert['independent_raw']['side_upper'])<target_side-1e-8:
                    length=cert['independent_raw']['side_upper']
                    if str(n) not in candidates or float(length)<float(candidates[str(n)]['side']):
                        candidates[str(n)]={'side':length,'squares':[[f'{v:.17g}' for v in row] for row in q],
                            'certificate':cert,'source':'Neighbor-packing deletion and FQ repair',
                            'provenance':{'source_n':args.source_n,'removed_original_index':removed,'seed':seed}}
        records.append(r)
        atomic_json(args.out/'results.json',records);atomic_npz(args.out/'donors.npz',donors)
        atomic_json(args.out/'candidates.json',candidates)
        summary={'elapsed_seconds':time.monotonic()-start,'trials':len(records),'certified_variants':len(donors),
                 'improved_cases':len(candidates),'minimum_candidate_side':min([x[0] for x in starts],default=None),
                 'reference_side':target_side,'candidates_sha256':fq.digest(args.out/'candidates.json')}
        atomic_json(args.out/'summary.json',summary)
        print(json.dumps({k:r[k] for k in ['mode','removed_original_index','status','after','target_side_gain'] if k in r}),flush=True)
        if not jobs and mode=='polish':
            jobs=[(i,'kick',q) for _,i,q in sorted(starts,key=lambda x:x[0])[:16]]
    summary.update(complete_deletion_pass=sum(r['mode']=='polish' for r in records)==len(source),
                   elapsed_seconds=time.monotonic()-start,
                   stopped_for_budget=bool(jobs),donors_sha256=fq.digest(args.out/'donors.npz'))
    atomic_json(args.out/'summary.json',summary);print(json.dumps(summary),flush=True)


if __name__=='__main__':main()
