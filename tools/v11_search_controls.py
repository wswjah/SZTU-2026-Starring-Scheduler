"""CPU-insurance and focused-state controls for the three fixed search variants."""
from pathlib import Path
import hashlib
import json
import re
import subprocess
from bench import run_case

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "results/v11_search/controls"
OUT.mkdir(parents=True, exist_ok=True)


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf8")


def compile_one(source, exe, definitions=()):
    command = ["g++", "-std=c++17", "-O2", *definitions, str(source), "-o", str(exe)]
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return {"command": command, "compiler_stderr": result.stderr,
            "exe_sha256": hashlib.sha256(exe.read_bytes()).hexdigest()}


def main():
    controls = []
    cases = ["fast_00", "standard_00", "large_01"]
    for name, original, original_results in [
        ("baseline", ROOT / "versions/v10_input_fix/main.cpp", ROOT / "results/v10_input_verification/train/fixed"),
        ("warm_rank", ROOT / "candidates/v11_search/warm_rank.cpp", ROOT / "results/v11_search/warm_rank"),
    ]:
        source, n = re.subn(r"PRM\(TS,\s*[^)]+\)", "PRM(TS, 0)", original.read_text(encoding="utf8"))
        assert n==1
        path = ROOT / f"candidates/v11_search/{name}_ts0_control.cpp"
        assert not path.exists()
        path.write_bytes(source.encode("utf8"))
        exe = ROOT / f"build/v11_search_{name}_ts0_control.exe"
        compiled = compile_one(path,exe)
        old = {r["case"]:r for r in json.loads((original_results / "summary.json").read_text(encoding="utf8"))}
        rows = []
        for case in cases:
            row = run_case(exe,ROOT / f"cases/train/{case}.in",OUT / name)
            assert row["ok"]
            row["ts1_full_report_equal"] = row["report"] == old[case]["report"]
            row["ts1_profit_delta"] = row["profit"] - old[case]["profit"]
            rows.append(row)
        dump(OUT / name / "summary.json", rows)
        controls.append({"name":name,"compiled":compiled,"rows":rows})
    tests = []
    for name, path, definitions in [
        ("warm_memo", ROOT / "tools/v11_search_warm_test.cpp", ()),
        ("wide_fanout_budget", ROOT / "tools/test_attributed96.cpp", ('-DATTRIBUTED96_SOURCE="../candidates/v11_search/full_wide.cpp"',)),
    ]:
        exe = ROOT / f"build/v11_search_test_{name}.exe"
        compiled = compile_one(path,exe,definitions)
        run = subprocess.run([str(exe)],cwd=ROOT,capture_output=True,text=True)
        assert run.returncode==0,run.stderr
        tests.append({"name":name,**compiled,"returncode":run.returncode,"stdout":run.stdout,"stderr":run.stderr})
    record = {"cpu_controls":controls,"focused_tests":tests,
              "all_six_ts0_reports_equal_to_ts1":all(r["ts1_full_report_equal"] for c in controls for r in c["rows"]),
              "note":"These three-world timing controls do not prove all worlds never trigger CPU insurance. Controls are not additional strategy candidates."}
    dump(OUT / "summary.json",record)
    print(json.dumps({"all_six_ts0_reports_equal_to_ts1":record["all_six_ts0_reports_equal_to_ts1"],
                      "rows":[{"name":c["name"],"case":r["case"],"equal":r["ts1_full_report_equal"],"delta":r["ts1_profit_delta"]}for c in controls for r in c["rows"]],
                      "focused_tests":[r["name"] for r in tests]}))


if __name__=="__main__":
    main()
