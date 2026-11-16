#define main v11_pull_solver_main
#ifndef V11_PULL_SOURCE
#define V11_PULL_SOURCE "../candidates/v11_pull/hybrid.cpp"
#endif
#include V11_PULL_SOURCE
#undef main

static void require(bool value,const char* why) {
    if(!value) { cerr<<"FAILED "<<why<<"\n"; exit(1); }
}
static bool same(const Cache& a,const Cache& b) {
    return a.q==b.q && a.cap==b.cap && a.sum==b.sum && a.ver==b.ver &&
           equal(a.in,a.in+400,b.in);
}
static Cache makeCache(ll capacity,initializer_list<int> order={}) {
    Cache c{}; c.cap=capacity;
    for(int l:order) cachePut(c,l);
    return c;
}
static void setImage(vector<int> layers) {
    imageLayers[0]=layers;v11ImageBytes[0]=0;v11RepeatedLayer[0]=false;
    bool seen[400]={};
    for(int l:layers) if(seen[l])v11RepeatedLayer[0]=true;else {
        v11ImageBytes[0]+=layerSize[l];seen[l]=true;
    }
}
struct OracleCache {
    vector<int> order;ll capacity,bytes;
    explicit OracleCache(const Cache& c):order(c.q),capacity(c.cap),bytes(c.sum){}
    bool hit(int l) {
        auto p=find(order.begin(),order.end(),l);
        if(p==order.end())return false;
        order.erase(p);order.push_back(l);return true;
    }
    void put(int l) {
        order.push_back(l);bytes+=layerSize[l];
        while(bytes>capacity) {bytes-=layerSize[order.front()];order.erase(order.begin());}
    }
};
static pair<ll,ll> oraclePull(OracleCache& m,OracleCache& r) {
    ll registry=0,rack=0;
    for(int l:imageLayers[0]) {
        if(m.hit(l))continue;
        if(r.hit(l))rack+=layerSize[l];
        else {registry+=layerSize[l];r.put(l);}
        m.put(l);
    }
    return {registry,rack};
}
static void checkPreview(Cache& m,Cache& r) {
    Cache oldm=m,oldr=r;
    OracleCache om(m),orr(r);
    auto first=oraclePull(om,orr),second=oraclePull(om,orr);
    auto got=v11PreviewImage(m,r,0);
    require(got.first.registry==first.first && got.first.rack==first.second,"first quote matches independent oracle");
    require(got.second.registry==second.first && got.second.rack==second.second,"second quote matches independent oracle");
    require(same(m,oldm)&&same(r,oldr),"preview leaves source caches untouched");
}
int main() {
    layerSize[0]=layerSize[1]=layerSize[2]=5;
    setImage({0,1});
    Cache m=makeCache(10,{1,2}),r=makeCache(100,{0,1});
    auto got=v11PreviewImage(m,r,0);
    require(got.first.registry==0&&got.first.rack==10&&got.second.registry==0&&got.second.rack==0,"future layer eviction");
    checkPreview(m,r);
    layerSize[0]=layerSize[1]=7;setImage({0,1});
    m=makeCache(7);r=makeCache(100);got=v11PreviewImage(m,r,0);
    require(got.first.registry==14&&got.second.rack==14,"oversize warm rack residual");checkPreview(m,r);
    r=makeCache(7);got=v11PreviewImage(m,r,0);
    require(got.first.registry==14&&got.second.registry==14,"oversize warm registry residual");checkPreview(m,r);
    layerSize[0]=layerSize[1]=4;setImage({0,0,1});
    m=makeCache(8);r=makeCache(100);got=v11PreviewImage(m,r,0);
    require(got.first.registry==8&&got.second.registry==0&&got.second.rack==0,"duplicates touch once");checkPreview(m,r);
    layerSize[0]=layerSize[1]=0;setImage({0,1});m=makeCache(0);r=makeCache(0);checkPreview(m,r);
    mt19937 rng(0x11961115);
    for(int trial=0;trial<20000;++trial) {
        int n=trial%10==0?400:1+rng()%40;
        for(int l=0;l<n;++l)layerSize[l]=rng()%501;
        m=makeCache(trial%17==0?0:rng()%5001);
        r=makeCache(trial%19==0?0:rng()%7001);
        for(int i=0,k=rng()%70;i<k;++i) {int l=rng()%n;if(!cacheHit(m,l))cachePut(m,l);}
        for(int i=0,k=rng()%90;i<k;++i) {int l=rng()%n;if(!cacheHit(r,l))cachePut(r,l);}
        vector<int> layers;
        for(int i=0,k=rng()%61;i<k;++i)layers.push_back(rng()%n);
        setImage(layers);checkPreview(m,r);
    }
    cout<<"V11 exact preview:5 directed cases and20000 randomized two-RUN previews passed; source caches unchanged\n";
}
