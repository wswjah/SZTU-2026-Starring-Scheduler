"""Freeze two train-selected finalists before examining their fresh-world results."""
from pathlib import Path
import hashlib
import json
import re
import subprocess
from pack_submission import pack, lex, significant, splice_lines

ROOT = Path(__file__).resolve().parent.parent
CONFIGS = {"v7_tuned": "combined", "v7_racks16": "racks_16"}
ATTRIBUTION = """// Based on Shuang-su/SZTU-2026-data-structure-final-homework.
// Upstream commit: a35a23f3a8a3c623ff9c62af15e680143264de5e.
// Local repairs, process CPU timing, last-tick cleanup, and tuned parameters.
"""
anchor = "void schedule() {\n    drainDeferredKills();"
cleanup = """
    // No future completion event can create revenue after the known final tick.
    if (now == T) {
        F(x,M) {
            while (!machJobs[x].empty() && commandsUsed < COMMAND_LIMIT)
                killNow(machJobs[x].back());
            if (commandsUsed == COMMAND_LIMIT) break;
        }
        return;
    }"""
records = []
for version_name, config in CONFIGS.items():
    original = ROOT / f"candidates/v7_cpu/{config}.cpp"
    source = original.read_text(encoding="utf8")
    assert source.count(anchor) == 1
    source = source.replace(anchor, anchor + cleanup)
    output = ROOT / "versions" / version_name
    assert not output.exists(), "Frozen version already exists"
    output.mkdir(parents=True)
    (output / "main.cpp").write_bytes(source.encode("utf8"))
    packed = ATTRIBUTION + pack(source)
    assert significant(lex(splice_lines(source))) == significant(lex(packed))
    raw = packed.encode("ascii")
    assert len(raw) <= 64000 and b"\r" not in raw
    (output / "submit.cpp").write_bytes(raw)
    exe = ROOT / f"build/{version_name}.exe"
    subprocess.run(["g++", "-std=c++17", "-O2", "-Wall", "-Wextra", str(output / "submit.cpp"),
                    "-o", str(exe)], check=True, cwd=ROOT)
    parameters = {k: float(re.search(rf"PRM\({k},\s*([^)]+)\)", source).group(1))
                  for k in ["SB", "RK", "KILLK", "ADM", "SP"]}
    record = {"date": "2026-11-15", "name": version_name, "selection_source": str(original),
              "selection_rule": "best train combination and less invasive racks-only comparison; no validation outcomes used",
              "parameters": parameters, "final_tick_cleanup": True,
              "windows_process_cpu_clock": True, "non_windows_clock_expression_preserved": True,
              "source": str(output / "main.cpp"), "source_sha256": hashlib.sha256(source.encode("utf8")).hexdigest(),
              "packed_source": str(output / "submit.cpp"), "packed_bytes": len(raw),
              "packed_sha256": hashlib.sha256(raw).hexdigest(), "tokens_verified": True,
              "attribution_preserved": True, "executable": str(exe), "exe_sha256": hashlib.sha256(exe.read_bytes()).hexdigest(),
              "official_submission_sent": False, "official_submission_authorized": False,
              "validation_set_manifest": "cases/v7_validation/manifest.json"}
    (output / "manifest.json").write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf8")
    records.append(record)
(ROOT / "research/v7_frozen_finalists.json").write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf8")
print(json.dumps([{k: r[k] for k in ["name", "parameters", "packed_bytes", "packed_sha256"]} for r in records]))
