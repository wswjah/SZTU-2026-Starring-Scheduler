"""Bounded, one-axis local parameter screening from the immutable 96-point base."""
from pathlib import Path
import hashlib
import json
import re
import subprocess
import sys
from compare import compare, markdown

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf8")
ROOT = Path(__file__).resolve().parent.parent
BASE = ROOT / "versions/v6_attributed96/main.cpp"
BASELINE = ROOT / "results/v6_attributed96_comparison/train"
CONFIGS = [("spread_low", "SP", .30), ("spread_high", "SP", .50),
           ("started_low", "SB", 2), ("started_high", "SB", 4),
           ("stop_later", "KILLK", .9), ("stop_earlier", "KILLK", 1.1),
           ("admit_more", "ADM", -.05), ("admit_less", "ADM", .05),
           ("racks_8", "RK", 8), ("racks_16", "RK", 16)]


def main():
    source = BASE.read_text(encoding="utf8")
    out = ROOT / "candidates/v7_params"
    out.mkdir(parents=True, exist_ok=True)
    manifest = []
    for name, key, value in CONFIGS:
        raw, count = re.subn(rf"PRM\({key},\s*[^)]+\)", f"PRM({key}, {value})", source)
        assert count == 1, key
        path = out / f"{name}.cpp"
        path.write_bytes(raw.encode("utf8"))
        exe = ROOT / "build" / f"v7_param_{name}.exe"
        compiled = subprocess.run(["g++", "-std=c++17", "-O2", str(path), "-o", str(exe)],
                                  cwd=ROOT, capture_output=True, text=True)
        assert compiled.returncode == 0, compiled.stderr
        manifest.append({"name": name, "parameter": key, "value": value,
                         "source": str(path), "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                         "executable": str(exe), "executable_sha256": hashlib.sha256(exe.read_bytes()).hexdigest()})
        print(json.dumps({"compiled": name}), flush=True)
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf8")
    summaries = []
    for config in manifest:
        result_dir = ROOT / "results/v7_parameter_screen" / config["name"]
        run = subprocess.run([sys.executable, "tools/bench.py", "--exe", config["executable"],
                              "--cases", "cases/train", "--out", str(result_dir), "--workers", "2"],
                             cwd=ROOT, capture_output=True, text=True, encoding="utf8")
        assert run.returncode == 0, run.stdout + run.stderr
        comparison = compare(BASELINE, result_dir)
        (result_dir / "comparison.json").write_text(json.dumps(comparison, indent=2), encoding="utf8")
        (result_dir / "comparison.md").write_text(markdown(comparison), encoding="utf8")
        valid = comparison["valid_range_summary"]
        valid_rows = [r for r in comparison["rows"] if not r["baseline_range_violations"] and not r["candidate_range_violations"]]
        row = {"name": config["name"], "parameter": config["parameter"], "value": config["value"],
               "valid_range": valid, "boundary": comparison["boundary_pressure_summary"],
               "worst_ratio": min(r["profit_ratio"] for r in valid_rows),
               "best_ratio": max(r["profit_ratio"] for r in valid_rows)}
        summaries.append(row)
        print(json.dumps({"name": row["name"], "profit_pct": valid["total_profit_increase_pct"],
                          "up": valid["improved"], "down": valid["regressed"],
                          "median": valid["median_profit_ratio"], "worst": row["worst_ratio"]}), flush=True)
        target = ROOT / "results/v7_parameter_screen/summary.json"
        target.write_text(json.dumps(summaries, ensure_ascii=False, indent=2), encoding="utf8")


if __name__ == "__main__":
    main()
