"""Two bounded ready-frontier forecast refinements; actual scheduling unchanged."""
from pathlib import Path
import hashlib
import json
import subprocess

ROOT=Path(__file__).resolve().parent.parent
BASE=ROOT/"versions/v10_input_fix/main.cpp"
HELPERS=r'''
constexpr bool v11FrontierAdjustTime=TIME_MODE;
struct V11FrontierMemo {
    ll registry,rack;
    int machineVersion,rackVersion,epoch;
    bool valid;
};
V11FrontierMemo v11FrontierMemo[120][360];
int v11FrontierEpoch[360];
ll v11FrontierImageBytes[120];
ll v11FrontierEligible,v11FrontierCalls,v11FrontierMachineQuotes,v11FrontierHits,v11FrontierChanges;
ll v11FrontierLower,v11FrontierHigher,v11FrontierTimeChanges;
ll v11FrontierLate,v11FrontierGuardReturns;
double v11FrontierCostDelta;
struct V11FrontierQuote {
    bool valid=false,warm=false;
    int machine=-1;
    ll prep=0;
    double cost=0,duration=0;
};
V11FrontierQuote v11QuoteReady(Job& j,double theta,ll headroom) {
    ++v11FrontierCalls;
    V11FrontierQuote best;
    if(j.c>headroom)return best;
    double estimate=max(1.,j.e*tenFactor(flows[j.wf].tenant)),bestObjective=1e100;
    ll times[30],fees[30];bool reachable[30];
    F(r,R){ll away;reachable[r]=transferCost(j,r,times[r],fees[r],away);}
    F(x,M) {
        int r=machRack[x];
        if(!reachable[r]||!machUp[x]||machCpu[x]<j.c||machMem[x]<j.m||freeCpu[x]<j.c||freeMem[x]<j.m)continue;
        ++v11FrontierMachineQuotes;
        auto& memo=v11FrontierMemo[j.img][x];
        if(memo.valid&&memo.machineVersion==machCache[x].ver&&memo.rackVersion==rackCache[r].ver&&memo.epoch==v11FrontierEpoch[x])++v11FrontierHits;
        else {
            memo.registry=memo.rack=0;
            for(int layer:imageLayers[j.img])if(!machCache[x].in[layer])
                (rackCache[r].in[layer]?memo.rack:memo.registry)+=layerSize[layer];
            memo.machineVersion=machCache[x].ver;memo.rackVersion=rackCache[r].ver;
            memo.epoch=v11FrontierEpoch[x];memo.valid=true;
        }
        ll prep=max(times[r],(memo.registry+Breg-1)/Breg+(memo.rack+Brack-1)/Brack);
        double corePrice=j.c*price[rackDc[r]],cash=memo.registry*Ureg+fees[r]+corePrice*(prep+estimate);
        double objective=cash+theta*prep;
        bool warm=false;
        // Only a complete resident image guarantees no second-RUN pull.
        if(PW>0&&v11FrontierImageBytes[j.img]<=machCache[x].cap) {
            double warmCash=memo.registry*Ureg+2.*fees[r]+corePrice*(times[r]+estimate);
            double warmObjective=warmCash+theta*times[r];
            if(warmObjective<objective)cash=warmCash,objective=warmObjective,prep=times[r],warm=true;
        }
        if(objective<bestObjective) {
            bestObjective=objective;best.valid=true;best.machine=x;best.warm=warm;
            best.prep=prep;best.duration=prep+estimate;best.cost=cash;
        }
    }
    return best;
}
void v11RefineFrontier(Flow& w,double& rem,double& work,double& cost,double* st,double* du) {
    if(!w.started||w.left>8)return;
    ++v11FrontierEligible;
    ll headroom=LLONG_MAX;
    for(int a=w.tenant;a>=0;a=tenPar[a])headroom=min(headroom,tenQuota[a]-tenUsed[a]);
    static bool changed[1<<16];
    F(i,w.n)changed[i]=false;
    bool any=false;
    F(i,w.n) {
        int ji=w.first+i;Job& j=jobs[ji];
        if(j.state||j.need)continue;
        auto quote=v11QuoteReady(j,jobTheta[ji],headroom);
        if(!quote.valid)continue;
        double oldCost=j.c*du[i]*price[rackDc[w.home]]+feeAvg+j.xf;
        cost+=quote.cost-oldCost;v11FrontierCostDelta+=quote.cost-oldCost;
        ++v11FrontierChanges;v11FrontierLower+=quote.cost<oldCost;v11FrontierHigher+=quote.cost>oldCost;
        if(v11FrontierAdjustTime) {
            v11FrontierTimeChanges+=du[i]!=quote.duration;
            du[i]=quote.duration;changed[i]=true;
        }
        any=true;
    }
    if(!v11FrontierAdjustTime||!any)return;
    rem=work=0;
    F(i,w.n) {
        int ji=w.first+i;Job& j=jobs[ji];st[i]=0;
        if(j.state>1)continue;
        for(int p:j.pre)st[i]=max(st[i],st[p-w.first]+du[p-w.first]);
        work+=j.c*(du[i]-(!j.state&&!changed[i]?WK*ovWait:0));
        rem=max(rem,st[i]+du[i]);jobTail[ji]=0;
    }
    ll grace=max(5,(w.dl-w.arrive)/3);
    for(int i=w.n-1;i>=0;--i) {
        int ji=w.first+i;Job& j=jobs[ji];
        if(j.state>1)continue;
        jobTail[ji]+=du[i];
        for(int p:j.pre)jobTail[p]=max(jobTail[p],jobTail[ji]);
        double path=st[i]+jobTail[ji],x=(now+path-w.dl)/(MG*path+1)+1;
        jobTheta[ji]=TH0*j.c+w.v*1./grace*min(1.,max(0.,x));
    }
}
'''


def once(source,old,new):
    assert source.count(old)==1,old[:90]
    return source.replace(old,new)


def make(mode):
    source=BASE.read_text(encoding="utf8")
    start=source.index("void flowEstimate(")
    end=source.index("// home rack of a workflow",start)
    block=source[start:end]
    old="""        jobTheta[ji] = TH0 * j.c + w.v * 1.0 / g * min(1.0, max(0.0, x));
    }
}"""
    block=once(block,old,old[:-1]+"    v11RefineFrontier(w, rem, work, cost, st, du);\n}")
    source=source[:start]+HELPERS.replace("TIME_MODE","true" if mode=="cost_and_time" else "false")+"\n"+block+source[end:]
    source=once(source,"""        int k = readInt();
        while (k--) imageLayers[i].push_back(readInt());""","""        int k = readInt();bool seen[400]{};
        while (k--) {
            int layer=readInt();imageLayers[i].push_back(layer);
            if(!seen[layer])v11FrontierImageBytes[i]+=layerSize[layer],seen[layer]=true;
        }""")
    source=once(source,"""            } else if (ev == "FAIL") {
                int x = readInt();""","""            } else if (ev == "FAIL") {
                int x = readInt();
                ++v11FrontierEpoch[x];""")
    source=once(source,"""    double used = V7_SCHEDULER_USED(TS), late = used - .08 - .62 * now / T;
    if (used > .93 || (late > 0 && now % (1 << min(5, int(late / .04))))) return;""","""    double used = V7_SCHEDULER_USED(TS), late = used - .08 - .62 * now / T;
    v11FrontierLate+=late>=0;
    if (used > .93 || (late > 0 && now % (1 << min(5, int(late / .04))))) {++v11FrontierGuardReturns;return;}""")
    source=once(source,"""        if (now == T) break;
    }
}""","""        if (now == T) break;
    }
    fprintf(stderr,"V11_FRONTIER eligible=%lld calls=%lld machine_quotes=%lld memo_hits=%lld changes=%lld lower=%lld higher=%lld time_changes=%lld estimate_cost_delta=%.9f late=%lld guard_returns=%lld\\n",v11FrontierEligible,v11FrontierCalls,v11FrontierMachineQuotes,v11FrontierHits,v11FrontierChanges,v11FrontierLower,v11FrontierHigher,v11FrontierTimeChanges,v11FrontierCostDelta,v11FrontierLate,v11FrontierGuardReturns);
}""")
    return source


def main():
    assert hashlib.sha256(BASE.read_bytes()).hexdigest()=="b0854a70f54ccb47d287a48be37e447eb100147ca3f2e556c20c20498f705ae6"
    out=ROOT/"candidates/v11_frontier";out.mkdir(parents=True,exist_ok=True)
    records=[]
    for mode in ["cost_only","cost_and_time"]:
        source=make(mode);path=out/f"{mode}.cpp";exe=ROOT/f"build/v11_frontier_{mode}.exe"
        assert not path.exists();path.write_bytes(source.encode("utf8"))
        build=subprocess.run(["g++","-std=c++17","-O2","-Wall","-Wextra",str(path),"-o",str(exe)],cwd=ROOT,capture_output=True,text=True)
        assert build.returncode==0 and not build.stderr,build.stderr
        records.append({"name":mode,"base":str(BASE),"base_sha256":hashlib.sha256(BASE.read_bytes()).hexdigest(),
                        "source":str(path),"source_sha256":hashlib.sha256(path.read_bytes()).hexdigest(),
                        "executable":str(exe),"exe_sha256":hashlib.sha256(exe.read_bytes()).hexdigest(),
                        "scope":"started and left<=8,currently ready jobs with individual immediate legal placement",
                        "objective":"cash + baseline current jobTheta * preparation;no LAK",
                        "cache_model":"membership quotes,not exact LRU;warm only when distinct image fits machine cache",
                        "time_refinement":mode=="cost_and_time","official_submission_sent":False})
    (ROOT/"research/v11_frontier_manifest.json").write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding="utf8")
    print(json.dumps([{k:r[k] for k in ["name","source_sha256"]} for r in records]))


if __name__=="__main__":main()
