"""CUDA minimax packing composition with a separate separator at every join.

Each block has an incoming and an outgoing support profile. They need not use
the same line normal. Prefix minima remove dominated (f,BR,TL) states on GPU;
only the compact frontier crosses PCIe. Diagonal composition geometry is
credited to avazaku / Chris Deotte; extends our CUDA corner-support solver.
"""
import argparse,hashlib,json,math,time
from pathlib import Path
import cupy as cp
import numpy as np
from gpu_fault_composition import inputs,crop_data,stitch,read_csv
from gpu_seam_profiles import CUDA as OLD_CUDA
from solver import normalize,side,grid
from gpu_families import min_gap

HELPERS=OLD_CUDA[:OLD_CUDA.index('extern "C" __global__ void extract')]
CUDA=r'''
extern "C" __global__ void extract(const double*p,int n,const double*r,
 const double*sorted,int donor,const double*cs,unsigned long long*best){
 int z=blockDim.x*blockIdx.x+threadIdx.x;if(z>=31*31*63)return;
 int dm=z%63+1,t=z/63,w=t/31+1,h=t%31+1,m=w*h+dm;if(m>n)return;
 double f=sorted[t*n+m-1]+3e-8;if(f<=3e-8||f>=.999999)return;
 double br[NA],tl[NA];for(int a=0;a<NA;a++){br[a]=-2.;tl[a]=2.;}
 int count=0;
 for(int i=0;i<n;i++)if(r[t*n+i]<=f-2e-8){
  count++;double x=p[3*i],y=p[3*i+1],ang=p[3*i+2],e=.5*(fabs(cos(ang))+fabs(sin(ang)));
  for(int a=0;a<NA;a++){
   double dummy,c=cs[2*a],s=cs[2*a+1];
   if(x+e>w-2e-8&&y-e<1.00000002){dummy=2.;bounds(x-w,y,ang,c,s,&dummy,&br[a]);}
   if(x-e<1.00000002&&y+e>h-2e-8){dummy=-2.;bounds(x,y-h,ang,c,s,&tl[a],&dummy);}
  }
 }
 if(count<m)return;
 unsigned long long q=(unsigned long long)ceil(f*1e9),job=donor*(31*31*63)+z,key=(q<<32)|job;
 for(int ai=0;ai<NA;ai++)for(int ao=0;ao<NA;ao++){
  int b=br[ao]<-1.5?0:max(0,min(NB-1,(int)ceil((br[ao]+1)*((NB-1)/2.)+2e-6)));
  int tt=tl[ai]>1.5?NB-1:max(0,min(NB-1,(int)floor((tl[ai]+1)*((NB-1)/2.)-2e-6)));
  long long ix=((((((long long)w*32+h)*64+dm)*NA+ai)*NA+ao)*NB+b)*NB+tt;
  atomicMin(best+ix,key);
 }
}
extern "C" __global__ void dag(int sum,const int*g,const unsigned int*f,int ng,
 unsigned long long*dp,const unsigned long long*prefix){
 int z=blockIdx.x,w=z/63+1,d=z%63+1,h=sum-w;if(h<1||h>31)return;
 for(int i=threadIdx.x;i<ng;i+=blockDim.x){
  const int* row=g+7*i;int gw=row[0],gh=row[1],gd=row[2],br=row[3],tl=row[4],ai=row[5],ao=row[6];
  if(gw>w||gh>h||gd>d)continue;
  unsigned long long*dst=dp+((((w*32+h)*64+d)*NA+ao)*NB+br);
  unsigned int limit=(*dst)>>32;if(f[i]>=limit)continue;
  if(gw==w&&gh==h&&gd==d){atomicMin(dst,((unsigned long long)f[i]<<32)|(4*i+3));continue;}
  if(gd==d)continue;
  for(int mode=0;mode<3;mode++){
   int x=w-gw-(mode==1),y=h-gh-(mode==2);if(x<1||y<1)continue;
   unsigned int prev=prefix[((((x*32+y)*64+d-gd)*NA+ai)*NB+(mode?NB-1:tl))]>>32;
   unsigned int q=max(prev,f[i]);if(q>=limit)continue;
   atomicMin(dst,((unsigned long long)q<<32)|(4*i+mode));
  }
 }
}
extern "C" __global__ void scan(int sum,const unsigned long long*dp,unsigned long long*prefix){
 int z=blockDim.x*blockIdx.x+threadIdx.x;if(z>=31*63*NA)return;
 int ao=z%NA;z/=NA;int w=z/63+1,d=z%63+1,h=sum-w;if(h<1||h>31)return;
 unsigned long long best=~0ULL;
 for(int br=0;br<NB;br++){
  int ix=((((w*32+h)*64+d)*NA+ao)*NB+br);
  best=min(best,((dp[ix]>>32)<<32)|br);prefix[ix]=best;
 }
}
'''

def pareto(best,nb):
    """Smaller BR and larger TL are better; retain incomparable f profiles."""
    active=cp.flatnonzero(best!=np.iinfo(np.uint64).max);original=best.ravel()[active].copy()
    shape=best.shape;front=best.reshape(-1,nb,nb)
    for b in range(1,nb):front[:,b,:]=cp.minimum(front[:,b,:],front[:,b-1,:])
    for t in range(nb-2,-1,-1):front[:,:,t]=cp.minimum(front[:,:,t],front[:,:,t+1])
    br=active//nb%nb;tl=active%nb;flat=front.ravel()
    left=cp.where(br>0,flat[cp.maximum(active-nb,0)],np.uint64(0xffffffffffffffff))
    upper=cp.where(tl<nb-1,flat[cp.minimum(active+1,flat.size-1)],np.uint64(0xffffffffffffffff))
    keep=(cp.minimum(left,upper)>>32)>(original>>32)
    return cp.asnumpy(active[keep]),cp.asnumpy(original[keep]),int(active.size)

def run(baseline,tag='adaptive_seams1',seconds=480,bins=16,degrees=(30,45,60),limit=None):
    start=time.perf_counter();NA=len(degrees);NB=bins+1
    free,_=cp.cuda.runtime.memGetInfo();pool_limit=min(13_000_000_000,int(free)-1_000_000_000)
    table_size=32*32*64*NA*NA*NB*NB*8
    if table_size+500_000_000>pool_limit:raise RuntimeError('Not enough shared GPU headroom for requested profile table')
    cp.get_default_memory_pool().set_limit(size=pool_limit)
    labels=json.loads(Path('artifacts/fault_source_labels.json').read_text(encoding='utf8'))
    with np.load('artifacts/fault_source_donors.npz')as frozen:legacy=[(frozen[k],labels[k])for k in frozen.files]
    base=read_csv(baseline)
    donors=[(p,'Public frontier:'+str(n))for n,p in base.items()if len(p)>4]
    for n in range(1,1001):base.setdefault(n,grid(n))
    fresh=[]
    for path in ['artifacts/tip_frontier1_gadgets.npz','artifacts/crystal_polished1_gadgets.npz']:
        with np.load(path)as z:fresh.extend((z[k],'FTMC donor (provenance in night files):'+k)for k in z.files)
    donors=fresh+donors+legacy
    if limit:donors=donors[:limit]
    oriented=[]
    for p,label in donors:
        for trans in [False,True]:
            r=p.copy()
            if trans:r[:,:2]=r[:,[1,0]];r[:,2]=np.pi/2-r[:,2]
            for sx,sy in [(1,1),(-1,1),(1,-1),(-1,-1)]:
                q=r.copy();q[:,0]*=sx;q[:,1]*=sy;q[:,2]*=sx*sy;oriented.append((normalize(q,0),label+f':T={trans}:{sx},{sy}'))
    src=f'#define NA {NA}\n#define NB {NB}\n'+HELPERS+CUDA
    mod=cp.RawModule(code=src,name_expressions=['extract','dag','scan']);extract,dag,scan=[mod.get_function(k)for k in ['extract','dag','scan']]
    best=cp.full((32,32,64,NA,NA,NB,NB),np.iinfo(np.uint64).max,cp.uint64)
    cs=cp.asarray([[math.cos(math.radians(d)),math.sin(math.radians(d))]for d in degrees])
    a,b=cp.cuda.Event(),cp.cuda.Event();gpu=0.;done=0
    print(json.dumps(dict(stage='adaptive extraction',degrees=degrees,bins=bins,oriented=len(oriented),table_bytes=table_size,pool_limit=pool_limit)),flush=True)
    for di,(p,label)in enumerate(oriented):
        a.record();r,sr=crop_data(p);extract(((31*31*63+127)//128,),(128,),(cp.asarray(p),np.int32(len(p)),r,sr,np.int32(di),cs,best))
        b.record();b.synchronize();gpu+=cp.cuda.get_elapsed_time(a,b)/1000;done=di+1
        if done%500==0:print(json.dumps(dict(stage='extract',done=done,seconds=time.perf_counter()-start,cuda_seconds=gpu)),flush=True)
        if time.perf_counter()-start>seconds*.7:break
    a.record();idx,keys,unpruned=pareto(best,NB);b.record();b.synchronize();gpu+=cp.cuda.get_elapsed_time(a,b)/1000
    del best,r,sr;cp.get_default_memory_pool().free_all_blocks()
    tl=idx%NB;z=idx//NB;br=z%NB;z//=NB;ao=z%NA;z//=NA;ai=z%NA;z//=NA;dm=z%64;z//=64;h=z%32;w=z//32
    f=(keys>>32).astype(np.uint32);donor=((keys&np.uint64(0xffffffff))//(31*31*63)).astype(np.int32)
    gg=np.column_stack((w,h,dm,br,tl,ai,ao)).astype(np.int32);order=np.argsort(f,kind='stable');gg,f,donor=gg[order],f[order],donor[order]
    ng=len(f);g=cp.asarray(gg);cf=cp.asarray(f)
    print(json.dumps(dict(stage='adaptive DP',populated=unpruned,pareto=ng,seconds=time.perf_counter()-start)),flush=True)
    dp=cp.full((32,32,64,NA,NB),np.iinfo(np.uint64).max,cp.uint64);prefix=cp.full_like(dp,np.iinfo(np.uint64).max)
    a.record()
    for total in range(2,63):
        dag((31*63,),(128,),(np.int32(total),g,cf,np.int32(ng),dp,prefix))
        scan(((31*63*NA+127)//128,),(128,),(np.int32(total),dp,prefix))
    b.record();b.synchronize();gpu+=cp.cuda.get_elapsed_time(a,b)/1000;values,pre=map(cp.asnumpy,[dp,prefix])
    winners={};records=[];bad=[]
    for n in range(5,1001):
        k=math.isqrt(n);d=n-k*k
        if not d:continue
        slab=values[1:k+1,1:k+1,d];jj=np.unravel_index(np.argmin(slab>>32),slab.shape);value=int(slab[jj])>>32
        if k+value*1e-9>=side(base[n])-1e-7:continue
        w,h,ao,br=jj[0]+1,jj[1]+1,jj[2],jj[3];rev=[];dd=d
        while True:
            action=int(values[w,h,dd,ao,br])&0xffffffff;gi,mode=divmod(action,4);rev.append((gi,mode))
            if mode==3:break
            gw,gh,gd,gbr,tl,ai,_=map(int,gg[gi]);w-=gw+(mode==1);h-=gh+(mode==2);dd-=gd;ao=ai;br=int(pre[w,h,dd,ao,NB-1 if mode else tl])&0xffffffff
        chain=list(reversed(rev));gadgets=[];recipe=[]
        for gi,mode in chain:
            w,h,d,br,tl,ai,ao=map(int,gg[gi]);di=int(donor[gi]);rr=dict(w=w,h=h,dm=d,br=br,tl=tl,f=int(f[gi])*1e-9,donor=di)
            gadgets.append(rr);recipe.append(dict(**rr,mode=mode,incoming_degrees=degrees[ai],outgoing_degrees=degrees[ao],origin=oriented[di][1]))
        p,kk=stitch([(j,mode)for j,(_,mode)in enumerate(chain)],gadgets,oriented)
        if kk<k:
            from packing_pipeline import border_expand
            p=border_expand(p,k-kk)
        assert len(p)==n,(n,len(p),recipe)
        gap=min_gap(p)
        if gap< -1e-9:bad.append(dict(n=n,gap=gap,recipe=recipe));continue
        winners[n]=p;records.append(dict(n=n,before=side(base[n]),after=side(p),gain=(side(base[n])-side(p))/math.sqrt(n),min_gap=gap,chain=recipe))
    np.savez_compressed(f'artifacts/{tag}_packings.npz',**{str(n):p for n,p in winners.items()})
    report=dict(baseline=baseline,seconds=time.perf_counter()-start,cuda_seconds=gpu,degrees=degrees,bins=bins,
        oriented_done=done,oriented_planned=len(oriented),populated_states=unpruned,pareto_states=ng,
        improved=len(winners),gain=sum(r['gain']for r in records),records=records,bad=bad,
        source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    Path(f'research/{tag}.json').write_text(json.dumps(report,indent=2),encoding='utf8')
    print(json.dumps({k:v for k,v in report.items()if k not in ['records','bad']}),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--baseline',required=True);p.add_argument('--seconds',type=float,default=480);p.add_argument('--bins',type=int,default=16);p.add_argument('--degrees',type=float,nargs='+',default=[30,45,60]);p.add_argument('--limit',type=int);p.add_argument('--tag',default='adaptive_seams1');a=p.parse_args();run(a.baseline,a.tag,a.seconds,a.bins,tuple(a.degrees),a.limit)
