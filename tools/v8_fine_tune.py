"""Bounded V8 neighbourhood search; never selects from held-out outcomes."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import subprocess
import sys
from compare import compare, markdown
from make_cases import BASE, PROFILES

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "versions/v7_tuned/main.cpp"
BASELINE = ROOT / "results/v8_baseline_train"
CONFIGS = {
    "sb_15": {"SB": 1.5}, "sb_25": {"SB": 2.5}, "sb_10": {"SB": 1},
    "kill_105": {"KILLK": 1.05}, "kill_115": {"KILLK": 1.15},
    "adm_025": {"ADM": .025}, "adm_075": {"ADM": .075},
    "spread_035": {"SP": .35}, "spread_045": {"SP": .45},
    "racks_14": {"RK": 14}, "racks_20": {"RK": 20},
    "tickprice_4": {"TH0": 4}, "tickprice_6": {"TH0": 6},
    "lookahead_075": {"LAK": .75}, "lookahead_125": {"LAK": 1.25},
    "slack_075": {"SL": .75}, "slack_125": {"SL": 1.25},
}


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf8")


def initialize():
    rows = json.loads((ROOT / "results/v7_final_main/summary.json").read_text(encoding="utf8"))
    dump(BASELINE / "summary.json", [r for r in rows if Path(r["input"]).parent.name == "train"])
    directory = ROOT / "cases/v8_holdout"
    assert not directory.exists(), "Never regenerate held-out seeds"
    directory.mkdir(parents=True)
    manifest = []

    def write(name, cfg, category):
        raw = "".join(f"{k} {v}\n" for k, v in cfg.items()).encode("ascii")
        path = directory / f"{name}.in"
        path.write_bytes(raw)
        manifest.append({"file": path.name, "parameters": cfg, "category": category,
                         "sha256": hashlib.sha256(raw).hexdigest()})

    for i, (profile, changes) in enumerate(PROFILES.items()):
        for j in range(4):
            cfg = BASE | changes | {"seed": 381115741 + i * 19273 + j * 78101}
            if profile == "large":
                cfg.update(load=.65, log_rate=.08)
            if profile == "fast":
                cfg.update(load=.75)
            write(f"{profile}_{j:02}", cfg, "new_seed")
    shifts = {
        "very_fast": dict(bias_lo=.25, bias_hi=.65, sigma=.2, straggler_p=.01, load=.25),
        "very_slow": dict(bias_lo=1.8, bias_hi=3.2, sigma=.45, straggler_p=.14, load=.55),
        "no_failures": dict(fail_frac=0, blackswan=0, link_events=100),
        "uncertain": dict(sigma=.8, straggler_p=.2, load=.7),
        "high_failures": dict(fail_frac=.4, precursor_frac=.65, falsealarm_frac=.2, load=.7),
        "sparse": dict(load=.2, fail_frac=.1), "dense": dict(load=1.5),
        "changing": dict(quota_events=220, link_events=450, audit_rate=5, load=.75),
    }
    for i, (profile, changes) in enumerate(shifts.items()):
        write(f"shift_{profile}", BASE | {"log_rate": .10} | changes |
              {"seed": 381415741 + i * 91397}, "distribution_shift")
    dump(directory / "manifest.json", manifest)
    dump(ROOT / "research/v8_plan.json", {
        "base": str(SOURCE), "source_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        "single_axis_configs": CONFIGS, "max_combinations": 2,
        "training": "cases/train (14 checked-range + 2 boundary)",
        "development_replay": "V7 validation/confirmation become development data if reused; never fresh V8 evidence",
        "held_out": "cases/v8_holdout, 40 new worlds, final candidates frozen before outcome evaluation",
        "selection": "Prefer positive aggregate and equal-weight mean; inspect median and worst regression. At most two disjoint top-axis combinations, then freeze finalists based on training only.",
        "official_submission_authorized": False,
    })
    print("Prepared V7 train baseline and froze 40 held-out worlds", flush=True)


def run_config(name, parameters, result_group="v8_fine"):
    source = SOURCE.read_text(encoding="utf8")
    for key, value in parameters.items():
        source, count = re.subn(rf"PRM\({key},\s*[^)]+\)", f"PRM({key}, {value})", source)
        assert count == 1, key
    path = ROOT / "candidates/v8_fine" / f"{name}.cpp"
    path.parent.mkdir(parents=True, exist_ok=True)
    assert not path.exists(), f"Do not overwrite previous experiment {path}"
    path.write_bytes(source.encode("utf8"))
    exe = ROOT / f"build/v8_fine_{name}.exe"
    compiled = subprocess.run(["g++", "-std=c++17", "-O2", str(path), "-o", str(exe)],
                              cwd=ROOT, capture_output=True, text=True)
    assert compiled.returncode == 0, compiled.stderr
    dest = ROOT / f"results/{result_group}/{name}"
    tested = subprocess.run([sys.executable, "tools/bench.py", "--exe", str(exe), "--cases",
                             "cases/train", "--out", str(dest), "--workers", "1"],
                            cwd=ROOT, capture_output=True, text=True, encoding="utf8")
    assert tested.returncode == 0, tested.stdout + tested.stderr
    comparison = compare(BASELINE, dest)
    dump(dest / "comparison.json", comparison)
    (dest / "comparison.md").write_text(markdown(comparison), encoding="utf8")
    valid = comparison["valid_range_summary"]
    ratios = [r["profit_ratio"] for r in comparison["rows"]
              if not r["baseline_range_violations"] and not r["candidate_range_violations"]
              and r["profit_ratio"] is not None]
    record = {"name": name, "parameters": parameters, "source": str(path),
              "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "executable": str(exe),
              "exe_sha256": hashlib.sha256(exe.read_bytes()).hexdigest(),
              "valid_range": valid, "boundary": comparison["boundary_pressure_summary"],
              "worst_ratio": min(ratios), "result_dir": str(dest)}
    print(json.dumps({"name": name, "pct": valid["total_profit_increase_pct"],
                      "mean_pct": valid["equal_weight_increase_pct"], "up": valid["improved"],
                      "down": valid["regressed"], "worst": min(ratios)}, ensure_ascii=False), flush=True)
    return record


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--initialize", action="store_true")
    parser.add_argument("--screen", action="store_true")
    parser.add_argument("--config", help="A name for a single extra train-only combination")
    parser.add_argument("--parameters", help="JSON object for the extra combination")
    args = parser.parse_args()
    if args.initialize:
        initialize()
    if args.screen:
        records = []
        for name, parameters in CONFIGS.items():
            records.append(run_config(name, parameters))
            dump(ROOT / "results/v8_fine/summary.json", records)
    if args.config:
        record = run_config(args.config, json.loads(args.parameters), "v8_combinations")
        dump(ROOT / f"results/v8_combinations/{args.config}/manifest.json", record)


if __name__ == "__main__":
    main()
