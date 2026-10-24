"""CUDA crop extraction and minimax staircase composition.

Composition geometry: Chris Deotte's public Multi-Gadget Fault DP notebook.
This implementation performs crop order statistics and the DAG DP on CUDA.
The conservative tip test certifies zero-buffer joins for every f < 1.
Inputs include credited public witnesses and independently generated V9 rows.
"""
import argparse,hashlib,json,math,time
from pathlib import Path
import cupy as cp
import numpy as np
import pandas as pd
from solver import side,normalize,grid
from gpu_families import min_gap
from hybrid_search import export

K=31;D=63;GAP=3e-8
CUDA=r'''
extern "C" __global__ void extract(const double* p,int n,const double* r,
 const double* sorted,int donor,unsigned long long* best){
 int z=blockDim.x*blockIdx.x+threadIdx.x;
 if(z>=31*31*63)return;
 int dm=z%63+1,t=z/63,w=t/31+1,h=t%31+1,m=w*h+dm;
 if(m>n)return;
 double f=sorted[t*n+m-1]+3e-8;
 if(f<=3e-8||f>=.999999)return;
 int br=1,tl=1,count=0;
 for(int i=0;i<n;i++)if(r[t*n+i]<=f-2e-8){
   count++; double x=p[3*i],y=p[3*i+1],a=p[3*i+2];
   double e=.5*(fabs(cos(a))+fabs(sin(a)));
   if(x+e>w+1e-9&&y-e<1.00000001)br=0;
   if(x-e<1.00000001&&y+e>h+1e-9)tl=0;
 }
 if(count<m)return;
 unsigned long long q=(unsigned long long)ceil(f*1e9);
 unsigned int job=donor*(31*31*63)+z;
 unsigned long long key=(q<<32)|job;
 atomicMin(best+(((w*32+h)*64+dm)*4+2*br+tl),key);
}
extern "C" __global__ void dag(int sum,const int* g,const double* f,int ng,
 double* dp,int* pg,int* ps,int* pm){
 int z=blockIdx.x*blockDim.x+threadIdx.x;
 if(z>=31*63*2)return;
 int b=z%2,d=(z/2)%63+1,w=z/(2*63)+1,h=sum-w;
 if(h<1||h>31)return;
 double value=2.;int prev=-1,which=-1,mode=-1;
 for(int i=0;i<ng;i++){
  int gw=g[5*i],gh=g[5*i+1],gd=g[5*i+2],br=g[5*i+3],tl=g[5*i+4];
  if(br!=b||gw>w||gh>h||gd>d||f[i]>=value)continue;
  if(gw==w&&gh==h&&gd==d){value=f[i];which=i;prev=-1;mode=-1;continue;}
  if(gd==d)continue;
  for(int m=0;m<3;m++){
   int x=w-gw-(m==1),y=h-gh-(m==2);
   if(x<1||y<1)continue;
   for(int pb=0;pb<2;pb++){
    if(m==0&&!pb&&!tl)continue;
    int ix=(((x*32+y)*64+(d-gd))*2+pb);
    double cand=fmax(f[i],dp[ix]);
    if(cand<value){value=cand;which=i;prev=ix;mode=m;}
   }
  }
 }
 int ix=(((w*32+h)*64+d)*2+b);
 dp[ix]=value;pg[ix]=which;ps[ix]=prev;pm[ix]=mode;
}
extern "C" __global__ void strips(int height,const double* cost,double* val,int* ph,int* pd){
 int z=blockDim.x*blockIdx.x+threadIdx.x;if(z>=31*64)return;
 int k=z/64+1,d=z%64;if(height>k)return;
 double best=2.;int hh=-1,dd=-1;
 for(int h=1;h<=height;h++)for(int t=0;t<=d;t++){
  double f=t?cost[(k*32+h)*64+t]:0.;
  double p=val[(k*32+height-h)*64+d-t];double v=f+p;
  if(v<best){best=v;hh=h;dd=t;}
 }
 int ix=(k*32+height)*64+d;val[ix]=best;ph[ix]=hh;pd[ix]=dd;
}
'''

# Native f-by-f corner typing is combined with a guaranteed padding direction.
# Type 2 moves upward at global F; type 1 moves rightward. Type 3 retains the
# older unit-corner guarantee, because two padding directions cannot be combined
# merely by assuming that each native corner is independently empty.
CUSHION_CUDA=r'''
extern "C" __global__ void extract_cushion(const double*p,int n,const double*r,
 const double*sorted,int donor,unsigned long long*best){
 int z=blockIdx.x*blockDim.x+threadIdx.x;if(z>=31*31*63)return;
 int d=z%63+1,t=z/63,w=t/31+1,h=t%31+1,m=w*h+d;if(m>n)return;
 double f=sorted[t*n+m-1]+3e-8;if(f<=3e-8||f>=.999999)return;
 int br=1,tl=1,ubr=1,utl=1,count=0;
 for(int i=0;i<n;i++)if(r[t*n+i]<=f-2e-8){
  count++;double x=p[3*i],y=p[3*i+1],a=p[3*i+2],e=.5*(fabs(cos(a))+fabs(sin(a)));
  if(x+e>w-1e-9){if(y-e<f+1e-8)br=0;if(y-e<1.00000001)ubr=0;}
  if(y+e>h-1e-9){if(x-e<f+1e-8)tl=0;if(x-e<1.00000001)utl=0;}
 }
 if(count<m)return;
 unsigned long long q=(unsigned long long)ceil(f*1e9),job=donor*(31*31*63)+z,key=(q<<32)|job;
 unsigned long long*dst=best+(((w*32+h)*64+d)*4);
 atomicMin(dst,key);if(tl)atomicMin(dst+1,key);if(br)atomicMin(dst+2,key);
 if(ubr&&utl)atomicMin(dst+3,key);
}
'''

def read_csv(path):
    df=pd.read_csv(path);return {int(n):g[['x','y','angle']].to_numpy(float) for n,g in df.groupby('n',sort=True)}

def inputs():
    frozen=Path('artifacts/fault_source_donors.npz')
    if frozen.exists():
        base=read_csv('research/latest/kirill.csv');sources={n:'Kirill V6 / credited public portfolio' for n in base}
        for n in range(1,1001):base.setdefault(n,grid(n));sources.setdefault(n,'grid')
        labels=json.loads(Path('artifacts/fault_source_labels.json').read_text())
        with np.load(frozen) as bank:donors=[(bank[k],labels[k]) for k in bank.files]
        return base,sources,donors
    base=read_csv('artifacts/sliding_candidate_submission.csv');sources={n:'V9' for n in base}
    for name in ['ensemble','alex']:
        pth=Path('research/latest')/(name+'.csv')
        if not pth.exists():continue
        for n,p in read_csv(pth).items():
            if n not in base or side(p)<side(base[n])-1e-10:base[n]=p;sources[n]=name
    for n in range(1,1001):base.setdefault(n,grid(n));sources.setdefault(n,'grid')
    donors=[];seen=set()
    def add(p,label):
        p=normalize(p,0);L=side(p)
        if len(p)<=int(math.floor(L+1e-7))**2 or L>=32 or len(p)<5:return
        digest=hashlib.sha256(np.round(p,7).tobytes()).hexdigest()
        if digest not in seen:seen.add(digest);donors.append((p,label))
    for n,p in base.items():add(p,sources[n]+':'+str(n))
    for name in ['sliding_refined','clipped_refined','sliding_relaxed']:
        pth=Path('artifacts')/(name+'_packings.npz')
        with np.load(pth) as b:
            for n in b.files:add(b[n],name+':'+n)
    extra=Path('research/latest/couzo_big.csv')
    if extra.exists():
        # External exact-witness conversions, credited to Couzo/original authors.
        # Large donors are cropped; the large layouts themselves are not submitted.
        df=pd.read_csv(extra);starts=np.flatnonzero(df.square_id.to_numpy()==0);stops=np.r_[starts[1:],len(df)]
        variants=[]
        for first,last in zip(starts,stops):
            part=df.iloc[first:last];n=int(part.n.iloc[0]);assert len(part)==n and np.array_equal(part.square_id,np.arange(n))
            variants.append((n,part[['x','y','angle']].to_numpy(float)))
        for vi,(n,p) in enumerate(variants):
            if side(p)<64:
                p=normalize(p,0);digest=hashlib.sha256(np.round(p,7).tobytes()).hexdigest()
                assert min_gap(p)>-1e-8,(n,vi,'invalid large donor')
                if digest not in seen:seen.add(digest);donors.append((p,'Couzo big:'+str(n)+':variant'+str(vi)))
    return base,sources,donors

def crop_data(p):
    e=.5*(abs(np.cos(p[:,2]))+abs(np.sin(p[:,2])))
    upper=cp.asarray(p[:,:2]+e[:,None]);wh=cp.asarray([(w,h) for w in range(1,32) for h in range(1,32)],dtype=cp.float64)
    r=cp.maximum(cp.maximum(upper[None,:,0]-wh[:,None,0],upper[None,:,1]-wh[:,None,1]),0)
    return r,cp.sort(r,axis=1)

def stitch(chain,gadgets,oriented,box=None):
    width=sum(gadgets[i]['w'] for i,m in chain)+sum(m==1 for i,m in chain[1:])
    height=sum(gadgets[i]['h'] for i,m in chain)+sum(m==2 for i,m in chain[1:])
    k=max(width,height);bx,by=(k,k) if box is None else box
    assert width<=bx and height<=by
    f=max(gadgets[i]['f'] for i,m in chain);placed=[];blocks=[];ox=0;oy=height-gadgets[chain[0][0]]['h']
    spans=[]
    for t,(gi,mode) in enumerate(chain):
        g=gadgets[gi];w,h=g['w'],g['h']
        if t:
            prev=gadgets[chain[t-1][0]];ox+=prev['w']+(mode==1);oy-=h+(mode==2)
        p=oriented[g['donor']][0];e=.5*(abs(np.cos(p[:,2]))+abs(np.sin(p[:,2])))
        r=np.maximum.reduce((p[:,0]+e-w,p[:,1]+e-h,np.zeros(len(p))))
        order=np.argsort(r,kind='stable');q=p[order[:w*h+g['dm']]].copy()
        if g.get('padding')=='up':q[:,1]+=max(0.,f-g['f'])
        if g.get('padding')=='right':q[:,0]+=max(0.,f-g['f'])
        q[:,:2]+=[ox,oy]
        blocks.append(q);spans.append((ox,oy,w,h))
    for x in range(bx):
        inspan=next((s for s in spans if s[0]<=x<s[0]+s[2]),None)
        if inspan:_,y0,w,h=inspan
        else:
            before=[s for s in spans if s[0]>x];y0=(before[0][1]+before[0][3]) if before else 0;h=0
        for y in range(by):
            if inspan and y0<=y<y0+h:continue
            shift=0 if y<y0 else f
            placed.append([x+.5+shift,y+.5+shift,0.])
    p=np.vstack((np.array(placed).reshape(-1,3),*blocks));assert len(p)==bx*by+sum(gadgets[i]['dm'] for i,m in chain)
    # Numerical clearance between otherwise exactly touching grid cells.
    p=normalize(p,0);p[:,:2]*=1+2e-10;return normalize(p,0),k

def run(seconds=240,limit=None,tag='fault_cuda',own_only=False,
        baseline_path=None,extra_donors=None,transpose=False,cushion=False):
    start=time.perf_counter();base,sources,donors=inputs()
    if baseline_path:
        base=read_csv(baseline_path)
        for n in range(1,1001):base.setdefault(n,grid(n))
        donors=[(p,'current certified portfolio:'+str(n)) for n,p in base.items()
                if len(p)>=5 and side(p)<math.ceil(math.sqrt(n))-1e-8]+donors
    if extra_donors:
        with np.load(extra_donors) as bank:
            donors=[(bank[k],'rectangular CUDA:'+k) for k in bank.files]+donors
    if own_only:donors=[d for d in donors if not d[1].startswith(('alex:','ensemble:'))]
    if limit:donors=donors[:limit]
    print(json.dumps(dict(stage='inputs',donors=len(donors),baseline_score=sum(side(p)/math.sqrt(n)-1 for n,p in base.items()))),flush=True)
    oriented=[]
    for p,label in donors:
        for trans in ([False,True] if transpose else [False]):
            r=p.copy()
            if trans:r[:,:2]=r[:,[1,0]];r[:,2]=np.pi/2-r[:,2]
            for sx,sy in [(1,1),(-1,1),(1,-1),(-1,-1)]:
                q=r.copy();q[:,0]*=sx;q[:,1]*=sy;q[:,2]*=sx*sy;q=normalize(q,0);oriented.append((q,label+f':transpose={trans}:{sx},{sy}'))
    best=cp.full(32*32*64*4,np.iinfo(np.uint64).max,cp.uint64);extract=cp.RawKernel(CUSHION_CUDA if cushion else CUDA,'extract_cushion' if cushion else 'extract');dag=cp.RawKernel(CUDA,'dag')
    ev1,ev2=cp.cuda.Event(),cp.cuda.Event();gpu=0.;done=0
    for di,(p,label) in enumerate(oriented):
        ev1.record();r,sorted_r=crop_data(p);extract(((31*31*63+127)//128,),(128,),(cp.asarray(p),np.int32(len(p)),r,sorted_r,np.int32(di),best));ev2.record();ev2.synchronize();gpu+=cp.cuda.get_elapsed_time(ev1,ev2)/1000;done=di+1
        if done%100==0:print(json.dumps(dict(stage='extract',oriented_done=done,seconds=time.perf_counter()-start,gpu_seconds=gpu)),flush=True)
        if time.perf_counter()-start>seconds*.65:break
    keys=cp.asnumpy(best).reshape(32,32,64,4);gadgets=[]
    for w,h,dm,flags in np.argwhere(keys<np.iinfo(np.uint64).max):
        key=int(keys[w,h,dm,flags]);di,z=divmod(key&0xffffffff,31*31*63)
        gadget=dict(w=int(w),h=int(h),dm=int(dm),br=int(flags//2),tl=int(flags%2),f=(key>>32)*1e-9,donor=di)
        if cushion:gadget['padding']='up' if flags==2 else 'right' if flags==1 else 'none'
        gadgets.append(gadget)
    print(json.dumps(dict(stage='dp',gadgets=len(gadgets),seconds=time.perf_counter()-start)),flush=True)
    g=cp.asarray([[r[k] for k in ['w','h','dm','br','tl']] for r in gadgets],dtype=cp.int32);f=cp.asarray([r['f'] for r in gadgets]);size=32*32*64*2
    dp=cp.full(size,2.,cp.float64);pg=cp.full(size,-1,cp.int32);ps=cp.full(size,-1,cp.int32);pm=cp.full(size,-1,cp.int32)
    ev1.record()
    for s in range(2,63):dag(((31*63*2+127)//128,),(128,),(np.int32(s),g,f,np.int32(len(gadgets)),dp,pg,ps,pm))
    ev2.record();ev2.synchronize();gpu+=cp.cuda.get_elapsed_time(ev1,ev2)/1000
    values=cp.asnumpy(dp).reshape(32,32,64,2);pga,psa,pma=[cp.asnumpy(a) for a in [pg,ps,pm]];candidates={};records=[];bad=[]
    def recover(ix):
        rev=[]
        while ix>=0:
            gi=int(pga[ix]);assert gi>=0;rev.append((gi,int(pma[ix])));ix=int(psa[ix])
        return list(reversed(rev))
    for n in range(5,1001):
        k=math.isqrt(n);dm=n-k*k
        if dm==0:continue
        slab=values[1:k+1,1:k+1,dm,:];j=np.unravel_index(np.argmin(slab),slab.shape);f0=float(slab[j])
        if k+f0>=side(base[n])-1e-8:continue
        w,h,b=j[0]+1,j[1]+1,j[2];ix=(((w*32+h)*64+dm)*2+b);rev=[]
        while ix>=0:
            gi=int(pga[ix]);assert gi>=0;rev.append((gi,int(pma[ix])));ix=int(psa[ix])
        chain=list(reversed(rev));p,kk=stitch(chain,gadgets,oriented)
        # If the used rectangle is smaller than k, add ordinary right/top grid borders.
        if kk<k:
            from packing_pipeline import border_expand
            p=border_expand(p,k-kk)
        assert len(p)==n,(n,len(p),kk,k,chain)
        gap=min_gap(p)
        if gap< -1e-9:bad.append(dict(n=n,gap=gap,chain=chain));continue
        candidates[n]=p;records.append(dict(n=n,before=side(base[n]),after=side(p),gain=(side(base[n])-side(p))/math.sqrt(n),chain=[dict(**gadgets[i],mode=m,origin=oriented[gadgets[i]['donor']][1]) for i,m in chain],min_gap=gap,structure='one_fault'))
    # Independent parallel faults: each horizontal strip carries its own chain.
    # Overhangs add vertically but only their maximum is needed horizontally.
    ev1.record();cost=dp.reshape(32,32,64,2).min(axis=3).copy()
    # Explicit GPU prefix minima; CuPy ufunc minimum.accumulate is unsupported.
    for z in range(1,32):cost[z]=cp.minimum(cost[z],cost[z-1])
    for z in range(1,32):cost[:,z]=cp.minimum(cost[:,z],cost[:,z-1])
    val=cp.full(32*32*64,2.,cp.float64);ph=cp.full(val.shape,-1,cp.int32);pd_=cp.full(val.shape,-1,cp.int32)
    val.reshape(32,32,64)[:,0,0]=0.;strip=cp.RawKernel(CUDA,'strips')
    for hh in range(1,32):strip(((31*64+127)//128,),(128,),(np.int32(hh),cost,val,ph,pd_))
    ev2.record();ev2.synchronize();gpu+=cp.cuda.get_elapsed_time(ev1,ev2)/1000
    va,ha,da=[cp.asnumpy(a).reshape(32,32,64) for a in [val,ph,pd_]];strip_records=[]
    for n in range(5,1001):
        k=math.isqrt(n);d=n-k*k
        if not d or k+va[k,k,d]>=side(candidates.get(n,base[n]))-1e-7:continue
        pieces=[];hh=k;dd=d;offset=0.;chains=[]
        while hh>0:
            h=int(ha[k,hh,dd]);t=int(da[k,hh,dd]);assert h>0 and t>=0
            if t:
                slab=values[1:k+1,1:h+1,t,:];jj=np.unravel_index(np.argmin(slab),slab.shape);w0,h0,b=jj[0]+1,jj[1]+1,jj[2]
                chain=recover((((w0*32+h0)*64+t)*2+b));p,_=stitch(chain,gadgets,oriented,box=(k,h));f0=max(gadgets[i]['f'] for i,m in chain)
                chains.append(dict(height=h,surplus=t,f=f0,chain=[dict(**gadgets[i],mode=m,origin=oriented[gadgets[i]['donor']][1]) for i,m in chain]))
            else:p=np.array([[x+.5,y+.5,0.] for x in range(k) for y in range(h)]);f0=0.
            p[:,1]+=offset;offset+=h+f0+1e-8;pieces.append(p);hh-=h;dd-=t
        p=normalize(np.vstack(pieces),0);assert len(p)==n
        gap=min_gap(p)
        if gap< -1e-9:bad.append(dict(n=n,gap=gap,structure='parallel_faults'));continue
        if side(p)>=side(candidates.get(n,base[n]))-1e-8:continue
        candidates[n]=p;strip_records.append(dict(n=n,before=side(base[n]),after=side(p),gain=(side(base[n])-side(p))/math.sqrt(n),strips=chains,min_gap=gap,structure='parallel_faults'))
    replaced={r['n'] for r in strip_records};records=[r for r in records if r['n'] not in replaced]+strip_records
    np.savez_compressed('artifacts/'+tag+'_packings.npz',**{str(n):p for n,p in candidates.items()})
    merged={**base,**candidates};export('artifacts/'+tag+'_submission.csv',merged,margin=0)
    report=dict(seconds=time.perf_counter()-start,cuda_seconds=gpu,baseline=baseline_path,extra_donors=extra_donors,transpose=transpose,cushion=cushion,oriented_done=done,oriented_planned=len(oriented),gadgets=len(gadgets),parallel_fault_wins=len(strip_records),improved=len(records),gain=sum(r['gain'] for r in records),score_estimate=sum(side(p)/math.sqrt(n)-1 for n,p in merged.items()),bad=bad,records=records,source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    Path('research/'+tag+'.json').write_text(json.dumps(report,indent=2));print(json.dumps({k:v for k,v in report.items() if k not in ['records','bad']}),flush=True)

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--seconds',type=float,default=240);a.add_argument('--limit',type=int);a.add_argument('--tag',default='fault_cuda');a.add_argument('--own-only',action='store_true');a.add_argument('--baseline');a.add_argument('--extra-donors');a.add_argument('--transpose',action='store_true');a.add_argument('--cushion',action='store_true');args=a.parse_args();run(args.seconds,args.limit,args.tag,args.own_only,args.baseline,args.extra_donors,args.transpose,args.cushion)
