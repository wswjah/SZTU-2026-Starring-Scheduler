// The actual experimental candidate is included without rewriting its functions.
#define main v8_donor_solver_main
#include "../candidates/v8_donor.cpp"
#undef main

static int version = 20000;
static void require(bool value,const char* why) {
    if (!value) { std::cerr << "FAILED: " << why << '\n'; std::exit(1); }
}
static void fixture() {
    jobs.clear(); flows.clear(); outbuf.clear();
    deferredKills.clear(); deferredHead=0; commandsUsed=0;
    v8DonorUses=v8DonorSaved=v8DonorChecks=0;
    T=600; now=10; D=1; N=R=2; M=1; K=3; L=I=1;
    Breg=Brack=1; Bnet=100; Ureg=Unet=1; price[0]=2;
    layerSize[0]=100; imageLayers[0]={0};
    for(int r=0;r<2;++r) {
        rackDc[r]=0; rackMachs[r].clear(); rackCache[r]=Cache{};
        rackCache[r].cap=1000; rackCache[r].ver=++version;
        for(int s=0;s<2;++s) rackDist[r][s]=r==s?0:3;
    }
    rackMachs[0]={0}; machRack[0]=0; machUp[0]=1; freedAt[0]=0;
    machCpu[0]=machMem[0]=freeCpu[0]=freeMem[0]=virtCpu[0]=virtMem[0]=64;
    machJobs[0].clear(); timeline[0].clear(); machCache[0]=Cache{}; machCache[0].cap=1000;
    tenPar[0]=-1; tenPar[1]=tenPar[2]=0;
    for(int o=0;o<3;++o) {
        tenQuota[o]=100; tenUsed[o]=tenFix[o]=tenRate[o]=tenRateStart[o]=0; tenF[o]=1;
    }
    for(int i=0;i<2;++i) {
        Flow w{}; w.id=1000+i; w.tenant=i+1; w.first=i; w.n=w.left=1;
        w.arrive=1; w.dl=500; w.v=100000; w.home=0;
        flows.push_back(w);
        Job j{}; j.id=101+i*101; j.wf=i; j.c=j.m=i?2:4; j.img=0; j.e=5;
        j.s=i?-1:1; j.zin=10; j.ready=3; j.resM=i?17:-1; j.resAt=4; j.resT=7; j.resEnd=99;
        jobs.push_back(j); jobTheta[i]=1000; jobTail[i]=5; jobEnd[i]=99;
    }
    overhead=3; ovWait=1; feeAvg=50;
    collectV8Donors();
}
static int findDonor(ll targetFee=30) {
    ll extraFee=-1;
    int donor=cheaperV8Donor(0,0,targetFee,extraFee);
    if(donor>=0) require(extraFee<targetFee,"accepted donor is strictly cheaper");
    return donor;
}
static void donorLegality() {
    fixture(); require(findDonor()==1,"different-tenant donor accepted");
    tenQuota[2]=1; require(findDonor()==-1,"donor leaf quota checked");
    tenQuota[2]=100; tenQuota[0]=1; require(findDonor()==-1,"donor ancestor quota checked");
    fixture(); jobs[1].c=5; require(findDonor()==-1,"donor cores no greater than target");
    fixture(); jobs[1].m=5; require(findDonor()==-1,"donor memory no greater than target");
    fixture(); freeCpu[0]=1; require(findDonor()==-1,"donor current cores checked");
    fixture(); freeMem[0]=1; require(findDonor()==-1,"donor current memory checked");
    fixture(); jobs[1].s=1; rackDist[0][1]=-1;
    require(findDonor()==-1,"unreachable donor input rejected");
    fixture(); jobs[1].state=1; require(findDonor()==-1,"pool entries recheck running state");
    fixture(); jobs[1].need=1; require(findDonor()==-1,"pool entries recheck dependencies");
    fixture(); flows[1].dead=1; require(findDonor()==-1,"pool entries recheck flow abandonment");
    fixture(); require(findDonor(0)==-1,"no donor charge when target input is already free");
}
static void actualAtomicExecution() {
    fixture(); commandsUsed=19998; tryPlace(0);
    require(commandsUsed==19998&&outbuf.empty(),"two command slots emit no partial donor batch");
    require(jobs[0].state==0&&jobs[1].state==0,"budget rejection preserves both jobs");
    require(tenFix[1]==0&&tenFix[2]==0&&machCache[0].sum==0,"budget rejection has no bill/cache effects");

    fixture(); commandsUsed=19997; tryPlace(0);
    require(commandsUsed==20000,"three command slots accept complete donor batch");
    require(outbuf=="RUN 202 0\nKILL 202\nRUN 101 0\n","distinct donor/target command order");
    require(jobs[0].state==1&&jobs[0].prep==4,"target starts using warm cache and its real transfer");
    require(jobs[1].state==0&&jobs[1].ready==3,"donor remains ready with original age");
    require(jobs[1].resM==17&&jobs[1].resAt==4&&jobs[1].resT==7&&jobs[1].resEnd==99,"donor reservation fields restored");
    require(!flows[1].started&&flows[1].dirty&&flows[1].left==1,"donor workflow bookkeeping preserved");
    require(tenFix[1]==30&&tenFix[2]==100,"real donor/target fees billed to own tenants");
    require(tenRate[1]==8&&tenRateStart[1]==80&&tenRate[2]==0&&tenRateStart[2]==0,"donor has no elapsed CPU bill");
    require(tenUsed[0]==4&&tenUsed[1]==4&&tenUsed[2]==0,"quota ledger contains only target after batch");
    require(freeCpu[0]==60&&freeMem[0]==60&&machJobs[0]==vector<int>{0},"machine resources contain only target");
    require(machCache[0].sum==100&&rackCache[0].sum==100&&runFee==130,"cache and learning cost include actual donor prewarm");
    require(v8DonorUses==1&&v8DonorSaved==30,"local network savings recorded");
}
int main() {
    donorLegality(); actualAtomicExecution();
    std::cout<<"donor focused regressions passed: quota, resources, connectivity, atomic budget, state and ledger\n";
}
