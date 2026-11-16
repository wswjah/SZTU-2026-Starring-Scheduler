"""Freeze all four predeclared refits, then run train128 and new80 unchanged."""
from pathlib import Path
import argparse
import hashlib
import json
import subprocess
import sys
from compare import compare, markdown
from v11_freeze import freeze

ROOT = Path(__file__).resolve().parent.parent
FROZEN = ROOT / "research/v15_frozen_models.json"
NAMES = ["A128_120", "B128_120", "tree128", "A128_steps"]


def load(path):
    return json.loads((ROOT / path).read_text(encoding="utf8"))


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf8")


def freezing():
    assert not FROZEN.exists()
    models = load("research/v15_models.json")
    assert isinstance(models, list) and len(models) == 4 and {m["name"] for m in models} == set(NAMES)
    records = []
    for name in NAMES:
        model = next(m for m in models if m["name"] == name)
        source = Path(model["source"])
        if not source.is_absolute():
            source = ROOT / source
        assert hashlib.sha256(source.read_bytes()).hexdigest() == model["source_sha256"]
        version = freeze("v15_"+name, source,
            "Predeclared data-expansion refit with fixed original gate;all4 enter new80 regardless training profit;no threshold search",
            "cases/v15_holdout/manifest.json", exe_name="v15_"+name+"_packed")
        records.append({"model": model, "version": version})
    dump(FROZEN, {"models": records, "fresh_profit_viewed": False,
        "all_predeclared_models_frozen": True, "selection": "No train-result selection;all four fixed policies",
        "input_plan": "research/v15_plan.json", "training_plan": "research/v15_training_plan.json",
        "official_submission_sent": False})
    print(json.dumps({"frozen": [r["version"]["name"] for r in records], "fresh_results_read": False}), flush=True)


def training(version):
    dest = ROOT / f"results/v15_train_{version['name']}"
    assert not dest.exists()
    result = subprocess.run([sys.executable, "tools/bench.py", "--exe", version["executable"],
        "--cases", "cases/v13_train32", "cases/v15_train96", "--out", str(dest / "raw"), "--workers", "1"],
        cwd=ROOT, capture_output=True, text=True, encoding="utf8")
    assert result.returncode == 0, result.stdout+result.stderr
    rows = load(str(dest / "raw/summary.json"))
    assert len(rows) == 128 and {r["exe_sha256"] for r in rows} == {version["exe_sha256"]}
    prefix = {"v13_train32": "v13", "v15_train96": "v15"}
    normalized = [dict(r, case=prefix[Path(r["input"]).parent.name]+"/"+r["case"]) for r in rows]
    assert len({r["case"] for r in normalized}) == 128
    dump(dest / "summary.json", normalized)
    old = [dict(r, case="v13/"+r["case"]) for r in load("results/v13_baseline_train32/summary.json")]
    old += [dict(r, case="v15/"+r["case"]) for r in load("results/v15_train96_baseline/summary.json")]
    # Each candidate keeps its own identical baseline copy to avoid concurrent writes.
    baseline = dest / "baseline128"
    dump(baseline / "summary.json", old)
    value = compare(baseline, dest)
    dump(dest / "comparison.json", value)
    (dest / "comparison.md").write_text(markdown(value), encoding="utf8")
    assert all(r["ok"] for r in rows)
    print(json.dumps({"version": version["name"], "training_runs": 128, "all_healthy": True,
        "train_profits_not_used_for_selection": True}), flush=True)


def running(name):
    frozen = load(str(FROZEN))
    version = next(row["version"] for row in frozen["models"] if row["version"]["name"] == name)
    assert hashlib.sha256(Path(version["executable"]).read_bytes()).hexdigest() == version["exe_sha256"]
    training(version)
    for split in ["holdout", "confirmation"]:
        result = subprocess.run([sys.executable, "tools/v11_holdout_run.py", "--version", name,
            "--stage", "v15", "--split", split], cwd=ROOT, capture_output=True, text=True, encoding="utf8")
        assert result.returncode == 0, result.stdout+result.stderr
        print(result.stdout.strip(), flush=True)


def auxiliary(name):
    frozen = load(str(FROZEN))
    version = next(row["version"] for row in frozen["models"] if row["version"]["name"] == name)
    dest = ROOT / f"results/v15_aux_{name}"
    assert not dest.exists()
    result = subprocess.run([sys.executable, "tools/bench.py", "--exe", version["executable"],
        "--cases", "cases/stress", "sample_00/turn_00.in", "sample_01/turn_00.in",
        "--out", str(dest), "--workers", "1"], cwd=ROOT, capture_output=True, text=True, encoding="utf8")
    assert result.returncode == 0, result.stdout+result.stderr
    rows = load(str(dest / "summary.json"))
    assert len(rows) == 6 and all(r["ok"] for r in rows)
    print(json.dumps({"version": name, "auxiliary6_healthy": True}), flush=True)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf8")
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["freeze", "run", "aux"])
    parser.add_argument("--name", choices=["v15_"+name for name in NAMES])
    args = parser.parse_args()
    if args.mode == "freeze":
        freezing()
    elif args.mode == "run":
        assert args.name
        running(args.name)
    else:
        assert args.name
        auxiliary(args.name)
