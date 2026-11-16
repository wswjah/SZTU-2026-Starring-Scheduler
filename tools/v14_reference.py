"""Run fixed99 and the unchanged tiny-tree policy on new neural validation cases."""
from pathlib import Path
import argparse
import hashlib
import json
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", choices=["v12_scan_input_fix", "v13_model_fast"], required=True)
    args = parser.parse_args()
    version = json.loads((ROOT / f"versions/{args.version}/manifest.json").read_text(encoding="utf8"))
    assert hashlib.sha256(Path(version["executable"]).read_bytes()).hexdigest() == version["exe_sha256"]
    suffix = "baseline" if args.version == "v12_scan_input_fix" else args.version
    for split in ["holdout", "confirmation"]:
        dest = ROOT / f"results/v14_{split}_{suffix}"
        assert not dest.exists()
        result = subprocess.run([sys.executable, "tools/bench.py", "--exe", version["executable"],
            "--cases", f"cases/v14_{split}", "--out", str(dest), "--workers", "1"],
            cwd=ROOT, capture_output=True, text=True, encoding="utf8")
        assert result.returncode == 0, result.stdout+result.stderr
        rows = json.loads((dest / "summary.json").read_text(encoding="utf8"))
        assert len(rows) == 40 and all(r["ok"] for r in rows)
        print(json.dumps({"version": args.version, "split": split, "completed": 40,
            "healthy": True, "profits_withheld_until_neural_selection_fixed": True}), flush=True)


if __name__ == "__main__":
    main()
