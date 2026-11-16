"""Three declared combinations of the promising one-axis screen, train only."""
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
CONFIGS = {
    "priority_capacity": {"SB": 2, "RK": 16},
    "economic_margin": {"KILLK": 1.1, "ADM": .05},
    "combined": {"SB": 2, "RK": 16, "KILLK": 1.1, "ADM": .05},
}
out = ROOT / "candidates/v7_combinations"
out.mkdir(parents=True, exist_ok=True)
base = (ROOT / "versions/v6_attributed96/main.cpp").read_text(encoding="utf8")
manifest = []
for name, values in CONFIGS.items():
    source = base
    for key, value in values.items():
        source, n = re.subn(rf"PRM\({key},\s*[^)]+\)", f"PRM({key}, {value})", source)
        assert n == 1
    path = out / f"{name}.cpp"
    path.write_bytes(source.encode("utf8"))
    exe = ROOT / f"build/v7_combo_{name}.exe"
    subprocess.run(["g++", "-std=c++17", "-O2", str(path), "-o", str(exe)], cwd=ROOT, check=True)
    result_dir = ROOT / f"results/v7_parameter_combinations/{name}"
    ran = subprocess.run([sys.executable, "tools/bench.py", "--exe", str(exe), "--cases", "cases/train",
                          "--out", str(result_dir), "--workers", "2"], cwd=ROOT, capture_output=True,
                         text=True, encoding="utf8")
    assert ran.returncode == 0, ran.stdout + ran.stderr
    comparison = compare(ROOT / "results/v6_attributed96_comparison/train", result_dir)
    (result_dir / "comparison.json").write_text(json.dumps(comparison, indent=2), encoding="utf8")
    (result_dir / "comparison.md").write_text(markdown(comparison), encoding="utf8")
    item = {"name": name, "parameters": values, "source": str(path),
            "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "executable": str(exe),
            "executable_sha256": hashlib.sha256(exe.read_bytes()).hexdigest(),
            "valid_range": comparison["valid_range_summary"], "boundary": comparison["boundary_pressure_summary"]}
    manifest.append(item)
    print(json.dumps({"name": name, "valid": item["valid_range"]}), flush=True)
(out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf8")
(ROOT / "results/v7_parameter_combinations/summary.json").write_text(json.dumps(manifest, indent=2), encoding="utf8")
