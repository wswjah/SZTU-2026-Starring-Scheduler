"""One further bracket step on four promising axes; never read validation."""
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
BASE = (ROOT / "versions/v6_attributed96/main.cpp").read_text(encoding="utf8")
CONFIGS = {"started_equal": {"SB": 1}, "stop_earlier_12": {"KILLK": 1.2},
           "admit_less_10": {"ADM": .10}, "racks_24": {"RK": 24}}
OUT = ROOT / "candidates/v7_bracket"
OUT.mkdir(parents=True, exist_ok=True)
results = []
for name, parameters in CONFIGS.items():
    source = BASE
    for key, value in parameters.items():
        source, n = re.subn(rf"PRM\({key},\s*[^)]+\)", f"PRM({key}, {value})", source)
        assert n == 1
    path = OUT / f"{name}.cpp"
    path.write_bytes(source.encode("utf8"))
    exe = ROOT / f"build/v7_bracket_{name}.exe"
    subprocess.run(["g++", "-std=c++17", "-O2", str(path), "-o", str(exe)], check=True, cwd=ROOT)
    dest = ROOT / f"results/v7_parameter_bracket/{name}"
    run = subprocess.run([sys.executable, "tools/bench.py", "--exe", str(exe), "--cases", "cases/train",
                          "--out", str(dest), "--workers", "2"], capture_output=True, text=True,
                         encoding="utf8", cwd=ROOT)
    assert run.returncode == 0, run.stdout + run.stderr
    comparison = compare(ROOT / "results/v6_attributed96_comparison/train", dest)
    (dest / "comparison.json").write_text(json.dumps(comparison, indent=2), encoding="utf8")
    (dest / "comparison.md").write_text(markdown(comparison), encoding="utf8")
    item = {"name": name, "parameters": parameters, "source": str(path),
            "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "executable": str(exe),
            "executable_sha256": hashlib.sha256(exe.read_bytes()).hexdigest(),
            "valid_range": comparison["valid_range_summary"], "boundary": comparison["boundary_pressure_summary"]}
    results.append(item)
    print(json.dumps({"name": name, "summary": item["valid_range"]}), flush=True)
(OUT / "manifest.json").write_text(json.dumps(results, indent=2), encoding="utf8")
(ROOT / "results/v7_parameter_bracket/summary.json").write_text(json.dumps(results, indent=2), encoding="utf8")
