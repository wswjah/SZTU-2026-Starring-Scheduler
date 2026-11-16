#define main v10_original_main
#include "../versions/v8_fine/main.cpp"
#undef main

static void require(bool ok,const char* message) {
    if(!ok) {std::cerr<<"FAILED "<<message<<'\n';std::exit(1);}
}

static void cacheOracle() {
    std::mt19937 rng(103991);
    for(int i=0;i<400;++i)layerSize[i]=1+rng()%200;
    for(int trial=0;trial<100;++trial) {
        Cache cache{};cache.cap=rng()%501;
        std::list<int> oracle;
        for(int step=0;step<300;++step) {
            int layer=rng()%400;
            auto pos=std::find(oracle.begin(),oracle.end(),layer);
            bool hit=pos!=oracle.end();
            require(cacheHit(cache,layer)==hit,"LRU hit agrees with list oracle");
            if(hit)oracle.erase(pos);
            else cachePut(cache,layer);
            oracle.push_back(layer);
            auto sum=[&](){long long total=0;for(int l:oracle)total+=layerSize[l];return total;};
            while(sum()>cache.cap)oracle.pop_front();
            require(std::vector<int>(oracle.begin(),oracle.end())==cache.q,"LRU order exact including oversized layers");
            require(cache.sum==sum(),"LRU byte sum exact");
            for(int l=0;l<400;++l)
                require(bool(cache.in[l])==(std::find(oracle.begin(),oracle.end(),l)!=oracle.end()),"LRU membership exact");
        }
    }
}

static void slackOracle() {
    std::mt19937 rng(104021);
    long long comparisons=0;
    for(int trial=0;trial<400;++trial) {
        int count=1+rng()%70,offset=rng()%30;
        jobs.assign(offset,Job{});flows.assign(1,Flow{});
        flows[0].first=offset;flows[0].n=count;
        for(int i=0;i<count;++i) {
            Job job{};job.wf=0;job.e=1+rng()%1000000;
            for(int p=0;p<i;++p)if(rng()%12==0)job.pre.push_back(offset+p);
            bool mayDone=true;for(int p:job.pre)mayDone&=jobs[p].state==2;
            job.state=mayDone&&rng()%3==0?2:0;
            jobs.push_back(job);
            for(int p:job.pre)jobs[p].suc.push_back(offset+i);
        }
        std::vector<long long> es(count,-1),tail(count,-1);
        std::function<long long(int)> before=[&](int i)->long long {
            if(es[i]>=0)return es[i];
            es[i]=0;for(int p:jobs[offset+i].pre)if(jobs[p].state<2)
                es[i]=std::max(es[i],before(p-offset)+jobs[p].e);
            return es[i];
        };
        std::function<long long(int)> after=[&](int i)->long long {
            if(tail[i]>=0)return tail[i];
            long long suffix=0;for(int s:jobs[offset+i].suc)if(jobs[s].state<2)
                suffix=std::max(suffix,after(s-offset));
            return tail[i]=jobs[offset+i].e+suffix;
        };
        long long cp=0;for(int i=0;i<count;++i)if(jobs[offset+i].state<2)cp=std::max(cp,before(i)+jobs[offset+i].e);
        for(int i=0;i<count;++i)if(jobs[offset+i].state<2) {
            require(slackOf(offset+i)==cp-before(i)-after(i),"SLACK agrees with independent recursive DAG oracle");
            ++comparisons;
        }
    }
    jobs.clear();jobs.resize(60000);flows.assign(1,Flow{});flows[0].n=60000;flows[0].first=0;
    for(int i=0;i<60000;++i) {
        jobs[i].wf=0;jobs[i].e=2000000000;jobs[i].state=0;
        if(i)jobs[i].pre.push_back(i-1);
    }
    require(slackOf(59999)==0&&slackOf(0)==0,"SLACK 60000-job path uses64bit lengths and valid bounds");
    std::cout<<"slack_comparisons="<<comparisons+2<<'\n';
}

int main() {
    cacheOracle();slackOracle();
    std::cout<<"LRU30000 operations and SLACK independent oracle passed\n";
}
