"""Run existing meaningful boundary regressions on the actual packed finalist."""
from pathlib import Path
import hashlib
import json
import subprocess

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "versions/v7_tuned/submit.cpp"
OUT = ROOT / "results/v7_final_checks"
OUT.mkdir(parents=True, exist_ok=True)
before = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
results = []
for label, harness, definition in [
    ("fanout_budget", "tools/test_attributed96.cpp", 'ATTRIBUTED96_SOURCE="../versions/v7_tuned/submit.cpp"'),
    ("horizon", "tools/test_v7_final_tick.cpp", 'V7_FINAL_TICK_SOURCE="../versions/v7_tuned/submit.cpp"'),
]:
    exe = ROOT / f"build/v7_check_{label}.exe"
    command = ["g++", "-std=c++17", "-O2", "-D" + definition, harness, "-o", str(exe)]
    compiled = subprocess.run(command, capture_output=True, text=True, cwd=ROOT)
    assert compiled.returncode == 0, compiled.stderr
    run = subprocess.run([str(exe)], capture_output=True, text=True, cwd=ROOT)
    assert run.returncode == 0, run.stderr
    results.append({"name": label, "command": command, "compiler_stderr": compiled.stderr,
                    "returncode": run.returncode, "stdout": run.stdout, "stderr": run.stderr,
                    "exe_sha256": hashlib.sha256(exe.read_bytes()).hexdigest()})
assert before == hashlib.sha256(SOURCE.read_bytes()).hexdigest()
(OUT / "summary.json").write_text(json.dumps({"packed_sha256": before, "source_unchanged": True,
                                              "all_passed": True, "results": results}, indent=2), encoding="utf8")
print(json.dumps({"all_passed": True, "packed_sha256": before, "checks": [r["name"] for r in results]}))
