"""Delete one square from a larger packing and compact the surviving geometry.

Read-only input is a full submission CSV. LP screening prioritizes deletions
whose local deformation could beat the incumbent for n-1. Every output remains
subject to independent official-metric validation before submission.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import time
import numpy as np
import pandas as pd
from packing_search import normalize, side, vertices, linear_step, compact


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--base',default='artifacts/baseline.csv')
    ap.add_argument('--out',default='artifacts/candidates/transfer.json')
    ap.add_argument('--min-n',type=int,default=100)
    ap.add_argument('--max-n',type=int,default=500)
    ap.add_argument('--max-deletions',type=int,default=24)
    ap.add_argument('--seconds',type=float,default=20)
    a=ap.parse_args()
    df=pd.read_csv(a.base)
    packings={int(n):normalize(g.sort_values('square_id')[['x','y','angle']].to_numpy(float)) for n,g in df.groupby('n')}
    sides={n:side(p) for n,p in packings.items()}
    out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True)
    saved=json.loads(out.read_text()) if out.exists() else {}
    rng=np.random.default_rng(20261024)
    tasks=[]
    for n in range(a.min_n,a.max_n+1):
        if n+1 not in packings: continue
        target=sides[n]
        if target>=np.ceil(np.sqrt(n))-1e-6: continue
        gap=sides[n+1]-target
        if gap>0.13 or gap<1e-7:continue
        tasks.append((gap,n))
    for gap,n in sorted(tasks):
        p=packings[n+1]
        v=vertices(p)+p[:,None,:2]
        target=min(sides[n],saved.get(str(n),{}).get('side',float('inf')))
        # Include every extreme square and a diverse sample of tilted and other squares.
        extremes=set()
        for dim in range(2):
            extremes.add(int(np.argmin(v[:,:,dim].min(1))))
            extremes.add(int(np.argmax(v[:,:,dim].max(1))))
        angle=np.abs((p[:,2]+np.pi/4)%(np.pi/2)-np.pi/4)
        selected=list(extremes)
        selected+=list(rng.choice(np.flatnonzero(angle>1e-4),size=min(a.max_deletions//2,int(np.sum(angle>1e-4))),replace=False))
        selected+=list(rng.choice(len(p),size=min(a.max_deletions,len(p)),replace=False))
        selected=list(dict.fromkeys(int(k) for k in selected))[:a.max_deletions]
        screened=0; start=time.monotonic()
        for k in selected:
            q=normalize(np.delete(p,k,axis=0))
            step,pred=linear_step(q,.2,.07)
            if step is None or side(q)+pred>target-1e-7:continue
            screened+=1
            q,info=compact(q,a.seconds,seed=10000*n+k)
            if info['side']<target-1e-8 and info['min_gap']>0:
                target=info['side']
                info.update({'source_n':n+1,'deleted_square':k,'previous_best':sides[n]})
                saved[str(n)]={'side':target,'squares':q.tolist(),'search':info}
                tmp=out.with_suffix('.tmp');tmp.write_text(json.dumps(saved));tmp.replace(out)
                print('IMPROVEMENT '+json.dumps({'n':n,**info}),flush=True)
        print(json.dumps({'n':n,'donor_gap':gap,'screened':screened,'tested':len(selected),'seconds':time.monotonic()-start,'best':target}),flush=True)


if __name__=='__main__':main()
