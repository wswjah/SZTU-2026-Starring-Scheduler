#define main v11_frontier_solver_main
#ifndef V11_FRONTIER_AUDIT_SOURCE
#define V11_FRONTIER_AUDIT_SOURCE "../candidates/v11_frontier/cost_only.cpp"
#endif
#include V11_FRONTIER_AUDIT_SOURCE
#undef main

static int fixtureVersion=10000;
static int comparisons=0;
static void require(bool ok,const char* message) {
    if(!ok){std::cerr<<"FAILED "<<message<<'\n';std::exit(1);}
}
static void close(double a,double b,const char* message) {
    ++comparisons;require(std::abs(a-b)<1e-8*std::max(1.,std::max(std::abs(a),std::abs(b))),message);
}

static std::string realState() {
    std::ostringstream out;out<<std::setprecision(17);
    for(int x=0;x<M;++x)out<<freeCpu[x]<<' '<<freeMem[x]<<' '<<machUp[x]<<' '<<virtCpu[x]<<' '<<virtMem[x]<<' ';
    for(int o=0;o<K;++o)out<<tenQuota[o]<<' '<<tenUsed[o]<<' '<<tenFix[o]<<' '<<tenRate[o]<<' '<<tenRateStart[o]<<' ';
    auto cache=[&](const Cache& c){out<<c.cap<<' '<<c.sum<<' '<<c.ver<<' ';for(int l:c.q)out<<l<<',';out<<';';for(int l=0;l<400;++l)out<<int(c.in[l]);};
    for(int r=0;r<R;++r)cache(rackCache[r]);for(int x=0;x<M;++x)cache(machCache[x]);
    for(const Job& j:jobs){
        out<<j.id<<' '<<j.wf<<' '<<j.c<<' '<<j.m<<' '<<j.e<<' '<<j.img<<' '<<j.s<<' '<<j.zin<<' '<<j.zout<<' '<<j.state<<' '<<j.mach<<' '<<j.t0<<' '<<j.prep<<' '<<j.outRack<<' '<<j.need<<' '<<j.ready<<' '<<j.resM<<' '<<j.resAt<<' '<<j.resT<<' '<<j.resEnd<<' '<<j.xt<<' '<<j.xf<<';';
        for(int p:j.pre)out<<p<<',';out<<';';for(int s:j.suc)out<<s<<',';out<<';';
    }
    for(const Flow& w:flows)out<<w.id<<' '<<w.tenant<<' '<<w.dl<<' '<<w.arrive<<' '<<w.first<<' '<<w.n<<' '<<w.left<<' '<<w.dead<<' '<<w.started<<' '<<w.home<<' '<<w.dirty<<' '<<w.key<<' '<<w.v<<';';
    out<<commandsUsed<<' '<<outbuf<<' '<<deferredHead<<' ';for(int j:deferredKills)out<<j<<',';
    for(int x=0;x<M;++x){for(int j:machJobs[x])out<<j<<',';for(auto p:timeline[x])out<<p.first<<','<<p.second<<';';}
    return out.str();
}

struct OracleQuote {bool valid=false,warm=false;int machine=-1;double cost=0,duration=0;long long prep=0;};
static OracleQuote quoteOracle(const Job& j,double theta,long long headroom) {
    OracleQuote best;if(j.c>headroom)return best;
    double estimate=std::max(1.,j.e*tenF[flows[j.wf].tenant]),bestObjective=1e100;
    for(int x=0;x<M;++x){
        int r=machRack[x];if(!machUp[x]||machCpu[x]<j.c||machMem[x]<j.m||freeCpu[x]<j.c||freeMem[x]<j.m)continue;
        long long time=0,fee=0;bool valid=true;
        std::vector<std::pair<int,int>> inputs;
        if(j.s>=0)inputs.push_back({j.s,j.zin});for(int p:j.pre)inputs.push_back({jobs[p].outRack,jobs[p].zout});
        for(auto input:inputs)if(input.first!=r){
            long long d=rackDist[r][input.first];if(d<0){valid=false;break;}
            time=std::max(time,d+(input.second+Bnet-1)/Bnet);fee+=input.second*d*Unet;
        }
        if(!valid)continue;
        long long registry=0,rack=0;
        for(int layer:imageLayers[j.img])if(!machCache[x].in[layer]){
            if(rackCache[r].in[layer])rack+=layerSize[layer];else registry+=layerSize[layer];
        }
        long long prep=std::max(time,(registry+Breg-1)/Breg+(rack+Brack-1)/Brack);
        double rate=j.c*price[rackDc[r]],cash=registry*Ureg+fee+rate*(prep+estimate),objective=cash+theta*prep;
        bool warm=false;
        std::set<int> distinct(imageLayers[j.img].begin(),imageLayers[j.img].end());long long imageBytes=0;
        for(int layer:distinct)imageBytes+=layerSize[layer];
        if(PW>0&&imageBytes<=machCache[x].cap){
            double warmCash=registry*Ureg+2.*fee+rate*(time+estimate),warmObjective=warmCash+theta*time;
            if(warmObjective<objective){cash=warmCash;objective=warmObjective;prep=time;warm=true;}
        }
        if(objective<bestObjective){bestObjective=objective;best={true,warm,x,cash,prep+estimate,prep};}
    }
    return best;
}

static void fixture(std::mt19937& rng) {
    T=600;now=50;D=2;R=3;M=6;K=4;L=6;I=3;
    Breg=7;Brack=13;Bnet=5;Ureg=3;Unet=2;price[0]=2;price[1]=5;
    for(int l=0;l<L;++l)layerSize[l]=1+rng()%90;
    imageLayers[0]={0,1,2};imageLayers[1]={2,3,2};imageLayers[2]={3,4,5};
    for(int im=0;im<I;++im){std::set<int> unique(imageLayers[im].begin(),imageLayers[im].end());v11FrontierImageBytes[im]=0;for(int l:unique)v11FrontierImageBytes[im]+=layerSize[l];}
    for(int r=0;r<R;++r){
        rackDc[r]=r?1:0;rackMachs[r].clear();rackCache[r]=Cache{};rackCache[r].cap=100+rng()%250;rackCache[r].ver=++fixtureVersion;
        for(int a=0;a<R;++a)rackDist[r][a]=r==a?0:1+std::abs(r-a);
        for(int l=0;l<L;++l)if(rng()%2)cachePut(rackCache[r],l);
    }
    if(rng()%3==0)for(int r=0;r<2;++r)rackDist[r][2]=rackDist[2][r]=-1;
    for(int x=0;x<M;++x){
        machRack[x]=x/2;machCpu[x]=8;machMem[x]=16;machUp[x]=rng()%4!=0;
        freeCpu[x]=rng()%9;freeMem[x]=rng()%17;virtCpu[x]=freeCpu[x];virtMem[x]=freeMem[x];
        machCache[x]=Cache{};machCache[x].cap=40+rng()%250;machCache[x].ver=++fixtureVersion;machJobs[x].clear();timeline[x].clear();
        rackMachs[x/2].push_back(x);for(int l=0;l<L;++l)if(rng()%2)cachePut(machCache[x],l);
    }
    machUp[0]=machUp[1]=1;freeCpu[0]=7;freeMem[0]=15;freeCpu[1]=8;freeMem[1]=16;
    tenPar[0]=-1;tenPar[1]=0;tenPar[2]=1;tenPar[3]=0;
    for(int o=0;o<K;++o){tenQuota[o]=o?10:20;tenUsed[o]=tenFix[o]=tenRate[o]=tenRateStart[o]=0;tenF[o]=.5+(rng()%5)*.5;}
    tenUsed[0]=tenUsed[1]=tenUsed[2]=1;
    int offset=rng()%15;jobs.assign(offset,Job{});flows.assign(1,Flow{});
    Flow& w=flows[0];w.id=999;w.first=offset;w.n=7;w.left=5;w.tenant=2;w.arrive=1;w.dl=55+rng()%60;w.home=0;w.started=1;w.v=10000;w.dirty=1;
    for(int i=0;i<7;++i){
        Job j{};j.id=100000000+i;j.wf=0;j.c=1+i%2;j.m=1+i%3;j.e=2+rng()%9;j.img=i%3;j.s=-1;j.zout=1+rng()%20;j.ready=40;j.resM=-1;j.xt=(rng()%3);j.xf=rng()%30;
        j.state=(i==0||i==6)?2:(i==4?1:0);j.outRack=rng()%R;
        if(i==1||i==2||i==4)j.pre={offset};
        if(i==3)j.pre={offset+1,offset+2};if(i==5)j.pre={offset+3,offset+4};
        j.need=(i==3||i==5)?2:0;
        if(i==2){j.s=rng()%R;j.zin=1+rng()%20;}
        if(i==4){j.c=j.m=1;j.mach=0;j.t0=45;j.prep=1;jobEnd[offset+i]=now+3;machJobs[0].push_back(offset+i);}
        jobs.push_back(j);for(int p:j.pre)jobs[p].suc.push_back(offset+i);
    }
    overhead=3;ovWait=7;feeAvg=50;commandsUsed=19999;outbuf="ANS\n";deferredKills={};deferredHead=0;
    memset(v11FrontierMemo,0,sizeof v11FrontierMemo);memset(v11FrontierEpoch,0,sizeof v11FrontierEpoch);
}

static void estimateCheck() {
    Flow& w=flows[0];int n=w.n;
    std::vector<double> du(n),st(n),tail(n),theta(n);double work=0,cost=0,rem=0;
    std::vector<bool> changed(n);
    for(int i=0;i<n;++i){
        Job& j=jobs[w.first+i];if(j.state>1)continue;
        for(int p:j.pre)st[i]=std::max(st[i],st[p-w.first]+du[p-w.first]);
        du[i]=j.state?jobEnd[w.first+i]-now:j.e*tenF[w.tenant]+OVK*overhead+j.xt;
        work+=j.c*du[i];if(!j.state)du[i]+=WK*ovWait;
        cost+=j.state?j.c*du[i]*price[rackDc[machRack[j.mach]]]:j.c*du[i]*price[rackDc[w.home]]+feeAvg+j.xf;
        rem=std::max(rem,st[i]+du[i]);
    }
    auto recomputeTheta=[&](){
        std::fill(tail.begin(),tail.end(),0);int grace=std::max(5,(w.dl-w.arrive)/3);
        for(int i=n-1;i>=0;--i){Job& j=jobs[w.first+i];if(j.state>1)continue;tail[i]+=du[i];for(int p:j.pre)tail[p-w.first]=std::max(tail[p-w.first],tail[i]);
            double path=st[i]+tail[i],x=(now+path-w.dl)/(MG*path+1)+1;theta[i]=TH0*j.c+w.v*1./grace*std::min(1.,std::max(0.,x));}
    };
    recomputeTheta();
    long long head=LLONG_MAX;for(int a=w.tenant;a>=0;a=tenPar[a])head=std::min(head,tenQuota[a]-tenUsed[a]);
    bool any=false;
    if(w.started&&w.left<=8)for(int i=0;i<n;++i){
        Job& j=jobs[w.first+i];if(j.state||j.need)continue;
        auto expected=quoteOracle(j,theta[i],head);auto actual=v11QuoteReady(j,theta[i],head);
        require(actual.valid==expected.valid,"quote legality");if(!expected.valid)continue;
        require(actual.machine==expected.machine&&actual.warm==expected.warm&&actual.prep==expected.prep,"quote machine/warm/prep");
        close(actual.cost,expected.cost,"quote cash units");close(actual.duration,expected.duration,"quote duration");
        cost+=expected.cost-(j.c*du[i]*price[rackDc[w.home]]+feeAvg+j.xf);
        if(v11FrontierAdjustTime){du[i]=expected.duration;changed[i]=true;}any=true;
    }
    if(v11FrontierAdjustTime&&any){
        std::fill(st.begin(),st.end(),0);rem=work=0;
        for(int i=0;i<n;++i){Job& j=jobs[w.first+i];if(j.state>1)continue;for(int p:j.pre)st[i]=std::max(st[i],st[p-w.first]+du[p-w.first]);
            rem=std::max(rem,st[i]+du[i]);work+=j.c*(du[i]-(!j.state&&!changed[i]?WK*ovWait:0));}
        recomputeTheta();
    }
    std::string before=realState();double gotRem,gotWork,gotCost;flowEstimate(w,gotRem,gotWork,gotCost);
    require(before==realState(),"forecast cannot mutate real state");
    close(gotCost,cost,"forecast cost replacement includes full old pending cost");
    close(gotWork,work,"forecast core-time work");close(gotRem,rem,"forecast critical path");
    for(int i=0;i<n;++i)if(jobs[w.first+i].state<2){close(jobTail[w.first+i],tail[i],"tail recomputed consistently");close(jobTheta[w.first+i],theta[i],"theta recomputed consistently");}
}

static void legalityChecks(std::mt19937& rng) {
    fixture(rng);int ji=flows[0].first+1;Job& j=jobs[ji];
    require(!v11QuoteReady(j,10,j.c-1).valid,"current headroom must cover individual job");
    for(int x=0;x<M;++x)machUp[x]=0;require(!v11QuoteReady(j,10,100).valid,"down machines excluded");
    for(int x=0;x<M;++x){machUp[x]=1;freeCpu[x]=0;}require(!v11QuoteReady(j,10,100).valid,"insufficient free cores excluded");
    for(int x=0;x<M;++x){freeCpu[x]=8;freeMem[x]=0;}require(!v11QuoteReady(j,10,100).valid,"insufficient free memory excluded");
    for(int x=0;x<M;++x){freeMem[x]=16;machCpu[x]=0;}require(!v11QuoteReady(j,10,100).valid,"physical capacity checked");
    for(int x=0;x<M;++x)machCpu[x]=8;
    j.s=2;j.zin=10;for(int r=0;r<R;++r)rackDist[r][2]=-1;
    for(int x=0;x<M;++x)machRack[x]=0;require(!v11QuoteReady(j,10,100).valid,"unreachable external input excluded");
}

static void failureMemoCheck(std::mt19937& rng) {
    fixture(rng);M=R=1;machRack[0]=rackDc[0]=0;freeCpu[0]=8;freeMem[0]=16;machUp[0]=1;
    rackDist[0][0]=0;Job& j=jobs[flows[0].first+1];j.s=-1;j.pre.clear();j.img=0;
    imageLayers[0]={0,1};layerSize[0]=10;layerSize[1]=20;v11FrontierImageBytes[0]=30;
    machCache[0]=Cache{};rackCache[0]=Cache{};machCache[0].cap=rackCache[0].cap=100;
    cachePut(machCache[0],0);cachePut(machCache[0],1);
    memset(v11FrontierMemo,0,sizeof v11FrontierMemo);
    auto before=v11QuoteReady(j,100,100);require(before.valid,"memo setup valid");
    long long hits=v11FrontierHits;auto repeated=v11QuoteReady(j,100,100);require(v11FrontierHits>hits,"membership memo hit exercised");
    close(before.cost,repeated.cost,"memo same-state quote");
    machCache[0].q.clear();machCache[0].sum=0;memset(machCache[0].in,0,400);++v11FrontierEpoch[0];
    auto after=v11QuoteReady(j,100,100);close(after.cost-before.cost,30.*Ureg,"FAIL epoch invalidates unchanged content version");
}

int main() {
    std::mt19937 rng(11162026);
    legalityChecks(rng);failureMemoCheck(rng);
    for(int trial=0;trial<120;++trial){fixture(rng);estimateCheck();}
    fixture(rng);flows[0].started=0;estimateCheck();
    fixture(rng);flows[0].left=9;estimateCheck();
    std::cout<<"frontier helper audit passed mode="<<v11FrontierAdjustTime<<" WK="<<WK<<" numerical_comparisons="<<comparisons<<'\n';
}
