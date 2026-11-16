"""Two-order actual-tryPlace rollout with transactional rollback, one candidate."""
from pathlib import Path
import hashlib
import json
import subprocess

ROOT=Path(__file__).resolve().parent.parent
BASE=ROOT/"versions/v10_input_fix/main.cpp"
HELPERS=r'''
ll v12OrderIq[120][30];
int v12OrderIv[120][30];
bool v12OrderGate;
ll v12OrderSearches,v12OrderSwaps,v12OrderTrials,v12OrderCopies;
struct V12OrderTxn;
V12OrderTxn* v12OrderActive;
struct V12OrderMachine {
    int x,freeC,freeM,freed,virtualC,virtualM;
    Cache cache;
    vector<int> running;
    vector<pair<double,ll>> releases;
};
struct V12OrderRack {int r;Cache cache;};
struct V12OrderTxn {
    int wi;
    array<int,2> ids;
    array<array<unsigned char,offsetof(Job,pre)>,2> savedJobs;
    array<unsigned char,sizeof(Flow)> savedFlow;
    int flowFirst,flowCount;
    array<ll,200> used,fix,rate,rateStart;
    vector<double> ends,tails,thetas;
    vector<V12OrderMachine> machines;
    vector<V12OrderRack> racks;
    double oldOverhead,oldWait,oldFee;
    ll oldRunFee;
    int oldCommands;
    size_t oldOutput;
    bool restored=false;
    V12OrderTxn(int flow,int a,int b):wi(flow),ids{{a,b}},flowFirst(flows[flow].first),flowCount(flows[flow].n),
        oldOverhead(overhead),oldWait(ovWait),oldFee(feeAvg),oldRunFee(runFee),oldCommands(commandsUsed),oldOutput(outbuf.size()) {
        assert(!v12OrderActive);
        static_assert(std::is_standard_layout<Job>::value,"Job scalar prefix must precede unchanged vectors");
        static_assert(std::is_trivially_copyable<Flow>::value,"Flow snapshot is raw-copyable");
        F(i,2)memcpy(savedJobs[i].data(),&jobs[ids[i]],savedJobs[i].size());
        memcpy(savedFlow.data(),&flows[wi],savedFlow.size());
        F(o,K)used[o]=tenUsed[o],fix[o]=tenFix[o],rate[o]=tenRate[o],rateStart[o]=tenRateStart[o];
        int first=flowFirst,count=flowCount;
        ends.assign(jobEnd+first,jobEnd+first+count);
        tails.assign(jobTail+first,jobTail+first+count);
        thetas.assign(jobTheta+first,jobTheta+first+count);
        machines.reserve(2);racks.reserve(2);
        v12OrderActive=this;
    }
    V12OrderTxn(const V12OrderTxn&)=delete;
    void touch(int x) {
        for(auto& saved:machines)if(saved.x==x)return;
        machines.push_back({x,freeCpu[x],freeMem[x],freedAt[x],virtCpu[x],virtMem[x],machCache[x],machJobs[x],timeline[x]});
        ++v12OrderCopies;
        int r=machRack[x];
        for(auto& saved:racks)if(saved.r==r)return;
        racks.push_back({r,rackCache[r]});
    }
    void rollback() {
        if(restored)return;
        v12OrderActive=nullptr;
        for(auto& saved:machines) {
            int x=saved.x;freeCpu[x]=saved.freeC;freeMem[x]=saved.freeM;freedAt[x]=saved.freed;
            virtCpu[x]=saved.virtualC;virtMem[x]=saved.virtualM;
            machCache[x]=std::move(saved.cache);machJobs[x]=std::move(saved.running);timeline[x]=std::move(saved.releases);
        }
        for(auto& saved:racks)rackCache[saved.r]=std::move(saved.cache);
        F(i,2)memcpy(reinterpret_cast<unsigned char*>(&jobs[ids[i]]),savedJobs[i].data(),savedJobs[i].size());
        memcpy(&flows[wi],savedFlow.data(),savedFlow.size());
        F(o,K)tenUsed[o]=used[o],tenFix[o]=fix[o],tenRate[o]=rate[o],tenRateStart[o]=rateStart[o];
        int first=flowFirst;
        copy(ends.begin(),ends.end(),jobEnd+first);copy(tails.begin(),tails.end(),jobTail+first);copy(thetas.begin(),thetas.end(),jobTheta+first);
        overhead=oldOverhead;ovWait=oldWait;feeAvg=oldFee;runFee=oldRunFee;
        commandsUsed=oldCommands;outbuf.resize(oldOutput);
        // Restored cache versions must never validate a hypothetical quote.
        memset(v12OrderIv,0,sizeof v12OrderIv);
        restored=true;
    }
    ~V12OrderTxn(){rollback();}
};
void v12OrderTouchMachine(int x){if(v12OrderActive)v12OrderActive->touch(x);}
struct V12OrderResult {int started=0;double score=-1e100;ll immediate=0;int commands=0;};
'''
ROLLOUT=r'''
bool v12OrderReservationLive(const Job& j) {
    return j.resT>now&&(j.resM<0||(machUp[j.resM]&&freedAt[j.resM]<j.resAt));
}
bool v12OrderIndividual(const Job& j) {
    for(int a=flows[j.wf].tenant;a>=0;a=tenPar[a])if(tenUsed[a]+j.c>tenQuota[a])return false;
    bool checked[30]={},reachable[30]={};
    F(x,M) {
        if(!machUp[x]||machCpu[x]<j.c||machMem[x]<j.m||freeCpu[x]<j.c||freeMem[x]<j.m)continue;
        int r=machRack[x];
        if(!checked[r]) {ll time,fee,away;reachable[r]=transferCost(const_cast<Job&>(j),r,time,fee,away);checked[r]=true;}
        if(reachable[r])return true;
    }
    return false;
}
V12OrderResult v12OrderEvaluate(int wi,int first,int second) {
    ++v12OrderTrials;
    V12OrderResult result;
    {
        V12OrderTxn trial(wi,first,second);
        tryPlace(first);tryPlace(second);
        result.started=(jobs[first].state==1)+(jobs[second].state==1);
        Flow& w=flows[wi];
        result.immediate=tenFix[w.tenant]-trial.fix[w.tenant];
        result.commands=commandsUsed-trial.oldCommands;
        double rem,work,cost,rev=0;
        flowEstimate(w,rem,work,cost);
        static const double scenarios[5]={-1,-.5,0,1,2};
        rem*=1+BB*log(w.left);
        F(k,5) {
            double finish=now+rem*(1+SP*scenarios[k]);
            if(finish<=T+HZ||!HS)rev+=revenueAt(w,finish)/5;
        }
        if(!HS&&now+rem>T)rev=0;
        double score=rev-result.immediate-cost;
        if(std::isfinite(score))result.score=score;
    }
    return result;
}
bool v12OrderPair(int wi,int first,int second) {
    if(!v12OrderGate||commandsUsed==COMMAND_LIMIT)return false;
    Flow& w=flows[wi];
    if(w.left>8||w.n>128||w.left<2||first==second)return false;
    Job& a=jobs[first];Job& b=jobs[second];
    if(a.state||b.state||a.need||b.need||a.wf!=wi||b.wf!=wi||v12OrderReservationLive(a)||v12OrderReservationLive(b))return false;
    double used=V7_SCHEDULER_USED(TS),late=used-.08-.62*now/T;
    if(used>=.65||late>=-.03)return false;
    if(!v12OrderIndividual(a)||!v12OrderIndividual(b))return false;
    ++v12OrderSearches;
    V12OrderResult ordinary=v12OrderEvaluate(wi,first,second),reversed=v12OrderEvaluate(wi,second,first);
    bool swapOrder=reversed.started>ordinary.started||(reversed.started==ordinary.started&&reversed.score>ordinary.score+1e-9);
    if(swapOrder){++v12OrderSwaps;swap(first,second);}
    tryPlace(first);tryPlace(second);
    return true;
}
'''


def once(source,old,new):
    assert source.count(old)==1,old[:100]
    return source.replace(old,new)


def make(source):
    assert "tok[1 << 23]" in source
    source=once(source,"int freedAt[360];","int freedAt[360];\nvoid v12OrderTouchMachine(int x);")
    source=once(source,"void runJob(int ji, int x) {","void runJob(int ji, int x) {\n    v12OrderTouchMachine(x);")
    source=once(source,"void occupy(int x, int ji, double end) {","void occupy(int x, int ji, double end) {\n    v12OrderTouchMachine(x);")
    source=once(source,"void tryPlace(int ji) {",HELPERS+"\nvoid tryPlace(int ji) {")
    source=once(source,"""            static ll iq[120][30];
            static int iv[120][30];
            ll& q = iq[j.img][r];
            if (iv[j.img][r] != rackCache[r].ver + 1) {
                iv[j.img][r] = rackCache[r].ver + 1, q = 0;""","""            ll& q = v12OrderIq[j.img][r];
            if (v12OrderIv[j.img][r] != rackCache[r].ver + 1) {
                v12OrderIv[j.img][r] = rackCache[r].ver + 1, q = 0;""")
    source=once(source,"void schedule() {",ROLLOUT+"\nvoid schedule() {")
    source=once(source,"""    double used = V7_SCHEDULER_USED(TS), late = used - .08 - .62 * now / T;
    if (used > .93""","""    double used = V7_SCHEDULER_USED(TS), late = used - .08 - .62 * now / T;
    v12OrderGate=late<-.03&&used<.65;
    if (used > .93""")
    source=once(source,"""        sort(ready.begin(), ready.end());
        for (auto& q : ready) tryPlace(q.second);""","""        sort(ready.begin(), ready.end());
        if(ready.size()==2&&v12OrderPair(o.second,ready[0].second,ready[1].second))continue;
        for (auto& q : ready) tryPlace(q.second);""")
    source=once(source,"""        if (now == T) break;
    }
}""","""        if (now == T) break;
    }
    fprintf(stderr,"V12_ORDER searches=%lld swaps=%lld trials=%lld machine_copies=%lld\\n",v12OrderSearches,v12OrderSwaps,v12OrderTrials,v12OrderCopies);
}""")
    return source


def main():
    source=make(BASE.read_text(encoding="utf8"))
    path=ROOT/"candidates/v12_order.cpp";exe=ROOT/"build/v12_order.exe"
    assert not path.exists(),"Never overwrite an existing experiment"
    path.write_bytes(source.encode("utf8"))
    build=subprocess.run(["g++","-std=c++17","-O2","-Wall","-Wextra",str(path),"-o",str(exe)],capture_output=True,text=True,cwd=ROOT)
    assert build.returncode==0 and not build.stderr,build.stderr
    record={"base":str(BASE),"base_sha256":hashlib.sha256(BASE.read_bytes()).hexdigest(),
            "source":str(path),"source_sha256":hashlib.sha256(path.read_bytes()).hexdigest(),
            "executable":str(exe),"exe_sha256":hashlib.sha256(exe.read_bytes()).hexdigest(),
            "search":"exactly2ready,left2..8,totalflow<=128,both individually immediate-feasible,no live reservations",
            "selection":"actual starts first,then original5-scenario expected revenue minus actual trial startup fees and remaining estimated cost;ties original order",
            "extra_cpu_gate":"late<-.03 and used<.65,checked at schedule and each pair;original insurance unchanged",
            "rollback":"touch journal for selected machines/racks;2jobs,currentflow forecasts,tenant bill/quota-used,EMAs,commands/output;clear registry quote versions against ABA",
            "official_submission_sent":False}
    (ROOT/"research/v12_order_manifest.json").write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding="utf8")
    print(json.dumps(record,ensure_ascii=False))


if __name__=="__main__":main()
