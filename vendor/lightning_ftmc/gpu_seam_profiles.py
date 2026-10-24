"""CUDA fault composition with conservative separating-line tip profiles.

Deotte's corner-free test is replaced by quantized support bounds of clipped
corner polygons. A zero-buffer join is valid even when both tips are occupied
if one common diagonal line separates their actual occupied portions.
All crop selection, profile generation and minimax DAG search run on CUDA.
"""
import argparse,hashlib,json,math,time
from pathlib import Path
import cupy as cp
import numpy as np
from gpu_fault_composition import inputs,crop_data,stitch,read_csv
from solver import side,normalize
from gpu_families import min_gap
from hybrid_search import export

CUDA=r'''
__device__ int clip(int n,double*x,double*y,int axis,double bound,int sign){
 double xx[12],yy[12];int m=0;if(!n)return 0;
 for(int i=0;i<n;i++){
  int j=(i+1)%n;double a=sign*((axis?y[i]:x[i])-bound),b=sign*((axis?y[j]:x[j])-bound);
  if(a>=0){xx[m]=x[i];yy[m++]=y[i];}
  if((a<0)!=(b<0)){double t=a/(a-b);xx[m]=x[i]+t*(x[j]-x[i]);yy[m++]=y[i]+t*(y[j]-y[i]);}
 }
 for(int i=0;i<m;i++){x[i]=xx[i];y[i]=yy[i];}return m;
}
__device__ void bounds(double x,double y,double a,double c,double s,double*lo,double*hi){
 double co=.5*cos(a),si=.5*sin(a),xx[12]={x+co-si,x-co-si,x-co+si,x+co+si},yy[12]={y+si+co,y-si+co,y-si-co,y+si-co};
 int n=4;n=clip(n,xx,yy,0,-2e-8,1);n=clip(n,xx,yy,0,1.00000002,-1);n=clip(n,xx,yy,1,-2e-8,1);n=clip(n,xx,yy,1,1.00000002,-1);
 for(int i=0;i<n;i++){double v=c*xx[i]-s*yy[i];*lo=fmin(*lo,v);*hi=fmax(*hi,v);}
}
extern "C" __global__ void extract(const double*p,int n,const double*r,const double*sorted,int donor,double c,double s,unsigned long long*best){
 int z=blockDim.x*blockIdx.x+threadIdx.x;if(z>=31*31*63)return;
 int dm=z%63+1,t=z/63,w=t/31+1,h=t%31+1,m=w*h+dm;if(m>n)return;
 double f=sorted[t*n+m-1]+3e-8;if(f<=3e-8||f>=.999999)return;
 double br=-2.,tl=2.;int count=0;
 for(int i=0;i<n;i++)if(r[t*n+i]<=f-2e-8){
  count++;double x=p[3*i],y=p[3*i+1],a=p[3*i+2],e=.5*(fabs(cos(a))+fabs(sin(a))),dummy;
  if(x+e>w-2e-8&&y-e<1.00000002){dummy=2.;bounds(x-w,y,a,c,s,&dummy,&br);}
  if(x-e<1.00000002&&y+e>h-2e-8){dummy=-2.;bounds(x,y-h,a,c,s,&tl,&dummy);}
 }
 if(count<m)return;
 int b=br < -1.5?0:max(0,min(32,(int)ceil((br+1)*16+2e-6)));
 int tbin=tl>1.5?32:max(0,min(32,(int)floor((tl+1)*16-2e-6)));
 unsigned long long q=(unsigned long long)ceil(f*1e9),job=donor*(31*31*63)+z;
 atomicMin(best+(((w*32+h)*64+dm)*33+b)*33+tbin,(q<<32)|job);
}
extern "C" __global__ void dag(int sum,const int*g,const unsigned int*f,int ng,unsigned long long*dp,const unsigned long long*prefix){
 int z=blockIdx.x,w=z/63+1,d=z%63+1,h=sum-w;if(h<1||h>31)return;
 for(int i=threadIdx.x;i<ng;i+=blockDim.x){
  int gw=g[5*i],gh=g[5*i+1],gd=g[5*i+2],br=g[5*i+3],tl=g[5*i+4];if(gw>w||gh>h||gd>d)continue;
  unsigned long long*dst=dp+(((w*32+h)*64+d)*33+br);unsigned int limit=(*dst)>>32;
  if(f[i]>=limit)continue;
  if(gw==w&&gh==h&&gd==d){atomicMin(dst,((unsigned long long)f[i]<<32)|(4*i+3));continue;}
  if(gd==d)continue;
  for(int mode=0;mode<3;mode++){
   int x=w-gw-(mode==1),y=h-gh-(mode==2);if(x<1||y<1)continue;
   unsigned int prev=prefix[(((x*32+y)*64+d-gd)*33+(mode?32:tl))]>>32;
   unsigned int q=max(prev,f[i]);if(q>=limit)continue;
   atomicMin(dst,((unsigned long long)q<<32)|(4*i+mode));
  }
 }
}
extern "C" __global__ void scan(int sum,const unsigned long long*dp,unsigned long long*prefix){
 int z=blockIdx.x*blockDim.x+threadIdx.x;if(z>=31*63)return;
 int w=z/63+1,d=z%63+1,h=sum-w;if(h<1||h>31)return;
 unsigned long long best=~0ULL;
 for(int b=0;b<33;b++){
  int ix=(((w*32+h)*64+d)*33+b);unsigned long long q=((dp[ix]>>32)<<32)|b;best=min(best,q);prefix[ix]=best;
 }
}
'''

def run(degrees=45.,seconds=240,tag='seam_cuda',limit=None,bins=32,interior=False,
        baseline_path=None,extra_donors=None,transpose=False):
    start=time.perf_counter();base,sources,donors=inputs()
    if baseline_path:
        from solver import grid
        base=read_csv(baseline_path)
        for n in range(1,1001):base.setdefault(n,grid(n))
        donors=[(p,'current certified portfolio:'+str(n)) for n,p in base.items()
                if len(p)>=5 and side(p)<math.ceil(math.sqrt(n))-1e-8]+donors
    else:
        for n,p in read_csv('research/latest/kirill.csv').items():
            if side(p)<side(base[n]):base[n]=p;sources[n]='Kirill V6'
    if extra_donors:
        with np.load(extra_donors) as bank:
            donors.extend((bank[k],'rectangular CUDA:'+k) for k in bank.files)
    if limit:donors=donors[:limit]
    if interior:
        # A crop can begin at an interior contact, not only a container corner.
        # Every retained unit square must lie wholly above/right of that anchor.
        # Re-normalization removes empty slack at the new crop origin.
        extra=[];seen=set()
        for p,label in donors:
            if len(p)<200:continue
            e=.5*(abs(np.cos(p[:,2]))+abs(np.sin(p[:,2])));lo=p[:,:2]-e[:,None];hi=p[:,:2]+e[:,None];span=hi.max(0)
            for fx,fy in [(0,.23),(.23,0),(.23,.23),(.47,.13),(.13,.47)]:
                ox=0. if fx==0 else float(np.sort(lo[:,0])[int(fx*len(p))]);oy=0. if fy==0 else float(np.sort(lo[:,1])[int(fy*len(p))]);keep=(lo[:,0]>=ox-1e-10)&(lo[:,1]>=oy-1e-10)
                if keep.sum()<5:continue
                q=normalize(p[keep],0);digest=hashlib.sha256(np.round(q,7).tobytes()).hexdigest()
                if digest in seen:continue
                seen.add(digest);extra.append((q,label+f':interior-{fx},{fy}'))
        print(json.dumps(dict(stage='interior crop sources',extra=len(extra))),flush=True);donors+=extra
    oriented=[]
    for p,label in donors:
        for trans in ([False,True] if transpose else [False]):
            r=p.copy()
            if trans:r[:,:2]=r[:,[1,0]];r[:,2]=np.pi/2-r[:,2]
            for sx,sy in [(1,1),(-1,1),(1,-1),(-1,-1)]:
                q=r.copy();q[:,0]*=sx;q[:,1]*=sy;q[:,2]*=sx*sy;oriented.append((normalize(q,0),label+f':transpose={trans}:{sx},{sy}'))
    nb=bins+1
    src=CUDA.replace('33','NB').replace('min(32,','min(NB-1,').replace('tl>1.5?32','tl>1.5?NB-1').replace('(mode?32:tl)','(mode?NB-1:tl)').replace('*16+','*((NB-1)/2.)+').replace('*16-','*((NB-1)/2.)-')
    mod=cp.RawModule(code='#define NB '+str(nb)+'\n'+src,name_expressions=['extract','dag','scan']);extract=mod.get_function('extract');dag=mod.get_function('dag');scan=mod.get_function('scan')
    best=cp.full(32*32*64*nb*nb,np.iinfo(np.uint64).max,cp.uint64);c,s=math.cos(math.radians(degrees)),math.sin(math.radians(degrees));a,b=cp.cuda.Event(),cp.cuda.Event();gpu=0.;done=0
    print(json.dumps(dict(stage='profile extraction',degrees=degrees,donors=len(donors))),flush=True)
    for di,(p,label) in enumerate(oriented):
        a.record();r,sr=crop_data(p);extract(((31*31*63+127)//128,),(128,),(cp.asarray(p),np.int32(len(p)),r,sr,np.int32(di),np.float64(c),np.float64(s),best));b.record();b.synchronize();gpu+=cp.cuda.get_elapsed_time(a,b)/1000;done=di+1
        if done%500==0:print(json.dumps(dict(stage='extract',done=done,seconds=time.perf_counter()-start,cuda_seconds=gpu)),flush=True)
        if time.perf_counter()-start>seconds*.6:break
    # Only populated profile entries cross PCIe, never the dense 570 MB table.
    active=cp.flatnonzero(best!=np.iinfo(np.uint64).max);idx=cp.asnumpy(active);keys=cp.asnumpy(best[active]);del best,active
    gadgets=[]
    for ix,key in zip(idx,keys):
        ix=int(ix);tl=ix%nb;ix//=nb;br=ix%nb;ix//=nb;dm=ix%64;ix//=64;h=ix%32;w=ix//32;key=int(key);di,_=divmod(key&0xffffffff,31*31*63)
        gadgets.append(dict(w=w,h=h,dm=dm,br=br,tl=tl,f=(key>>32)*1e-9,donor=di))
    gadgets.sort(key=lambda g:g['f']);ng=len(gadgets);g=cp.asarray([[r[k] for k in ['w','h','dm','br','tl']] for r in gadgets],cp.int32);f=cp.asarray([round(r['f']*1e9) for r in gadgets],cp.uint32)
    print(json.dumps(dict(stage='profile DP',gadgets=ng,seconds=time.perf_counter()-start)),flush=True)
    dp=cp.full(32*32*64*nb,np.iinfo(np.uint64).max,cp.uint64);prefix=cp.full_like(dp,np.iinfo(np.uint64).max);a.record()
    for total in range(2,63):
        dag((31*63,),(128,),(np.int32(total),g,f,np.int32(ng),dp,prefix));scan(((31*63+127)//128,),(128,),(np.int32(total),dp,prefix))
    b.record();b.synchronize();gpu+=cp.cuda.get_elapsed_time(a,b)/1000;keys=cp.asnumpy(dp).reshape(32,32,64,nb);pre=cp.asnumpy(prefix).reshape(keys.shape)
    candidates={};records=[];bad=[]
    for n in range(5,1001):
        k=math.isqrt(n);dm=n-k*k
        if not dm:continue
        slab=keys[1:k+1,1:k+1,dm,:];jj=np.unravel_index(np.argmin(slab>>32),slab.shape);w,h,br=jj[0]+1,jj[1]+1,jj[2];value=int(slab[jj])>>32
        if k+value*1e-9>=side(base[n])-1e-7:continue
        rev=[];dd=dm
        while True:
            key=int(keys[w,h,dd,br]);action=key&0xffffffff;gi,mode=divmod(action,4);rec=gadgets[gi];rev.append((gi,mode))
            if mode==3:break
            w-=rec['w']+(mode==1);h-=rec['h']+(mode==2);dd-=rec['dm'];br=int(pre[w,h,dd,bins if mode else rec['tl']])&0xffffffff
        chain=list(reversed(rev));p,kk=stitch(chain,gadgets,oriented)
        if kk<k:
            from packing_pipeline import border_expand
            p=border_expand(p,k-kk)
        assert len(p)==n
        gap=min_gap(p)
        if gap< -1e-9:
            bad.append(dict(n=n,gap=gap,value=value,w=w,h=h,chain=[gadgets[i] for i,m in chain] if len(bad)<3 else []));continue
        candidates[n]=p;records.append(dict(n=n,before=side(base[n]),after=side(p),gain=(side(base[n])-side(p))/math.sqrt(n),min_gap=gap,chain=[dict(**gadgets[i],mode=m,origin=oriented[gadgets[i]['donor']][1]) for i,m in chain]))
    np.savez_compressed('artifacts/'+tag+'_packings.npz',**{str(n):p for n,p in candidates.items()});merged={**base,**candidates};export('artifacts/'+tag+'_submission.csv',merged,margin=0)
    report=dict(seconds=time.perf_counter()-start,cuda_seconds=gpu,degrees=degrees,bins=bins,interior_crops=interior,baseline=baseline_path,extra_donors=extra_donors,transpose=transpose,oriented_done=done,oriented_planned=len(oriented),gadgets=ng,improved=len(records),gain=sum(r['gain'] for r in records),score_estimate=sum(side(p)/math.sqrt(n)-1 for n,p in merged.items()),bad=bad,records=records,source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    Path('research/'+tag+'.json').write_text(json.dumps(report,indent=2));print(json.dumps({k:v for k,v in report.items() if k not in ['records','bad']}),flush=True)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--degrees',type=float,default=45);ap.add_argument('--seconds',type=float,default=240);ap.add_argument('--tag',default='seam_cuda');ap.add_argument('--limit',type=int);ap.add_argument('--bins',type=int,default=32);ap.add_argument('--interior',action='store_true');ap.add_argument('--baseline');ap.add_argument('--extra-donors');ap.add_argument('--transpose',action='store_true');a=ap.parse_args();run(a.degrees,a.seconds,a.tag,a.limit,a.bins,a.interior,a.baseline,a.extra_donors,a.transpose)
