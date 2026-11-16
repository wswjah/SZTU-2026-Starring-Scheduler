"""Actual scheduler boundary tests and a checked-scratch negative control.

The production candidate is never edited. MinGW here lacks libubsan, so copies
replace only the fixed successor scratch arrays with checked operator[] types.
The negative control restores the former late bounds check to prove detection.
"""
from pathlib import Path
import hashlib
import json
import subprocess

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "versions/v6_attributed96/main.cpp"
HARNESS = ROOT / "tools/test_attributed96.cpp"
OUT = ROOT / "results/v6_attributed96_focused"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compile_and_run(label, extra):
    exe = ROOT / f"build/test_attributed96_{label}.exe"
    command = ["g++", "-std=c++17", "-O2", *extra, str(HARNESS), "-o", str(exe)]
    built = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    if built.returncode:
        raise RuntimeError(built.stderr)
    ran = subprocess.run([str(exe)], cwd=ROOT, capture_output=True, text=True)
    result = {"command": command, "compiler_stderr": built.stderr,
              "executable_sha256": digest(exe), "returncode": ran.returncode,
              "stdout": ran.stdout, "stderr": ran.stderr}
    (OUT / f"{label}.json").write_text(json.dumps(result, indent=2), encoding="utf8")
    return result


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    before = digest(SOURCE)
    raw = SOURCE.read_text(encoding="utf8")
    substitutions = {
        "static int qr[8][5], nq[8];": "static CheckedMatrix<int,8,5> qr; static CheckedArray<int,8> nq;",
        "static ll qz[8][5];": "static CheckedMatrix<ll,8,5> qz;",
        "static double qm[8][5], qf[8][5];": "static CheckedMatrix<double,8,5> qm, qf;",
        "int ns = 0, sj[8];": "int ns = 0; CheckedArray<int,8> sj;",
    }
    checked = raw
    for old, new in substitutions.items():
        assert checked.count(old) == 1, old
        checked = checked.replace(old, new)
    checked_path = ROOT / "build/attributed96_checked_source.cpp"
    checked_path.write_text(checked, encoding="utf8")

    old_guard = "            if (ns >= 8) break;  // Check before any access to qr/ns scratch rows.\n"
    assert checked.count(old_guard) == 1
    negative = checked.replace(old_guard, "")
    assert negative.count("            if (!k) continue;") == 1
    negative = negative.replace("            if (!k) continue;", "            if (!k || ns > 7) continue;")
    negative_path = ROOT / "build/attributed96_negative_source.cpp"
    negative_path.write_text(negative, encoding="utf8")

    normal = compile_and_run("production", [])
    instrumented = compile_and_run("checked", ["-DATTRIBUTED96_CHECKED_SCRATCH",
        '-DATTRIBUTED96_SOURCE="../build/attributed96_checked_source.cpp"'])
    negative_result = compile_and_run("negative_control", ["-DATTRIBUTED96_CHECKED_SCRATCH",
        '-DATTRIBUTED96_SOURCE="../build/attributed96_negative_source.cpp"'])
    assert normal["returncode"] == 0, normal
    assert instrumented["returncode"] == 0, instrumented
    assert negative_result["returncode"] == 97, negative_result
    assert "8 >= 8" in negative_result["stderr"], negative_result
    assert digest(SOURCE) == before, "Production candidate unexpectedly changed"
    report = {"production_source": str(SOURCE), "production_sha256": before,
              "production_source_unchanged": True,
              "ubsan_available": False,
              "ubsan_limitation": "MinGW linker cannot find -lubsan",
              "fallback": "Only successor scratch arrays use checked indexing in a generated copy",
              "production_passed": True, "checked_scratch_passed": True,
              "negative_control_caught_original_index_8": True,
              "checks": ["tryPlace successor counts 0,1,7,8,9,16,64,1000",
                         "19998 command slots used: no partial 3-command prewarm",
                         "19997 used: exact RUN/KILL/RUN ends at 20000",
                         "19999 used: cache-hit one-command RUN accepted",
                         "20000 used: no commands or resources changed",
                         "deferred stops survive a tick and honor remaining budget",
                         "DONE/FAIL expire pending stops without illegal KILL",
                         "quota, CPU, memory and affine bill reconcile"]}
    (OUT / "summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf8")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
