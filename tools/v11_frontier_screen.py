"""Finish the two predeclared frontier trials from their audited sources."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys
from compare import compare, markdown

ROOT = Path(__file__).resolve().parent.parent


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf8")
    configs = json.loads((ROOT / "research/v11_frontier_manifest.json").read_text(encoding="utf8"))
    records = []
    for config in configs:
        assert hashlib.sha256(Path(config["source"]).read_bytes()).hexdigest() == config["source_sha256"]
        assert hashlib.sha256(Path(config["executable"]).read_bytes()).hexdigest() == config["exe_sha256"]
        dest = ROOT / f"results/v11_frontier/{config['name']}"
        assert not dest.exists(), "Do not replace a completed trial"
        tested = subprocess.run([sys.executable, "tools/bench.py", "--exe", config["executable"],
                                 "--cases", "cases/train", "--out", str(dest), "--workers", "1"],
                                cwd=ROOT, capture_output=True, text=True, encoding="utf8")
        assert tested.returncode == 0, tested.stdout+tested.stderr
        value = compare(ROOT / "results/v11_baseline_train", dest)
        (dest / "comparison.json").write_text(json.dumps(value, indent=2), encoding="utf8")
        (dest / "comparison.md").write_text(markdown(value), encoding="utf8")
        v = value["valid_range_summary"]
        worst = min((r for r in value["rows"] if not r["baseline_range_violations"] and r["profit_ratio"] is not None),
                    key=lambda r: r["profit_ratio"])
        raw = json.loads((dest / "summary.json").read_text(encoding="utf8"))
        diagnostics = [{"case": r["case"], "diagnostic": (Path(r["run_dir"]) / "solver_stderr.txt").read_text(encoding="utf8").strip()}
                       for r in raw]
        record = {**config, "valid_range": v, "boundary": value["boundary_pressure_summary"],
                  "worst": worst, "health": value["candidate_health"], "diagnostics": diagnostics}
        records.append(record)
        (ROOT / "research/v11_frontier_results.json").write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf8")
        print(json.dumps({"name": config["name"], "pct": v["total_profit_increase_pct"],
                          "mean_pct": v["equal_weight_increase_pct"], "median": v["median_profit_ratio"],
                          "up": v["improved"], "down": v["regressed"], "worst": worst["profit_ratio"],
                          "max_cpu": value["candidate_health"]["max_cpu_seconds"]}), flush=True)


if __name__ == "__main__":
    main()
