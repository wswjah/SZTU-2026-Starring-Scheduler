"""Freeze a train-selected source before evaluating new V8 worlds."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import subprocess
from pack_submission import pack, lex, significant, splice_lines

ROOT = Path(__file__).resolve().parent.parent


def freeze(name, source_path, selection):
    source_path = Path(source_path).resolve()
    source = source_path.read_text(encoding="utf8")
    directory = ROOT / "versions" / name
    assert not directory.exists(), "Frozen source must never be overwritten"
    directory.mkdir(parents=True)
    main = directory / "main.cpp"
    main.write_bytes(source.encode("utf8"))
    attribution = ("// Based on Shuang-su/SZTU-2026-data-structure-final-homework.\n"
                   "// Upstream commit: a35a23f3a8a3c623ff9c62af15e680143264de5e.\n"
                   "// Local repairs, process CPU timing, final-tick cleanup and V8 research.\n")
    packed = attribution + pack(source)
    assert significant(lex(splice_lines(source))) == significant(lex(packed))
    raw = packed.encode("ascii")
    assert len(raw) <= 64000 and b"\r" not in raw
    submission = directory / "submit.cpp"
    submission.write_bytes(raw)
    exe = ROOT / f"build/{name}.exe"
    result = subprocess.run(["g++", "-std=c++17", "-O2", "-Wall", "-Wextra", str(submission),
                             "-o", str(exe)], cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert not result.stderr.strip(), result.stderr
    record = {
        "date": "2026-11-15", "name": name, "parent": "versions/v7_tuned",
        "selection_source": str(source_path), "selection_rule": selection,
        "parameters": {k: float(v) for k, v in re.findall(r"PRM\((\w+),\s*([\d.]+)\)", source)},
        "source": str(main), "source_sha256": hashlib.sha256(main.read_bytes()).hexdigest(),
        "packed_source": str(submission), "packed_bytes": len(raw),
        "packed_sha256": hashlib.sha256(raw).hexdigest(), "tokens_verified": True,
        "attribution_preserved": True, "executable": str(exe),
        "exe_sha256": hashlib.sha256(exe.read_bytes()).hexdigest(),
        "holdout": "cases/v8_holdout/manifest.json",
        "official_submission_authorized": False, "official_submission_sent": False,
    }
    (directory / "manifest.json").write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf8")
    print(json.dumps(record, ensure_ascii=False))
    return record


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    parser.add_argument("source")
    parser.add_argument("--selection", required=True)
    args = parser.parse_args()
    freeze(args.name, args.source, args.selection)
