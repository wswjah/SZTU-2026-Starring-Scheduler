"""Exercise real packed finalists' command and input boundary paths."""
from pathlib import Path
import hashlib
import json
import subprocess

ROOT = Path(__file__).resolve().parent.parent


def main():
    for name in ["v11_pen_scan", "v11_warm_pen_scan"]:
        version_path = ROOT / f"versions/{name}/manifest.json"
        version = json.loads(version_path.read_text(encoding="utf8"))
        before = hashlib.sha256(Path(version["packed_source"]).read_bytes()).hexdigest()
        assert before == version["packed_sha256"]
        results = []
        for label, harness, macro in [
            ("fanout_budget", "tools/test_attributed96.cpp", "ATTRIBUTED96_SOURCE"),
            ("horizon", "tools/test_v7_final_tick.cpp", "V7_FINAL_TICK_SOURCE"),
        ]:
            exe = ROOT / f"build/{name}_check_{label}.exe"
            definition = f'{macro}="../versions/{name}/submit.cpp"'
            compiled = subprocess.run(["g++", "-std=c++17", "-O2", "-D"+definition, harness, "-o", str(exe)],
                                      capture_output=True, text=True, cwd=ROOT)
            assert compiled.returncode == 0, compiled.stderr
            tested = subprocess.run([str(exe)], capture_output=True, text=True, cwd=ROOT)
            assert tested.returncode == 0, tested.stdout+tested.stderr
            results.append({"name": label, "exit_code": tested.returncode,
                            "stdout": tested.stdout, "stderr": tested.stderr,
                            "compiler_stderr": compiled.stderr,
                            "compiler_note": "Renaming production main for inclusion may warn about its implicit return; production main compilation was warning-free."})
        raw = (ROOT / "results/v10_fix_input/large_huffman_protocol.in").read_bytes()
        expected = "".join(f"ANS {3000000 if tick<=20 else 0}\nEND\n" for tick in range(1,401)).encode("ascii")
        tested = subprocess.run([version["executable"]], input=raw, capture_output=True, cwd=ROOT, timeout=20)
        assert tested.returncode == 0 and not tested.stderr
        assert tested.stdout.replace(b"\r\n", b"\n") == expected
        results.append({"name": "large_hex_input", "decoded_characters": 3000000,
                        "hex_characters": 6000000, "answers_exact": 400,
                        "method": "Direct complete protocol replay; separate from TPJ generated-world runs"})
        assert hashlib.sha256(Path(version["packed_source"]).read_bytes()).hexdigest() == before
        out = ROOT / f"results/{name}_final_checks"
        out.mkdir(parents=True, exist_ok=True)
        (out / "summary.json").write_text(json.dumps({"packed_sha256": before, "source_unchanged": True,
                                                      "all_passed": True, "results": results}, indent=2), encoding="utf8")
        version["final_checks"] = {"all_passed": True, "report": str(out / "summary.json")}
        version_path.write_text(json.dumps(version, ensure_ascii=False, indent=2), encoding="utf8")
        print(json.dumps({"name": name, "all_checks_passed": True, "source_unchanged": True}), flush=True)


if __name__ == "__main__":
    main()
