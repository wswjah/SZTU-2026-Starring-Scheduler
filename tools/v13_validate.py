"""Freeze the three V13 training-selected candidates, then validate unchanged."""
from pathlib import Path
import argparse
import hashlib
import json
import subprocess
import sys
from v11_freeze import freeze

ROOT = Path(__file__).resolve().parent.parent
SELECTION = ROOT / "research/v13_frozen_selection.json"
CANDIDATES = [
    ("v13_kill109", "candidates/v13_fine/kill_109.cpp",
     "Only fine config with positive training aggregate (+0.0218%); 10 up/22 down, substantial downside, exploratory comparator only"),
    ("v13_admit055", "candidates/v13_fine/admit_055.cpp",
     "Training broadest gains20/32, median positive and worst-1.85%, despite aggregate-0.1130%; compare stability against aggregate selection"),
    ("v13_model_strict", "candidates/v13_model/veto_strict.cpp",
     "Best of four predeclared model gates on training32: aggregate+0.0880%,18 up/14 down; no new model thresholds"),
]


def select():
    assert not SELECTION.exists(), "Never replace an experiment's frozen selection"
    assert hashlib.sha256((ROOT / CANDIDATES[2][1]).read_bytes()).hexdigest() == \
        "560c63b3dbcbe6341b315b1b56ef36f0d41dd902d12216bb5cb12ba3d4d5d55c"
    records = []
    for name, source, reason in CANDIDATES:
        records.append(freeze(name, ROOT / source, reason, "cases/v13_holdout/manifest.json"))
    record = {
        "date": "2026-11-16", "selection_data": "V13 new training32 only",
        "fresh_data_used_for_selection": False,
        "old_development_used_for_selection": False,
        "candidates": records,
        "validation": "All three unchanged sources on fresh40 then unchanged confirmation40; report both separately and combined80, no threshold changes",
        "interpretation": "Local profit cannot establish an official score; positive aggregate alone does not establish robustness",
        "production_default_unchanged": True,
        "official_submission_authorized": False,
        "official_submission_sent": False,
    }
    SELECTION.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf8")


def run(name):
    selection = json.loads(SELECTION.read_text(encoding="utf8"))
    manifest = next(r for r in selection["candidates"] if r["name"] == name)
    for field, sha in [("packed_source", "packed_sha256"), ("executable", "exe_sha256")]:
        assert hashlib.sha256(Path(manifest[field]).read_bytes()).hexdigest() == manifest[sha]
    for split in ["holdout", "confirmation"]:
        process = subprocess.run([sys.executable, "tools/v11_holdout_run.py", "--version", name,
                                  "--stage", "v13", "--split", split], cwd=ROOT,
                                 capture_output=True, text=True, encoding="utf8")
        assert process.returncode == 0, process.stdout+process.stderr
        print(process.stdout.strip(), flush=True)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf8")
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["freeze", "run"])
    parser.add_argument("--name", choices=[x[0] for x in CANDIDATES])
    args = parser.parse_args()
    if args.mode == "freeze":
        select()
    else:
        assert args.name
        run(args.name)
