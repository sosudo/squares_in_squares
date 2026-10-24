#!/usr/bin/env python3
"""Check retained matching-type alternatives to one fixed winning pair recipe."""
import argparse
import json
import math
import os
from pathlib import Path
import time

for variable in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[variable]='1'
import numpy as np
from audit_donor_retention import digest,parse_type
from compose_gadgets import extents
from extract_broad_active_frontier import orient,geometry_sha
from cpu_recipe_replay import public_functions,cross_block_separated
from exact_pair_composition import build_pair
from fq_capacity_probe import full_certificate

ROOT=Path(__file__).resolve().parents[1]


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--pair-run',type=Path,required=True)
    ap.add_argument('--retained-bank',type=Path,required=True)
    ap.add_argument('--n',type=int,required=True)
    ap.add_argument('--out',type=Path,required=True)
    args=ap.parse_args();start=time.monotonic();args.out.mkdir(parents=True,exist_ok=False)
    candidate=json.loads((args.pair_run/'candidates.json').read_text())[str(args.n)]
    recipe=candidate['provenance']['pair'];threshold=float(candidate['side'])-recipe['k']
    first,second=recipe['first'],recipe['second']
    pools=[[],[]];matching=[0,0];admitted_keys=set()
    with np.load(args.retained_bank,allow_pickle=False) as z:
        for key in z.files:
            p=z[key];parsed=parse_type(key,p)
            if parsed is None:continue
            for index,target in enumerate((first,second)):
                if parsed['canonical_type']!=f"{min(target['w'],target['h'])}_{max(target['w'],target['h'])}_{target['d']}":continue
                matching[index]+=1
                trans=parsed['w']!=target['w']
                for sx,sy in ((1,1),(-1,1),(1,-1),(-1,-1)):
                    q=orient(p,trans,sx,sy);_,hi=extents(q)
                    f=float(max(hi.max(0)-[target['w'],target['h']]))
                    padded=math.ceil((f+3e-8)*1e9)*1e-9
                    if padded>threshold+1e-10:continue
                    admitted_keys.add(key)
                    pools[index].append(dict(w=target['w'],h=target['h'],d=target['d'],f=padded,pose=q,
                        key=key,reflection=[sx,sy],transpose=trans,actual_bloat=f,geometry_sha256=geometry_sha(q)))
    stitch,_=public_functions(ROOT/'vendor/lightning_ftmc')
    tests=0;passed=[]
    for a in pools[0]:
        for b in pools[1]:
            tests+=1
            if not cross_block_separated(a['pose'],b['pose'],a['w'],b['h'],recipe['mode']):continue
            q=build_pair(a,b,recipe['mode'],recipe['k'],stitch)
            certificate=full_certificate(q) if q is not None else {'valid':False}
            passed.append(dict(first={k:v for k,v in a.items() if k!='pose'},
                second={k:v for k,v in b.items() if k!='pose'},certificate=certificate))
    ties=[p for p in passed if p['certificate']['valid'] and
          float(p['certificate']['independent_raw']['side_upper'])<=float(candidate['side'])+1e-10]
    result=dict(n=args.n,elapsed_seconds=time.monotonic()-start,mode=recipe['mode'],k=recipe['k'],
        winning_side=candidate['side'],matching_retained_pose_counts=matching,
        retained_source_poses_with_scalar_room=len(admitted_keys),retained_source_keys=sorted(admitted_keys),
        oriented_pool_sizes=list(map(len,pools)),pair_tests=tests,sat_passes=len(passed),
        certified_ties_or_improvements=len(ties),results=passed,
        retained_bank_sha256=digest(args.retained_bank),pair_candidates_sha256=digest(args.pair_run/'candidates.json'),
        source_sha256=digest(__file__),
        scope='All retained matching-type poses with enough scalar room, both role orientations and four reflections each, '
              'holding the successful pair mode and square container fixed. This is not a proof about other composition templates.',
        no_submission=True)
    (args.out/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    (args.out/'source.py').write_bytes(Path(__file__).read_bytes())
    print(json.dumps({k:v for k,v in result.items() if k!='results'}))


if __name__=='__main__':main()
