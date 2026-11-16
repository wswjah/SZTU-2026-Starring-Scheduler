"""Bounded train and TS0 controls for V11 exact image quote variants."""
from pathlib import Path
import hashlib
import json
import re
import subprocess
import sys
from compare import compare,markdown

ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/"results/v11_pull"


def dump(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding="utf8")


def compile_source(source,exe,flags=()):
    result=subprocess.run(["g++","-std=c++17","-O2",*flags,str(source),"-o",str(exe)],cwd=ROOT,capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    return result


def bench(exe,dest,cases):
    run=subprocess.run([sys.executable,"tools/bench.py","--exe",str(exe),"--cases",*map(str,cases),"--out",str(dest),"--workers","1"],cwd=ROOT,capture_output=True,text=True,encoding="utf8")
    assert run.returncode==0,run.stdout+run.stderr
    return json.loads((dest/"summary.json").read_text(encoding="utf8"))


def diagnostics(rows):
    result={k:0 for k in ["previews","exact","first_mismatch","warm_residual","guard_samples","late_samples","guard_returns"]}
    worlds=[]
    for row in rows:
        stderr=(Path(row["run_dir"])/"solver_stderr.txt").read_text(encoding="utf8")
        values={k:float(v) if "." in v else int(v) for k,v in re.findall(r"\b([a-z_]+)=([\d.]+)",stderr)}
        for key in result:result[key]+=values[key]
        worlds.append({"case":row["case"],**values})
    return {"totals":result,"worlds":worlds}


def main():
    if hasattr(sys.stdout,"reconfigure"):sys.stdout.reconfigure(encoding="utf8")
    OUT.mkdir(parents=True,exist_ok=True)
    test_exe=ROOT/"build/v11_pull_tests.exe"
    compiled=compile_source(ROOT/"tools/v11_pull_tests.cpp",test_exe)
    tests=subprocess.run([str(test_exe)],cwd=ROOT,capture_output=True,text=True)
    assert tests.returncode==0,tests.stderr
    dump(OUT/"focused_tests.json",{"all_passed":True,"stdout":tests.stdout,"compiler_stderr":compiled.stderr,
                                "exe_sha256":hashlib.sha256(test_exe.read_bytes()).hexdigest()})
    print(tests.stdout.strip(),flush=True)
    configs=json.loads((ROOT/"research/v11_pull_manifest.json").read_text(encoding="utf8"))
    baseline=ROOT/"results/v10_input_verification/train/fixed"
    summaries=[]
    for config in configs:
        dest=OUT/config["name"]/"train"
        rows=bench(config["executable"],dest,[ROOT/"cases/train"])
        value=compare(baseline,dest)
        dump(dest/"comparison.json",value)
        (dest/"comparison.md").write_text(markdown(value),encoding="utf8")
        ratios=[r["profit_ratio"] for r in value["rows"] if not r["baseline_range_violations"] and r["profit_ratio"] is not None]
        record={**config,"valid_range":value["valid_range_summary"],"boundary":value["boundary_pressure_summary"],
                "all_health":value["candidate_health"],"worst_ratio":min(ratios),"diagnostics":diagnostics(rows)}
        summaries.append(record)
        dump(OUT/"summary.json",summaries)
        v=record["valid_range"]
        print(json.dumps({"name":config["name"],"pct":v["total_profit_increase_pct"],"up":v["improved"],"down":v["regressed"],"median":v["median_profit_ratio"],"mean_pct":v["equal_weight_increase_pct"],"worst":min(ratios),"max_cpu":value["candidate_health"]["max_cpu_seconds"],"guards":record["diagnostics"]["totals"]}),flush=True)
    # A small policy control, with all candidates and baseline using TS0.
    control_cases=[ROOT/f"cases/train/{name}.in" for name in ["standard_00","heavy_00","fast_00"]]
    sources={"baseline":ROOT/"versions/v10_input_fix/main.cpp",**{c["name"]:Path(c["source"]) for c in configs}}
    controls={}
    for name,src in sources.items():
        text=src.read_text(encoding="utf8")
        assert text.count("PRM(TS, 1);")==1
        text=text.replace("PRM(TS, 1);","PRM(TS, 0);")
        path=ROOT/f"candidates/v11_pull/{name}_ts0.cpp"
        assert not path.exists()
        path.write_bytes(text.encode("utf8"))
        exe=ROOT/f"build/v11_pull_{name}_ts0.exe"
        compile_source(path,exe)
        controls[name]=bench(exe,OUT/"ts0"/name,control_cases)
    control={}
    base={r["case"]:r for r in controls["baseline"]}
    production={r["case"]:r for r in json.loads((baseline/"summary.json").read_text(encoding="utf8"))}
    control["baseline_ts0_vs_ts1_full_reports"]={k:base[k]["report"]==production[k]["report"] for k in base}
    for name in [c["name"] for c in configs]:
        a={r["case"]:r for r in controls[name]}
        ts1={r["case"]:r for r in json.loads((OUT/name/"train/summary.json").read_text(encoding="utf8"))}
        control[name]={"ts0_vs_ts1_full_reports":{k:a[k]["report"]==ts1[k]["report"] for k in a},
                       "profit_vs_baseline":{k:{"baseline":base[k]["profit"],"candidate":a[k]["profit"],"delta":a[k]["profit"]-base[k]["profit"]} for k in a}}
    dump(OUT/"ts0_controls.json",control)
    dump(ROOT/"research/v11_pull_results.json",{"experiments":summaries,"ts0_controls":control,
         "focused_tests":"results/v11_pull/focused_tests.json","actual_runs":32+9,
         "audit_total":sum(r["audit_total"] for c in configs for r in json.loads((OUT/c["name"]/'train/summary.json').read_text(encoding="utf8")))+sum(r["audit_total"] for a in controls.values() for r in a),
         "official_submission_sent":False})
    print(json.dumps({"ts0_controls":control}),flush=True)


if __name__=="__main__":main()
