"""Policy-identical production reduction of the already selected strict gate."""
from pathlib import Path
import hashlib
import json
import subprocess
from v13_model_common import ROOT,once

SOURCE=ROOT/"candidates/v13_model/veto_strict.cpp"


def make(source):
    old="struct V13ModelForecast {double rem=0,work=0,cost=0,rev=0;int tick=0,roots=0;};"
    source=once(source,old,"struct V13ModelForecast {double cost=0,rev=0;};")
    begin=source.index("void v13ModelFeatures(")
    end=source.index("static void v13ModelPredict",begin)
    old_feature=source[begin:end]
    feature="""void v13ModelFeatures(int ji,int,double,bool,float* x) {
    const Job& j=jobs[ji];const Flow& w=flows[j.wf];const V13ModelForecast& p=v13ModelForecasts[j.wf];
    double value=max(1.,double(w.v));
    x[5]=float((p.rev-p.cost)/value);
    x[10]=float(tenFactor(w.tenant));
}

"""
    source=once(source,old_feature,feature)
    source=once(source,"""ll v13ModelAttempts,v13ModelRejects,v13ModelLate,v13ModelGuardReturns;
#ifdef V13_MODEL_DISABLED
volatile double v13ModelDisabledSink;
#endif
""","")
    source=once(source,"    ++v13ModelAttempts;\n","")
    source=once(source,"    float x[18];v13ModelFeatures(ji,machine,prep,warm,x);","    float x[18]{};v13ModelFeatures(ji,machine,prep,warm,x);")
    source=once(source,"""    const auto& forecast=v13ModelForecasts[jobs[ji].wf];
    (void)forecast;
#ifdef V13_MODEL_DISABLED
    v13ModelDisabledSink=prediction[0]+prediction[1]+x[0];
    return true;
#else
""","")
    source=once(source,"""    v13ModelRejects+=!allow;
    return allow;
#endif""","""    return allow;""")
    source=once(source,"""            v13forecast.rem=rem;v13forecast.work=work;v13forecast.cost=cost;v13forecast.rev=rev;v13forecast.tick=now;""","""            v13forecast.cost=cost;v13forecast.rev=rev;""")
    source=once(source,"""                F(i,w.n)v13forecast.roots+=jobs[w.first+i].pre.empty();
""","")
    source=once(source,"""    v13ModelLate+=late>=0;
    if (used > .93 || (late > 0 && now % (1 << min(5, int(late / .04))))) {++v13ModelGuardReturns;return;}""","""    if (used > .93 || (late > 0 && now % (1 << min(5, int(late / .04))))) return;""")
    source=once(source,'    fprintf(stderr,"V13_MODEL_POLICY attempts=%lld rejects=%lld late=%lld guard_returns=%lld\\n",v13ModelAttempts,v13ModelRejects,v13ModelLate,v13ModelGuardReturns);\n',"")
    return source


def main():
    original=SOURCE.read_text(encoding="utf8")
    assert hashlib.sha256(SOURCE.read_bytes()).hexdigest()=="560c63b3dbcbe6341b315b1b56ef36f0d41dd902d12216bb5cb12ba3d4d5d55c"
    model=json.loads((ROOT/"research/v13_model_tree.json").read_text(encoding="utf8"))
    assert set(model["tree"]["feature"])-{-2}=={5,10}
    source=make(original)
    tree=(ROOT/"candidates/v13_model/tree.inc").read_text(encoding="ascii")
    assert tree in original and tree in source
    condition="bool allow=!(prediction[1]<0.08&&x[5]<0.4&&flows[jobs[ji].wf].n>=3);"
    assert condition in original and condition in source
    header=original[:original.index("#include <bits/stdc++.h>")]
    assert source.startswith(header)
    assert "tok[1 << 23]"in source and "v13BeforeJob"in source
    path=ROOT/"candidates/v13_model/production.cpp";exe=ROOT/"build/v13_model_production.exe"
    assert not path.exists();path.write_bytes(source.encode("utf8"))
    compiled=subprocess.run(["g++","-std=c++17","-O2","-Wall","-Wextra",str(path),"-o",str(exe)],capture_output=True,text=True,cwd=ROOT)
    assert compiled.returncode==0 and not compiled.stderr,compiled.stderr
    record={"date":"2026-11-16","selection_source":str(SOURCE),"selection_sha256":hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
            "source":str(path),"source_sha256":hashlib.sha256(path.read_bytes()).hexdigest(),"source_bytes":path.stat().st_size,
            "executable":str(exe),"exe_sha256":hashlib.sha256(exe.read_bytes()).hexdigest(),
            "only_runtime_features":[5,10],"tree_and_strict_gate_preserved_exactly":True,"original_header_preserved":True,
            "forecast_cached_at_same_original_schedule_point":True,"job_scalar_rejection_rollback_preserved":True,
            "no_retraining_or_policy_changes":True,"official_submission_sent":False,
            "interactive_verification":"Root will pack and compare80 full reports;this reduction task runs non-interactive audits only"}
    (ROOT/"research/v13_model_production.json").write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding="utf8")
    print(json.dumps(record,ensure_ascii=False))


if __name__=="__main__":main()
