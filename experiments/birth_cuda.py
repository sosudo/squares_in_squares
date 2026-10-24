"""Separate FP64 proposal-only mixed-size physical-energy CUDA optimizer.

The pinned public L-BFGS/storage skeleton is reused, but its objective is a
new explicit mixed-size SAT objective. Original unit-only sources are untouched.
The last row alone has variable size; all other unit squares may move globally.
"""
from __future__ import annotations
import ast
import hashlib
import math
from pathlib import Path
import numpy as np

OPTIONS=('--std=c++17','--fmad=false')
OBJECTIVE=r'''
__device__ double objective(double*q,double*g,int n,double L,double birth,int nc,int*head,int*next,double*cs,double*r,double*maxpen){
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
  double x=q[3*i],y=q[3*i+1],c=cs[2*i],s=cs[2*i+1],si=(i==n-1?birth:1.);
  double gx=0,gy=0,ga=0,h=.5*si*(fabs(c)+fabs(s)),dh=.5*si*(-s*sg(c)+c*sg(s));
  double b[4]={h-x,h-y,x+h-L,y+h-L};
  for(int k=0;k<4;k++)if(b[k]>0){double p=b[k];energy+=p*p;mp=fmax(mp,p);ga+=2*p*dh;
   if(k==0)gx-=2*p;if(k==1)gy-=2*p;if(k==2)gx+=2*p;if(k==3)gy+=2*p;}
  int cx=max(0,min(nc-1,int(floor((x+3)/1.5)))),cy=max(0,min(nc-1,int(floor((y+3)/1.5))));
  for(int yy=max(0,cy-1);yy<=min(nc-1,cy+1);yy++)for(int xx=max(0,cx-1);xx<=min(nc-1,cx+1);xx++)
   for(int j=head[yy*nc+xx];j>=0;j=next[j])if(j!=i){
    double dx=q[3*j]-x,dy=q[3*j+1]-y;if(dx*dx+dy*dy>2.00000001)continue;
    double cj=cs[2*j],sj=cs[2*j+1],ssize=(j==n-1?birth:1.);
    double cd=c*cj+s*sj,sd=c*sj-s*cj,C=fabs(cd)+fabs(sd),rd=.5*(-sd*sg(cd)+cd*sg(sd));
    double ux[4]={c,-s,cj,-sj},uy[4]={s,c,sj,cj},depth[4],z[4];
    double p=1e300;
    for(int k=0;k<4;k++){
     z[k]=dx*ux[k]+dy*uy[k];
     double rad=(k<2?.5*si+.5*ssize*C:.5*ssize+.5*si*C);
     depth[k]=rad-fabs(z[k]);p=fmin(p,depth[k]);
    }
    if(p<=0)continue;
    energy+=.5*p*p;mp=fmax(mp,p);
    double sumx=0,sumy=0,suma=0;
    int approaches=((i==n-1||j==n-1)&&birth<1.?2:1);
    for(int approach=0;approach<approaches;approach++){
     double direction=(approach==0?-1.:1.),sign_c=sg(cd),sign_s=sg(sd),dd[4];
     if(approaches==2){
      double relative_direction=(j==n-1?direction:-direction);
      double cd_dot=-sd*relative_direction,sd_dot=cd*relative_direction;
      if(cd==0)sign_c=sg(cd_dot);if(sd==0)sign_s=sg(sd_dot);
      double Cdot=sign_c*cd_dot+sign_s*sd_dot;
      for(int k=0;k<4;k++){
       bool owner_is_birth=(k<2?i==n-1:j==n-1);
       double zdot=owner_is_birth?direction*(-dx*uy[k]+dy*ux[k]):0.;
       double sign_z=(z[k]!=0?sg(z[k]):sg(zdot));
       dd[k]=.5*(k<2?ssize:si)*Cdot-sign_z*zdot;
      }
     }else for(int k=0;k<4;k++)dd[k]=0.;
     double best=1e300;for(int k=0;k<4;k++)if(depth[k]==p)best=fmin(best,dd[k]);
     int count=0;double tx=0,ty=0,ta=0,rd_limit=.5*(-sd*sign_c+cd*sign_s);
     for(int k=0;k<4;k++)if(depth[k]==p&&dd[k]==best){
      bool owner_is_birth=(k<2?i==n-1:j==n-1);
      double zdot=(approaches==2&&owner_is_birth)?direction*(-dx*uy[k]+dy*ux[k]):0.;
      double sign=(z[k]!=0?sg(z[k]):sg(zdot));
      count++;tx+=sign*ux[k];ty+=sign*uy[k];
      ta+=(k<2?ssize*rd_limit+sign*(-dx*uy[k]+dy*ux[k]):si*rd_limit);
     }
     sumx+=tx/count;sumy+=ty/count;suma+=ta/count;
    }
    gx+=2*p*sumx/approaches;gy+=2*p*sumy/approaches;ga-=2*p*suma/approaches;
   }
  g[3*i]=gx;g[3*i+1]=gy;g[3*i+2]=ga;
 }
 r[tid]=energy;r[blockDim.x+tid]=mp;__syncthreads();
 for(int t=blockDim.x/2;t;t/=2){if(tid<t){r[tid]+=r[tid+t];r[blockDim.x+tid]=fmax(r[blockDim.x+tid],r[blockDim.x+tid+t]);}__syncthreads();}
 if(tid==0)*maxpen=r[blockDim.x];double answer=r[0];__syncthreads();return answer;
}
'''


def mixed_cuda_source(path):
    """AST-load a literal only; do not import/execute the upstream GPU module."""
    text=Path(path).read_text();tree=ast.parse(text)
    values=[ast.literal_eval(node.value)for node in tree.body if isinstance(node,ast.Assign)
            and any(isinstance(t,ast.Name)and t.id=='CUDA'for t in node.targets)]
    if len(values)!=1:raise ValueError('Expected one upstream CUDA literal')
    original=values[0]
    # Pin the upstream string independently of surrounding Python import code.
    sha=hashlib.sha256(original.encode()).hexdigest()
    if sha!='c1452753438fb9644446c375a06dd4ad66466985232bd06d31f4ba5502b97989':
        raise ValueError('Unexpected pinned optimizer skeleton SHA '+sha)
    start=original.index('__device__ double objective(');end=original.index('__global__ void eval(',start)
    source=original[:start]+OBJECTIVE+original[end:]
    replacements={
        'return (x>1e-12)-(x < -1e-12);':'return (x>0)-(x<0);',
        'double*Ls,int*head':'double*Ls,double*Births,int*head',
        'n,Ls[b],nc,':'n,Ls[b],Births[b],nc,',
        'double L=Ls[b],E=':'double L=Ls[b],birth=Births[b],E=',
        'n,L,nc,':'n,L,birth,nc,'}
    counts={}
    for old,new in replacements.items():
        counts[old]=source.count(old)
        if not counts[old]:raise ValueError('Missing expected upstream skeleton expression')
        source=source.replace(old,new)
    return source,dict(upstream_literal_sha256=sha,mixed_source_sha256=hashlib.sha256(source.encode()).hexdigest(),
        skeleton_replacements=counts,objective='Unordered pair penetration squared plus four wall penetration squared',
        sizes='Only row n-1 has birth size, every other row side1',
        broad_phase='Original1.5 cells, radius sqrt2; conservative because all sides<=1',
        tie_rule='Mixed pairs: rank exact active depths by one-sided birth-angle depth derivatives, then average both limiting gradients. Uniform averaging only over remaining selected ties; unit-only pairs retain symmetric exact active-axis averaging.',compiler_options=list(OPTIONS),
        original_unit_source_modified=False,proposal_only=True)


class Solver:
    def __init__(self,cp,path):
        self.cp=cp;self.source,self.audit=mixed_cuda_source(path)
        self.module=cp.RawModule(code=self.source,options=OPTIONS,name_expressions=['eval','lbfgs'])

    def buffers(self,poses,sides,birth_size):
        cp=self.cp;q=cp.array(poses,dtype=cp.float64,copy=True,order='C')
        if q.ndim!=3 or q.shape[2]!=3 or q.shape[1]<2 or not bool(cp.isfinite(q).all()):raise ValueError('Invalid poses')
        B,n,_=q.shape;sides=np.asarray(sides,dtype=np.float64)
        births=np.broadcast_to(np.asarray(birth_size,dtype=np.float64),(B,)).copy()
        if sides.shape!=(B,)or not np.isfinite(sides).all()or min(sides)<=0 or not np.isfinite(births).all()or not ((births>0)&(births<=1)).all():
            raise ValueError('Invalid fixed boxes or birth size')
        nc=int(np.ceil((sides.max()+6)/1.5))+1
        return q,B,n,nc,cp.asarray(sides),cp.asarray(births),cp.empty((B,nc*nc),cp.int32),cp.empty((B,n),cp.int32),cp.empty((B,n,2),cp.float64)

    def energy(self,poses,sides,birth_size):
        cp=self.cp;q,B,n,nc,L,bs,h,l,cs=self.buffers(poses,sides,birth_size)
        g=cp.empty_like(q);e=cp.empty((B,2),cp.float64)
        self.module.get_function('eval')((B,),(256,),(q,g,e,np.int32(n),np.int32(nc),L,bs,h,l,cs))
        return cp.asnumpy(e),cp.asnumpy(g)

    def quench(self,poses,sides,birth_size,steps=400):
        """Fresh work/history allocation per growth stage or within-size quench."""
        if not isinstance(steps,int)or not 0<=steps<=1600:raise ValueError('Bounded steps required')
        cp=self.cp;q,B,n,nc,L,bs,h,l,cs=self.buffers(poses,sides,birth_size);M=8
        work=cp.empty((B,5,n,3),cp.float64);hist=cp.empty((B,2,M,n,3),cp.float64);out=cp.empty((B,3),cp.float64)
        self.module.get_function('lbfgs')((B,),(256,),(q,work,hist,out,np.int32(n),np.int32(nc),L,bs,h,l,cs,np.int32(steps),np.int32(M)))
        return cp.asnumpy(q),cp.asnumpy(out)
