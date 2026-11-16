"""Verify fixed old policies on the newly frozen80 worlds without exposing profits."""
from pathlib import Path
import argparse
import hashlib
import json
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", choices=["v12_scan_input_fix", "v13_model_fast", "v14_mlp_A", "v14_mlp_B"], required=True)
    args = parser.parse_args()
    plan = json.loads((ROOT / "research/v15_plan.json").read_text(encoding="utf8"))
    version = plan["references"][args.version]
    assert hashlib.sha256(Path(version["executable"]).read_bytes()).hexdigest() == version["exe_sha256"]
    suffix = "baseline" if args.version == "v12_scan_input_fix" else args.version
    for split in ["holdout", "confirmation"]:
        directory = ROOT / f"results/v15_{split}_{suffix}"
        assert not directory.exists()
        process = subprocess.run([sys.executable, "tools/bench.py", "--exe", version["executable"],
            "--cases", f"cases/v15_{split}", "--out", str(directory), "--workers", "1"],
            cwd=ROOT, capture_output=True, text=True, encoding="utf8")
        assert process.returncode == 0, process.stdout+process.stderr
        rows = json.loads((directory / "summary.json").read_text(encoding="utf8"))
        assert len(rows) == 40 and all(r["ok"] for r in rows)
        print(json.dumps({"version": args.version, "split": split, "healthy_runs": 40,
            "profits_withheld_until_refits_frozen": True}), flush=True)


if __name__ == "__main__":
    main()
