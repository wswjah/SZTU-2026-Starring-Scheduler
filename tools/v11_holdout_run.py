"""Run a frozen candidate; withhold profit output until final selection is fixed."""
from pathlib import Path
import argparse
import json
import subprocess
import sys
from compare import compare, markdown

ROOT = Path(__file__).resolve().parent.parent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", required=True)
    parser.add_argument("--split", default="holdout", choices=["holdout", "confirmation"])
    parser.add_argument("--stage", default="v11", choices=["v11", "v12", "v13", "v14", "v15"])
    args = parser.parse_args()
    manifest = json.loads((ROOT / f"versions/{args.version}/manifest.json").read_text(encoding="utf8"))
    dest = ROOT / f"results/{args.stage}_{args.split}_{args.version}"
    assert not dest.exists(), "Do not replace prior validation output"
    result = subprocess.run([sys.executable, "tools/bench.py", "--exe", manifest["executable"],
                             "--cases", f"cases/{args.stage}_{args.split}", "--out", str(dest), "--workers", "1"],
                            cwd=ROOT, capture_output=True, text=True, encoding="utf8")
    assert result.returncode == 0, result.stdout+result.stderr
    baseline = ROOT / f"results/{args.stage}_{args.split}_baseline"
    if (baseline / "summary.json").is_file():
        value = compare(baseline, dest)
        (dest / "comparison.json").write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf8")
        (dest / "comparison.md").write_text(markdown(value), encoding="utf8")
    rows = json.loads((dest / "summary.json").read_text(encoding="utf8"))
    assert all(r["ok"] for r in rows)
    print(json.dumps({"version": args.version, "split": args.split, "completed": len(rows),
                      "all_runs_ok": True, "profit_output_withheld": True}))


if __name__ == "__main__":
    main()
