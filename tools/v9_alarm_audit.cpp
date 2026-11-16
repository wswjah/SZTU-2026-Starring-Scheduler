// Include the real candidate; the log1p probe only observes identical math.
#include <bits/stdc++.h>
static std::vector<float> auditLogValues;
static double auditLog1p(double x) {
    double value=std::log1p(x);
    auditLogValues.push_back(float(value));
    return value;
}
#define log1p auditLog1p
#define main v9_original_solver_main
#include "../candidates/v9_alarm_normal.cpp"
#undef main
#undef log1p

static void ensure(bool value,const char* message) {
    if(!value) { std::cerr<<"AUDIT FAILED: "<<message<<'\n';std::exit(1); }
}

static int fixtureVersion=100000;
static void placementFixture(int machines,bool external) {
    jobs.clear();flows.clear();outbuf.clear();deferredKills.clear();deferredHead=0;commandsUsed=0;
    T=600;now=10;D=N=K=L=I=1;R=external?2:1;M=machines;
    Breg=10;Brack=10;Bnet=1;Ureg=1;Unet=external?817:1;price[0]=2;
    layerSize[0]=100;imageLayers[0]={0};
    for(int r=0;r<R;++r) {
        rackDc[r]=0;rackMachs[r].clear();rackCache[r]=Cache{};rackCache[r].cap=1000;
        rackCache[r].ver=++fixtureVersion;
        for(int a=0;a<R;++a)rackDist[r][a]=r==a?0:1;
    }
    for(int x=0;x<M;++x) {
        machRack[x]=0;machUp[x]=1;machCpu[x]=machMem[x]=64;
        freeCpu[x]=freeMem[x]=virtCpu[x]=virtMem[x]=64;freedAt[x]=0;
        machJobs[x].clear();timeline[x].clear();machCache[x]=Cache{};machCache[x].cap=1000;
        rackMachs[0].push_back(x);
        for(int h=0;h<3;++h)v9Probabilities[x][h]=v9Background[h];
    }
    tenPar[0]=-1;tenQuota[0]=100;tenUsed[0]=tenFix[0]=tenRate[0]=tenRateStart[0]=0;tenF[0]=1;
    Flow flow{};flow.id=900;flow.tenant=0;flow.first=flow.home=0;flow.n=flow.left=1;
    flow.arrive=1;flow.dl=500;flow.v=100000;flows.push_back(flow);
    Job job{};job.id=901;job.wf=0;job.c=job.m=1;job.e=5;job.img=0;job.s=external?1:-1;
    job.zin=job.zout=1;job.ready=1;job.resM=-1;jobs.push_back(job);
    jobTheta[0]=100;jobTail[0]=5;jobEnd[0]=100;overhead=3;ovWait=1;feeAvg=50;
}

static void placementChecks() {
    placementFixture(2,false);tryPlace(0);
    ensure(jobs[0].state==1&&jobs[0].mach==0,"background-risk tie selects first machine");
    placementFixture(2,false);
    for(int h=0;h<3;++h)v9Probabilities[0][h]=.9;
    tryPlace(0);
    ensure(jobs[0].state==1&&jobs[0].mach==1,"risk fee changes actual machine choice");
    placementFixture(1,true);tryPlace(0);
    ensure(commandsUsed==1&&jobs[0].prep==10,"ordinary start is cheaper without excess risk");
    placementFixture(1,true);
    v9Probabilities[0][0]=.1;v9Probabilities[0][1]=.3;v9Probabilities[0][2]=.6;
    tryPlace(0);
    ensure(commandsUsed==3&&jobs[0].prep==2,"both-risk pricing can favor shorter prewarm exposure");
    ensure(tenFix[0]==1734&&tenUsed[0]==1&&freeCpu[0]==63,"risk pricing leaves real command ledger intact");
}

int main() {
    std::cout<<std::setprecision(17);
    int worlds;std::cin>>worlds;
    for(int wi=0;wi<worlds;++wi) {
        std::string path;int samples;
        std::cin>>path>>T>>M>>W>>samples;
        std::set<std::pair<int,int>> selected;
        for(int i=0;i<samples;++i) {int t,x;std::cin>>t>>x;selected.insert({t,x});}
        memset(alarmAt,0,sizeof alarmAt);memset(v9LinePeak,0,sizeof v9LinePeak);
        std::ifstream stream(path);ensure(bool(stream),"open relative tape");
        std::string line;getline(stream,line);getline(stream,line);
        while(getline(stream,line)) {
            std::replace(line.begin(),line.end(),',',' ');
            std::istringstream fields(line);
            int tick,x,up,dc,cpu,mem;long long alarm,lines,chars,peak;
            fields>>tick>>x>>up>>dc>>cpu>>mem>>alarm>>lines>>chars>>peak;
            ensure(bool(fields),"parse raw tape");
            alarmAt[x][tick]=alarm;v9LinePeak[x][tick]=peak;
        }
        for(now=1;now<=T;++now) {
            auditLogValues.clear();v9UpdateAlarmRisk();
            ensure(auditLogValues.size()==size_t(3*M),"real feature function computes exactly three logs per machine");
            for(auto row:selected) if(row.first==now) {
                int x=row.second;
                std::cout<<"S "<<wi<<' '<<now<<' '<<x;
                for(int k=0;k<3;++k)std::cout<<' '<<auditLogValues[3*x+k];
                for(int k=0;k<3;++k)std::cout<<' '<<v9Probabilities[x][k];
                std::cout<<'\n';
            }
        }
    }
    int tests;std::cin>>tests;
    for(int i=0;i<tests;++i) {
        float features[10];for(float& f:features)std::cin>>f;
        double p[3];v9Predict(features,p);
        std::cout<<"P "<<i;for(double value:p)std::cout<<' '<<value;std::cout<<'\n';
    }
    double probabilities[]={.1,.3,.6};
    for(double h:{-1.,0.,1.,3.,4.,8.,10.,16.,24.})
        std::cout<<"I "<<h<<' '<<v9Interpolated(probabilities,h)<<'\n';
    feeAvg=100;
    for(int k=0;k<3;++k)v9Probabilities[0][k]=probabilities[k];
    for(double wait:{0.,.5,3.}) for(double prep:{0.,2.,20.})
        std::cout<<"R "<<wait<<' '<<prep<<' '<<v9RiskPenalty(0,wait,prep,10,2,10)<<'\n';
    for(int k=0;k<3;++k)v9Probabilities[0][k]=v9Background[k]*.5;
    std::cout<<"B "<<v9RiskPenalty(0,0,2,10,2,10)<<'\n';
    placementChecks();
    std::cout<<"C placement_checks_passed\n";
}
