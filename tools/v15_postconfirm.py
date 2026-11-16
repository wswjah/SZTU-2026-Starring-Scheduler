"""An untouched40-world check after expanded-B emerged on the primary80."""
from pathlib import Path
import argparse
import hashlib
import json
import subprocess
import sys
from compare import compare, markdown
from v13_make_cases import write_set

ROOT = Path(__file__).resolve().parent.parent
NAMES = ["v12_scan_input_fix", "v14_mlp_A", "v14_mlp_B", "v15_B128_120"]


def load(path):
    return json.loads((ROOT / path).read_text(encoding="utf8"))


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf8")


def prepare():
    path = ROOT / "research/v15_postconfirmation_plan.json"
    assert not path.exists()
    choices = {name: load(f"versions/{name}/manifest.json") for name in NAMES}
    plan = {"date": "2026-11-16", "purpose": "Fresh40 after expandedB emerged from predeclared4 on primary80;no refitting or threshold changes",
        "selection_observed": "B128+0.5313% vs oldB-0.0460%,oldA+0.2961% on primary80;A refits flat;4-pressureB-0.4201% remains a risk",
        "fixed_candidates": choices, "generation": "Same32 profile+8shift layout,seed2021116287+i104729",
        "validation": "All four run on the same post40; compareB128 with oldB and oldA separately, retain all outcomes",
        "official_submission_sent": False}
    dump(path, plan)
    existing_seeds = set()
    for manifest in (ROOT / "cases").glob("*/manifest.json"):
        rows = json.loads(manifest.read_text(encoding="utf8"))
        if isinstance(rows, list):
            for row in rows:
                if "seed" in row.get("parameters", {}):
                    existing_seeds.add(row["parameters"]["seed"])
    entries = []
    for i, row in enumerate(load("cases/v15_holdout/manifest.json")):
        parameters = dict(row["parameters"])
        parameters["seed"] = 2021116287+i*104729
        assert parameters["seed"] not in existing_seeds
        entries.append((row["file"], parameters, row["category"]))
    write_set("v15_postconfirmation", entries)
    print("Frozen selected-policy postconfirmation40;weights/policies unchanged")


def run(name):
    plan = load("research/v15_postconfirmation_plan.json")
    version = plan["fixed_candidates"][name]
    assert hashlib.sha256(Path(version["executable"]).read_bytes()).hexdigest() == version["exe_sha256"]
    suffix = "baseline" if name == "v12_scan_input_fix" else name
    dest = ROOT / f"results/v15_postconfirmation_{suffix}"
    assert not dest.exists()
    result = subprocess.run([sys.executable, "tools/bench.py", "--exe", version["executable"],
        "--cases", "cases/v15_postconfirmation", "--out", str(dest), "--workers", "1"],
        cwd=ROOT, capture_output=True, text=True, encoding="utf8")
    assert result.returncode == 0, result.stdout+result.stderr
    rows = load(str(dest / "summary.json"))
    assert len(rows) == 40 and all(r["ok"] for r in rows)
    print(json.dumps({"name": name, "postconfirmation_runs": 40, "all_healthy": True}), flush=True)


def reporting():
    out = ROOT / "results/v15_postconfirmation_report"
    out.mkdir(parents=True, exist_ok=True)
    results, runs = {}, []
    for name in NAMES:
        suffix = "baseline" if name == "v12_scan_input_fix" else name
        rows = load(f"results/v15_postconfirmation_{suffix}/summary.json")
        runs += rows
        if suffix == "baseline":
            continue
        value = compare(ROOT / "results/v15_postconfirmation_baseline", ROOT / f"results/v15_postconfirmation_{suffix}")
        dump(out / (name+".json"), value)
        (out / (name+".md")).write_text(markdown(value), encoding="utf8")
        results[name] = {"post40": value["valid_range_summary"], "health": value["candidate_health"],
            "worst": min((r for r in value["rows"] if r["profit_ratio"] is not None), key=lambda r:r["profit_ratio"])}
        old, new = [], []
        for split in ["holdout", "confirmation", "postconfirmation"]:
            old += [dict(r,case=split+"/"+r["case"])for r in load(f"results/v15_{split}_baseline/summary.json")]
            new += [dict(r,case=split+"/"+r["case"])for r in load(f"results/v15_{split}_{name}/summary.json")]
        for label, values in [("baseline120", old), (name+"_120", new)]:
            dump(out / label / "summary.json", values)
        combined = compare(out / "baseline120", out / (name+"_120"))
        dump(out / (name+"_120.json"), combined)
        results[name]["new120"] = combined["valid_range_summary"]
    for reference in ["v14_mlp_A", "v14_mlp_B"]:
        value = compare(ROOT / f"results/v15_postconfirmation_{reference}", ROOT / "results/v15_postconfirmation_v15_B128_120")
        results["v15_B128_120"]["post40_vs_"+reference] = value["valid_range_summary"]
        combined = compare(out / (reference+"_120"), out / "v15_B128_120_120")
        results["v15_B128_120"]["new120_vs_"+reference] = combined["valid_range_summary"]
    assert len(runs) == 160 and all(r["ok"] and r["audit_errors"]==0 and r["incidents"]==0 for r in runs)
    record = {"comparisons": results, "health": {"runs": 160, "audit_total": sum(r["audit_total"]for r in runs),
        "audit_errors": 0, "illegal_commands": 0, "max_cpu_seconds": max(r["solver_cpu_seconds"]for r in runs)},
        "no_refit_or_threshold_change": True, "official_submission_sent": False}
    dump(ROOT / "research/v15_postconfirmation_results.json", record)
    print(json.dumps({"post40": {k:v["post40"]["total_profit_increase_pct"]for k,v in results.items()},
        "combined120": {k:v["new120"]["total_profit_increase_pct"]for k,v in results.items()}, "health":record["health"]}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["prepare", "run", "report"])
    parser.add_argument("--name", choices=NAMES)
    args = parser.parse_args()
    if args.mode == "prepare":
        prepare()
    elif args.mode == "run":
        assert args.name
        run(args.name)
    else:
        reporting()
