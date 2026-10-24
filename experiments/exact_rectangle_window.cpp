// Exact maximum-depth sweep for closed binary64 rectangular-window constraints.
// Adapted from this project's proven exact_square_window.cpp; tree/event logic unchanged.
// No geometry acceptance is claimed here; the Python caller certifies subsets.
#include <algorithm>
#include <cmath>
#include <iomanip>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

struct Box { double x0,y0,x1,y1; };
struct Rect { double x0,x1,y0,y1; int id,lo,hi; };
struct Event { double x; int rectangle,delta; };
struct Tree {
    int n;
    std::vector<int> mx,lazy,pos;
    explicit Tree(int count):n(count),mx(4*count),lazy(4*count),pos(4*count) { init(1,0,n-1); }
    void init(int v,int lo,int hi) {
        pos[v]=lo;
        if(lo==hi)return;
        int mid=(lo+hi)/2;init(v*2,lo,mid);init(v*2+1,mid+1,hi);
    }
    void add(int v,int lo,int hi,int a,int b,int delta) {
        if(a<=lo&&hi<=b){mx[v]+=delta;lazy[v]+=delta;return;}
        int mid=(lo+hi)/2;
        if(a<=mid)add(v*2,lo,mid,a,b,delta);
        if(b>mid)add(v*2+1,mid+1,hi,a,b,delta);
        int child=mx[v*2]>=mx[v*2+1]?v*2:v*2+1;
        mx[v]=lazy[v]+mx[child];pos[v]=pos[child];
    }
    void add(int a,int b,int delta){add(1,0,n-1,a,b,delta);}
};

void query(const std::vector<Box>& boxes,double width,double height) {
    if(!std::isfinite(width)||!std::isfinite(height)||width<=0||height<=0)throw std::runtime_error("invalid rectangle");
    std::vector<Rect> rectangles;
    std::vector<double> ys;
    for(int i=0;i<(int)boxes.size();++i){
        const auto& p=boxes[i];
        Rect r{p.x1-width,p.x0,p.y1-height,p.y0,i,0,0};
        if(r.x0<=r.x1&&r.y0<=r.y1){rectangles.push_back(r);ys.push_back(r.y0);ys.push_back(r.y1);}
    }
    if(rectangles.empty()){std::cout<<"{\"count\":0,\"x\":0,\"y\":0,\"ids\":[]}\n"<<std::flush;return;}
    std::sort(ys.begin(),ys.end());ys.erase(std::unique(ys.begin(),ys.end()),ys.end());
    std::vector<Event> events;
    for(int i=0;i<(int)rectangles.size();++i){
        auto& r=rectangles[i];
        r.lo=std::lower_bound(ys.begin(),ys.end(),r.y0)-ys.begin();
        r.hi=std::lower_bound(ys.begin(),ys.end(),r.y1)-ys.begin();
        events.push_back({r.x0,i,1});events.push_back({r.x1,i,-1});
    }
    std::sort(events.begin(),events.end(),[](const Event&a,const Event&b){return a.x<b.x;});
    Tree tree(ys.size());int best=0;double bx=0,by=0;
    for(size_t i=0;i<events.size();){
        size_t end=i+1;while(end<events.size()&&events[end].x==events[i].x)++end;
        // Closed endpoints: add every interval starting here, query, then
        // remove intervals ending here (including zero-width rectangles).
        for(size_t j=i;j<end;++j)if(events[j].delta==1){const auto&r=rectangles[events[j].rectangle];tree.add(r.lo,r.hi,1);}
        if(tree.mx[1]>best){best=tree.mx[1];bx=events[i].x;by=ys[tree.pos[1]];}
        for(size_t j=i;j<end;++j)if(events[j].delta==-1){const auto&r=rectangles[events[j].rectangle];tree.add(r.lo,r.hi,-1);}
        i=end;
    }
    std::vector<int> ids;
    for(const auto&r:rectangles)if(r.x0<=bx&&bx<=r.x1&&r.y0<=by&&by<=r.y1)ids.push_back(r.id);
    if((int)ids.size()!=best)throw std::runtime_error("sweep/extraction count mismatch");
    std::cout<<"{\"count\":"<<best<<",\"x\":"<<bx<<",\"y\":"<<by<<",\"ids\":[";
    for(size_t i=0;i<ids.size();++i){if(i)std::cout<<',';std::cout<<ids[i];}
    std::cout<<"]}\n"<<std::flush;
}

int main(){
    std::ios::sync_with_stdio(false);std::cin.tie(nullptr);std::cout<<std::setprecision(17);
    try {
        std::vector<Box> boxes;std::string command;
        while(std::cin>>command){
            if(command=="LOAD"){
                int count;if(!(std::cin>>count)||count<1||count>200000)throw std::runtime_error("invalid count");
                boxes.resize(count);
                for(auto&b:boxes){
                    if(!(std::cin>>b.x0>>b.y0>>b.x1>>b.y1)||!std::isfinite(b.x0)||!std::isfinite(b.y0)||!std::isfinite(b.x1)||!std::isfinite(b.y1)||b.x0>b.x1||b.y0>b.y1)throw std::runtime_error("invalid bbox");
                }
                std::cout<<"{\"loaded\":"<<count<<"}\n"<<std::flush;
            }else if(command=="QUERY"){
                double width,height;if(!(std::cin>>width>>height)||boxes.empty())throw std::runtime_error("query without source");query(boxes,width,height);
            }else if(command=="EXIT")return 0;
            else throw std::runtime_error("unknown command");
        }
    }catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 2;}
}
