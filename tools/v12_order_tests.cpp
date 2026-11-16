#define main v12_order_solver_main
#ifndef V12_ORDER_AUDIT_SOURCE
#define V12_ORDER_AUDIT_SOURCE "../candidates/v12_order.cpp"
#endif
#include V12_ORDER_AUDIT_SOURCE
#undef main

static int checks;
static void require(bool value,const char* why){++checks;if(!value){std::cerr<<"FAILED "<<why<<'\n';std::exit(1);}}
static void equal(double a,double b,const char* why){require(std::abs(a-b)<1e-8,why);}
template<class T>static void bytes(std::string& out,const T& value){out.append(reinterpret_cast<const char*>(&value),sizeof value);}
static std::string state() {
    std::string out;
    auto cache=[&](const Cache& c){bytes(out,c.cap);bytes(out,c.sum);bytes(out,c.ver);out.append(c.in,400);bytes(out,c.q.size());for(int l:c.q)bytes(out,l);};
    for(int x=0;x<M;++x){cache(machCache[x]);bytes(out,freeCpu[x]);bytes(out,freeMem[x]);bytes(out,freedAt[x]);bytes(out,virtCpu[x]);bytes(out,virtMem[x]);bytes(out,machJobs[x].size());for(int j:machJobs[x])bytes(out,j);bytes(out,timeline[x].size());for(auto p:timeline[x]){bytes(out,p.first);bytes(out,p.second);}}
    for(int r=0;r<R;++r)cache(rackCache[r]);
    for(int o=0;o<K;++o){bytes(out,tenUsed[o]);bytes(out,tenFix[o]);bytes(out,tenRate[o]);bytes(out,tenRateStart[o]);bytes(out,tenQuota[o]);}
    for(const Job& j:jobs){out.append(reinterpret_cast<const char*>(&j),offsetof(Job,pre));bytes(out,j.pre.size());for(int p:j.pre)bytes(out,p);bytes(out,j.suc.size());for(int s:j.suc)bytes(out,s);}
    for(const Flow& w:flows){bytes(out,w);for(int j=w.first;j<w.first+w.n&&j<int(jobs.size());++j){bytes(out,jobEnd[j]);bytes(out,jobTail[j]);bytes(out,jobTheta[j]);}}
    bytes(out,overhead);bytes(out,ovWait);bytes(out,feeAvg);bytes(out,runFee);bytes(out,commandsUsed);out+=outbuf;bytes(out,deferredHead);for(int j:deferredKills)bytes(out,j);
    return out;
}

static void fixture(bool external=true,int cores=2) {
    require(!v12OrderActive,"no transaction leaks between fixtures");
    T=600;now=10;D=1;N=R=2;M=1;K=2;L=2;I=2;
    Breg=1;Brack=10;Bnet=5;Ureg=1;Unet=2;price[0]=1;layerSize[0]=50;layerSize[1]=30;
    imageLayers[0]={0};imageLayers[1]={1};
    for(int r=0;r<R;++r){rackDc[r]=0;rackMachs[r].clear();rackCache[r]=Cache{};rackCache[r].cap=100;for(int s=0;s<R;++s)rackDist[r][s]=r==s?0:3;}
    rackMachs[0]={0};machRack[0]=0;machCpu[0]=freeCpu[0]=virtCpu[0]=cores;machMem[0]=freeMem[0]=virtMem[0]=16;freedAt[0]=0;machUp[0]=1;
    machCache[0]=Cache{};machCache[0].cap=100;machJobs[0].clear();timeline[0].clear();
    tenPar[0]=-1;tenPar[1]=0;for(int o=0;o<K;++o){tenQuota[o]=10;tenUsed[o]=tenFix[o]=tenRate[o]=tenRateStart[o]=0;tenF[o]=1;}
    jobs.assign(2,Job{});flows.assign(1,Flow{});
    Flow& w=flows[0];memset(&w,0xB6,sizeof w);w.id=900;w.tenant=1;w.dl=500;w.arrive=1;w.first=0;w.n=w.left=2;w.dead=0;w.started=0;w.home=0;w.dirty=1;w.adm=0;w.key=-1;w.v=10000;
    for(int i=0;i<2;++i){
        Job& j=jobs[i];memset(reinterpret_cast<unsigned char*>(&j),0xA5,offsetof(Job,pre));
        j.id=100+i;j.wf=0;j.c=j.m=1;j.e=5;j.img=0;j.s=external&&!i?1:-1;j.zin=10;j.zout=1;j.state=0;j.need=0;j.ready=1;j.resT=0;j.xt=j.xf=0;
        jobEnd[i]=0;jobTail[i]=5;jobTheta[i]=100;
    }
    overhead=3;ovWait=1;feeAvg=50;runFee=17;commandsUsed=0;outbuf="ANS 123\n";deferredKills.clear();deferredHead=0;v12OrderGate=true;
    memset(v12OrderIq,0,sizeof v12OrderIq);memset(v12OrderIv,0,sizeof v12OrderIv);
}

static V12OrderResult actualPrice(int first,int second) {
    V12OrderResult result;
    {
        V12OrderTxn txn(0,first,second);
        long long original=tenFix[1];int used=commandsUsed;
        tryPlace(first);tryPlace(second);
        result.started=(jobs[0].state==1)+(jobs[1].state==1);
        result.immediate=tenFix[1]-original;result.commands=commandsUsed-used;
        double rem,work,cost;flowEstimate(flows[0],rem,work,cost);
        double revenue=0;double factors[]={-1,-.5,0,1,2};rem*=1+BB*log(flows[0].left);
        for(double factor:factors){double finish=now+rem*(1+SP*factor);if(finish<=T+HZ||!HS)revenue+=revenueAt(flows[0],finish)/5;}
        if(!HS&&now+rem>T)revenue=0;
        result.score=revenue-result.immediate-cost;
    }
    return result;
}

static void exactRollbackAndPrice() {
    fixture();std::string initial=state();
    auto original=v12OrderEvaluate(0,0,1);require(state()==initial&&!v12OrderActive,"first order restores all logical state including sentinel bytes");
    auto reversed=v12OrderEvaluate(0,1,0);require(state()==initial&&!v12OrderActive,"second order restores all logical state including sentinel bytes");
    require(original.started==2&&reversed.started==2,"both tested orders actually start two jobs");
    require(original.immediate==170&&reversed.immediate==110,"trial costs include original prewarm repeated input fees");
    require(original.commands==4&&reversed.commands==4,"trial command counts reflect real RUN/KILL/RUN plus RUN");
    equal(reversed.score-original.score,60,"true startup savings appear once in rollout score");
    for(auto pair:std::vector<std::pair<int,int>>{{0,1},{1,0}}){auto got=v12OrderEvaluate(0,pair.first,pair.second),actual=actualPrice(pair.first,pair.second);require(state()==initial,"independent real-price probe rolls back");require(got.started==actual.started&&got.immediate==actual.immediate&&got.commands==actual.commands,"simulated metadata equals actual tryPlace path");equal(got.score,actual.score,"rollout score equals same real placements forecast");}
    for(int r=0;r<30;++r)for(int im=0;im<120;++im)require(v12OrderIv[im][r]==0,"hypothetical registry quote versions invalidated");
    require(v12OrderPair(0,0,1),"eligible pair commits chosen order");
    require(outbuf.find("RUN 101 0")<outbuf.find("RUN 100 0"),"lower-cost reverse order is the only committed output");
    require(commandsUsed==4&&tenFix[1]==110&&tenUsed[0]==2&&tenUsed[1]==2,"only committed branch bills and uses quota");
    require(std::count(outbuf.begin(),outbuf.end(),'\n')==5,"no hypothetical commands leaked into output");
}

static void budgetAndReservation() {
    for(int remaining=0;remaining<=7;++remaining){
        fixture(false);commandsUsed=COMMAND_LIMIT-remaining;std::string initial=state();
        auto result=v12OrderEvaluate(0,0,1);require(state()==initial,"budget trial restores command counter/output/resources");
        int starts=remaining<3?0:remaining==3?1:2,commands=remaining<3?0:remaining==3?3:4;
        require(result.started==starts&&result.commands==commands,"trial honors atomic prewarm at 20k boundary");
        tryPlace(0);tryPlace(1);require(commandsUsed<=COMMAND_LIMIT,"committed commands stay within 20k");
    }
    fixture(false,1);std::string initial=state();
    auto result=v12OrderEvaluate(0,0,1);require(result.started==1&&state()==initial,"busy-machine reservation and virtual timeline are restored");
    fixture(false);jobs[0].resT=now+3;jobs[0].resM=0;jobs[0].resAt=now;
    initial=state();require(!v12OrderPair(0,0,1)&&state()==initial,"live reservation bypasses search without state change");
    fixture(false);tenQuota[0]=0;initial=state();require(!v12OrderPair(0,0,1)&&state()==initial,"individual ancestor quota check bypasses search");
    fixture(false);v12OrderGate=false;initial=state();require(!v12OrderPair(0,0,1)&&state()==initial,"extra CPU gate bypass leaves ordinary path available");
    fixture(false);flows[0].left=9;initial=state();require(!v12OrderPair(0,0,1)&&state()==initial,"left-scope bound");
    fixture(false);flows[0].n=129;initial=state();require(!v12OrderPair(0,0,1)&&state()==initial,"snapshot size bound");
}

static void quoteABA() {
    fixture(false);std::string initial=state();auto unused=v12OrderEvaluate(0,0,1);(void)unused;
    require(state()==initial&&rackCache[0].ver==0,"cache content/version rolled back before ABA probe");
    cachePut(rackCache[0],1);
    require(rackCache[0].ver==1&&!rackCache[0].in[0],"different real insertion recreates hypothetical version with different contents");
    tryPlace(0);require(v12OrderIq[0][0]==50,"registry estimate recomputes after rollback ABA");
    require(tenFix[1]==50,"actual billing after ABA still pays real first registry pull");
}

static void tieOriginalOrder() {
    fixture(false);auto a=v12OrderEvaluate(0,0,1),b=v12OrderEvaluate(0,1,0);
    equal(a.score,b.score,"symmetric orders have equal score");
    require(v12OrderPair(0,0,1),"symmetric pair searches");
    require(outbuf.find("RUN 100 0")<outbuf.find("RUN 101 0"),"ties preserve original order");
}

static void multipleMachineRollback() {
    std::mt19937 rng(121611);
    for(int trial=0;trial<200;++trial){
        fixture(trial%2==0);M=4;
        rackMachs[0].clear();rackMachs[1].clear();
        for(int x=0;x<M;++x){
            machRack[x]=x%2;rackMachs[x%2].push_back(x);machCpu[x]=4;machMem[x]=8;machUp[x]=1;
            freeCpu[x]=virtCpu[x]=1+rng()%4;freeMem[x]=virtMem[x]=1+rng()%8;freedAt[x]=rng()%now;
            machJobs[x].clear();timeline[x].clear();machCache[x]=Cache{};machCache[x].cap=20+rng()%100;
            if(rng()%2)cachePut(machCache[x],rng()%2);
        }
        for(int r=0;r<R;++r)if(rng()%2)cachePut(rackCache[r],rng()%2);
        for(int j=0;j<2;++j){jobs[j].c=1+rng()%2;jobs[j].m=1+rng()%3;jobs[j].img=rng()%2;}
        commandsUsed=COMMAND_LIMIT-rng()%10;overhead=1+rng()%8;feeAvg=10+rng()%100;
        std::string initial=state();
        auto forward=v12OrderEvaluate(0,0,1);(void)forward;
        require(state()==initial&&!v12OrderActive,"multi-machine forward rollback exact");
        auto reverse=v12OrderEvaluate(0,1,0);(void)reverse;
        require(state()==initial&&!v12OrderActive,"multi-machine reverse rollback exact");
    }
}

int main() {
    exactRollbackAndPrice();budgetAndReservation();quoteABA();multipleMachineRollback();tieOriginalOrder();
    std::cout<<"V12 order transaction tests passed checks="<<checks<<"\n";
}
