"""Two disabled-gate controls, then all four predeclared policies on train32."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys
from bench import run_case
from compare import compare,markdown
from v13_model_common import ROOT


def main():
    records=json.loads((ROOT/"research/v13_model_policies.json").read_text(encoding="utf8"))
    baseline_dir=ROOT/"results/v13_baseline_train32"
    baseline={r["case"]:r for r in json.loads((baseline_dir/"summary.json").read_text(encoding="utf8"))}
    control_source=Path(next(r["source"]for r in records if r["name"]=="veto_strict"))
    control_exe=ROOT/"build/v13_model_disabled.exe"
    compiled=subprocess.run(["g++","-std=c++17","-O2","-Wall","-Wextra","-DV13_MODEL_DISABLED",str(control_source),"-o",str(control_exe)],capture_output=True,text=True,cwd=ROOT)
    assert compiled.returncode==0 and not compiled.stderr,compiled.stderr
    controls=[]
    for name in ["fast_00","standard_00"]:
        row=run_case(control_exe,ROOT/f"cases/v13_train32/{name}.in",ROOT/"results/v13_model_disabled")
        assert row["ok"] and row["report"]==baseline[name]["report"],(name,row["report"],baseline[name]["report"])
        controls.append(row)
    (ROOT/"results/v13_model_disabled/summary.json").write_text(json.dumps(controls,ensure_ascii=False,indent=2),encoding="utf8")
    summaries=[]
    for record in records:
        name=record["name"];out=ROOT/f"results/v13_model_policies/{name}"
        run=subprocess.run([sys.executable,"tools/bench.py","--exe",record["executable"],"--cases","cases/v13_train32","--out",str(out),"--workers","1"],capture_output=True,text=True,encoding="utf8",cwd=ROOT)
        assert run.returncode==0,run.stdout+run.stderr
        comparison=compare(baseline_dir,out)
        (out/"comparison.json").write_text(json.dumps(comparison,ensure_ascii=False,indent=2),encoding="utf8")
        (out/"comparison.md").write_text(markdown(comparison),encoding="utf8")
        rows=json.loads((out/"summary.json").read_text(encoding="utf8"))
        summary={**record,"valid_range":comparison["valid_range_summary"],"boundary":comparison["boundary_pressure_summary"],
                 "runs":len(rows),"audit_total":sum(r["audit_total"]for r in rows),"all_ok":all(r["ok"]for r in rows),"result_dir":str(out)}
        summaries.append(summary)
        (ROOT/"research/v13_model_screen.json").write_text(json.dumps({"controls_full_report_equal":True,"controls":2,"candidates":summaries},ensure_ascii=False,indent=2),encoding="utf8")
        stats=summary["valid_range"]
        print(json.dumps({"name":name,"profit_pct":stats["total_profit_increase_pct"],"up":stats["improved"],"down":stats["regressed"],"equal":stats["unchanged"]}),flush=True)


if __name__=="__main__":main()
