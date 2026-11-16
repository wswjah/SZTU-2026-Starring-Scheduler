"""Verify exact reports, then pair3 pressure repetitions in rotated order."""
from pathlib import Path
import hashlib
import json
import statistics
from bench import run_case

ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/"results/v11_perf_paired"
CONFIGS={"base":ROOT/"build/v10_input_fix.exe","memo":ROOT/"build/v11_perf_memo.exe","o3":ROOT/"build/v11_perf_o3.exe"}


def read(path):
    return json.loads((ROOT/path/"summary.json").read_text(encoding="utf8"))


def main():
    baseline={r["case"]:r for r in read("results/v10_input_verification/train/fixed")}
    train=[]
    for name in ["memo","o3"]:
        rows=read(f"results/v11_perf_{name}_train")
        assert len(rows)==16 and all(r["ok"] for r in rows)
        differences=[r["case"] for r in rows if r["report"]!=baseline[r["case"]]["report"]]
        assert not differences,(name,differences)
        train.append({"name":name,"all_full_reports_equal":True,"runs":16,"audit_total":sum(r["audit_total"]for r in rows),
                      "total_cpu":sum(r["solver_cpu_seconds"]for r in rows),"max_cpu":max(r["solver_cpu_seconds"]for r in rows)})
    pressure_baseline={r["case"]:r for r in read("results/v10_input_verification/stress/fixed")}
    cases=sorted((ROOT/"cases/stress").glob("*.in"))
    rows=[]
    names=list(CONFIGS)
    for repeat in range(3):
        for ci,case in enumerate(cases):
            order=names[(repeat+ci)%3:]+names[:(repeat+ci)%3]
            for name in order:
                result=run_case(CONFIGS[name],case,OUT/f"rep{repeat}"/name)
                assert result["ok"] and result["report"]==pressure_baseline[case.stem]["report"],(repeat,name,case,result["report"])
                rows.append(dict(result,config=name,repeat=repeat))
            print(json.dumps({"repeat":repeat,"case":case.stem,"complete":True}),flush=True)
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/"summary.json").write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding="utf8")
    total={name:sum(r["solver_cpu_seconds"]for r in rows if r["config"]==name) for name in names}
    bycase={case.stem:{name:statistics.median(r["solver_cpu_seconds"]for r in rows if r["config"]==name and r["case"]==case.stem)for name in names}for case in cases}
    result={"training":train,"paired_pressure_runs":len(rows),"all_reports_identical":True,"all_ok":True,
            "audit_total":sum(r["audit_total"]for r in rows),"total_cpu":total,
            "relative_total_cpu":{name:total[name]/total["base"]for name in names},
            "case_median_cpu":bycase,"order":"3 rotated repetitions percase,base/memo/O3 interleaved,all workers1",
            "configs":{name:{"exe":str(path),"exe_sha256":hashlib.sha256(path.read_bytes()).hexdigest()}for name,path in CONFIGS.items()},
            "official_submission_sent":False}
    (ROOT/"research/v11_perf_results.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf8")
    print(json.dumps({"total_cpu":total,"ratios":result["relative_total_cpu"],"medians":bycase}),flush=True)


if __name__=="__main__":main()
