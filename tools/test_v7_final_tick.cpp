// Focused horizon/command-budget regression for the unchanged candidate.
#define main candidate_main
#ifndef V7_FINAL_TICK_SOURCE
#define V7_FINAL_TICK_SOURCE "../candidates/v7_final_tick.cpp"
#endif
#include V7_FINAL_TICK_SOURCE
#undef main

static void fixture() {
    jobs.clear(); flows.clear(); outbuf.clear();
    deferredKills.clear(); deferredHead=0; commandsUsed=0;
    T=600; now=T-1; R=K=D=L=I=1; M=2;
    Breg=Brack=Bnet=1; Ureg=Unet=1; price[0]=2;
    tenPar[0]=-1; tenQuota[0]=100;
    tenUsed[0]=tenFix[0]=tenRate[0]=tenRateStart[0]=0;
    rackDc[0]=0; rackDist[0][0]=0;
    imageLayers[0].clear(); rackCache[0]=Cache{};
    Flow w{};w.tenant=0;w.n=w.left=3;w.first=0;w.started=1;
    flows.push_back(w);
    for(int x=0;x<M;++x) {
        machJobs[x].clear();machRack[x]=0;machUp[x]=1;
        freeCpu[x]=freeMem[x]=machCpu[x]=machMem[x]=64;
        machCache[x]=Cache{};
    }
    for(int i=0;i<3;++i) {
        Job j{};j.id=100+i;j.wf=0;j.c=j.m=1;j.s=-1;j.img=0;j.e=5;
        jobs.push_back(j);
    }
    runJob(0,0);runJob(1,1);
    now=T;outbuf.clear();commandsUsed=0;
}
static void require(bool value,const char* why) {
    if(!value) {std::cerr<<why<<'\n';std::exit(1);}
}
int main() {
    fixture();
    schedule();
    require(commandsUsed==2,"all last-tick running jobs stopped");
    require(machJobs[0].empty()&&machJobs[1].empty(),"running vectors empty");
    require(jobs[0].state==0&&jobs[1].state==0&&jobs[2].state==0,"no pending job starts");
    require(tenUsed[0]==0&&tenRate[0]==0&&tenFix[0]==4,"bill and quota settled at current tick");
    require(outbuf.find("RUN ")==std::string::npos,"no new RUN at horizon");

    fixture();commandsUsed=COMMAND_LIMIT-1;
    schedule();
    require(commandsUsed==COMMAND_LIMIT,"one remaining command used");
    require(machJobs[0].size()+machJobs[1].size()==1,"budget leaves one running job untouched");
    require(outbuf.find("RUN ")==std::string::npos,"budget edge emits no RUN");

    fixture();commandsUsed=COMMAND_LIMIT;
    schedule();
    require(commandsUsed==COMMAND_LIMIT&&outbuf.empty(),"full budget emits nothing");
    require(machJobs[0].size()+machJobs[1].size()==2,"full budget does not mutate running state");

    fixture();release(0);jobs[0].state=2;
    deferredKills={0,1};deferredHead=0;
    schedule();
    require(commandsUsed==1&&outbuf=="KILL 101\n","deferred DONE expires and running stops once");
    require(jobs[0].state==2&&jobs[1].state==0,"completed job preserved");
    require(deferredKills.empty()&&deferredHead==0,"deferred queue drained");
    std::cout<<"final_tick cleanup: horizon, budget and deferred DONE passed\n";
}
