"""Freeze at most one positive training policy per neural architecture."""
from pathlib import Path
import argparse
import hashlib
import json
import subprocess
import sys
from v11_freeze import freeze

ROOT = Path(__file__).resolve().parent.parent
SELECTION = ROOT / "research/v14_frozen_selection.json"


def selecting():
    choices = json.loads((ROOT / "research/v14_mlp_selected.json").read_text(encoding="utf8"))
    assert isinstance(choices, list) and len(choices) <= 2
    assert len({row["architecture"] for row in choices}) == len(choices)
    assert not SELECTION.exists()
    records = []
    for choice in choices:
        assert choice["architecture"] in ["A", "B"] and choice["training_profit_increase_pct"] > 0
        source = Path(choice["source"])
        if not source.is_absolute():
            source = ROOT / source
        assert hashlib.sha256(source.read_bytes()).hexdigest() == choice["source_sha256"]
        version = freeze("v14_mlp_"+choice["architecture"], source,
            "Architecture's highest aggregate positive policy on training32 only; "+choice["selection_reason"],
            "cases/v14_holdout/manifest.json")
        records.append({"training_choice": choice, "version": version})
    record = {"date": "2026-11-16", "models_trained_on": "V13 admittedflows32 worlds only",
        "selection_data": "V13 train32 closed-loop policies only",
        "fresh_data_used_for_selection": False, "model_architecture_epoch_thresholds_changed": False,
        "validation": "Two unchanged V14 fresh40 splits frozen before neural fitting; compare99 and frozen tiny-tree on the same80 inputs",
        "candidates": records, "official_submission_sent": False,
        "case_manifests_sha256": {split: hashlib.sha256((ROOT / f"cases/v14_{split}/manifest.json").read_bytes()).hexdigest() for split in ["holdout", "confirmation"]},
        "fixed_references": {name: json.loads((ROOT / f"versions/{name}/manifest.json").read_text(encoding="utf8"))["packed_sha256"] for name in ["v12_scan_input_fix", "v13_model_fast"]},
        "no_positive_policy_action": "If empty, report all neural training failures; do not invent new thresholds or select nonpositive policies"}
    SELECTION.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf8")
    print(json.dumps({"frozen": [r["version"]["name"] for r in records], "fresh_results_read": False}))


def run(name):
    record = json.loads(SELECTION.read_text(encoding="utf8"))
    version = next(row["version"] for row in record["candidates"] if row["version"]["name"] == name)
    assert hashlib.sha256(Path(version["executable"]).read_bytes()).hexdigest() == version["exe_sha256"]
    for split in ["holdout", "confirmation"]:
        result = subprocess.run([sys.executable, "tools/v11_holdout_run.py", "--version", name,
            "--stage", "v14", "--split", split], cwd=ROOT, capture_output=True, text=True, encoding="utf8")
        assert result.returncode == 0, result.stdout+result.stderr
        print(result.stdout.strip(), flush=True)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf8")
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["freeze", "run"])
    parser.add_argument("--name", choices=["v14_mlp_A", "v14_mlp_B"])
    args = parser.parse_args()
    if args.mode == "freeze":
        selecting()
    else:
        assert args.name
        run(args.name)
