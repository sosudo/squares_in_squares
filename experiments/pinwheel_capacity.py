"""Read-only capacity screens for finite four-arm pinwheel models."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[k]='1'
import numpy as np
from compose_gadgets import extents,read_baseline,side


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--bank',type=Path,required=True)
    p.add_argument('--portfolio',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    args=p.parse_args();args.out.mkdir(parents=True,exist_ok=False)
    pointer=json.loads(args.portfolio.read_text());baseline=Path(pointer['safe']['path'])
    assert hashlib.sha256(baseline.read_bytes()).hexdigest()==pointer['safe']['sha256']
    base=read_baseline(baseline);before=np.array([0.]+[side(base[n])for n in range(1,1001)])
    source={'bank_sha256':hashlib.sha256(args.bank.read_bytes()).hexdigest(),
            'baseline':pointer['safe'],'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'scope':'Finite502-partner input; no geometry admission or exhaustive mixed-arm claim.'}
    symmetric=[];directional=[];interlocking=[]
    with np.load(args.bank,allow_pickle=False)as bank:
        for key in bank.files:
            q=bank[key];lo,hi=extents(q);span=hi.max(0)-lo.min(0);m=len(q)
            w,h,d=map(int,key.split('__')[0].split('_'));assert m==w*h+d
            f=float(max(span-[w,h]));k=w+h;n=k*k+4*d
            if n<=1000 and f>=0:
                length=k+2*f
                lower=max(1,math.floor(length-1)**2)
                gain,target=max(((before[t]-length)/math.sqrt(t),t)for t in range(lower,n+1))
                symmetric.append(dict(key=key,w=w,h=h,d=d,f=f,n=n,side=length,
                                      best_drop_n=target,best_drop_gain=float(gain)))
            for swap in (False,True):
                a,b=span[::-1]if swap else span
                directional.append((key,swap,float(a),float(b),m))
            A,B=sorted(span,reverse=True)
            if 4*m>1000:continue
            for c in range(math.isqrt(1000-4*m)+1):
                n=4*m+c*c;lower=max(A,A+B-1,2*B+c,math.sqrt(n))
                if lower<A+B and lower<before[n]-1e-6:
                    interlocking.append(dict(key=key,m=m,A=float(A),B=float(B),core=c,n=n,
                        optimistic_side_lower=float(lower),baseline_side=float(before[n]),
                        optimistic_score_headroom=float((before[n]-lower)/math.sqrt(n))))
    a=np.array([r[2]for r in directional]);b=np.array([r[3]for r in directional]);m=np.array([r[4]for r in directional])
    L=np.maximum(a[:,None]+b[None,:],a[None,:]+b[:,None]);cx=L-2*b[None,:];cy=L-2*b[:,None]
    tol=1e-9
    n=2*(m[:,None]+m[None,:])+np.floor(np.maximum(cx,0)+tol).astype(int)*np.floor(np.maximum(cy,0)+tol).astype(int)
    padA=np.floor(np.maximum(L-b[None,:]-a[:,None],0)+tol).astype(int)*np.floor(b[:,None]+tol).astype(int)
    padB=np.floor(np.maximum(L-b[:,None]-a[None,:],0)+tol).astype(int)*np.floor(b[None,:]+tol).astype(int)
    n+=2*(padA+padB)
    valid=(cx>=-tol)&(cy>=-tol)&(n<=1000)&(n>=1);ii,jj=np.nonzero(valid)
    gain=(before[n[ii,jj]]-L[ii,jj])/np.sqrt(n[ii,jj]);top=[]
    for i in np.argsort(-gain)[:20]:
        x,y=ii[i],jj[i]
        top.append(dict(first=directional[x],second=directional[y],side=float(L[x,y]),
            core_width=float(cx[x,y]),core_height=float(cy[x,y]),n=int(n[x,y]),
            arm_padding=int(2*(padA[x,y]+padB[x,y])),score_headroom=float(gain[i])))
    symmetric.sort(key=lambda r:r['best_drop_gain'],reverse=True)
    interlocking.sort(key=lambda r:r['optimistic_score_headroom'],reverse=True)
    result={**source,'symmetric':{'count_formula':'(w+h)^2+4d','side_formula':'w+h+2f',
                'tested':len(symmetric),'positive':sum(r['best_drop_gain']>1e-8 for r in symmetric),'rows':symmetric},
            'anisotropic_opposite_pairs':{'side_formula':'max(A_width+B_thickness,B_length+A_thickness)',
                'core_formula':'floor(L−2B_thickness)*floor(L−2A_thickness)',
                'optimistic_floor_tolerance':tol,'ordered_pairs':len(directional)**2,'feasible_pairs':len(ii),
                'positive':int((gain>1e-8).sum()),'top':top},
            'interlocking':{'count_formula':'4m+c²','side_lower':'max(A,A+B−1,2B+c,sqrt(N))',
                'headroom_candidates':len(interlocking),'rows':interlocking}}
    (args.out/'capacity.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'symmetric_positive':result['symmetric']['positive'],
          'anisotropic_positive':result['anisotropic_opposite_pairs']['positive'],
          'interlocking_optimistic_jobs':len(interlocking)}))


if __name__=='__main__':main()
