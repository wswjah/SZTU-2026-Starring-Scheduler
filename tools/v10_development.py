"""Check three train-motivated alternatives on old V8 development worlds."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys
from compare import compare, markdown

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "results/v10_development"
CHOICES = {
    "reserve_15": "build/v10_fine_reserve_15.exe",
    "away_075": "build/v10_fine_away_075.exe",
    "path_growth_045": "build/v10_duration_path_growth_045.exe",
}


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf8")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf8")
    assert not (ROOT / "research/v10_development_plan.json").exists()
    dump(ROOT / "research/v10_development_plan.json", {
        "choices": CHOICES, "reason": "RESV15 positive aggregate/mean/median; PEN.75 positive median9 wins despite aggregate loss; BB.045 low-impact positive aggregate/mean",
        "scope": "Prior V8 holdout+confirmation80 become development, not fresh V10 evidence",
        "primary_candidate": "One-byte input buffer fix, retain all official99 parameters regardless of these results",
        "selection": "No additional configurations or combinations based on development outcomes",
    })
    old = []
    for split in ["holdout", "confirmation"]:
        rows = json.loads((ROOT / f"results/v8_{split}_fine/summary.json").read_text(encoding="utf8"))
        old += [dict(r, case=f"{split}/"+r["case"]) for r in rows]
    baseline = OUT / "baseline"
    dump(baseline / "summary.json", old)
    summary = []
    for name, executable in CHOICES.items():
        combined = []
        for split in ["holdout", "confirmation"]:
            dest = OUT / name / split
            run = subprocess.run([sys.executable, "tools/bench.py", "--exe", executable,
                                  "--cases", f"cases/v8_{split}", "--out", str(dest), "--workers", "1"],
                                 capture_output=True, text=True, encoding="utf8", cwd=ROOT)
            assert run.returncode == 0, run.stdout+run.stderr
            rows = json.loads((dest / "summary.json").read_text(encoding="utf8"))
            combined += [dict(r, case=f"{split}/"+r["case"]) for r in rows]
        dest = OUT / name / "combined"
        dump(dest / "summary.json", combined)
        comparison = compare(baseline, dest)
        dump(OUT / name / "comparison.json", comparison)
        (OUT / name / "comparison.md").write_text(markdown(comparison), encoding="utf8")
        v = comparison["valid_range_summary"]
        worst = min((r for r in comparison["rows"] if r["profit_ratio"] is not None), key=lambda r: r["profit_ratio"])
        row = {"name": name, "executable": executable,
               "exe_sha256": hashlib.sha256((ROOT / executable).read_bytes()).hexdigest(),
               "valid_range": v, "worst": worst}
        summary.append(row)
        dump(OUT / "summary.json", summary)
        print(json.dumps({"name": name, "pct": v["total_profit_increase_pct"], "up": v["improved"],
                          "down": v["regressed"], "mean_pct": v["equal_weight_increase_pct"],
                          "median": v["median_profit_ratio"], "worst": worst["profit_ratio"]}), flush=True)


if __name__ == "__main__":
    main()
