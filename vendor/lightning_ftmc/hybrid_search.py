"""Combine credited portfolios, CUDA families, and independently measured crops."""
import csv,json,math,time
from pathlib import Path
from collections import defaultdict
import numpy as np
from solver import grid,side,normalize
from packing_pipeline import border_expand,trim_order
from gpu_families import construct

def read_csv(path):
    groups=defaultdict(list)
    with Path(path).open(newline='') as f:
        for row in csv.DictReader(f):groups[int(row['n'])].append([float(row[k]) for k in ['x','y','angle']])
    return {n:np.asarray(p) for n,p in groups.items()}

def export(path,bank,margin=4e-7):
    with Path(path).open('w',newline='') as f:
        w=csv.writer(f);w.writerow(['id','n','square_id','x','y','angle']);idx=0
        for n,p in sorted(bank.items()):
            p=normalize(p,margin)
            if side(p)>=math.ceil(math.sqrt(n))-1e-8:continue
            for j,(x,y,a) in enumerate(p):
                w.writerow([idx,n,j,format(x,'.17g'),format(y,'.17g'),format(a,'.17g')]);idx+=1

def solve(include_gpu=True,transfer=True,include_recent=True):
    start=time.perf_counter();bank={n:grid(n) for n in range(1,1001)};lengths=np.ceil(np.sqrt(np.arange(1,1001)))
    labels={n:'grid' for n in bank};ablation=[]
    def checkpoint(stage):
        row=dict(stage=stage,score=float(np.sum(lengths/np.sqrt(np.arange(1,1001))-1)))
        ablation.append(row);print(json.dumps(row),flush=True)
    def offer(p,label,crops=False):
        if not crops:
            n=len(p)
            if n<=1000 and side(p)<lengths[n-1]-1e-8:
                bank[n]=p.copy();lengths[n-1]=side(p);labels[n]=label
            return
        for dx in (-.5,0,.5):
            for dy in (-.5,0,.5):
                q=p[trim_order(p,(dx,dy))];h=(np.abs(np.cos(q[:,2]))+np.abs(np.sin(q[:,2])))/2
                lo=np.minimum.accumulate(q[:,:2]-h[:,None],axis=0);hi=np.maximum.accumulate(q[:,:2]+h[:,None],axis=0)
                ll=np.max(hi-lo,axis=1)[:1000]
                for j in np.flatnonzero(ll<lengths[:len(ll)]-1e-8):
                    n=int(j+1);bank[n]=q[:n].copy();lengths[j]=ll[j];labels[n]=label
    avazaku=read_csv('artifacts/avazaku-v1/submission.csv')
    for p in avazaku.values():offer(p,'avazaku v1')
    checkpoint('Squarecraft v1')
    own=read_csv('artifacts/submission.csv')
    for p in own.values():offer(p,'our v1')
    checkpoint('Best of both portfolios')
    candidates=[(p,'avazaku transferred') for p in avazaku.values()]+[(p,'our v1 transferred') for p in own.values()]
    if include_recent:
        references=json.loads(Path('artifacts/recent_references.json').read_text())
        for rec in references:
            p=np.array(rec['packing'],dtype=float)
            label=f"recent {rec['source']['group']} n={rec['N']}"
            offer(p,label)
            if side(p)<math.ceil(math.sqrt(len(p)))-1e-7:candidates.append((p,label))
        checkpoint('Recent credited numerical witnesses')
    np.savez_compressed('artifacts/hybrid_baseline.npz',**{str(n):p for n,p in bank.items()})
    if transfer:
        for p,label in candidates:
            for t in range(max(0,int(32-side(p)))+1):offer(border_expand(p,t),label,True)
        checkpoint('Cross-size transfer and crops')
    if include_gpu:
        recipes=json.loads(Path('artifacts/gpu_family_recipes.json').read_text())
        for rec in recipes:
            p=construct(rec['corners'],rec['b'],rec['c'],math.radians(rec['degrees']))
            label=f"CUDA family {rec['corners']}/{rec['b']}/{rec['c']}/{rec['degrees']}deg"
            for t in range(max(0,int(32-side(p)))+1):offer(border_expand(p,t),label,True)
        checkpoint('CUDA generalized cores + crops')
    np.savez_compressed('artifacts/hybrid_packings.npz',**{str(n):p for n,p in bank.items()})
    Path('artifacts/hybrid_provenance.json').write_text(json.dumps(labels,indent=2))
    Path('artifacts/hybrid_ablation.json').write_text(json.dumps(ablation,indent=2))
    export('artifacts/hybrid_submission.csv',bank)
    print('DONE seconds',time.perf_counter()-start,flush=True)
    return bank,ablation

if __name__=='__main__':solve()
