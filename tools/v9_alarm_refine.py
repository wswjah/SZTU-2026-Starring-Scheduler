"""Two bounded follow-ups: quarter loss and risk only for exactly equal quotes."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys
from compare import compare, markdown
from v9_alarm_candidates import make

ROOT = Path(__file__).resolve().parent.parent


def make_tie():
    source = (ROOT / "candidates/v9_alarm_normal.cpp").read_text(encoding="utf8")
    old = "    int bx = -1, bwarm = 0;"
    assert source.count(old) == 1
    source = source.replace(old, old + "\n    double bestRisk=1e100;")
    for old, new in [("if (cr.first >= best) continue;", "if (cr.first > best) continue;"),
                     ("if (cr.first + th * wt >= best) continue;", "if (cr.first + th * wt > best) continue;")]:
        assert source.count(old) == 1
        source = source.replace(old, new)
    old = """            cost+=v9RiskPenalty(x,wt,s,est,corePrice,th);
            warm+=v9RiskPenalty(x,wt,tts[r],est,corePrice,th);
            int wm = PW > 0 && warm < cost;
            if (wm) cost = warm, s = tts[r];
            if (cost < best) best = cost, bx = x, bw = wt, bs = s, bwarm = wm;"""
    new = """            // Preserve the baseline quote and warm decision; use risk only at exact ties.
            int wm = PW > 0 && warm < cost;
            if (wm) cost = warm, s = tts[r];
            double risk=v9RiskPenalty(x,wt,s,est,corePrice,th);
            if (cost < best || (cost == best && risk < bestRisk))
                best = cost, bx = x, bw = wt, bs = s, bwarm = wm, bestRisk=risk;"""
    assert source.count(old) == 1
    source = source.replace(old, new)
    path = ROOT / "candidates/v9_alarm_tie.cpp"
    assert not path.exists()
    path.write_bytes(source.encode("utf8"))
    exe = ROOT / "build/v9_alarm_tie.exe"
    run = subprocess.run(["g++", "-std=c++17", "-O2", "-Wall", "-Wextra", str(path), "-o", str(exe)],
                         capture_output=True, text=True, cwd=ROOT)
    assert run.returncode == 0 and not run.stderr, run.stderr
    return {"name": "tie", "source": str(path), "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "executable": str(exe), "exe_sha256": hashlib.sha256(exe.read_bytes()).hexdigest(),
            "rule": "Original quote/warm decision unchanged, smaller model penalty breaks exact quote ties only; equality pruning opened"}


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf8")
    records = [make(.25, "quarter"), make_tie()]
    (ROOT / "research/v9_alarm_refine_manifest.json").write_text(json.dumps(records, indent=2), encoding="utf8")
    results = []
    for record in records:
        dest = ROOT / f"results/v9_alarm_screen/{record['name']}"
        tested = subprocess.run([sys.executable, "tools/bench.py", "--exe", record["executable"],
                                 "--cases", "cases/train", "--out", str(dest), "--workers", "1"],
                                capture_output=True, text=True, encoding="utf8", cwd=ROOT)
        assert tested.returncode == 0, tested.stdout+tested.stderr
        comparison = compare(ROOT / "results/v9_alarm_baseline_train", dest)
        (dest / "comparison.json").write_text(json.dumps(comparison, indent=2), encoding="utf8")
        (dest / "comparison.md").write_text(markdown(comparison), encoding="utf8")
        valid = comparison["valid_range_summary"]
        record.update(valid_range=valid, boundary=comparison["boundary_pressure_summary"])
        results.append(record)
        (ROOT / "research/v9_alarm_refine_results.json").write_text(json.dumps(results, indent=2), encoding="utf8")
        print(json.dumps({"name": record["name"], "pct": valid["total_profit_increase_pct"],
                          "mean_pct": valid["equal_weight_increase_pct"], "up": valid["improved"],
                          "down": valid["regressed"]}), flush=True)


if __name__ == "__main__":
    main()
