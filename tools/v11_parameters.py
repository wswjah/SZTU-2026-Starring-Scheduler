"""Bounded higher-effort scheduling experiments; no official submissions."""
from pathlib import Path
import hashlib
import json
import re
import subprocess
import sys
from compare import compare, markdown
from make_cases import BASE, PROFILES

ROOT = Path(__file__).resolve().parent.parent
BASE_SOURCE = ROOT / "versions/v10_input_fix/main.cpp"
EXPECTED = "b0854a70f54ccb47d287a48be37e447eb100147ca3f2e556c20c20498f705ae6"
OUT = ROOT / "results/v11_parameters"
CONFIGS = {
    "recheck_1": {"THR": 1}, "recheck_2": {"THR": 2}, "recheck_3": {"THR": 3},
    "retry_1": {"RT0": 1}, "reservation_life_1": {"RT1": 1}, "reservation_life_2": {"RT1": 2},
    "reservation_fraction_025": {"RTK": .25},
    "reserve_10": {"RESV": 10}, "reserve_20": {"RESV": 20},
    "urgency_margin_075": {"MG": .75}, "urgency_margin_125": {"MG": 1.25},
    "dead_045": {"DEADK": .45}, "dead_075": {"DEADK": .75},
    "queue_01": {"WK": .1}, "queue_025": {"WK": .25},
}


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf8")


def setup():
    assert hashlib.sha256(BASE_SOURCE.read_bytes()).hexdigest() == EXPECTED
    baseline = ROOT / "results/v11_baseline_train"
    rows = json.loads((ROOT / "results/v10_input_fix_production/summary.json").read_text(encoding="utf8"))
    dump(baseline / "summary.json", [r for r in rows if Path(r["input"]).parent.name == "train"])
    directory = ROOT / "cases/v11_holdout"
    assert not directory.exists(), "Preserve existing held-out worlds"
    directory.mkdir(parents=True)
    manifest = []

    def write(name, cfg, category):
        raw = "".join(f"{k} {v}\n" for k, v in cfg.items()).encode("ascii")
        path = directory / f"{name}.in"
        path.write_bytes(raw)
        manifest.append({"file": path.name, "parameters": cfg, "category": category,
                         "sha256": hashlib.sha256(raw).hexdigest()})

    for i, (name, changes) in enumerate(PROFILES.items()):
        for j in range(4):
            cfg = BASE | changes | {"seed": 711115723 + i*19501 + j*78179}
            if name == "large":
                cfg.update(load=.65, log_rate=.08)
            if name == "fast":
                cfg.update(load=.75)
            write(f"{name}_{j:02}", cfg, "new_seed")
    shifts = {
        "very_fast": dict(bias_lo=.25, bias_hi=.65, sigma=.2, straggler_p=.01, load=.25),
        "very_slow": dict(bias_lo=1.8, bias_hi=3.2, sigma=.45, straggler_p=.14, load=.55),
        "no_failures": dict(fail_frac=0, blackswan=0, link_events=100),
        "uncertain": dict(sigma=.8, straggler_p=.2, load=.7),
        "high_failures": dict(fail_frac=.4, precursor_frac=.65, falsealarm_frac=.2, load=.7),
        "sparse": dict(load=.2, fail_frac=.1), "dense": dict(load=1.5),
        "changing": dict(quota_events=220, link_events=450, audit_rate=5, load=.75),
    }
    for i, (name, changes) in enumerate(shifts.items()):
        write(f"shift_{name}", BASE | {"log_rate": .10} | changes |
              {"seed": 711415723 + i*91453}, "distribution_shift")
    dump(directory / "manifest.json", manifest)
    dump(ROOT / "research/v11_plan.json", {
        "base": str(BASE_SOURCE), "base_sha256": EXPECTED, "official_best": 99,
        "buffer_fix_retained": True, "official_submission_authorized": False,
        "user_submission_decision": "Do not submit yet; retain fix for next combined candidate",
        "parameters": CONFIGS,
        "parallel_branches": ["Up to3 wider rack/lookahead searches", "2 exact-LRU quote variants", "Memo/portableO3 performance controls"],
        "selection": "train16 then old V8development80, choose at most2 frozen finalists before fresh40; no parameters selected from fresh outcomes",
        "compute": "Keep1sec safety guard, distinguish extra CPU from extra profit; controls if CPU guard changes reports",
        "scope": "Train16 has2 old log boundaries; all are retained and checked-range stats separate",
    })


def run_config(name, parameters, rewrite=None):
    source = BASE_SOURCE.read_text(encoding="utf8")
    for key, value in parameters.items():
        source, count = re.subn(rf"PRM\({key},\s*[^)]+\)", f"PRM({key}, {value})", source)
        assert count == 1
    if rewrite:
        before = "w.dirty || (late < 0 && (now + wi) % int(THR) == 0)"
        assert source.count(before) == 1
        source = source.replace(before, rewrite)
    path = ROOT / "candidates/v11_parameters" / f"{name}.cpp"
    path.parent.mkdir(parents=True, exist_ok=True)
    assert not path.exists()
    path.write_bytes(source.encode("utf8"))
    exe = ROOT / f"build/v11_parameter_{name}.exe"
    compiled = subprocess.run(["g++", "-std=c++17", "-O2", str(path), "-o", str(exe)],
                              cwd=ROOT, capture_output=True, text=True)
    assert compiled.returncode == 0, compiled.stderr
    dest = OUT / name
    run = subprocess.run([sys.executable, "tools/bench.py", "--exe", str(exe), "--cases", "cases/train",
                          "--out", str(dest), "--workers", "1"], cwd=ROOT,
                         capture_output=True, text=True, encoding="utf8")
    assert run.returncode == 0, run.stdout+run.stderr
    value = compare(ROOT / "results/v11_baseline_train", dest)
    dump(dest / "comparison.json", value)
    (dest / "comparison.md").write_text(markdown(value), encoding="utf8")
    valid = value["valid_range_summary"]
    worst = min((r for r in value["rows"] if not r["baseline_range_violations"] and r["profit_ratio"] is not None),
                key=lambda r: r["profit_ratio"])
    record = {"name": name, "parameters": parameters, "rewrite": rewrite,
              "source": str(path), "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
              "executable": str(exe), "exe_sha256": hashlib.sha256(exe.read_bytes()).hexdigest(),
              "valid_range": valid, "boundary": value["boundary_pressure_summary"], "worst": worst,
              "max_cpu_seconds": value["candidate_health"]["max_cpu_seconds"]}
    dump(dest / "manifest.json", record)
    print(json.dumps({"name": name, "pct": valid["total_profit_increase_pct"],
                      "mean_pct": valid["equal_weight_increase_pct"], "up": valid["improved"],
                      "down": valid["regressed"], "worst": worst["profit_ratio"],
                      "max_cpu": record["max_cpu_seconds"]}), flush=True)
    return record


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf8")
    setup()
    records = []
    for name, params in CONFIGS.items():
        records.append(run_config(name, params))
        dump(OUT / "summary.json", records)
    # Only this one extra structural recheck, specified before any outcomes.
    records.append(run_config("active_frontier_recheck", {},
        "w.dirty || (late < 0 && (w.left <= 3 || (now + wi) % int(THR) == 0))"))
    dump(OUT / "summary.json", records)


if __name__ == "__main__":
    main()
