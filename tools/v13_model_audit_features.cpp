// Include the actual trace and exported predictor unchanged; no interactor runs.
#define main v13ModelAuditTraceMain
#include "../candidates/v13_model/trace.cpp"
#undef main
#include "../candidates/v13_model/tree.inc"

static void auditRequire(bool ok,const char* message) {
    if(!ok) { std::fprintf(stderr,"AUDIT_FAILED %s\n",message);std::exit(9); }
}
struct AuditFixture {
    int horizon,tick,arrival,deadline,forecastTick;
    double rawRem,work,cost,rev,factor,preparation;
    int warm,zin,distance;
    array<ll,4> quota,used;
};
static void featureFixture(int index,const AuditFixture& fixture) {
    T=fixture.horizon;now=fixture.tick;D=1;R=2;M=1;K=4;Bnet=10;Unet=3;
    const int n=7,roots=2;
    flows.assign(1,Flow{});jobs.assign(n,Job{});v13ModelForecasts.assign(1,V13ModelForecast{});
    Flow& w=flows[0];w.first=0;w.n=w.left=n;w.v=1200;w.tenant=1;w.arrive=fixture.arrival;w.dl=fixture.deadline;
    Job& j=jobs[0];j.id=100;j.wf=0;j.c=4;j.e=9;j.s=fixture.zin?1:-1;j.zin=fixture.zin;
    // The first job is a root. Set the rest so the cached root count is also2.
    for(int i=2;i<n;++i)jobs[i].pre={i==2?0:1};
    machRack[0]=0;rackDc[0]=rackDc[1]=0;rackDist[0][0]=0;rackDist[0][1]=fixture.distance;
    tenPar[0]=-1;tenPar[1]=3;tenPar[2]=3;tenPar[3]=0; // Parents need not be numerically sorted.
    for(int i=0;i<K;++i) {tenQuota[i]=fixture.quota[i];tenUsed[i]=fixture.used[i];tenFix[i]=100+i;tenRate[i]=20+i;tenRateStart[i]=30+i;}
    tenF[1]=fixture.factor;
    auto& p=v13ModelForecasts[0];p.rem=fixture.rawRem*(1+BB*log(w.left));p.work=fixture.work;
    p.cost=fixture.cost;p.rev=fixture.rev;p.tick=fixture.forecastTick;p.roots=roots;
    commandsUsed=19997;outbuf="ANS retained\nRUN retained\n";runFee=313;
    overhead=3.75;ovWait=2.25;feeAvg=77.5;
    for(int i=0;i<n;++i) {jobEnd[i]=100+i;jobTail[i]=200+i;jobTheta[i]=300+i;}
    array<unsigned char,offsetof(Job,pre)> jobBefore;
    array<unsigned char,sizeof(Flow)> flowBefore;
    memcpy(jobBefore.data(),&j,jobBefore.size());memcpy(flowBefore.data(),&w,flowBefore.size());
    float features[18];v13ModelFeatures(0,0,fixture.preparation,fixture.warm,features);
    auditRequire(memcmp(jobBefore.data(),&j,jobBefore.size())==0,"feature helper changed Job scalars");
    auditRequire(memcmp(flowBefore.data(),&w,flowBefore.size())==0,"feature helper changed Flow");
    for(int i=0;i<K;++i) auditRequire(tenUsed[i]==fixture.used[i]&&tenQuota[i]==fixture.quota[i]&&tenFix[i]==100+i&&tenRate[i]==20+i&&tenRateStart[i]==30+i,"feature helper changed a tenant ledger");
    for(int i=0;i<n;++i) auditRequire(jobEnd[i]==100+i&&jobTail[i]==200+i&&jobTheta[i]==300+i,"feature helper changed forecast arrays");
    auditRequire(commandsUsed==19997&&outbuf=="ANS retained\nRUN retained\n"&&runFee==313,"feature helper billed or emitted a command");
    auditRequire(overhead==3.75&&ovWait==2.25&&feeAvg==77.5,"feature helper changed EMA");
    std::printf("{\"id\":%d,\"T\":%d,\"now\":%d,\"arrival\":%d,\"deadline\":%d,\"forecast_tick\":%d,\"n\":%d,\"roots\":%d,\"value\":%lld,",index,T,now,w.arrive,w.dl,p.tick,n,roots,w.v);
    std::printf("\"raw_rem\":%.17g,\"cached_rem\":%.17g,\"work\":%.17g,\"cost\":%.17g,\"rev\":%.17g,\"factor\":%.17g,\"preparation\":%.17g,\"warm\":%d,\"cores\":%d,\"estimate\":%d,\"zin\":%d,\"distance\":%d,\"Unet\":%lld,",fixture.rawRem,p.rem,p.work,p.cost,p.rev,tenF[1],fixture.preparation,fixture.warm,j.c,j.e,j.zin,fixture.distance,Unet);
    std::printf("\"parents\":[-1,3,3,0],\"tenant\":1,\"quota\":[");for(int i=0;i<K;++i)std::printf("%s%lld",i?",":"",tenQuota[i]);
    std::printf("],\"used\":[");for(int i=0;i<K;++i)std::printf("%s%lld",i?",":"",tenUsed[i]);
    std::printf("],\"features\":[");for(int i=0;i<18;++i)std::printf("%s%.9g",i?",":"",double(features[i]));
    double prediction[2];v13ModelPredict(features,prediction);
    std::printf("],\"prediction\":[%.17g,%.17g],\"public_state_unchanged\":true}\n",prediction[0],prediction[1]);
}
int main(int argc,char** argv) {
    if(argc>1&&string(argv[1])=="tree") {
        int count;auditRequire(std::scanf("%d",&count)==1,"tree input row count");
        for(int row=0;row<count;++row) {
            float x[18];for(float& value:x)auditRequire(std::scanf("%f",&value)==1,"tree feature input");
            double prediction[2];v13ModelPredict(x,prediction);std::printf("%.17g %.17g\n",prediction[0],prediction[1]);
        }
        return 0;
    }
    const AuditFixture fixtures[]={
        {600,83,17,250,76,55,1000,450,930,1.3,6,1,25,2,{{72,25,1,40}},{{60,7,1,28}}},
        {400,210,30,390,203,90,2400,620,1100,2.25,14,0,25,3,{{100,60,1,30}},{{80,10,1,5}}},
        {400,397,20,300,390,9,80,450,600,.75,3,1,10,4,{{200,20,1,100}},{{190,3,1,95}}},
        {600,599,60,700,599,3,40,170,1000,1.1,0,0,0,2,{{999,40,1,80}},{{900,2,1,50}}},
    };
    for(int i=0;i<4;++i)featureFixture(i,fixtures[i]);
    return 0;
}
