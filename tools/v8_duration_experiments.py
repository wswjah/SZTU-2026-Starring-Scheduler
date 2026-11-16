"""Two predeclared V8 duration structures; train-only, no submission/network."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys
from compare import compare, markdown

ROOT = Path(__file__).resolve().parent.parent
BASE = ROOT / "versions/v7_tuned/main.cpp"


def once(source, old, new):
    assert source.count(old) == 1, repr(old)
    return source.replace(old, new)


def path_noise(source):
    source = once(source, "double revenueAt(Flow& w, double f) {", "double v8FlowSpread = 1;\n\ndouble revenueAt(Flow& w, double f) {")
    source = once(source, "static double st[1 << 16], du[1 << 16];", "static double st[1 << 16], du[1 << 16], pathSq[1 << 16];\n    double longestSq = 0;")
    source = once(source, "        for (int p : j.pre) st[i] = max(st[i], st[p - w.first] + du[p - w.first]);", """        pathSq[i] = 0;
        for (int p : j.pre) {
            double finish = st[p - w.first] + du[p - w.first];
            if (finish > st[i]) st[i] = finish, pathSq[i] = pathSq[p - w.first];
        }""")
    source = once(source, "        rem = max(rem, st[i] + du[i]);", """        pathSq[i] += du[i] * du[i];
        if (st[i] + du[i] > rem) rem = st[i] + du[i], longestSq = pathSq[i];""")
    source = once(source, "    ll g = max(5, (w.dl - w.arrive) / 3);\n    for (int i = w.n - 1;", """    // Keep half the variance shared by the tenant; aggregate the other half
    // over the predicted critical path instead of treating all jobs as one shock.
    v8FlowSpread = sqrt(.5 + .5 * min(1.0, longestSq / (rem * rem + 1e-9)));
    ll g = max(5, (w.dl - w.arrive) / 3);
    for (int i = w.n - 1;""")
    source = once(source, "rem * (1 + SP * sc[k])", "rem * (1 + SP * v8FlowSpread * sc[k])")
    return source


def refresh_running(source):
    return once(source,
        "jobEnd[q] = max(now + 1 + OD * el, jobEnd[q])",
        "jobEnd[q] = max(now + 1 + OD * el, jobs[q].t0 + jobs[q].prep + max(1.0, jobs[q].e * tenF[o]))")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf8")
    baseline = json.loads((ROOT / "results/v7_final_main/summary.json").read_text(encoding="utf8"))
    out = ROOT / "results/v8_duration"
    out.mkdir(parents=True, exist_ok=True)
    base_dir = out / "baseline_train"
    base_dir.mkdir(exist_ok=True)
    baseline = [r for r in baseline if Path(r["input"]).parent.name == "train"]
    assert len(baseline) == 16
    (base_dir / "summary.json").write_text(json.dumps(baseline, indent=2), encoding="utf8")
    source = BASE.read_text(encoding="utf8")
    records = []
    for name, change in [("path_noise", path_noise), ("refresh_running", refresh_running)]:
        path = ROOT / f"candidates/v8_duration_{name}.cpp"
        assert not path.exists(), "Preserve previous experiment artifacts"
        text = change(source)
        path.write_bytes(text.encode("utf8"))
        exe = path.with_suffix(".exe")
        subprocess.run(["g++", "-std=c++17", "-O2", "-Wall", "-Wextra", str(path), "-o", str(exe)], check=True, cwd=ROOT)
        dest = out / name
        subprocess.run([sys.executable, "tools/bench.py", "--exe", str(exe), "--cases", "cases/train", "--out", str(dest), "--workers", "1"], check=True, cwd=ROOT)
        value = compare(base_dir, dest)
        (dest / "comparison.json").write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf8")
        (dest / "comparison.md").write_text(markdown(value), encoding="utf8")
        valid_rows = [r for r in value["rows"] if not r["baseline_range_violations"] and not r["candidate_range_violations"]]
        record = {"name": name, "source": str(path), "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                  "executable": str(exe), "exe_sha256": hashlib.sha256(exe.read_bytes()).hexdigest(),
                  "valid_range": value["valid_range_summary"], "boundary": value["boundary_pressure_summary"],
                  "worst_valid": min(valid_rows, key=lambda r: r["profit_ratio"]), "health": value["candidate_health"]}
        records.append(record)
        (ROOT / "research/v8_duration_results.json").write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf8")
        print(json.dumps({"completed": name, "valid": record["valid_range"], "worst": record["worst_valid"]}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
