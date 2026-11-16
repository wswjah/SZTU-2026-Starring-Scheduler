"""Verify the actual packed buffer fix on the complete transcript and worlds."""
from pathlib import Path
import hashlib
import json
import subprocess
import time
from bench import _usage
from compare import compare, markdown

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "results/v10_input_verification"


def dump(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf8")


def main():
    manifest_path = ROOT / "versions/v10_input_fix/manifest.json"
    version = json.loads(manifest_path.read_text(encoding="utf8"))
    exe = Path(version["executable"])
    assert hashlib.sha256(exe.read_bytes()).hexdigest() == version["exe_sha256"]
    transcript = (ROOT / "results/v10_fix_input/large_huffman_protocol.in").read_bytes()
    expected = "".join(f"ANS {3000000 if tick<=20 else 0}\nEND\n" for tick in range(1,401)).encode("ascii")
    start = time.perf_counter()
    process = subprocess.Popen([str(exe)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=ROOT)
    stdout, stderr = process.communicate(transcript, timeout=20)
    usage = _usage(process)
    assert process.returncode == 0 and not stderr
    assert stdout.replace(b"\r\n", b"\n") == expected
    protocol = {"source": version["packed_source"], "exe_sha256": version["exe_sha256"],
                "protocol_input_sha256": hashlib.sha256(transcript).hexdigest(),
                "protocol_input_bytes": len(transcript), "decoded_characters": 3000000,
                "encoded_hex_characters": 6000000, "all_400_answers_exact": True,
                "exit_code": process.returncode, "wall_seconds": time.perf_counter()-start,
                "usage": usage, "method": "Full direct protocol replay, not local TPJ validation of this custom transcript"}
    dump(OUT / "packed_large_protocol.json", protocol)
    (OUT / "packed_large_protocol_stdout.txt").write_bytes(stdout)

    runs = json.loads((ROOT / "results/v10_input_fix_production/summary.json").read_text(encoding="utf8"))
    assert len(runs) == 60 and all(r["ok"] for r in runs)
    assert {r["exe_sha256"] for r in runs} == {version["exe_sha256"]}
    old = json.loads((ROOT / "results/v8_fine_production/summary.json").read_text(encoding="utf8"))
    groups = {}
    all_equal = []
    for name in ["train", "stress", "v10_holdout"]:
        candidate = [r for r in runs if Path(r["input"]).parent.name == name]
        baseline = (json.loads((ROOT / "results/v10_holdout_99/summary.json").read_text(encoding="utf8"))
                    if name == "v10_holdout" else [r for r in old if Path(r["input"]).parent.name == name])
        new_dir, old_dir = OUT / name / "fixed", OUT / name / "original99"
        dump(new_dir / "summary.json", candidate)
        dump(old_dir / "summary.json", baseline)
        comparison = compare(old_dir, new_dir)
        dump(OUT / name / "comparison.json", comparison)
        (OUT / name / "comparison.md").write_text(markdown(comparison), encoding="utf8")
        mapping = {r["case"]: r for r in baseline}
        equal = [{"case": r["case"], "group": name, "report_equal": r["report"] == mapping[r["case"]]["report"],
                  "input_equal": r["input_sha256"] == mapping[r["case"]]["input_sha256"]} for r in candidate]
        assert all(r["report_equal"] and r["input_equal"] for r in equal)
        all_equal += equal
        groups[name] = {"runs": len(candidate), "all_reports_equal": True,
                        "valid_range": comparison["valid_range_summary"]}
    health = {"production_exe_runs": len(runs), "audit_total": sum(r["audit_total"] for r in runs),
              "audit_errors": sum(r["audit_errors"] for r in runs),
              "illegal_commands": sum(r["incidents"] for r in runs),
              "max_cpu_seconds": max(r["solver_cpu_seconds"] for r in runs),
              "max_peak_memory_bytes": max(r["solver_peak_memory_bytes"] for r in runs),
              "all_60_full_reports_equal_to_official99": True,
              "scope": "Train16 includes2 large log boundary worlds; stress4 and fresh40 pass available bounds"}
    dump(OUT / "equivalence.json", all_equal)
    dump(OUT / "summary.json", {"health": health, "groups": groups, "large_protocol": protocol})
    version["validation"] = {**health, "large_protocol_all_answers_exact": True,
                             "report": "results/v10_input_verification/summary.json"}
    dump(manifest_path, version)
    print(json.dumps({"health": health, "large_protocol": protocol}))


if __name__ == "__main__":
    main()
