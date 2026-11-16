"""Evaluate a train-shortlisted policy on the already-known V8 worlds."""
from pathlib import Path
import argparse
import hashlib
import json
import subprocess
import sys
from compare import compare, markdown

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "results/v11_development"


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf8")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", required=True)
    parser.add_argument("--exe", required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--reason", required=True)
    parser.add_argument("--stage", default="v11", choices=["v11", "v12"])
    args = parser.parse_args()
    dest = ROOT / f"results/{args.stage}_development" / args.name
    assert not dest.exists(), "Do not overwrite an existing development experiment"
    dest.mkdir(parents=True)
    record = {"name": args.name, "source": str((ROOT / args.source).resolve()),
              "source_sha256": hashlib.sha256((ROOT / args.source).read_bytes()).hexdigest(),
              "executable": str((ROOT / args.exe).resolve()),
              "exe_sha256": hashlib.sha256((ROOT / args.exe).read_bytes()).hexdigest(),
              "selection_reason": args.reason,
              "scope": "Old V8 holdout/confirmation80; development only, not fresh V11 evidence"}
    dump(dest / "manifest.json", record)
    old, new = [], []
    for split in ["holdout", "confirmation"]:
        tested = subprocess.run([sys.executable, "tools/bench.py", "--exe", args.exe,
                                 "--cases", f"cases/v8_{split}", "--out", str(dest / split), "--workers", "1"],
                                cwd=ROOT, capture_output=True, text=True, encoding="utf8")
        assert tested.returncode == 0, tested.stdout+tested.stderr
        for rows, path in [(old, ROOT / f"results/v8_{split}_fine/summary.json"),
                           (new, dest / split / "summary.json")]:
            rows.extend(dict(r, case=f"{split}/"+r["case"]) for r in json.loads(path.read_text(encoding="utf8")))
    baseline, candidate = dest / "baseline", dest / "combined"
    dump(baseline / "summary.json", old)
    dump(candidate / "summary.json", new)
    value = compare(baseline, candidate)
    dump(dest / "comparison.json", value)
    (dest / "comparison.md").write_text(markdown(value), encoding="utf8")
    valid = value["valid_range_summary"]
    worst = min((r for r in value["rows"] if r["profit_ratio"] is not None), key=lambda r: r["profit_ratio"])
    record.update(valid_range=valid, worst=worst, all_health=value["candidate_health"])
    dump(dest / "manifest.json", record)
    print(json.dumps({"name": args.name, "pct": valid["total_profit_increase_pct"],
                      "mean_pct": valid["equal_weight_increase_pct"], "median": valid["median_profit_ratio"],
                      "up": valid["improved"], "down": valid["regressed"],
                      "worst": worst["profit_ratio"], "max_cpu": value["candidate_health"]["max_cpu_seconds"]}), flush=True)


if __name__ == "__main__":
    main()
