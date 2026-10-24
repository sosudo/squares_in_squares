"""Independent FTMC/refill campaign, following Deotte's public architecture.

Novelty archive, rational-slope core families, FP32 T4 screening, FP64 final
quench, exact finite-candidate upright refill and unchanged official admission.
All expensive execution belongs to Kaggle. No local search is required.
"""
import os
for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ[k]='1'
import argparse,json,math,time,hashlib,warnings
from pathlib import Path
import numpy as np
import cupy as cp
from scipy.spatial import cKDTree
from scipy.optimize import linprog
from scipy.sparse import coo_matrix
from upright_refill import half,gaps,refill,check as refill_check
from gpu_rect_explore import quench as explore,check as gpu_check
from gpu_rect_optimizer import quench as precise
from gpu_upright_rows import refill_batch,check as row_check
from solver import normalize
warnings.filterwarnings('ignore',message='Unrecognized options detected')

def atom_json(path,value):
    p=Path(path);t=p.with_suffix(p.suffix+'.tmp');t.write_text(json.dumps(value,indent=2),encoding='utf8');t.replace(p)
def atom_npz(path,bank):
    p=Path(path);t=p.with_suffix(p.suffix+'.tmp')
    with t.open('wb')as f:np.savez_compressed(f,**bank)
    t.replace(p)
def dimensions(p):
    e=half(p[:,2]);return (p[:,:2]+e[:,None]).max(0)-(p[:,:2]-e[:,None]).min(0)
def excess(p,w,h):return float(max(dimensions(p)-[w,h]))
def repair(p,clearance=3e-9):
    p=normalize(p,0);pairs=cKDTree(p[:,:2]).query_pairs(1.415,output_type='ndarray')
    if len(pairs):
        i,j=pairs.T;d=p[j,:2]-p[i,:2];a,b=p[i,2],p[j,2]
        z=np.maximum.reduce([abs(d[:,0]*np.cos(t)+d[:,1]*np.sin(t))for t in [a,a+np.pi/2,b,b+np.pi/2]])
        r=.5*(1+abs(np.cos(a-b))+abs(np.sin(a-b)));ratio=max(1.,float(np.max((r+clearance)/np.maximum(z,1e-30))))
        if ratio>1.002:return None
        p[:,:2]*=ratio
    return normalize(p,0)

def rect_lp(p,w,h,rounds=3):
    p=normalize(p,0);n=len(p);f=excess(p,w,h)
    for _ in range(rounds):
        a=p[:,2];c,s=np.cos(a),np.sin(a);e=half(a);pairs=cKDTree(p[:,:2]).query_pairs(1.7,output_type='ndarray')
        if not len(pairs):return repair(p)
        i,j=pairs.T;d=p[j,:2]-p[i,:2];ux=np.column_stack((c[i],-s[i],c[j],-s[j]));uy=np.column_stack((s[i],c[i],s[j],c[j]))
        pr=d[:,0,None]*ux+d[:,1,None]*uy;k=abs(pr).argmax(1);ii=np.arange(len(i));sign=np.where(pr[ii,k]>=0,1.,-1.);vx=ux[ii,k]*sign;vy=uy[ii,k]*sign
        cols=[np.column_stack((2*i,2*i+1,2*j,2*j+1))];vals=[np.column_stack((vx,vy,-vx,-vy))];rhs=[-.5*(1+abs(np.cos(a[i]-a[j]))+abs(np.sin(a[i]-a[j])))-4e-9];rows=[np.repeat(ii,4)];offset=len(i);ids=np.arange(n)
        for dim,span in [(0,w),(1,h)]:
            for upper in [False,True]:
                cols.append(np.column_stack((2*ids+dim,np.full(n,2*n))));vals.append(np.tile([1. if upper else -1.,-1. if upper else 0.],(n,1)))
                rhs.append((span if upper else 0)-e-4e-9);rows.append(np.repeat(np.arange(offset,offset+n),2));offset+=n
        A=coo_matrix((np.concatenate([v.ravel()for v in vals]),(np.concatenate(rows),np.concatenate([v.ravel()for v in cols]))),shape=(offset,2*n+1)).tocsr()
        obj=np.zeros(2*n+1);obj[-1]=1.;fit=linprog(obj,A_ub=A,b_ub=np.concatenate(rhs),bounds=[(x-.065,x+.065)for x in p[:,:2].ravel()]+[(max(0.,f-.08),f+.03)],method='highs',options={'time_limit':.7,'primal_feasibility_tolerance':1e-9,'dual_feasibility_tolerance':1e-9,'threads':1})
        if not fit.success:break
        q=p.copy();q[:,:2]=fit.x[:2*n].reshape(n,2);q=repair(q)
        if q is None or excess(q,w,h)>=f-1e-9:break
        p=q;f=excess(p,w,h)
    return repair(p)

def certify(p):
    import sys,csv,io
    sys.path.insert(0,str(Path('research').resolve()));import official_metric as metric
    n=len(p);rows=[dict(n=str(n),square_id=str(i),x=format(x,'.17g'),y=format(y,'.17g'),angle=format(a,'.17g'))for i,(x,y,a)in enumerate(p)]
    raw=metric._evaluate_puzzle_worker((n,rows))
    if raw[3]!='ok':return False
    import pandas as pd
    s=io.StringIO();pd.read_csv(io.StringIO(pd.DataFrame(rows).to_csv(index=False))).to_csv(s,index=False,float_format='%.17g');s.seek(0)
    rt=metric._evaluate_puzzle_worker((n,list(csv.DictReader(s))))
    return rt[3]=='ok' and abs(raw[1]-rt[1])<1e-10

def fingerprint(p):
    a=(p[:,2]+np.pi/4)%(np.pi/2)-np.pi/4;tilted=p[abs(a)>.018]
    hist=np.histogram(a,bins=np.linspace(-np.pi/4,np.pi/4,13))[0]
    if len(tilted):
        xy=tilted[:,:2]-tilted[:,:2].min(0);span=np.maximum(np.ptp(xy,axis=0),1.)
        shape=np.histogram2d(xy[:,0]/span[0],xy[:,1]/span[1],bins=(5,8),range=((0,1.000001),(0,1.000001)))[0].ravel()
    else:shape=np.zeros(40)
    signature=np.r_[len(tilted),hist,shape]
    return hashlib.sha256(signature.astype(np.int32).tobytes()).hexdigest()[:12]

def cold_core(w,h,f,m,rng,angle):
    # A genuinely new rational-slope lattice phase; no incumbent coordinates.
    c,s=np.cos(angle),np.sin(angle);extent=.5*(abs(c)+abs(s));W,H=w+f,h+f
    uv=np.array([(x,y)for x in range(-36,37)for y in range(-36,37)],float)
    uv+=rng.uniform(-.5,.5,2);xy=uv@np.array([[c,s],[-s,c]])+[W/2,H/2]
    mask=(xy[:,0]>=extent)&(xy[:,0]<=W-extent)&(xy[:,1]>=extent)&(xy[:,1]<=H-extent);xy=xy[mask]
    if len(xy)<m:return None
    # Prefer a long diagonal band; vary its offset and taper from scratch.
    axis=np.array([w,h],float);axis/=np.linalg.norm(axis);normal=np.array([-axis[1],axis[0]])
    score=abs((xy-[W/2,H/2])@normal-rng.uniform(-.4,.4))+.015*abs((xy-[W/2,H/2])@axis)
    return np.column_stack((xy[np.argsort(score)[:m]],np.full(m,angle)))

def mutations(p,w,h,d,rng,B,mode,archive):
    a=(p[:,2]+np.pi/4)%(np.pi/2)-np.pi/4;tilt=abs(a)>.018;core=p[tilt].copy();upright=p[~tilt]
    if len(core)<4 or len(core)>160:return [],[],[]
    m0=len(core);offset=1 if mode==1 else -int(rng.integers(1,4))if mode==2 else 0;m=min(len(p)-2,max(4,m0+offset));f0=excess(p,w,h)
    seeds=[];fs=[];meta=[];angles=np.radians([26.565051,28.072487,33.690068,36.869898,40.,45.,-26.565051,-33.690068])
    for b in range(B):
        q=core.copy();angle=float(angles[(b+int(rng.integers(len(angles))))%len(angles)])
        if mode==5:
            q=cold_core(w,h,f0,m,rng,angle)
            if q is None:continue
        elif mode==4 and archive:
            q=archive[int(rng.integers(len(archive)))].copy();aa=(q[:,2]+np.pi/4)%(np.pi/2)-np.pi/4;q=q[abs(aa)>.018]
            if len(q)<4:continue
        if len(q)>m:
            axis=np.array([w,h],float);score=q[:,:2]@axis;ids=np.argsort(score);drop=ids[:len(q)-m]if b%2 else ids[-(len(q)-m):];q=np.delete(q,drop,axis=0)
        while len(q)<m:
            axis=np.array([w,h],float);axis/=np.linalg.norm(axis);origin=q[rng.integers(len(q))].copy();projection=q[:,:2]@axis;cut=np.median(projection)
            q[projection>cut,:2]+=.42*axis;q[projection<=cut,:2]-=.42*axis;origin[:2]=q[:,:2].mean(0)+rng.normal(0,.15,2)
            q=np.vstack((q,origin))
        if mode==3 and len(upright):
            tree=cKDTree(q[:,:2]);near=tree.query(upright[:,:2])[0];ids=np.argsort(near)[:min(10,len(upright))]
            u=upright[int(rng.choice(ids))].copy();u[2]=float(np.median(q[:,2]));tip=np.argmax(np.linalg.norm(q[:,:2]-u[:2],axis=1));q[tip]=u
        if mode!=5:
            centre=q[:,:2].mean(0);old=.25*np.angle(np.mean(np.exp(4j*q[:,2])))
            delta=((angle-old+np.pi/4)%(np.pi/2)-np.pi/4) if b%3==0 else rng.normal(0,.018 if b%2 else .065)
            c,s=np.cos(delta),np.sin(delta);q[:,:2]=(q[:,:2]-centre)@np.array([[c,s],[-s,c]])+centre;q[:,2]+=delta
            q[:,0]+=(q[:,1]-centre[1])*rng.normal(0,.015);q[:,:2]+=rng.normal(0,.004,q[:,:2].shape)
        q=normalize(q,0);wh=dimensions(q);box=np.array([w+f0,h+f0]);q[:,:2]+=(box-wh)/2
        depth=[.002,.008,.02,.045,.08,.12][b%6];ftry=max(.12,f0-depth)
        seeds.append(q);fs.append(ftry);meta.append(dict(mode=mode,core_count=m,angle=angle,cold=mode==5))
    return seeds,fs,meta

EXTRACT=r'''
extern "C" __global__ void extract(const double*sorted,int n,int donor,unsigned long long*best){
 int z=blockIdx.x*blockDim.x+threadIdx.x;if(z>=31*31*63)return;
 int d=z%63+1,t=z/63,w=t/31+1,h=t%31+1,m=w*h+d;if(m>n)return;
 double f=sorted[t*n+m-1]+3e-8;if(f<=3e-8||f>=.999999)return;
 unsigned long long q=(unsigned long long)ceil(f*1e9),job=donor*(31*31*63)+z;atomicMin(best+(w*32+h)*64+d,(q<<32)|job);
}'''

def build_library(baseline,examples,limit=320):
    from gpu_fault_composition import read_csv,crop_data
    start=time.perf_counter();bank={};variants={};provenance={};donors=[]
    z=np.load(examples);meta=z['meta_39']
    for k,row in enumerate(meta):
        w,h,d=map(int,row[:3])
        for stage in ['before','after']:
            p=z[f'{stage}_{k}'];assert len(p)==w*h+d
            for swap in [False,True]:
                q=p.copy();ww,hh=w,h
                if swap:q[:,:2]=q[:,[1,0]];q[:,2]=np.pi/2-q[:,2];ww,hh=h,w
                key=f'{ww}_{hh}_{d}';q=normalize(q,0)
                variants[key+f'__{stage}{k}']=q
                if key not in bank or excess(q,ww,hh)<excess(bank[key],ww,hh):bank[key]=q;provenance[key]=f'Chris Deotte published {stage}_{k}, dataset v2'
    atom_npz('artifacts/night_seed_gadgets.npz',bank);atom_npz('artifacts/night_seed_variants.npz',variants);atom_json('research/night_priorities.json',{})
    full=read_csv(baseline)
    for n,p in full.items():
        if n<5:continue
        for swap in [False,True]:
            q=p.copy()
            if swap:q[:,:2]=q[:,[1,0]];q[:,2]=np.pi/2-q[:,2]
            for sx,sy in [(1,1),(-1,1),(1,-1),(-1,-1)]:
                t=q.copy();t[:,0]*=sx;t[:,1]*=sy;t[:,2]*=sx*sy;donors.append((normalize(t,0),n))
    kernel=cp.RawKernel(EXTRACT,'extract');best=cp.full(32*32*64,np.uint64(0xffffffffffffffff));
    for i,(p,n)in enumerate(donors):
        r,s=crop_data(p);kernel(((31*31*63+127)//128,),(128,),(s,np.int32(len(p)),np.int32(i),best))
        if i%500==0:cp.cuda.Stream.null.synchronize();print(json.dumps(dict(stage='GPU crop library',done=i,total=len(donors),seconds=time.perf_counter()-start)),flush=True)
    kk=cp.asnumpy(best).reshape(32,32,64);rank=[]
    incumbent={n:excess(p,math.isqrt(n),math.isqrt(n))for n,p in full.items()}
    for w,h,d in np.argwhere(kk<np.uint64(0xffffffffffffffff)):
        f=(int(kk[w,h,d])>>32)*1e-9
        if w+h>54 or w*h+d>600 or min(w,h)<2:continue
        leverage=sum(max(0.,incumbent.get(k*k+d,1.)-(f-.04))/math.sqrt(k*k+d)for k in range(max(int(w),int(h)),32)if k*k+d<=1000)
        rank.append((leverage,int(w),int(h),int(d),f))
    rank.sort(reverse=True)
    for score,w,h,d,f in rank[:limit]:
        value=int(kk[w,h,d]);di=(value&0xffffffff)//(31*31*63);p,n=donors[di];e=half(p[:,2]);r=np.maximum.reduce((p[:,0]+e-w,p[:,1]+e-h,np.zeros(len(p))));q=normalize(p[np.argsort(r,kind='stable')[:w*h+d]],0);key=f'{w}_{h}_{d}'
        if key not in bank or excess(q,w,h)<excess(bank[key],w,h):bank[key]=q;provenance[key]=f'Certified union crop n={n}, D4 donor {di}'
    atom_npz('artifacts/night_seed_gadgets.npz',bank);atom_json('research/night_seed_provenance.json',provenance)
    priority={f'{w}_{h}_{d}':score for score,w,h,d,f in rank[:limit]}
    atom_json('research/night_priorities.json',priority);print(json.dumps(dict(stage='GPU library complete',gadgets=len(bank),seconds=time.perf_counter()-start)),flush=True)

def worker(device,seconds=21600,replicas=64,seed=0):
    cp.cuda.Device(device).use();start=time.perf_counter();rng=np.random.default_rng(20261024+seed+device*19937)
    stats=dict(device=device,seed=seed,batches=0,core_trials=0,refill_success=0,full_quenches=0,accepted=0,cuda_seconds=0.,families={},official_rejected=0)
    checks=dict(refill=refill_check(),gpu=gpu_check(),cuda_rows=row_check());atom_json(f'research/worker{device}_checks.json',checks);print(json.dumps(dict(stage='preflight passed',device=device,checks=checks)),flush=True)
    initial=np.load('artifacts/night_seed_gadgets.npz');bank={k:initial[k]for k in initial.files};archive={k:[p.copy()]for k,p in bank.items()};wins={};records=[]
    if Path('artifacts/night_seed_variants.npz').exists():
        with np.load('artifacts/night_seed_variants.npz')as variants:
            for name in variants.files:
                root=name.split('__')[0]
                if root in archive:archive[root].append(variants[name])
    existing=Path(f'artifacts/worker{device}_gadgets.npz')
    if existing.exists():
        with np.load(existing)as old:
            for key in old.files:
                root=key.split('__')[0];w,h,d=map(int,root.split('_'));p=old[key];archive.setdefault(root,[]).append(p)
                if root not in bank or excess(p,w,h)<excess(bank[root],w,h):bank[root]=p
                wins[key]=p
    priority=json.loads(Path('research/night_priorities.json').read_text());keys=list(bank);visits={k:0 for k in keys}
    event1,event2=cp.cuda.Event(),cp.cuda.Event()
    def checkpoint():
        atom_npz(existing,wins);stats.update(seconds=time.perf_counter()-start,gadgets=len(wins),latest=records[-1]if records else None,records=records[-300:]);atom_json(f'research/worker{device}_status.json',stats)
    checkpoint()
    while time.perf_counter()-start<seconds:
        weights=np.array([(.08+100*priority.get(k,0.)) / math.sqrt(1+visits[k]) for k in keys]);weights/=weights.sum();key=keys[int(rng.choice(len(keys),p=weights))];visits[key]+=1
        w,h,d=map(int,key.split('_'));p=bank[key];f0=excess(p,w,h);mode=(stats['batches']+device)%6;stats['batches']+=1;stats['families'][str(mode)]=stats['families'].get(str(mode),0)+1
        source=archive[key][int(rng.integers(len(archive[key])))];seeds,fs,recipes=mutations(source,w,h,d,rng,replicas,mode,archive[key])
        if not seeds:continue
        stats['core_trials']+=len(seeds);fs=np.minimum(np.array(fs),f0-.0005);loose=min(.995,f0+.035);event1.record()
        cq,out=explore(np.asarray(seeds),np.tile([w+loose,h+loose],(len(seeds),1)),steps=500)
        event2.record();event2.synchronize();stats['cuda_seconds']+=cp.cuda.get_elapsed_time(event1,event2)/1000
        scores=cp.asnumpy(out);cores=cp.asnumpy(cq).astype(float);event1.record()
        packed,capacity=refill_batch(cq,w,h,loose,w*h+d,soft=.008)
        event2.record();event2.synchronize();stats['cuda_seconds']+=cp.cuda.get_elapsed_time(event1,event2)/1000
        row_counts=cp.asnumpy(capacity);row_seeds=cp.asnumpy(packed).astype(float);filled=[];filled_fs=[];which=[];seen=set();fill_reports=[]
        for job in np.argsort(-row_counts,kind='stable'):
            b=int(job)//2
            if row_counts[job]<w*h+d:break
            if not np.isfinite(scores[b]).all()or not np.isfinite(cores[b]).all()or scores[b,1]>.01:continue
            sig=fingerprint(cores[b])+str(int(job)%2)
            if sig in seen:continue
            seen.add(sig);filled.append(row_seeds[job]);filled_fs.append(fs[b]);which.append(b);stats['refill_success']+=1
            if len(filled)>=8:break
        # Only a few near-capacity failures reach the more expensive 2-D MILP.
        near=np.argsort(-row_counts.reshape(-1,2).max(1),kind='stable');attempts=0
        import signal
        previous=signal.getsignal(signal.SIGALRM)
        def timed_out(signum,frame):raise TimeoutError('Refill seed budget')
        signal.signal(signal.SIGALRM,timed_out)
        try:
            for b in near:
                if len(filled)>=12 or attempts>=4:break
                if row_counts.reshape(-1,2)[b].max()<w*h+d-4:continue
                if not np.isfinite(cores[b]).all()or scores[b,1]>.01:continue
                attempts+=1;extra=p[abs((p[:,2]+np.pi/4)%(np.pi/2)-np.pi/4)<.018]
                try:
                    signal.setitimer(signal.ITIMER_REAL,1.25)
                    q,fr=refill(w+loose,h+loose,cores[b],w*h+d,extra,seconds=.25,soft=.008)
                except TimeoutError:q=None;fr=dict(timeout=True)
                finally:signal.setitimer(signal.ITIMER_REAL,0)
                fill_reports.append(fr)
                if q is not None:filled.append(q);filled_fs.append(fs[b]);which.append(int(b));stats['refill_success']+=1
        finally:signal.signal(signal.SIGALRM,previous)
        gained=False;best=f0
        if filled:
            R=16;qbatch=np.repeat(np.asarray(filled),R,axis=0);ff=np.repeat(np.array(filled_fs),R);origins=np.repeat(np.array(which),R)
            for j in range(len(qbatch)):
                if j%R==0:continue
                mask=abs((qbatch[j,:,2]+np.pi/4)%(np.pi/2)-np.pi/4)>.018
                qbatch[j,mask,:2]+=rng.normal(0,.0003,(int(mask.sum()),2));qbatch[j,mask,2]+=rng.normal(0,.0004,int(mask.sum()))
            event1.record();cq,out=explore(qbatch,np.column_stack((w+ff,h+ff)),steps=1800)
            event2.record();event2.synchronize();stats['cuda_seconds']+=cp.cuda.get_elapsed_time(event1,event2)/1000;rough=cp.asnumpy(out);q32=cp.asnumpy(cq);stats['full_quenches']+=len(qbatch)
            pick=np.argsort(rough[:,1])[:8];event1.record()
            cq,out=precise(q32[pick],np.column_stack((w+ff[pick]+2e-5,h+ff[pick]+2e-5)),steps=1100)
            event2.record();event2.synchronize();stats['cuda_seconds']+=cp.cuda.get_elapsed_time(event1,event2)/1000
            q64=cp.asnumpy(cq);end=cp.asnumpy(out)
            for k,b in enumerate(pick):
                if not np.isfinite(end[k]).all()or not np.isfinite(q64[k]).all()or end[k,1]>3e-5:continue
                q=rect_lp(q64[k],w,h);f=excess(q,w,h)if q is not None else 99.
                if q is None or f>f0+.025 or gaps(q)<1e-10:continue
                signature=fingerprint(q);known={fingerprint(t)for t in archive[key]}
                improved=f<f0-2e-7
                if not improved and signature in known:continue
                if not certify(q):stats['official_rejected']+=1;continue
                if signature not in known:archive[key].append(q);archive[key]=sorted(archive[key],key=lambda t:excess(t,w,h))[:6]
                wins[key+'__'+signature]=q
                if improved:
                    bank[key]=q;f0=f;best=f;gained=True;stats['accepted']+=1
                    records.append(dict(key=key,before=excess(p,w,h),after=f,mode=mode,recipe=recipes[int(origins[int(b)])],signature=signature,minimum_gap=gaps(q),official_raw_and_pandas=True))
                    print(json.dumps(dict(stage='new certified gadget',device=device,**records[-1])),flush=True)
        stats['last_batch']=dict(key=key,mode=mode,core_candidates=len(seeds),refilled=len(filled),fill_reports=fill_reports[-4:],before=excess(p,w,h),after=best)
        checkpoint()
        if stats['batches']%4==0:print(json.dumps({k:v for k,v in stats.items()if k not in ['records','latest','last_batch']}),flush=True)
    checkpoint();print(json.dumps(dict(stage='worker complete',device=device,seconds=time.perf_counter()-start,accepted=stats['accepted'])),flush=True)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--library',action='store_true');ap.add_argument('--baseline');ap.add_argument('--examples');ap.add_argument('--device',type=int,default=0);ap.add_argument('--seconds',type=float,default=21600);ap.add_argument('--replicas',type=int,default=64);ap.add_argument('--seed',type=int,default=0);a=ap.parse_args()
    cp.cuda.Device(a.device).use()
    if a.library:build_library(a.baseline,a.examples)
    else:worker(a.device,a.seconds,a.replicas,a.seed)
