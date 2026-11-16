"""Run all eight fixed NN gates only on train32;select<=1 positive perarchitecture."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys
from bench import run_case
from compare import compare,markdown
from v13_model_common import ROOT


def main():
    numeric=json.loads((ROOT/"research/v14_mlp_numeric.json").read_text(encoding="utf8"));assert numeric["all_passed"]
    records=json.loads((ROOT/"research/v14_mlp_policies.json").read_text(encoding="utf8"))
    baseline_dir=ROOT/"results/v13_baseline_train32"
    baseline={r["case"]:r for r in json.loads((baseline_dir/"summary.json").read_text(encoding="utf8"))}
    controls=[]
    for architecture in ["A","B"]:
        source=Path(next(r["source"]for r in records if r["name"]==f"{architecture}_veto_strict"))
        exe=ROOT/f"build/v14_mlp_{architecture}_disabled.exe"
        compiled=subprocess.run(["g++","-std=c++17","-O2","-Wall","-Wextra","-DV13_MODEL_DISABLED",str(source),"-o",str(exe)],capture_output=True,text=True,cwd=ROOT)
        assert compiled.returncode==0 and not compiled.stderr,compiled.stderr
        for case in ["fast_00","standard_00"]:
            result=run_case(exe,ROOT/f"cases/v13_train32/{case}.in",ROOT/f"results/v14_mlp_disabled/{architecture}")
            assert result["ok"]and result["report"]==baseline[case]["report"],(architecture,case,result["report"],baseline[case]["report"])
            controls.append(dict(result,architecture=architecture))
    (ROOT/"results/v14_mlp_disabled/summary.json").write_text(json.dumps(controls,ensure_ascii=False,indent=2),encoding="utf8")
    summaries=[]
    for record in records:
        assert hashlib.sha256(Path(record["source"]).read_bytes()).hexdigest()==record["source_sha256"]
        out=ROOT/f"results/v14_mlp_train/{record['name']}"
        run=subprocess.run([sys.executable,"tools/bench.py","--exe",record["executable"],"--cases","cases/v13_train32","--out",str(out),"--workers","1"],capture_output=True,text=True,encoding="utf8",cwd=ROOT)
        assert run.returncode==0,run.stdout+run.stderr
        comparison=compare(baseline_dir,out)
        (out/"comparison.json").write_text(json.dumps(comparison,ensure_ascii=False,indent=2),encoding="utf8")
        (out/"comparison.md").write_text(markdown(comparison),encoding="utf8")
        rows=json.loads((out/"summary.json").read_text(encoding="utf8"))
        summary={**record,"valid_range":comparison["valid_range_summary"],"boundary":comparison["boundary_pressure_summary"],
                 "runs":len(rows),"audit_total":sum(r["audit_total"]for r in rows),"all_ok":all(r["ok"]for r in rows),"result_dir":str(out)}
        summaries.append(summary)
        (ROOT/"research/v14_mlp_screen.json").write_text(json.dumps({"disabled_controls":4,"all_disabled_reports_equal":True,"candidates":summaries},ensure_ascii=False,indent=2),encoding="utf8")
        s=summary["valid_range"]
        print(json.dumps({"name":record["name"],"profit_pct":s["total_profit_increase_pct"],"up":s["improved"],"down":s["regressed"],"equal":s["unchanged"]}),flush=True)
    selected=[]
    for architecture in ["A","B"]:
        possibilities=[r for r in summaries if r["architecture"]==architecture and r["valid_range"]["total_profit_increase_pct"]>0]
        if not possibilities:continue
        best=max(possibilities,key=lambda r:r["valid_range"]["total_profit_increase_pct"])
        selected.append({k:best[k]for k in ["architecture","name","policy","source","source_sha256","executable"]}|
                        {"training_profit_increase_pct":best["valid_range"]["total_profit_increase_pct"],
                         "selection_reason":"Highest positive aggregate train32 profit amongthe4 predeclared policies for thisarchitecture;no fresh outcomes read,no extra fitting or thresholds"})
    (ROOT/"research/v14_mlp_selected.json").write_text(json.dumps(selected,ensure_ascii=False,indent=2),encoding="utf8")
    print(json.dumps({"selected":selected},ensure_ascii=False),flush=True)


if __name__=="__main__":main()
