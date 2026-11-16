"""Collect current99-policy admissions and reconcile independent per-flow ledgers."""
from pathlib import Path
import hashlib
import json
import subprocess
from v13_model_common import ROOT,BASE,FEATURES,base_instrumentation,once,declare_plan

TRACE_DECL=r'''
struct V13ModelLedger {bool seen=false;int tick=-1,runs=0;ll run=0,pull=0,net=0;array<float,18> x{};};
vector<V13ModelLedger> v13ModelLedger;
ll v13ModelLate,v13ModelGuardReturns;
'''


def main():
    declare_plan()
    source=base_instrumentation(BASE.read_text(encoding="utf8"))
    source=once(source,"int freedAt[360];","int freedAt[360];\n"+TRACE_DECL)
    source=once(source,"""    tenFix[o] += cp * (now - j.t0);""","""    tenFix[o] += cp * (now - j.t0);
    v13ModelLedger[j.wf].run+=cp*(now-j.t0);""")
    source=once(source,"""    tenFix[o] += runFee = tf + qreg * Ureg;""","""    tenFix[o] += runFee = tf + qreg * Ureg;
    v13ModelLedger[j.wf].pull+=qreg*Ureg;v13ModelLedger[j.wf].net+=tf;++v13ModelLedger[j.wf].runs;""")
    source=once(source,"""    int rdy = j.ready;""","""    if(!w.started&&!v13ModelLedger[j.wf].seen) {
        auto& sample=v13ModelLedger[j.wf];sample.seen=true;sample.tick=now;
        v13ModelFeatures(ji,bx,bs,bwarm,sample.x.data());
    }
    int rdy = j.ready;""")
    source=once(source,"""                v13ModelForecasts.push_back(v13forecast);""","""                v13ModelForecasts.push_back(v13forecast);
                v13ModelLedger.emplace_back();""")
    source=once(source,"""    if (used > .93 || (late > 0 && now % (1 << min(5, int(late / .04))))) return;""","""    v13ModelLate+=late>=0;
    if (used > .93 || (late > 0 && now % (1 << min(5, int(late / .04))))) {++v13ModelGuardReturns;return;}""")
    dump=r'''
    F(x,M)for(int ji:machJobs[x]) {
        const Job& j=jobs[ji];v13ModelLedger[j.wf].run+=j.c*price[rackDc[machRack[x]]]*(T+1-j.t0);
    }
    fprintf(stderr,"V13_MODEL_META,T=%d,flows=%zu,late=%lld,guard_returns=%lld\n",T,flows.size(),v13ModelLate,v13ModelGuardReturns);
    fprintf(stderr,"V13_MODEL_HEADER,flow,seen,first_tick,arrival,deadline,grace,value,jobs,finish,earned,cost,run,pull,net,runs");
    F(k,18){fprintf(stderr,",f%d",k);}fprintf(stderr,"\n");
    F(wi,flows.size()) {
        const Flow& w=flows[wi];const auto& row=v13ModelLedger[wi];int grace=max(5,(w.dl-w.arrive)/3);ll earned=0;
        int finish=w.left?-1:w.endT;
        if(!w.left&&finish<=T) {
            if(finish<=w.dl)earned=w.v;
            else if(finish<w.dl+grace)earned=ll(__int128(w.v)*(w.dl+grace-finish)/grace);
        }
        ll cost=row.run+row.pull+row.net;
        fprintf(stderr,"V13_MODEL,%d,%d,%d,%d,%d,%d,%lld,%d,%d,%lld,%lld,%lld,%lld,%lld,%d",wi,int(row.seen),row.tick,w.arrive,w.dl,grace,w.v,w.n,finish,earned,cost,row.run,row.pull,row.net,row.runs);
        for(float value:row.x){fprintf(stderr,",%.9g",double(value));}fprintf(stderr,"\n");
    }
'''
    source=once(source,"""        if (now == T) break;
    }
}""","""        if (now == T) break;
    }
"""+dump+"}")
    directory=ROOT/"candidates/v13_model";directory.mkdir(parents=True,exist_ok=True)
    path=directory/"trace.cpp";exe=ROOT/"build/v13_model_trace.exe"
    if path.exists():assert path.read_bytes()==source.encode("utf8"),"Do not change an existing trace source"
    else:path.write_bytes(source.encode("utf8"))
    compiled=subprocess.run(["g++","-std=c++17","-O2","-Wall","-Wextra",str(path),"-o",str(exe)],capture_output=True,text=True,cwd=ROOT)
    assert compiled.returncode==0 and not compiled.stderr,compiled.stderr
    record={"base":str(BASE),"base_sha256":hashlib.sha256(BASE.read_bytes()).hexdigest(),"source":str(path),
            "source_sha256":hashlib.sha256(path.read_bytes()).hexdigest(),"executable":str(exe),"exe_sha256":hashlib.sha256(exe.read_bytes()).hexdigest(),
            "features":FEATURES,"schema":"V13_MODEL_META,HEADER,rows afterfinalEND only","official_submission_sent":False}
    (ROOT/"research/v13_model_trace_manifest.json").write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding="utf8")
    print(json.dumps({"source_sha256":record["source_sha256"],"features":len(FEATURES)}))


if __name__=="__main__":main()
