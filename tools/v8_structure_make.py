"""Two predeclared quota-aware completion forecasts, based on frozen V7."""
from pathlib import Path
import hashlib
import json
import subprocess

ROOT = Path(__file__).resolve().parent.parent
BASE = ROOT / "versions/v7_tuned/main.cpp"
source = BASE.read_text(encoding="utf8")
records = []
for name, discount in [("quota", 0), ("contention", .5)]:
    candidate = source.replace(
        "double jobEnd[1 << 17]", 
        "long long v8Forecasts, v8Bounds;\ndouble v8BoundExtra;\n"
        "double jobEnd[1 << 17]", 1)
    candidate = candidate.replace(
        "rem = work = cost = 0;\n    F(i, w.n)",
        "rem = work = cost = 0;\n    int ownRunning = 0;\n    F(i, w.n)", 1)
    candidate = candidate.replace(
        "work += j.c * du[i];",
        "work += j.c * du[i];\n        if (j.state) ownRunning += j.c;", 1)
    anchor = "    ll g = max(5, (w.dl - w.arrive) / 3);\n    for (int i = w.n - 1;"
    assert candidate.count(anchor) == 1
    addition = f"""    // A DAG cannot finish sooner than its remaining core-ticks fit the quota.
    // Competing running work is discounted rather than treated as permanent.
    double capacity = 1e18;
    for (int a = w.tenant; a >= 0; a = tenPar[a])
        capacity = min(capacity, double(tenQuota[a]) - {discount} * max(0LL, tenUsed[a] - ownRunning));
    double bound = work / max(1.0, capacity);
    ++v8Forecasts;
    if (bound > rem) {{ ++v8Bounds; v8BoundExtra += bound - rem; rem = bound; }}
"""
    candidate = candidate.replace(anchor, addition + anchor)
    ending = "        if (now == T) break;\n    }\n}"
    assert candidate.count(ending) == 1
    candidate = candidate.replace(ending, "        if (now == T) break;\n    }\n"
        '    fprintf(stderr, "v8_forecasts=%lld v8_bounds=%lld v8_extra=%.9f\\n", v8Forecasts, v8Bounds, v8BoundExtra);\n}')
    path = ROOT / f"candidates/v8_structure_{name}.cpp"
    exe = ROOT / f"build/v8_structure_{name}.exe"
    path.write_bytes(candidate.encode("utf8"))
    subprocess.run(["g++", "-std=c++17", "-O2", "-Wall", "-Wextra", str(path), "-o", str(exe)], check=True)
    records.append({"name": name, "source": str(path), "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    "executable": str(exe), "exe_sha256": hashlib.sha256(exe.read_bytes()).hexdigest(),
                    "discount_competing_usage": discount, "base_sha256": hashlib.sha256(BASE.read_bytes()).hexdigest()})
(ROOT / "research/v8_structure_manifest.json").write_text(json.dumps(records, indent=2), encoding="utf8")
print(json.dumps(records))
