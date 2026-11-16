"""Fine single-axis and joint policy search on32 previously unused worlds."""
from pathlib import Path
import hashlib
import json
import re
import subprocess
import sys
from compare import compare, markdown

ROOT = Path(__file__).resolve().parent.parent
BASE = ROOT / "versions/v12_scan_input_fix/main.cpp"
EXPECTED = "d59972ba208958bca0688f432515e60edee920815596eb32644415d461224828"
CONFIGS = {
    "kill_109": {"KILLK": 1.09}, "kill_1095": {"KILLK": 1.095},
    "kill_1105": {"KILLK": 1.105}, "kill_111": {"KILLK": 1.11},
    "admit_045": {"ADM": .045}, "admit_0475": {"ADM": .0475},
    "admit_0525": {"ADM": .0525}, "admit_055": {"ADM": .055},
    "started_195": {"SB": 1.95}, "started_205": {"SB": 2.05},
    "tick_39": {"TH0": 3.9}, "tick_41": {"TH0": 4.1},
    "spread_0395": {"SP": .395}, "spread_0405": {"SP": .405},
    "slack_12": {"SL": 1.2}, "slack_13": {"SL": 1.3},
    "away_095": {"PEN": .95}, "away_105": {"PEN": 1.05},
    "joint_conservative1": {"KILLK": 1.105, "ADM": .0525, "SB": 2.05, "TH0": 4.1, "SP": .405, "SL": 1.3},
    "joint_conservative2": {"KILLK": 1.11, "ADM": .055, "SB": 2.05, "TH0": 4.1, "SP": .405, "SL": 1.25, "PEN": .95},
    "joint_aggressive1": {"KILLK": 1.095, "ADM": .0475, "SB": 1.95, "TH0": 3.9, "SP": .395, "SL": 1.2},
    "joint_aggressive2": {"KILLK": 1.09, "ADM": .045, "SB": 1.95, "TH0": 3.9, "SP": .395, "SL": 1.25, "PEN": 1.05},
    "joint_profit1": {"KILLK": 1.105, "ADM": .0475, "SB": 2.05, "TH0": 3.9, "SP": .4, "SL": 1.3, "PEN": .95},
    "joint_profit2": {"KILLK": 1.095, "ADM": .0525, "SB": 1.95, "TH0": 4.1, "SP": .4, "SL": 1.2, "PEN": 1.05},
}


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf8")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf8")
    assert hashlib.sha256(BASE.read_bytes()).hexdigest() == EXPECTED
    plan = ROOT / "research/v13_plan.json"
    assert not plan.exists(), "Do not silently change a declared search"
    dump(plan, {
        "date": "2026-11-16", "official_best": 99, "submissions_authorized": False,
        "base": str(BASE), "base_sha256": EXPECTED,
        "training": "cases/v13_train32:32 newly generated worlds, oldtrain16 no longer used to select parameters",
        "validation": "cases/v13_holdout40 andconfirmation40 frozen before outcomes, never fit",
        "fine_parameters": CONFIGS, "fine_config_count": len(CONFIGS),
        "small_model": "Current99-policy first-admission trace on same32 training worlds, wholeworldCV, tiny tree,4 predeclared closedloop policies",
        "selection": "Choose at most3 shortlisted sources from training+known old development;freeze before fresh40,then unchangedconfirmation40. Report aggregate/median/wins/worst and nonpositive baselines.",
        "controls": "All candidates retain8MiB fix, direct integer scanner, CPU insurance,20k budget. Default official99 files untouched.",
    })
    records = []
    base = BASE.read_text(encoding="utf8")
    for name, changes in CONFIGS.items():
        source = base
        for key, value in changes.items():
            source, count = re.subn(rf"PRM\({key},\s*[^)]+\)", f"PRM({key}, {value})", source)
            assert count == 1, key
        path = ROOT / f"candidates/v13_fine/{name}.cpp"
        path.parent.mkdir(parents=True, exist_ok=True)
        assert not path.exists()
        path.write_bytes(source.encode("utf8"))
        exe = ROOT / f"build/v13_fine_{name}.exe"
        build = subprocess.run(["g++", "-std=c++17", "-O2", str(path), "-o", str(exe)],
                               cwd=ROOT, capture_output=True, text=True)
        assert build.returncode == 0, build.stderr
        dest = ROOT / f"results/v13_fine/{name}"
        tested = subprocess.run([sys.executable, "tools/bench.py", "--exe", str(exe), "--cases", "cases/v13_train32",
                                 "--out", str(dest), "--workers", "1"], cwd=ROOT,
                                capture_output=True, text=True, encoding="utf8")
        assert tested.returncode == 0, tested.stdout+tested.stderr
        comparison = compare(ROOT / "results/v13_baseline_train32", dest)
        dump(dest / "comparison.json", comparison)
        (dest / "comparison.md").write_text(markdown(comparison), encoding="utf8")
        valid = comparison["valid_range_summary"]
        eligible = [r for r in comparison["rows"] if not r["baseline_range_violations"] and r["profit_ratio"] is not None]
        worst = min(eligible, key=lambda r: r["profit_ratio"])
        rows = json.loads((dest / "summary.json").read_text(encoding="utf8"))
        # Earned-value normalization avoids exploding ratios for near-zero profits.
        old = {r["case"]: r for r in json.loads((ROOT / "results/v13_baseline_train32/summary.json").read_text(encoding="utf8"))}
        normalized = [(r["profit"]-old[r["case"]]["profit"])/max(1, old[r["case"]]["earned"]) for r in rows]
        record = {"name": name, "parameters": changes, "source": str(path),
                  "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "executable": str(exe),
                  "exe_sha256": hashlib.sha256(exe.read_bytes()).hexdigest(), "valid_range": valid,
                  "boundary": comparison["boundary_pressure_summary"], "worst": worst,
                  "mean_profit_delta_per_baseline_earned": sum(normalized)/len(normalized),
                  "all_health": comparison["candidate_health"]}
        records.append(record)
        dump(dest / "manifest.json", record)
        dump(ROOT / "results/v13_fine/summary.json", records)
        print(json.dumps({"name": name, "pct": valid["total_profit_increase_pct"],
                          "median": valid["median_profit_ratio"], "up": valid["improved"], "down": valid["regressed"],
                          "worst": worst["profit_ratio"], "earned_norm_pct": 100*record["mean_profit_delta_per_baseline_earned"]}), flush=True)


if __name__ == "__main__":
    main()
