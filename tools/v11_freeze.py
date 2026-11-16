"""Freeze a locally selected source, reusing the exact existing99 header."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import subprocess
from pack_submission import pack, lex, significant, splice_lines

ROOT = Path(__file__).resolve().parent.parent


def freeze(name, source_path, reason, holdout="cases/v11_holdout/manifest.json", exe_name=None):
    source_path = Path(source_path).resolve()
    source = source_path.read_text(encoding="utf8")
    assert "tok[1 << 23]" in source and "COMMAND_LIMIT = 20000" in source
    assert re.search(r"PRM\(TS,\s*1\)", source)
    directory = ROOT / "versions" / name
    assert not directory.exists(), "Do not replace a frozen candidate"
    directory.mkdir(parents=True)
    (directory / "main.cpp").write_bytes(source.encode("utf8"))
    original_packed = (ROOT / "versions/v8_fine/submit.cpp").read_text(encoding="ascii")
    header = "".join(original_packed.splitlines(keepends=True)[:3])
    assert all(line.startswith("//") for line in header.splitlines())
    packed = header+pack(source)
    assert significant(lex(splice_lines(source))) == significant(lex(packed))
    raw = packed.encode("ascii")
    assert len(raw) <= 64000 and b"\r" not in raw
    (directory / "submit.cpp").write_bytes(raw)
    exe = ROOT / f"build/{exe_name or name}.exe"
    result = subprocess.run(["g++", "-std=c++17", "-O2", "-Wall", "-Wextra", str(directory / "submit.cpp"),
                             "-o", str(exe)], cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0 and not result.stderr, result.stderr
    record = {"name": name, "selection_source": str(source_path), "selection_reason": reason,
              "source": str(directory / "main.cpp"), "source_sha256": hashlib.sha256(source.encode("utf8")).hexdigest(),
              "packed_source": str(directory / "submit.cpp"), "packed_bytes": len(raw),
              "packed_sha256": hashlib.sha256(raw).hexdigest(), "tokens_verified": True,
              "original_header_retained_exactly": True, "new_header_comments_added": False,
              "buffer_fix_retained": True, "cpu_insurance_retained": True,
              "parameters": {k: float(v) for k, v in re.findall(r"PRM\((\w+),\s*([\d.]+)\)", source)},
              "executable": str(exe), "exe_sha256": hashlib.sha256(exe.read_bytes()).hexdigest(),
              "holdout": holdout,
              "official_submission_authorized": False, "official_submission_sent": False,
              "submission_decision": "User deferred submissions; local research only"}
    (directory / "manifest.json").write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf8")
    print(json.dumps({k: record[k] for k in ["name", "packed_bytes", "packed_sha256", "selection_reason"]}))
    return record


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    parser.add_argument("source")
    parser.add_argument("--reason", required=True)
    args = parser.parse_args()
    freeze(args.name, args.source, args.reason)
