"""Closed-loop train-only screening of three declared alarm risk strengths."""
from pathlib import Path
import json
import subprocess
import sys
from compare import compare, markdown

ROOT = Path(__file__).resolve().parent.parent


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf8")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf8")
    old = json.loads((ROOT / "results/v8_fine_production/summary.json").read_text(encoding="utf8"))
    baseline = ROOT / "results/v9_alarm_baseline_train"
    dump(baseline / "summary.json", [r for r in old if Path(r["input"]).parent.name == "train"])
    configurations = json.loads((ROOT / "research/v9_alarm_candidates.json").read_text(encoding="utf8"))
    summary = []
    for config in configurations:
        dest = ROOT / f"results/v9_alarm_screen/{config['name']}"
        run = subprocess.run([sys.executable, "tools/bench.py", "--exe", config["executable"],
                              "--cases", "cases/train", "--out", str(dest), "--workers", "1"],
                             cwd=ROOT, capture_output=True, text=True, encoding="utf8")
        assert run.returncode == 0, run.stdout+run.stderr
        value = compare(baseline, dest)
        dump(dest / "comparison.json", value)
        (dest / "comparison.md").write_text(markdown(value), encoding="utf8")
        valid = value["valid_range_summary"]
        worst = min((r for r in value["rows"] if not r["baseline_range_violations"] and r["profit_ratio"] is not None),
                    key=lambda r: r["profit_ratio"])
        record = {**config, "valid_range": valid, "worst": worst,
                  "boundary": value["boundary_pressure_summary"]}
        summary.append(record)
        dump(ROOT / "results/v9_alarm_screen/summary.json", summary)
        print(json.dumps({"name": config["name"], "pct": valid["total_profit_increase_pct"],
                          "up": valid["improved"], "down": valid["regressed"],
                          "mean_pct": valid["equal_weight_increase_pct"], "worst": worst["profit_ratio"]}), flush=True)


if __name__ == "__main__":
    main()
