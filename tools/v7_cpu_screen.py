"""Re-evaluate every shortlisted parameter under process-CPU timing on Windows."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys
from compare import compare, markdown
from v7_portable_clock import adapt

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf8")
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "candidates/v7_cpu"
RESULTS = ROOT / "results/v7_cpu_screen"
OUT.mkdir(parents=True, exist_ok=True)
configs = [{"name": "baseline", "source": str(ROOT / "versions/v6_attributed96/main.cpp")}]
for name in ["v7_params", "v7_combinations", "v7_bracket"]:
    configs += json.loads((ROOT / "candidates" / name / "manifest.json").read_text(encoding="utf8"))
manifest = []
for config in configs:
    name = config["name"]
    source = adapt(Path(config["source"]).read_text(encoding="utf8"))
    path = OUT / f"{name}.cpp"
    path.write_bytes(source.encode("utf8"))
    exe = ROOT / f"build/v7_cpu_{name}.exe"
    run = subprocess.run(["g++", "-std=c++17", "-O2", str(path), "-o", str(exe)],
                         cwd=ROOT, capture_output=True, text=True)
    assert run.returncode == 0, run.stderr
    manifest.append({"name": name, "upstream_source": config["source"], "source": str(path),
                     "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "executable": str(exe),
                     "exe_sha256": hashlib.sha256(exe.read_bytes()).hexdigest()})
    print(json.dumps({"compiled_cpu": name}), flush=True)
(OUT / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf8")
summary = []
for config in manifest:
    name = config["name"]
    dest = RESULTS / name
    run = subprocess.run([sys.executable, "tools/bench.py", "--exe", config["executable"],
                          "--cases", "cases/train", "--out", str(dest), "--workers", "2"],
                         cwd=ROOT, capture_output=True, text=True, encoding="utf8")
    assert run.returncode == 0, run.stdout + run.stderr
    comparison = compare(RESULTS / "baseline", dest)
    (dest / "comparison.json").write_text(json.dumps(comparison, indent=2), encoding="utf8")
    (dest / "comparison.md").write_text(markdown(comparison), encoding="utf8")
    valid = comparison["valid_range_summary"]
    valid_rows = [r for r in comparison["rows"] if not r["baseline_range_violations"] and not r["candidate_range_violations"]]
    item = {"name": name, "valid_range": valid, "boundary": comparison["boundary_pressure_summary"],
            "worst_ratio": min(r["profit_ratio"] for r in valid_rows),
            "best_ratio": max(r["profit_ratio"] for r in valid_rows)}
    summary.append(item)
    print(json.dumps({"name": name, "valid_profit_pct": valid["total_profit_increase_pct"],
                      "up": valid["improved"], "down": valid["regressed"],
                      "median": valid["median_profit_ratio"], "worst": item["worst_ratio"]}), flush=True)
    (RESULTS / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf8")
