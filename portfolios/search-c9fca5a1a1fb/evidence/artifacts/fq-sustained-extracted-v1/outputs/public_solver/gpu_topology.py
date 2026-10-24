"""Independent CUDA basin hopping: spatial hashing + per-island L-BFGS.

Every square has independent x/y/angle. Overlaps are allowed during repair;
incumbents are admitted only after independent full SAT/interval checks.
"""
import argparse,json,math,time
from pathlib import Path
import numpy as np
import cupy as cp
from scipy.spatial import cKDTree
from solver import side,normalize,grid
from gpu_families import min_gap
from hybrid_search import export

CUDA=r'''
extern "C" {
__device__ double sg(double x){return (x>1e-12)-(x < -1e-12);}
__device__ double dot(const double*a,const double*b,int m,double*r){
 double z=0;for(int k=threadIdx.x;k<m;k+=blockDim.x)z+=a[k]*b[k];
 r[threadIdx.x]=z;__syncthreads();
 for(int t=blockDim.x/2;t;t/=2){if(threadIdx.x<t)r[threadIdx.x]+=r[threadIdx.x+t];__syncthreads();}
 double answer=r[0];__syncthreads();return answer;
}
__device__ double objective(double*q,double*g,int n,double L,int nc,int*head,int*next,double*cs,double*r,double*maxpen){
 int tid=threadIdx.x;
 for(int k=tid;k<nc*nc;k+=blockDim.x)head[k]=-1;
 __syncthreads();
 for(int i=tid;i<n;i+=blockDim.x){
  cs[2*i]=cos(q[3*i+2]);cs[2*i+1]=sin(q[3*i+2]);
  int x=max(0,min(nc-1,int(floor((q[3*i]+3)/1.5))));
  int y=max(0,min(nc-1,int(floor((q[3*i+1]+3)/1.5))));
  next[i]=atomicExch(head+y*nc+x,i);
 }__syncthreads();
 double energy=0,mp=0;
 for(int i=tid;i<n;i+=blockDim.x){
  double x=q[3*i],y=q[3*i+1],c=cs[2*i],s=cs[2*i+1];
  double gx=0,gy=0,ga=0,h=.5*(fabs(c)+fabs(s)),dh=.5*(-s*sg(c)+c*sg(s));
  double b[4]={h-x,h-y,x+h-L,y+h-L};
  for(int k=0;k<4;k++)if(b[k]>0){double p=b[k];energy+=2*p*p;mp=fmax(mp,p);ga+=4*p*dh;
   if(k==0)gx-=4*p;if(k==1)gy-=4*p;if(k==2)gx+=4*p;if(k==3)gy+=4*p;}
  int cx=max(0,min(nc-1,int(floor((x+3)/1.5)))),cy=max(0,min(nc-1,int(floor((y+3)/1.5))));
  for(int yy=max(0,cy-1);yy<=min(nc-1,cy+1);yy++)for(int xx=max(0,cx-1);xx<=min(nc-1,cx+1);xx++)
   for(int j=head[yy*nc+xx];j>=0;j=next[j])if(j!=i){
    double dx=q[3*j]-x,dy=q[3*j+1]-y;if(dx*dx+dy*dy>2.00000001)continue;
    double cj=cs[2*j],sj=cs[2*j+1],cd=c*cj+s*sj,sd=c*sj-s*cj;
    double rad=.5*(1+fabs(cd)+fabs(sd))+2e-10,rd=.5*(-sd*sg(cd)+cd*sg(sd));
    double ux[4]={c,-s,cj,-sj},uy[4]={s,c,sj,cj};int a=0;double z=dx*ux[0]+dy*uy[0];
    for(int k=1;k<4;k++){double v=dx*ux[k]+dy*uy[k];if(fabs(v)>fabs(z)){a=k;z=v;}}
    double p=rad-fabs(z);if(p<=0)continue;
    energy+=.25*p*p;mp=fmax(mp,p);double sign=sg(z);
    gx+=p*sign*ux[a];gy+=p*sign*uy[a];
    ga-=p*(rd+(a<2?sign*(-dx*uy[a]+dy*ux[a]):0));
   }
  g[3*i]=gx;g[3*i+1]=gy;g[3*i+2]=ga;
 }
 r[tid]=energy;r[blockDim.x+tid]=mp;__syncthreads();
 for(int t=blockDim.x/2;t;t/=2){if(tid<t){r[tid]+=r[tid+t];r[blockDim.x+tid]=fmax(r[blockDim.x+tid],r[blockDim.x+tid+t]);}__syncthreads();}
 if(tid==0)*maxpen=r[blockDim.x];double answer=r[0];__syncthreads();return answer;
}
__global__ void eval(double*q,double*g,double*e,int n,int nc,double*Ls,int*head,int*next,double*cs){
 __shared__ double r[512],mp;
 int b=blockIdx.x;double v=objective(q+b*3*n,g+b*3*n,n,Ls[b],nc,head+b*nc*nc,next+b*n,cs+b*2*n,r,&mp);
 if(threadIdx.x==0){e[2*b]=v;e[2*b+1]=mp;}
}
__global__ void lbfgs(double*Q,double*work,double*history,double*out,int n,int nc,double*Ls,int*heads,int*links,double*trigs,int steps,int M){
 __shared__ double r[512],mp,alpha[12],rho[12],syarr[12],yyarr[12];
 int b=blockIdx.x,tid=threadIdx.x,d=3*n;
 double*q=Q+b*d,*g=work+b*d*5,*v=g+d,*trial=v+d,*gt=trial+d,*direction=gt+d;
 double*S=history+b*2*M*d,*Y=S+M*d;int*head=heads+b*nc*nc,*next=links+b*n;double*cs=trigs+b*2*n;
 double L=Ls[b],E=objective(q,g,n,L,nc,head,next,cs,r,&mp);int stored=0,last=0,its=0;
 for(int it=0;it<steps;it++){
  its=it;if(mp<2e-11)break;
  for(int k=tid;k<d;k+=blockDim.x)v[k]=g[k];__syncthreads();
  for(int j=0;j<stored;j++){int h=(last-1-j+M)%M;double z=dot(S+h*d,v,d,r)*rho[h];
   if(tid==0)alpha[h]=z;__syncthreads();for(int k=tid;k<d;k+=blockDim.x)v[k]-=z*Y[h*d+k];__syncthreads();}
  double scale=stored?fmin(10.,fmax(1e-6,syarr[(last-1+M)%M]/yyarr[(last-1+M)%M])):.2;
  for(int k=tid;k<d;k+=blockDim.x)v[k]*=scale;__syncthreads();
  for(int j=stored-1;j>=0;j--){int h=(last-1-j+M)%M;double z=dot(Y+h*d,v,d,r)*rho[h];
   double a=alpha[h]-z;for(int k=tid;k<d;k+=blockDim.x)v[k]+=a*S[h*d+k];__syncthreads();}
  for(int k=tid;k<d;k+=blockDim.x)direction[k]=-v[k];__syncthreads();
  double slope=dot(g,direction,d,r);
  if(slope>=-1e-30){for(int k=tid;k<d;k+=blockDim.x)direction[k]=-.2*g[k];__syncthreads();slope=dot(g,direction,d,r);stored=0;}
  double dm=0;for(int k=tid;k<d;k+=blockDim.x)dm=fmax(dm,fabs(direction[k]));r[tid]=dm;__syncthreads();
  for(int t=blockDim.x/2;t;t/=2){if(tid<t)r[tid]=fmax(r[tid],r[tid+t]);__syncthreads();}
  double step=fmin(1.,.2/fmax(1e-30,r[0])),En=E;bool ok=false;
  for(int ls=0;ls<24;ls++){
   for(int k=tid;k<d;k+=blockDim.x)trial[k]=q[k]+step*direction[k];__syncthreads();
   En=objective(trial,gt,n,L,nc,head,next,cs,r,&mp);
   if(En<=E+1e-4*step*slope){ok=true;break;}step*=.5;
  }
  if(!ok)break;
  for(int k=tid;k<d;k+=blockDim.x){v[k]=trial[k]-q[k];direction[k]=gt[k]-g[k];}__syncthreads();
  double sy=dot(v,direction,d,r),yy=dot(direction,direction,d,r);
  if(sy>1e-24&&yy>1e-30){for(int k=tid;k<d;k+=blockDim.x){S[last*d+k]=v[k];Y[last*d+k]=direction[k];}__syncthreads();
   if(tid==0){rho[last]=1/sy;syarr[last]=sy;yyarr[last]=yy;}__syncthreads();last=(last+1)%M;stored=min(M,stored+1);}
  for(int k=tid;k<d;k+=blockDim.x){q[k]=trial[k];g[k]=gt[k];}__syncthreads();E=En;
 }
 if(tid==0){out[3*b]=E;out[3*b+1]=mp;out[3*b+2]=its;}
}
}
'''
mod=cp.RawModule(code=CUDA,options=('--std=c++17',),name_expressions=['eval','lbfgs'])

def buffers(q,L):
    q=cp.asarray(q,dtype=cp.float64);B,n,_=q.shape;nc=int(math.ceil((max(L)+6)/1.5))+1
    return q,n,nc,cp.asarray(L,dtype=cp.float64),cp.empty((B,nc*nc),cp.int32),cp.empty((B,n),cp.int32),cp.empty((B,n,2),cp.float64)

def energy(q,L):
    q,n,nc,L,h,l,cs=buffers(q,L);g=cp.empty_like(q);e=cp.empty((len(q),2),cp.float64)
    mod.get_function('eval')((len(q),),(256,),(q,g,e,np.int32(n),np.int32(nc),L,h,l,cs))
    return cp.asnumpy(e),cp.asnumpy(g)

def quench(q,L,steps=1200):
    q,n,nc,L,h,l,cs=buffers(q,L);B=len(q);M=8
    work=cp.empty((B,5,n,3),cp.float64);hist=cp.empty((B,2,M,n,3),cp.float64);out=cp.empty((B,3),cp.float64)
    mod.get_function('lbfgs')((B,),(256,),(q,work,hist,out,np.int32(n),np.int32(nc),L,h,l,cs,np.int32(steps),np.int32(M)))
    return cp.asnumpy(q),cp.asnumpy(out)

def check():
    rng=np.random.default_rng(17);q=rng.uniform(.4,2.5,(1,5,3));q[:,:,2]*=.2
    e,g=energy(q,[3.]);errs=[]
    for i,k in [(0,0),(1,2),(3,1),(4,2)]:
        plus=q.copy();minus=q.copy();plus[0,i,k]+=1e-6;minus[0,i,k]-=1e-6
        fd=(energy(plus,[3.])[0][0,0]-energy(minus,[3.])[0][0,0])/2e-6
        errs.append(abs(fd-g[0,i,k]))
    assert max(errs)<1e-6,errs
    qq,o=quench(q,[3.],100)
    assert o[0,0]<e[0,0],(e,o)
    print('CUDA analytic gradient / descent checks passed',max(errs),flush=True)

def reinsert(p,rng,count):
    """Destroy a spatial region; insert into sampled largest holes, new angles."""
    n=len(p);L=side(p);pivot=p[rng.integers(n),:2]
    ids=np.argsort(np.sum((p[:,:2]-pivot)**2,axis=1))[:count]
    keep=np.ones(n,bool);keep[ids]=False;xy=p[keep,:2].copy()
    for i in ids:
        cand=rng.uniform(.6,max(.6001,L-.6),(256,2));dist=cKDTree(xy).query(cand)[0] if len(xy) else np.ones(256)
        pos=cand[np.argmax(dist)];p[i,:2]=pos;p[i,2]=rng.choice([0,np.pi/4,rng.uniform(-np.pi/4,np.pi/4)])
        xy=np.vstack((xy,pos))
    return p

def starts(n,bank,refs,rng,B,roundno,archive=None):
    base=normalize(bank[n],0);L=side(base);seeds=[base]
    seeds.extend(normalize(np.array(r['packing']),0) for r in refs if r['N']==n and r['L']<L*1.04)
    if n%4==0 and n//4 in bank:
        old=normalize(bank[n//4],0);parts=[]
        for x,y,a in old:
            co,si=np.cos(a),np.sin(a);rot=np.array([[co,si],[-si,co]])
            for off in [[-.5,-.5],[.5,-.5],[-.5,.5],[.5,.5]]:parts.append([*(np.array(off)@rot+2*np.array([x,y])),a])
        seeds.append(normalize(np.array(parts),0))
    if archive:seeds.extend(archive)
    seeds.append(normalize(grid(n),0))
    qs=[];kinds=[]
    for b in range(B):
        q=seeds[b%len(seeds)].copy();q[:,:2]*=(L-1)/(max(1e-9,side(q)-1))
        kind=b%6
        if b<2:kind=0
        if kind==0:q[:,:2]+=rng.normal(0,.0003,q[:,:2].shape);q[:,2]+=rng.normal(0,.0002,n)
        elif kind==1:
            ids=np.argsort(np.sum((q[:,:2]-q[rng.integers(n),:2])**2,axis=1))[:max(3,n//8)]
            a=rng.uniform(-.4,.4);c,s=np.cos(a),np.sin(a);xy=q[ids,:2].mean(0)
            q[ids,:2]=(q[ids,:2]-xy)@np.array([[c,s],[-s,c]])+xy+rng.normal(0,.2,2);q[ids,2]+=a
        elif kind==2:q=reinsert(q,rng,max(2,n//12))
        elif kind==3:
            q[:,:2]+=rng.normal(0,.05,q[:,:2].shape);q[:,2]+=rng.normal(0,.08,n)
        elif kind==4:
            cut=rng.uniform(.2,.8)*L;ids=q[:,1]>cut;q[ids,0]+=rng.choice([-.35,.35]);q[ids,2]+=rng.uniform(-.1,.1)
        else:
            # Crossover: retain one half, replace the other by a different seed.
            other=seeds[(b+1)%len(seeds)];ids=np.argsort(q[:,0]);other=other[np.argsort(other[:,0])]
            q[ids[n//2:]]=other[n//2:];q[:,0]+=rng.normal(0,.02,n)
        qs.append(q);kinds.append(kind)
    return np.array(qs),kinds

def repair_tiny(p):
    """Pair-specific clearance correction; reject large expansions."""
    p=normalize(p,0);pairs=cKDTree(p[:,:2]).query_pairs(1.415,output_type='ndarray')
    if not len(pairs):return p
    i,j=pairs.T;d=p[j,:2]-p[i,:2];a=p[i,2];b=p[j,2]
    z=np.maximum.reduce([np.abs(d[:,0]*np.cos(a)+d[:,1]*np.sin(a)),np.abs(-d[:,0]*np.sin(a)+d[:,1]*np.cos(a)),np.abs(d[:,0]*np.cos(b)+d[:,1]*np.sin(b)),np.abs(-d[:,0]*np.sin(b)+d[:,1]*np.cos(b))])
    rad=.5*(1+np.abs(np.cos(a-b))+np.abs(np.sin(a-b)))
    factor=max(1.,float(np.max((rad+2e-10)/np.maximum(z,1e-30))))
    if factor>1.00002:return None
    p[:,:2]*=factor;return normalize(p,0)

def search(seconds=240,B=96,steps=1600,ns=None,input_path='artifacts/gpu_deep_packings.npz',tag='gpu_topology',staged=False):
    check();loaded=np.load(input_path);bank={int(n):loaded[n] for n in loaded.files}
    refs=json.loads(Path('artifacts/recent_references.json').read_text());rng=np.random.default_rng(20261022)
    if ns is None:ns=[17,27,34,51,68,80,109,126,143,167,211,241,273,307,500,645,646,804]
    start=time.perf_counter();rows=[];hits=[];roundno=0;archives={}
    while time.perf_counter()-start<seconds:
        n=ns[roundno%len(ns)];old=side(bank[n]);q,kinds=starts(n,bank,refs,rng,B,roundno,archives.get(n))
        # Different requested contractions prevent all islands following one basin.
        target=old-np.geomspace(2e-7,.025,B);at=time.perf_counter()
        archived=0
        if staged:
            # Make room to cross contact barriers, retaining several alternative basins.
            direct=q[:2].copy()
            loose=old+np.linspace(.015,.25,B)
            q,soft=quench(q,loose,max(500,steps//2))
            candidates=[];signatures=set()
            for b in np.argsort(soft[:,0]):
                if soft[b,1]>1e-6:continue
                p=repair_tiny(q[b])
                if p is None or side(p)>old+.3:continue
                # Coarse spatial/orientation occupancy removes near-duplicate islands.
                signature=tuple(np.histogramdd(np.column_stack((p[:,:2]/old,p[:,2]%(np.pi/2))),bins=(6,6,4),range=((0,1),(0,1),(0,np.pi/2)))[0].astype(int).ravel())
                if signature in signatures:continue
                signatures.add(signature);candidates.append(p)
                if len(candidates)>=8:break
            if candidates:archives[n]=candidates
            archived=len(candidates);q[:2]=direct
            q,_=quench(q,np.full(B,old+.003),max(400,steps//2))
        q,stats=quench(q,target,steps);feasible=0
        for b in np.argsort(stats[:,0]):
            if stats[b,1]>1e-5:continue
            p=repair_tiny(q[b])
            if p is not None and side(p)<side(bank[n])-5e-8 and min_gap(p)>-2e-10:
                feasible+=1;before=side(bank[n]);bank[n]=p;hits.append(dict(n=n,before=before,after=side(p),mutation=kinds[b],island=int(b),round=roundno))
        row=dict(round=roundno,n=n,seconds=time.perf_counter()-at,islands=B,before=old,after=side(bank[n]),best_penetration=float(stats[:,1].min()),minimum_energy=float(stats[:,0].min()),mean_iterations=float(stats[:,2].mean()),improvements=feasible,diverse_loose_basins=archived)
        rows.append(row);roundno+=1
        np.savez_compressed(f'artifacts/{tag}_packings.npz',**{str(n):p for n,p in bank.items()})
        Path(f'research/{tag}_status.json').write_text(json.dumps(dict(seconds=time.perf_counter()-start,algorithm='Spatial hash, independent per-island L-BFGS and destroy/reinsert/block/crossover starts',staged=staged,rows=rows,hits=hits),indent=2))
        print(json.dumps(row),flush=True)
    export(f'artifacts/{tag}_submission.csv',bank,margin=4e-9)
    return bank,hits

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--seconds',type=float,default=240);a.add_argument('--islands',type=int,default=96);a.add_argument('--steps',type=int,default=1600);a.add_argument('--check',action='store_true');a.add_argument('--ns',type=int,nargs='*');a.add_argument('--input',default='artifacts/gpu_deep_packings.npz');a.add_argument('--tag',default='gpu_topology');a.add_argument('--staged',action='store_true');args=a.parse_args()
    if args.check:check()
    else:search(args.seconds,args.islands,args.steps,args.ns,args.input,args.tag,args.staged)
