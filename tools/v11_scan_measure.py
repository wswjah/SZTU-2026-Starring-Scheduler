"""Check complete train reports and optionally run a quiet-window paired test."""
from pathlib import Path
import argparse
import hashlib
import json
import statistics
from bench import run_case

ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/"results/v11_scan_paired"


def load(path):
    return json.loads((ROOT/path/"summary.json").read_text(encoding="utf8"))


def main():
    parser=argparse.ArgumentParser();parser.add_argument("--pressure",action="store_true");args=parser.parse_args()
    baseline={r["case"]:r for r in load("results/v10_input_verification/train/fixed")}
    train=load("results/v11_scan_train")
    assert len(train)==16 and all(r["ok"]for r in train)
    differences=[r["case"]for r in train if r["report"]!=baseline[r["case"]]["report"]]
    assert not differences,differences
    record={"train_runs":16,"all_full_reports_equal":True,"all_runs_ok":True,
            "audit_total":sum(r["audit_total"]for r in train),"audit_errors":sum(r["audit_errors"]for r in train),
            "illegal_commands":sum(r["incidents"]for r in train),
            "max_cpu_seconds":max(r["solver_cpu_seconds"]for r in train),
            "primitive_tests":"results/v11_scan_test/summary.json","pressure_started":False,
            "official_submission_sent":False}
    path=ROOT/"research/v11_scan_results.json"
    if args.pressure:
        assert not OUT.exists(),"Do not overwrite a previous timing run"
        old_stress={r["case"]:r for r in load("results/v10_input_verification/stress/fixed")}
        configs={"base":ROOT/"build/v10_input_fix.exe","scan":ROOT/"build/v11_scan.exe"}
        rows=[];cases=sorted((ROOT/"cases/stress").glob("*.in"))
        for repeat in range(3):
            for index,case in enumerate(cases):
                order=["base","scan"] if (repeat+index)%2==0 else ["scan","base"]
                for name in order:
                    result=run_case(configs[name],case,OUT/f"rep{repeat}"/name)
                    assert result["ok"] and result["report"]==old_stress[case.stem]["report"],(name,case,result["report"])
                    rows.append(dict(result,config=name,repeat=repeat))
                print(json.dumps({"repeat":repeat,"case":case.stem,"complete":True}),flush=True)
        OUT.mkdir(parents=True,exist_ok=True)
        (OUT/"summary.json").write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding="utf8")
        totals={name:sum(r["solver_cpu_seconds"]for r in rows if r["config"]==name)for name in configs}
        record.update(pressure_started=True,pressure_runs=len(rows),pressure_all_reports_equal=True,
                      pressure_audit_total=sum(r["audit_total"]for r in rows),pressure_cpu_totals=totals,
                      pressure_cpu_ratio=totals["scan"]/totals["base"],
                      pressure_case_medians={case.stem:{name:statistics.median(r["solver_cpu_seconds"]for r in rows if r["config"]==name and r["case"]==case.stem)for name in configs}for case in cases},
                      pressure_order="3 repetitions,case order fixed,base/scan interleaved with alternating first execution,workers1")
    path.write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding="utf8")
    print(json.dumps(record,ensure_ascii=False))


if __name__=="__main__":main()
