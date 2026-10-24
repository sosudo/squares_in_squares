"""CPU-only monotone admission with unchanged official metric and pandas replay."""
import os
for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','VECLIB_MAXIMUM_THREADS']:os.environ[k]='1'
import sys,csv,json,hashlib,io,argparse,math
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
import numpy as np
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'research'));sys.path.insert(0,str(Path(__file__).parent/'kirill_sources'))
import official_metric as metric
from packing_geometry import side,repair
def groups(p):
 d={}
 with Path(p).open(newline='')as f:
  for r in csv.DictReader(f):d.setdefault(int(r['n']),[]).append(r)
 return d
def array(rows):return np.array([[float(r[k])for k in ['x','y','angle']]for r in rows])
def rows(n,p):return [dict(n=str(n),square_id=str(i),x=format(x,'.17g'),y=format(y,'.17g'),angle=format(a,'.17g'))for i,(x,y,a)in enumerate(p)]
def check(job):
 n,new,old=job;a=metric._evaluate_puzzle_worker((n,old));b=metric._evaluate_puzzle_worker((n,new))
 rec=dict(n=n,before=float(a[2]),after=float(b[2])if b[2]is not None else None,gain=a[1]-b[1],status=b[3])
 if b[3]!='ok'or rec['gain']<1e-10:return n,None,rec
 import pandas as pd
 text=io.StringIO();pd.read_csv(io.StringIO(pd.DataFrame(new).to_csv(index=False))).to_csv(text,index=False,float_format='%.17g');text.seek(0)
 rt=metric._evaluate_puzzle_worker((n,list(csv.DictReader(text))))
 if rt[3]!='ok'or abs(rt[1]-b[1])>1e-10:return n,None,dict(**rec,roundtrip_rejected=rt[3])
 return n,new,rec
def write(path,bank):
 with Path(path).open('w',newline='')as f:
  w=csv.writer(f);w.writerow(['id','n','square_id','x','y','angle']);i=0
  for n,rr in sorted(bank.items()):
   for r in rr:w.writerow([i,n,r['square_id'],r['x'],r['y'],r['angle']]);i+=1
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('--baseline',required=True);a.add_argument('--sources',nargs='+',required=True);a.add_argument('--tag',required=True);a.add_argument('--include-new',action='store_true');x=a.parse_args();bank=groups(x.baseline);records=[];rejected=[];stages=[]
 for source in x.sources:
  p=Path(source)
  if p.suffix=='.npz':
   z=np.load(p);candidate={}
   for key in z.files:
    n=int(key);q=repair(z[key],clearance=4e-10)
    if q is not None:candidate[n]=rows(n,q)
  else:candidate=groups(p)
  tasks=[]
  for n,rr in candidate.items():
   old=bank.get(n)
   if old is None and x.include_new and 1<=n<=1000:
    k=math.ceil(math.sqrt(n))
    old=rows(n,np.array([(i%k+.5,i//k+.5,0.)for i in range(n)]))
   if old is not None and side(array(rr))<side(array(old))-1e-8:tasks.append((n,rr,old))
  kept=[]
  with ProcessPoolExecutor(max_workers=2)as pool:
   for n,new,r in pool.map(check,tasks):
    r['stage']=p.stem
    if new is not None:bank[n]=new;kept.append(r);records.append(r)
    else:rejected.append(r)
  stage=dict(stage=p.stem,accepted=len(kept),gain=sum(r['gain']for r in kept),sha256=hashlib.sha256(p.read_bytes()).hexdigest());stages.append(stage);print(json.dumps(stage),flush=True)
 out=R/'artifacts'/f'{x.tag}_submission.csv';write(out,bank);report=dict(baseline=x.baseline,sha256=hashlib.sha256(out.read_bytes()).hexdigest(),gain=sum(r['gain']for r in records),stages=stages,records=records,rejected=rejected)
 (R/'research'/f'{x.tag}.json').write_text(json.dumps(report,indent=2));print(json.dumps({k:v for k,v in report.items()if k not in ['records','rejected']}),flush=True)
