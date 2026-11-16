"""A bounded neighbourhood search from the exact official99 source."""
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
SOURCE = ROOT / "versions/v8_fine/main.cpp"
EXPECTED = "b39a299e1983d1837393cdce80fce6ffbdaa209df170a7d865069df011514e3d"
BASELINE = ROOT / "results/v10_baseline_train"
CONFIGS = {
    "tickprice_3": {"TH0": 3}, "tickprice_35": {"TH0": 3.5}, "tickprice_45": {"TH0": 4.5},
    "slack_11": {"SL": 1.1}, "slack_14": {"SL": 1.4}, "slack_15": {"SL": 1.5},
    "started_175": {"SB": 1.75}, "started_225": {"SB": 2.25},
    "kill_1075": {"KILLK": 1.075}, "kill_1125": {"KILLK": 1.125},
    "admit_04": {"ADM": .04}, "admit_06": {"ADM": .06},
    "spread_0375": {"SP": .375}, "spread_0425": {"SP": .425},
    "away_075": {"PEN": .75}, "away_125": {"PEN": 1.25},
    "reserve_15": {"RESV": 15}, "reserve_45": {"RESV": 45},
    "registry_08": {"RF": .8}, "registry_12": {"RF": 1.2},
}


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf8")


def initialize():
    assert hashlib.sha256(SOURCE.read_bytes()).hexdigest() == EXPECTED
    rows = json.loads((ROOT / "results/v8_fine_production/summary.json").read_text(encoding="utf8"))
    dump(BASELINE / "summary.json", [r for r in rows if Path(r["input"]).parent.name == "train"])
    out = ROOT / "cases/v10_holdout"
    assert not out.exists(), "Never regenerate held-out inputs"
    out.mkdir(parents=True)
    manifest = []

    def write(name, cfg, category):
        raw = "".join(f"{k} {v}\n" for k, v in cfg.items()).encode("ascii")
        path = out / f"{name}.in"
        path.write_bytes(raw)
        manifest.append({"file": path.name, "parameters": cfg, "category": category,
                         "sha256": hashlib.sha256(raw).hexdigest(),
                         "purpose": "V10 final frozen candidates only; no fitting on these outcomes"})

    for i, (profile, changes) in enumerate(PROFILES.items()):
        for j in range(4):
            cfg = BASE | changes | {"seed": 601115183 + i*19139 + j*78163}
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
              {"seed": 601415183 + i*91393}, "distribution_shift")
    dump(out / "manifest.json", manifest)
    dump(ROOT / "research/v10_plan.json", {
        "base": str(SOURCE), "base_sha256": EXPECTED, "official_best": 99,
        "root_configs": CONFIGS, "duration_configs_count": 14,
        "max_root_combinations": 3, "max_duration_combinations": 1,
        "train": "cases/train,14 checked range+2 large log boundaries",
        "development": "V8 holdout/confirmation80 now development only, previous results known",
        "fresh": "cases/v10_holdout40 frozen before any V10 result",
        "selection": "Train shortlist then development80. Prefer broad case gains and positive median/equal-weight mean, report all losses. Freeze at most2 finalists before fresh evaluation.",
        "correctness": "Independent protocol/state/bounds audit in parallel; only concrete reproducible fixes considered",
        "official_submission_authorized": False,
    })
    print("V10 train baseline prepared;40 fresh worlds frozen", flush=True)


def run_config(name, parameters, group="v10_fine"):
    source = SOURCE.read_text(encoding="utf8")
    assert hashlib.sha256(SOURCE.read_bytes()).hexdigest() == EXPECTED
    for key, value in parameters.items():
        source, count = re.subn(rf"PRM\({key},\s*[^)]+\)", f"PRM({key}, {value})", source)
        assert count == 1, key
    path = ROOT / "candidates/v10_fine" / f"{name}.cpp"
    path.parent.mkdir(parents=True, exist_ok=True)
    assert not path.exists(), f"Never overwrite existing experiment {name}"
    path.write_bytes(source.encode("utf8"))
    exe = ROOT / f"build/v10_fine_{name}.exe"
    compiled = subprocess.run(["g++", "-std=c++17", "-O2", str(path), "-o", str(exe)],
                              cwd=ROOT, capture_output=True, text=True)
    assert compiled.returncode == 0, compiled.stderr
    dest = ROOT / f"results/{group}/{name}"
    tested = subprocess.run([sys.executable, "tools/bench.py", "--exe", str(exe), "--cases",
                             "cases/train", "--out", str(dest), "--workers", "1"],
                            cwd=ROOT, capture_output=True, text=True, encoding="utf8")
    assert tested.returncode == 0, tested.stdout+tested.stderr
    value = compare(BASELINE, dest)
    dump(dest / "comparison.json", value)
    (dest / "comparison.md").write_text(markdown(value), encoding="utf8")
    valid = value["valid_range_summary"]
    ratios = [r["profit_ratio"] for r in value["rows"] if not r["baseline_range_violations"] and r["profit_ratio"] is not None]
    record = {"name": name, "parameters": parameters, "source": str(path),
              "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "executable": str(exe),
              "exe_sha256": hashlib.sha256(exe.read_bytes()).hexdigest(), "result_dir": str(dest),
              "valid_range": valid, "boundary": value["boundary_pressure_summary"], "worst_ratio": min(ratios)}
    dump(dest / "manifest.json", record)
    print(json.dumps({"name": name, "pct": valid["total_profit_increase_pct"],
                      "mean_pct": valid["equal_weight_increase_pct"], "median": valid["median_profit_ratio"],
                      "up": valid["improved"], "down": valid["regressed"], "worst": min(ratios)}), flush=True)
    return record


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--initialize", action="store_true")
    parser.add_argument("--screen", action="store_true")
    parser.add_argument("--config")
    parser.add_argument("--parameters")
    args = parser.parse_args()
    if args.initialize:
        initialize()
    if args.screen:
        rows = []
        for name, parameters in CONFIGS.items():
            rows.append(run_config(name, parameters))
            dump(ROOT / "results/v10_fine/summary.json", rows)
    if args.config:
        run_config(args.config, json.loads(args.parameters), "v10_combinations")


if __name__ == "__main__":
    main()
