"""Freeze a one-character repair while preserving the exact submitted header."""
from pathlib import Path
import hashlib
import json
import subprocess
from pack_submission import lex, significant

ROOT = Path(__file__).resolve().parent.parent
BASE = ROOT / "versions/v8_fine"
OUT = ROOT / "versions/v10_input_fix"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    assert not OUT.exists(), "Do not overwrite frozen artifacts"
    old_main = (BASE / "main.cpp").read_bytes()
    new_main = (ROOT / "candidates/v10_fix_input.cpp").read_bytes()
    assert old_main.replace(b"tok[1 << 22]", b"tok[1 << 23]") == new_main
    old_packed = (BASE / "submit.cpp").read_bytes()
    assert old_packed.count(b"tok[1<<22]") == 1
    new_packed = old_packed.replace(b"tok[1<<22]", b"tok[1<<23]")
    differences = [i for i, (a, b) in enumerate(zip(old_packed, new_packed)) if a != b]
    assert len(old_packed) == len(new_packed) and len(differences) == 1
    assert significant(lex(new_main.decode("ascii"))) == significant(lex(new_packed.decode("ascii")))
    assert old_packed.splitlines()[:3] == new_packed.splitlines()[:3]
    OUT.mkdir(parents=True)
    (OUT / "main.cpp").write_bytes(new_main)
    (OUT / "submit.cpp").write_bytes(new_packed)
    exe = ROOT / "build/v10_input_fix.exe"
    built = subprocess.run(["g++", "-std=c++17", "-O2", "-Wall", "-Wextra", str(OUT / "submit.cpp"), "-o", str(exe)],
                           cwd=ROOT, capture_output=True, text=True)
    assert built.returncode == 0 and not built.stderr, built.stderr
    record = {"date": "2026-11-15", "name": "v10_input_fix", "parent": "versions/v8_fine",
              "parent_official_score": 99, "change": "Only tok capacity exponent22->23 (4MiB->8MiB)",
              "source": str(OUT / "main.cpp"), "source_sha256": sha(OUT / "main.cpp"),
              "packed_source": str(OUT / "submit.cpp"), "packed_bytes": len(new_packed),
              "packed_sha256": sha(OUT / "submit.cpp"), "packed_differing_byte_count": 1,
              "differing_byte_zero_based": differences[0], "new_header_comments_added": False,
              "header_identical_to_official99": True, "all_scheduling_parameters_unchanged": True,
              "tokens_verified": True, "executable": str(exe), "exe_sha256": sha(exe),
              "official_submission_authorized": False, "official_submission_sent": False,
              "reproducer": "research/v10_fix_input_manifest.json",
              "fresh_manifest": "cases/v10_holdout/manifest.json"}
    (OUT / "manifest.json").write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf8")
    print(json.dumps({k: record[k] for k in ["name", "packed_bytes", "packed_sha256", "packed_differing_byte_count", "new_header_comments_added"]}))


if __name__ == "__main__":
    main()
