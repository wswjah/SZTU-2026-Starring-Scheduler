// Fixed-state tests of actual policy sources; no interactive evaluator.
#define main v13ModelAuditPolicyMain
#ifndef V13_MODEL_AUDIT_SOURCE
#define V13_MODEL_AUDIT_SOURCE "../candidates/v13_model/veto_strict.cpp"
#endif
#include V13_MODEL_AUDIT_SOURCE
#undef main

static void requireGate(bool ok,const char* why) {
    if(!ok){std::fprintf(stderr,"GATE_AUDIT_FAILED %s\n",why);std::exit(11);}
}
static int fixtureVersion=10000;
static void gateFixture(int count=3) {
    T=600;now=10;D=N=R=M=K=L=I=1;Breg=1;Brack=10;Bnet=1;Ureg=Unet=1;price[0]=2;
    jobs.assign(max(3,count),Job{});flows.assign(1,Flow{});v13ModelForecasts.assign(1,V13ModelForecast{});
    Flow& w=flows[0];w.id=1;w.tenant=0;w.first=0;w.n=w.left=count;w.home=0;w.v=1000;w.dl=500;w.arrive=1;
    Job& j=jobs[0];
    // Leave only never-read reservation/placement fields with a nonzero byte
    // pattern; the production gate must not typed-read old resEnd/resAt/resM.
    memset(reinterpret_cast<unsigned char*>(&j),0xa5,offsetof(Job,pre));
    j.id=7;j.wf=0;j.c=j.m=1;j.e=5;j.img=0;j.s=-1;j.zin=j.zout=0;j.state=j.need=0;
    j.ready=1;j.resT=0;j.xt=j.xf=0;
    for(int i=1;i<count;++i){jobs[i].s=-1;jobs[i].pre={0};j.suc.push_back(i);}
    for(int i=0;i<count;++i){jobTheta[i]=100;jobTail[i]=5;jobEnd[i]=50;}
    auto& forecast=v13ModelForecasts[0];forecast.cost=700;forecast.rev=750;
#ifndef V13_MODEL_AUDIT_PRODUCTION
    forecast.rem=20;forecast.work=100;forecast.tick=now;forecast.roots=1;
#endif
    tenPar[0]=-1;tenQuota[0]=10000;tenUsed[0]=tenFix[0]=tenRate[0]=tenRateStart[0]=0;tenF[0]=1.5;
    rackDc[0]=machRack[0]=0;rackDist[0][0]=0;rackMachs[0]={0};
    machUp[0]=1;freedAt[0]=0;machCpu[0]=machMem[0]=freeCpu[0]=freeMem[0]=virtCpu[0]=virtMem[0]=64;
    machJobs[0].clear();timeline[0].clear();imageLayers[0]={0};layerSize[0]=10;
    machCache[0]=Cache{};rackCache[0]=Cache{};machCache[0].cap=rackCache[0].cap=100;
    rackCache[0].ver=++fixtureVersion;
    commandsUsed=0;outbuf="ANS retained\n";runFee=313;overhead=3;ovWait=1;feeAvg=50;
#ifndef V13_MODEL_AUDIT_PRODUCTION
    v13ModelAttempts=v13ModelRejects=v13ModelLate=v13ModelGuardReturns=0;
#endif
}
static void noRealEffects(int commands=0) {
    requireGate(commandsUsed==commands&&outbuf=="ANS retained\n","unexpected emitted command");
    requireGate(tenFix[0]==0&&tenRate[0]==0&&tenRateStart[0]==0&&tenUsed[0]==0,"unexpected bill/quota effect");
    requireGate(freeCpu[0]==64&&freeMem[0]==64&&machJobs[0].empty(),"unexpected actual occupancy");
}
static void actualPlacementCases() {
    gateFixture();array<unsigned char,offsetof(Job,pre)> before;memcpy(before.data(),&jobs[0],before.size());
    tryPlace(0);
#if V13_MODEL_AUDIT_KIND==0
    requireGate(jobs[0].state==1&&commandsUsed==3&&v13ModelRejects==0,"light minimum leaf implies no-op");
#else
#ifndef V13_MODEL_AUDIT_PRODUCTION
    requireGate(v13ModelAttempts==1&&v13ModelRejects==1,"selected known low-margin fixture must be rejected");
#endif
    requireGate(memcmp(before.data(),&jobs[0],before.size())==0,"rejection must restore raw scalar/reservation bytes");
    noRealEffects();
    requireGate(machCache[0].q.empty()&&rackCache[0].q.empty()&&machCache[0].sum==0&&rackCache[0].sum==0,"rejection must precede cache effects");
    requireGate(virtCpu[0]==64&&virtMem[0]==64&&timeline[0].empty(),"rejection must precede virtual occupancy");
    requireGate(!flows[0].started&&!flows[0].dirty&&runFee==313&&overhead==3&&ovWait==1&&feeAvg==50,"rejection changed flow/EMA/runFee");
#endif
    gateFixture();commandsUsed=19998;tryPlace(0);
    noRealEffects(19998);requireGate(machCache[0].sum==0&&rackCache[0].sum==0,"insufficient atomic budget must precede cache");
#ifndef V13_MODEL_AUDIT_PRODUCTION
    requireGate(v13ModelAttempts==0,"insufficient atomic budget must precede model");
#endif
    gateFixture();tenQuota[0]=0;tryPlace(0);noRealEffects();
#ifndef V13_MODEL_AUDIT_PRODUCTION
    requireGate(v13ModelAttempts==0,"quota skip must not consult model");
#endif
    gateFixture();jobs[0].resT=now+3;jobs[0].resM=-1;tryPlace(0);noRealEffects();
    requireGate(timeline[0].empty(),"live postponement must preserve original skip");
#ifndef V13_MODEL_AUDIT_PRODUCTION
    requireGate(v13ModelAttempts==0,"live postponement must not consult model");
#endif
    gateFixture();jobs[0].resT=now+3;jobs[0].resM=0;jobs[0].resAt=now-1;jobs[0].resEnd=now+7;tryPlace(0);noRealEffects();
    requireGate(virtCpu[0]==63&&timeline[0].size()==1,"live machine reservation must use original occupy");
#ifndef V13_MODEL_AUDIT_PRODUCTION
    requireGate(v13ModelAttempts==0,"live machine reservation must not consult model");
#endif
    gateFixture();flows[0].started=1;tryPlace(0);
    requireGate(jobs[0].state==1&&commandsUsed==3,"started retry must bypass new-flow gate");
#ifndef V13_MODEL_AUDIT_PRODUCTION
    requireGate(v13ModelAttempts==0,"started retry must not consult model");
#endif
    std::puts("gate state cases passed: actual rejection,raw-prefix,budget,quota,reservations,started-retry");
}
int main(int argc,char** argv) {
    if(argc>1&&string(argv[1])=="decisions") {
        int count;requireGate(std::scanf("%d",&count)==1,"decision input count");
        for(int i=0;i<count;++i){
            int n;double factor,cost,rev;requireGate(std::scanf("%d%lf%lf%lf",&n,&factor,&cost,&rev)==4,"decision input row");
            gateFixture(n);tenF[0]=factor;v13ModelForecasts[0].cost=cost;v13ModelForecasts[0].rev=rev;
            float x[18]{};v13ModelFeatures(0,0,0,false,x);double prediction[2];v13ModelPredict(x,prediction);
            bool allow=v13ModelAllow(0,0,0,false);
            std::printf("%d %.17g %.17g %.9g %.9g\n",int(allow),prediction[0],prediction[1],double(x[5]),double(x[10]));
        }
        return 0;
    }
    actualPlacementCases();return 0;
}
