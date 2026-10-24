"""Batched CUDA upright refill bounds using exact weighted whole-row DP.

Each row mixes left/right wall lattice phases with exact 1-D greedy MIS.
Whole rows use a weighted path MIS; a transposed pass handles columns.
This is a feasible seed family, not global 2-D MIS. Soft core overlaps are
allowed only during exploration and must subsequently be repaired/certified.
"""
import cupy as cp
import numpy as np
CUDA=r'''
extern "C" __global__ void refill(const float*core,int m,int w,int h,float f,
 int total,float soft,float*out,int*capacity){
 int b=blockIdx.x,swap=blockIdx.y,tid=threadIdx.x;
 int width=swap?h:w,height=swap?w:h,rows=2*height,job=2*b+swap;
 __shared__ float tx[192],ty[192],co[192],si[192],positions[64][32];
 __shared__ int count[64],dp[65],choice[64];
 for(int k=tid;k<m;k+=blockDim.x){float a=core[(b*m+k)*3+2];
  tx[k]=core[(b*m+k)*3+(swap?1:0)];ty[k]=core[(b*m+k)*3+(swap?0:1)];
  co[k]=swap?sinf(a):cosf(a);si[k]=swap?cosf(a):sinf(a);
 }__syncthreads();
 if(tid<rows){
  float y=.5f+tid/2+(tid%2)*f,last=-10.f;int n=0;
  for(int j=0;j<2*width;j++){
   float x=.5f+j/2+(j%2)*f;if(x-last<.999998f)continue;
   bool good=true;
   for(int k=0;k<m;k++){
    float dx=x-tx[k],dy=y-ty[k],c=co[k],s=si[k];
    float rad=.5f*(1.f+fabsf(c)+fabsf(s));
    float z=fmaxf(fmaxf(fabsf(dx),fabsf(dy)),fmaxf(fabsf(dx*c+dy*s),fabsf(-dx*s+dy*c)));
    if(z<rad-soft-2e-6f){good=false;break;}
   }
   if(good){positions[tid][n++]=x;last=x;}
  }count[tid]=n;
 }__syncthreads();
 if(tid==0){
  dp[0]=0;
  for(int r=0;r<rows;r++){int take=count[r]+(r>=1?dp[r-1]:0);choice[r]=take>dp[r];dp[r+1]=max(dp[r],take);}
  capacity[job]=m+dp[rows];
  float*q=out+job*total*3;
  for(int k=0;k<m;k++)for(int d=0;d<3;d++)q[3*k+d]=core[(b*m+k)*3+d];
  int n=m;
  for(int r=rows-1;r>=0&&n<total;){
   if(!choice[r]){r--;continue;}
   float y=.5f+r/2+(r%2)*f;
   for(int j=0;j<count[r]&&n<total;j++){
    float x=positions[r][j];q[3*n]=swap?y:x;q[3*n+1]=swap?x:y;q[3*n+2]=0.f;n++;
   }r-=2;
  }
 }
}'''
kernel=cp.RawKernel(CUDA,'refill')
def refill_batch(core,w,h,f,total,soft=.008):
    core=cp.asarray(core,dtype=cp.float32);B,m,_=core.shape
    assert m<=192 and w<=31 and h<=31 and 0<=f<1
    out=cp.zeros((2*B,total,3),cp.float32);counts=cp.empty(2*B,cp.int32)
    kernel((B,2),(128,),(core,np.int32(m),np.int32(w),np.int32(h),np.float32(f),np.int32(total),np.float32(soft),out,counts))
    return out,counts
def check():
    from upright_refill import gaps
    p,c=refill_batch(np.empty((1,0,3)),3,3,.2,9,soft=0.)
    counts=cp.asnumpy(c);q=cp.asnumpy(p);assert min(counts)==9 and all(gaps(r)>-2e-6 for r in q)
    core=np.array([[[1.5,1.5,.3]]]);p,c=refill_batch(core,4,4,.1,8,soft=0.)
    counts=cp.asnumpy(c);q=cp.asnumpy(p)
    good=[i for i,k in enumerate(counts)if k>=8];assert good and all(gaps(q[i])>-3e-6 for i in good)
    return dict(empty_grid_capacity=9,tilted_feasible_row_families=len(good))
