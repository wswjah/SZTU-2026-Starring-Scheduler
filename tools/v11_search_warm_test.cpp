#define main v11WarmSolverMain
#include "../candidates/v11_search/warm_rank.cpp"
#undef main

static void require(bool condition,const char* reason) {
    if(!condition) { std::cerr<<reason<<'\n'; std::exit(1); }
}
int main() {
    T=600; now=10; D=K=L=I=1; N=R=M=17;
    Breg=Brack=Bnet=1; Ureg=Unet=1; price[0]=1;
    layerSize[0]=100; imageLayers[0]={0}; tenPar[0]=-1; tenQuota[0]=100000;
    tenF[0]=1; overhead=3; ovWait=1; feeAvg=50;
    for(int r=0;r<R;++r) {
        rackDc[r]=0; machRack[r]=r; rackMachs[r]={r};
        machUp[r]=1; machCpu[r]=machMem[r]=freeCpu[r]=freeMem[r]=virtCpu[r]=virtMem[r]=64;
        rackCache[r]=Cache{}; machCache[r]=Cache{};
        rackCache[r].cap=machCache[r].cap=200;
        rackCache[r].ver=1000+r; machCache[r].ver=2000+r;
        for(int s=0;s<R;++s) rackDist[r][s]=r==s?0:1;
    }
    cachePut(machCache[16],0);
    Flow flow{}; flow.id=1; flow.tenant=0; flow.n=flow.left=1; flow.home=0;
    flow.v=10000; flow.dl=500; flow.arrive=1; flows.push_back(flow);
    Job job{}; job.id=7; job.wf=0; job.c=job.m=1; job.e=5; job.img=0; job.s=-1;
    job.resM=-1; job.ready=1; jobs.push_back(job); jobTheta[0]=100;
    tryPlace(0);
    require(jobs[0].state==1&&jobs[0].mach==16,"warm machine beyond the old16-rack shortlist must be considered");
    require(commandsUsed==1&&runFee==0&&jobs[0].prep==0,"warm selected machine needs one RUN and no registry fee");
    killNow(0);
    Cache& failed=machCache[16];
    failed.q.clear(); failed.sum=0; ++failed.ver; memset(failed.in,0,sizeof failed.in);
    // Same membership/version change as the candidate's real FAIL handling.
    outbuf.clear(); commandsUsed=0; jobs[0].resT=0;
    tryPlace(0);
    require(jobs[0].state==1&&jobs[0].mach==0,"cache clearing plus version invalidation must remove stale warm ranking");
    require(commandsUsed==3&&runFee==100,"cold choice follows the original atomic prewarm path");
    require(tenUsed[0]==1&&tenRate[0]==1&&freeCpu[0]==63,"actual resource and quota accounting remains consistent");
    std::cout<<"warm ranking cache memo and clearing regression passed\n";
}
