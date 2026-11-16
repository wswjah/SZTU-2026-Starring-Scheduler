"""Build exactly the four predeclared first-admission gates, no running-job veto."""
from pathlib import Path
import hashlib
import json
import subprocess
from v13_model_common import ROOT,BASE,POLICIES,base_instrumentation,once


def gate_fragment(policy):
    if policy["type"]=="net_veto":
        condition=f"!(prediction[1]<{policy['net_threshold']}&&x[5]<{policy['forecast_net_threshold']}&&flows[jobs[ji].wf].n>={policy['min_jobs']})"
    else:
        weight=policy["model_weight"]
        condition=f"((1-{weight})*forecast.rev+{weight}*prediction[0]*flows[jobs[ji].wf].v>forecast.cost*(1+ADM))"
    return r'''
ll v13ModelAttempts,v13ModelRejects,v13ModelLate,v13ModelGuardReturns;
#ifdef V13_MODEL_DISABLED
volatile double v13ModelDisabledSink;
#endif
static bool v13ModelAllow(int ji,int machine,double prep,bool warm) {
    ++v13ModelAttempts;
    float x[18];v13ModelFeatures(ji,machine,prep,warm,x);
    double prediction[2];v13ModelPredict(x,prediction);
    const auto& forecast=v13ModelForecasts[jobs[ji].wf];
    (void)forecast;
#ifdef V13_MODEL_DISABLED
    v13ModelDisabledSink=prediction[0]+prediction[1]+x[0];
    return true;
#else
    bool allow=CONDITION;
    v13ModelRejects+=!allow;
    return allow;
#endif
}
'''.replace("CONDITION",condition)


def make(name,policy):
    source=base_instrumentation(BASE.read_text(encoding="utf8"))
    tree=(ROOT/"candidates/v13_model/tree.inc").read_text(encoding="ascii")
    source=once(source,"void tryPlace(int ji) {",tree+"\n"+gate_fragment(policy)+"\nvoid tryPlace(int ji) {")
    source=once(source,"""    Job& j = jobs[ji];
    Flow& w = flows[j.wf];
    for (int a = w.tenant;""","""    Job& j = jobs[ji];
    Flow& w = flows[j.wf];
    array<unsigned char,offsetof(Job,pre)> v13BeforeJob;
    if(!w.started)memcpy(v13BeforeJob.data(),&j,v13BeforeJob.size());
    for (int a = w.tenant;""")
    source=once(source,"""    int rdy = j.ready;""","""    if(!w.started&&!v13ModelAllow(ji,bx,bs,bwarm)) {
        memcpy(reinterpret_cast<unsigned char*>(&j),v13BeforeJob.data(),v13BeforeJob.size());
        return;
    }
    int rdy = j.ready;""")
    source=once(source,"""    if (used > .93 || (late > 0 && now % (1 << min(5, int(late / .04))))) return;""","""    v13ModelLate+=late>=0;
    if (used > .93 || (late > 0 && now % (1 << min(5, int(late / .04))))) {++v13ModelGuardReturns;return;}""")
    source=once(source,"""        if (now == T) break;
    }
}""","""        if (now == T) break;
    }
    fprintf(stderr,"V13_MODEL_POLICY attempts=%lld rejects=%lld late=%lld guard_returns=%lld\\n",v13ModelAttempts,v13ModelRejects,v13ModelLate,v13ModelGuardReturns);
}""")
    path=ROOT/f"candidates/v13_model/{name}.cpp";exe=ROOT/f"build/v13_model_{name}.exe"
    assert not path.exists();path.write_bytes(source.encode("utf8"))
    compiled=subprocess.run(["g++","-std=c++17","-O2","-Wall","-Wextra",str(path),"-o",str(exe)],capture_output=True,text=True,cwd=ROOT)
    assert compiled.returncode==0 and not compiled.stderr,compiled.stderr
    return {"name":name,"policy":policy,"source":str(path),"source_sha256":hashlib.sha256(path.read_bytes()).hexdigest(),
            "executable":str(exe),"exe_sha256":hashlib.sha256(exe.read_bytes()).hexdigest(),
            "model_sha256":hashlib.sha256((ROOT/"research/v13_model_tree.json").read_bytes()).hexdigest(),
            "gate_scope":"!started,immediate placement and complete command budget checked,before any prewarm RUN",
            "rejection":"Restore pre-tryPlace scalar job/reservation state,emit no command and do not alter cache/bill/quota",
            "official_submission_sent":False}


def main():
    records=[make(name,policy)for name,policy in POLICIES.items()]
    (ROOT/"research/v13_model_policies.json").write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding="utf8")
    print(json.dumps([{k:r[k]for k in ["name","source_sha256"]}for r in records]))


if __name__=="__main__":main()
