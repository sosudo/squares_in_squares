"""Measure new8x20 donor interfaces before authorizing any composition search.

The narrow target is the saved mode2 n865 chain with its one-row buffer
removed, which would yield n808. This program makes no geometry admission.
"""
import time
STARTED=time.monotonic()
import argparse
import hashlib
import json
import os
from pathlib import Path
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
import numpy as np
from compose_gadgets import extents,normalize
from extract_broad_active_frontier import profiles,orient
from pinwheel_interlock import cross_gap


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--old',type=Path,required=True);ap.add_argument('--new',type=Path,required=True)
    ap.add_argument('--portfolio',type=Path,required=True);ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--max-bloat',type=float,help='Optional broader family cost limit; each later pair must still beat its own incumbent')
    args=ap.parse_args();args.out.mkdir(parents=True,exist_ok=False)
    ptr=json.loads(args.portfolio.read_text());official=Path(ptr['safe']['official_report'])
    assert sha(official)==ptr['safe']['official_report_sha256']
    rr=json.loads(official.read_text());assert rr['sha256']==ptr['safe']['sha256']
    target=next(float(r['side'])for r in rr['results']if r['n']==808);target_limit=target-28-1e-7
    limit=target_limit if args.max_bloat is None else args.max_bloat
    if not 0<limit<=1:raise ValueError('Only positive-surplus subunit-bloat family states are in scope')
    entries={'old':[],'new':[]};poses={};counts={};complete=True
    for role,path in [('old',args.old),('new',args.new)]:
        seen=0;eligible=0
        with np.load(path,allow_pickle=False)as bank:
            for name in bank.files:
                if time.monotonic()-STARTED>75:complete=False;break
                w0,h0,d=map(int,name.split('__')[0].split('_'));p=bank[name]
                if sorted([w0,h0])!=[8,20]or d!=12:raise ValueError('Unexpected donor family')
                seen+=1
                for swap in (False,True):
                    w,h=(h0,w0)if swap else(w0,h0)
                    for sx,sy in ((1,1),(-1,1),(1,-1),(-1,-1)):
                        q=orient(p,swap,sx,sy);lo,hi=extents(q)
                        f=float(max(hi.max(0)-lo.min(0)-[w,h]))
                        if f>=limit:continue
                        eligible+=1;pr=[profiles(q,w,h,a,a,32)for a in(30,45,60)]
                        key=f'{role}:{name}:{swap}:{sx}:{sy}'
                        row=dict(key=key,source_key=name,w=w,h=h,f=f,transform=[swap,sx,sy],
                            geometry_sha256=hashlib.sha256(np.asarray(q,dtype='<f8').tobytes()).hexdigest(),
                            br=[p['br_bin']for p in pr],tl=[p['tl_bin']for p in pr],
                            br_support=[p['outgoing_br_support']for p in pr],
                            tl_support=[p['incoming_tl_support']for p in pr])
                        entries[role].append(row);poses[key]=q
            counts[role]={'input_arrays':len(bank.files),'processed_arrays':seen,'eligible_orientations':eligible}
    result={}
    for role,rows in entries.items():
        previous=[r for r in rows if r['w']==20];current=[r for r in rows if r['w']==8]
        signature=lambda r:(r['w'],r['h'],tuple(r['br']),tuple(r['tl']))
        old_signatures={signature(r)for r in entries['old']}
        diagnostics=[];proposals={}
        for ai,a in enumerate((30,45,60)):
            best_br=min(previous,key=lambda r:r['br_support'][ai]);best_tl=max(current,key=lambda r:r['tl_support'][ai])
            q=poses[best_tl['key']].copy();q[:,:2]+=[20,-20]
            gap=cross_gap(poses[best_br['key']],q)
            item={'degrees':a,'minimum_previous_br':best_br['br'][ai],'maximum_next_tl':best_tl['tl'][ai],
                  'minimum_previous_br_support':best_br['br_support'][ai],
                  'maximum_next_tl_support':best_tl['tl_support'][ai],
                  'profile_gap':best_tl['tl_support'][ai]-best_br['br_support'][ai],
                  'extremal_pair_exact_sat_gap':gap,'previous':best_br['key'],'next':best_tl['key']}
            diagnostics.append(item)
            if item['profile_gap']>=0 and max(best_br['f'],best_tl['f'])<target_limit:
                proposals[str(a)]=[best_br['key'],best_tl['key']]
        # Fixed mirrors of the actual lowest-bloat sources provide the baseline
        # collision measurement, independently of any profile quantization.
        a=min(previous,key=lambda r:r['f']);b=min(current,key=lambda r:r['f'])
        q=poses[b['key']].copy();q[:,:2]+=[20,-20]
        result[role]={'profile_signatures':len({signature(r)for r in rows}),
            'new_signatures_over_old':len({signature(r)for r in rows}-old_signatures),
            'minimum_bloat':min(r['f']for r in rows),'lowest_bloat_pair_sat_gap':cross_gap(poses[a['key']],q),
            'profile_angles':diagnostics,'candidate_profile_pairs':proposals}
    report={'status':'complete'if complete else'bounded_partial','seconds':time.monotonic()-STARTED,
        'source_sha256':sha(__file__),'inputs':{'old':{'path':str(args.old),'sha256':sha(args.old)},
        'new':{'path':str(args.new),'sha256':sha(args.new)}},'portfolio':ptr['safe'],
        'target':{'n':808,'baseline_side':target,'maximum_admissible_component_bloat':target_limit,
                  'recipe':'20x8+12 followed by8x20+12,mode0;28²+24=808',
                  'original_buffered_case':865,'full_geometry_certificate_required':True},
        'profile_cost_limit':limit,'coverage':counts,'results':result,'fresh_geometry_certification':False,'search_launched':False,
        'scope':'Whole-donor corner profiles at30/45/60deg only, all finite D4s below the explicitly reported profile cost limit. Each complete pair must separately beat its own incumbent. No crop or arbitrary-separator exhaustiveness claim.'}
    (args.out/'profile_records.json').write_text(json.dumps(entries,indent=2)+'\n')
    report['profile_records_sha256']=sha(args.out/'profile_records.json')
    (args.out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items()if k not in('portfolio','inputs')},indent=2))


if __name__=='__main__':main()
