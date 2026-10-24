// Bounded finite minimax proposal DP. Geometry acceptance belongs to Python.
#include <algorithm>
#include <cmath>
#include <iomanip>
#include <iostream>
#include <set>
#include <string>
#include <tuple>
#include <vector>
constexpr int B=6, SIZE=32*32*64;
struct Type{int w,h,d;double f;};
struct Node{double f=2.;int g=-1,mode=-1,prev=-1,rank=-1,zeros=0,length=0;};
int index(int w,int h,int d){return (w*32+h)*64+d;}
int main(){
 std::ios::sync_with_stdio(false);std::cin.tie(nullptr);std::cout<<std::setprecision(17);
 int ng,nb,nq;if(!(std::cin>>ng>>nb>>nq)||ng<1||ng>20000||nb<0||nq<1)return 2;
 std::vector<Type> types(ng);for(auto&t:types){std::cin>>t.w>>t.h>>t.d>>t.f;if(t.w<1||t.h<1||t.w>31||t.h>31||t.d<1||t.d>63||!(t.f>0&&t.f<1))return 3;}
 std::set<std::pair<int,int>> forbidden;
 for(int i=0,a,b;i<nb;i++){std::cin>>a>>b;forbidden.insert({a,b});}
 std::vector<std::tuple<int,int,int>> queries;
 for(int i=0,n,k,d;i<nq;i++){std::cin>>n>>k>>d;queries.emplace_back(n,k,d);}
 std::vector<Node> dp(SIZE*B);
 auto add=[&](int state,Node q){
  Node* a=dp.data()+state*B;
  // Preserve distinct last/penultimate types and modes at the same minimax
  // cost rather than filling the small beam with equivalent order traces.
  int pg=q.prev>=0?dp[q.prev*B+q.rank].g:-1;
  for(int j=0;j<B;j++)if(a[j].g==q.g&&a[j].mode==q.mode){
   int oldpg=a[j].prev>=0?dp[a[j].prev*B+a[j].rank].g:-1;
   if(pg==oldpg){
    if(std::tie(q.f,q.zeros,q.length)>=std::tie(a[j].f,a[j].zeros,a[j].length))return;
    for(int k=j;k+1<B;k++)a[k]=a[k+1];a[B-1]=Node{};break;
   }
  }
  int at=B;for(int j=0;j<B;j++)if(std::tie(q.f,q.zeros,q.length)<std::tie(a[j].f,a[j].zeros,a[j].length)){at=j;break;}
  if(at<B){for(int j=B-1;j>at;j--)a[j]=a[j-1];a[at]=q;}
 };
 for(int sum=2;sum<=62;sum++)for(int w=1;w<=31;w++){
  int h=sum-w;if(h<1||h>31)continue;
  for(int d=1;d<=63;d++)for(int gi=0;gi<ng;gi++){
   const auto&g=types[gi];if(g.w>w||g.h>h||g.d>d)continue;
   int dst=index(w,h,d);
   if(g.w==w&&g.h==h&&g.d==d){add(dst,Node{g.f,gi,3,-1,-1,0,1});continue;}
   if(g.d==d)continue;
   for(int mode=0;mode<3;mode++){
    int x=w-g.w-(mode==1),y=h-g.h-(mode==2);if(x<1||y<1)continue;
    int prev=index(x,y,d-g.d);
    for(int rank=0;rank<B;rank++){
     const Node&p=dp[prev*B+rank];if(p.g<0)break;
     if(mode==0&&forbidden.count({p.g,gi}))continue;
     add(dst,Node{std::max(p.f,g.f),gi,mode,prev,rank,p.zeros+(mode==0),p.length+1});
    }
   }
  }
 }
 for(auto[n,k,d]:queries){
  std::vector<std::pair<int,int>> order;
  for(int w=1;w<=k;w++)for(int h=1;h<=k;h++)for(int rank=0;rank<B;rank++)if(dp[index(w,h,d)*B+rank].g>=0)order.push_back({index(w,h,d),rank});
  std::sort(order.begin(),order.end(),[&](auto a,auto b){const auto&x=dp[a.first*B+a.second];const auto&y=dp[b.first*B+b.second];return std::tie(x.f,x.zeros,x.length,a)<std::tie(y.f,y.zeros,y.length,b);});
  std::set<std::vector<std::pair<int,int>>> seen;int emitted=0;
  for(auto[state,rank]:order){
   const Node&end=dp[state*B+rank];std::vector<std::pair<int,int>> chain;
   for(int guard=0;;guard++){
    if(guard>63)return 4;const Node&q=dp[state*B+rank];chain.push_back({q.g,q.mode});
    if(q.mode==3)break;state=q.prev;rank=q.rank;if(state<0||rank<0)return 5;
   }
   std::reverse(chain.begin(),chain.end());if(!seen.insert(chain).second)continue;
   std::cout<<"{\"n\":"<<n<<",\"f\":"<<end.f<<",\"chain\":[";
   for(size_t i=0;i<chain.size();i++){if(i)std::cout<<',';std::cout<<'['<<chain[i].first<<','<<chain[i].second<<']';}
   std::cout<<"]}\n";if(++emitted==8)break;
  }
 }
}
