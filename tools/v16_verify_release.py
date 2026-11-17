"""Rebuild and locally verify the published V16 buffer-only repair.

Requires Python and g++ on PATH. Full closed-loop checks also require a separately
obtained local judge, supplied by --judge (default: ROOT/tpj_win.exe).
No network access, credentials, Git operations or official submission are used.
The output directory must be new; all generated binaries and transcripts stay
there. Use --protocol-only to run without the local judge.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


EXPECTED_SUBMIT_SHA256 = "d84158ac1f864dfcc5642eafe400bf482f3cc8e5a8f54775eed36cf1fec49417"
VERSIONS = ("v8_fine", "v10_input_fix", "v16_buffer_only")
PUBLIC_CASES = (
    "cases/train/standard_00.in",
    "cases/train/fast_00.in",
    "cases/stress/failures.in",
    "cases/stress/logs_audits.in",
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def relative_argument(path: Path, directory: Path) -> str:
    # A relative output name also avoids MinGW linker issues with Unicode paths.
    try:
        return os.path.relpath(path, directory)
    except ValueError:
        return str(path)


def check_sources(root: Path, pack) -> dict:
    paths = [root / "versions" / version / name
             for version in VERSIONS for name in ("main.cpp", "submit.cpp")]
    paths += [root / "main.cpp", root / "submit.cpp"]
    for path in paths:
        require(path.is_file(), f"Missing source: {path}")

    def tokens(path):
        return pack.significant(pack.lex(pack.splice_lines(path.read_text(encoding="utf8"))))

    by_version = {}
    for version in VERSIONS:
        main = tokens(root / "versions" / version / "main.cpp")
        packed = tokens(root / "versions" / version / "submit.cpp")
        require(main == packed, f"main/submit preprocessing tokens differ in {version}")
        by_version[version] = packed
    old, fixed = by_version["v8_fine"], by_version["v16_buffer_only"]
    require(len(old) == len(fixed), "V8/V16 token counts differ")
    differences = [(i, a, b) for i, (a, b) in enumerate(zip(old, fixed)) if a != b]
    require(len(differences) == 1, "Expected exactly one changed preprocessing token")
    index, before, after = differences[0]
    require(before.kind == after.kind == "number" and before.text == "22" and after.text == "23",
            "The changed token is not the buffer exponent22->23")
    require([token.text for token in old[index-4:index+2]] == ["tok", "[", "1", "<<", "22", "]"],
            "The changed exponent is not in tok[1<<22]")
    require(by_version["v10_input_fix"] == fixed, "V10 and V16 preprocessing tokens differ")
    require(tokens(root / "main.cpp") == fixed and tokens(root / "submit.cpp") == fixed,
            "Root default source tokens differ from V16")
    candidate = root / "versions/v16_buffer_only/submit.cpp"
    require(sha(candidate) == EXPECTED_SUBMIT_SHA256, "V16 submit source hash does not match the released artifact")
    require((root / "submit.cpp").read_bytes() == candidate.read_bytes(),
            "Root submit.cpp is not byte-identical to the released V16 submit.cpp")
    return {
        "source_hashes": {str(path.relative_to(root)): sha(path) for path in paths},
        "v16_submit_sha256": sha(candidate),
        "root_submit_byte_identical_to_v16": True,
        "main_submit_tokens_identical_in_each_version": True,
        "v10_v16_tokens_identical": True,
        "v8_v16_token_differences": [{"token_index": index, "before": before.text,
                                      "after": after.text, "context": "tok[1<<22] -> tok[1<<23]"}],
        "method": "pack_submission.splice_lines -> lex -> significant; comments ignored",
    }


def compile_source(root: Path, source: Path, build: Path, name: str) -> tuple[Path, dict]:
    executable = build / (name + (".exe" if os.name == "nt" else ""))
    command = ["g++", "-std=c++17", "-O2", "-Wall", "-Wextra",
               relative_argument(source, build), "-o", executable.name]
    result = subprocess.run(command, cwd=build, capture_output=True, text=True,
                            encoding="utf8", errors="replace", timeout=90)
    record = {"source": str(source.relative_to(root)), "source_sha256": sha(source),
              "command": command, "working_directory": str(build),
              "exit_code": result.returncode, "stdout": result.stdout,
              "stderr": result.stderr}
    require(result.returncode == 0, f"Compilation failed for {source}: {result.stderr[:2000]}")
    record["executable"] = str(executable)
    record["exe_sha256"] = sha(executable)
    return executable, record


def make_protocol(huffman_codes) -> tuple[bytes, bytes, dict]:
    frequencies = [1, 1, 2, 3, 5, 8, 13, 21, 34]
    codes = huffman_codes(frequencies)
    require(codes[0] == "11111110", "Unexpected Huffman code for the published reproducer")
    count = 3_000_000
    encoded = bytes([int(codes[0], 2)]).hex() * count
    require(len(encoded) == 6_000_000, "Unexpected encoded log length")
    initialization = ["400 2 2 2 2 30 1 1 1 20 1", "1 1 1 1 1", "1 1",
                      "0 0 1", "1 1 1", "0 1 1 1", "1 1 1 1", "0 1 1", "-1 100"]
    initialization += ["0 1"] * 29
    initialization += ["1", "1 0", " ".join(map(str, frequencies)), "a 1"]
    transcript = "\n".join(initialization) + f"\nTICK 1 1 1\nLOG 0 {8 * count} {encoded}\nALARM 0\n"
    transcript += "".join(f"TICK {tick} 0 1\nALARM 0\n" for tick in range(2, 401))
    expected = "".join(f"ANS {count if tick <= 20 else 0}\nEND\n" for tick in range(1, 401))
    return transcript.encode("ascii"), expected.encode("ascii"), {
        "decoded_characters": count, "encoded_hex_characters": len(encoded),
        "huffman_code_for_a": codes[0], "audit_count": 400,
        "expected": "ALARM=3000000 at ticks1..20; ALARM=0 at ticks21..400; each tick ends with END",
        "scope": "Manually constructed full protocol with exact answers; not TPJ-certified world or official hidden data",
    }


def run_protocol(executable: Path, data: bytes, expected: bytes, destination: Path) -> dict:
    try:
        result = subprocess.run([str(executable)], input=data, capture_output=True,
                                cwd=destination, timeout=20)
        timed_out, returncode, stdout, stderr = False, result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired as error:
        timed_out, returncode = True, None
        stdout, stderr = error.stdout or b"", error.stderr or b""
    (destination / "stdout.txt").write_bytes(stdout)
    (destination / "stderr.txt").write_bytes(stderr)
    return {"timeout": timed_out, "exit_code": returncode,
            "all_answers_exact": not timed_out and returncode == 0 and stdout.replace(b"\r\n", b"\n") == expected,
            "first_line": stdout.splitlines()[0].decode("ascii", errors="replace") if stdout else None,
            "stdout_sha256": hashlib.sha256(stdout).hexdigest(),
            "stderr_excerpt": stderr.decode("utf8", errors="replace")[:2000]}


def verify(args, root: Path, out: Path, summary: dict) -> None:
    sys.path.insert(0, str(root / "tools"))
    import pack_submission
    from v10_fix_input import huffman_codes

    summary["sources"] = check_sources(root, pack_submission)
    build = out / "build"
    build.mkdir()
    base_exe, base_build = compile_source(root, root / "versions/v8_fine/submit.cpp", build, "v8")
    fixed_exe, fixed_build = compile_source(root, root / "versions/v16_buffer_only/submit.cpp", build, "v16")
    summary["compilation"] = {"v8": base_build, "v16": fixed_build}
    data, expected, protocol = make_protocol(huffman_codes)
    protocol_dir = out / "protocol"
    protocol_dir.mkdir()
    (protocol_dir / "long_huffman.in").write_bytes(data)
    protocol["input_sha256"] = hashlib.sha256(data).hexdigest()
    for label, executable in (("v8", base_exe), ("v16", fixed_exe)):
        run_dir = protocol_dir / label
        run_dir.mkdir()
        protocol[label] = run_protocol(executable, data, expected, run_dir)
    protocol["v8_result_caveat"] = "The original writes out of bounds; its undefined behavior need not reproduce a fixed answer or even a failure on another build"
    summary["long_log_protocol"] = protocol
    require(protocol["v16"]["all_answers_exact"], "V16 did not produce all400 exact protocol answers")

    pairs = []
    summary["closed_loop_pairs"] = pairs
    if not args.protocol_only:
        from bench import run_case
        judge = Path(args.judge).resolve() if args.judge else root / "tpj_win.exe"
        require(judge.is_file(), f"Local judge missing: {judge}; supply --judge or use --protocol-only")
        summary["judge"] = {"path": str(judge), "sha256": sha(judge)}
        case_names = list(PUBLIC_CASES)
        if args.with_samples:
            samples = ["sample_00/turn_00.in", "sample_01/turn_00.in"]
            require(all((root / name).is_file() for name in samples),
                    "--with-samples requires both original sample directories under --root")
            case_names += samples
        summary["case_scope"] = "Four pre-existing public development/stress cases, not new unseen validation; original samples added only when explicitly requested"
        for index, name in enumerate(case_names):
            case_path = root / name
            require(case_path.is_file(), f"Missing public case: {case_path}")
            pair_dir = out / "closed_loop" / str(index)
            baseline = run_case(base_exe, case_path, pair_dir / "v8", judge=judge)
            fixed = run_case(fixed_exe, case_path, pair_dir / "v16", judge=judge)
            pair = {"case": name, "full_report_equal": baseline["report"] == fixed["report"],
                    "v8": baseline, "v16": fixed}
            pairs.append(pair)
            require(baseline["ok"] and fixed["ok"], f"Closed-loop correctness check failed: {name}")
            require(pair["full_report_equal"], f"V8/V16 full judge reports differ: {name}")

    final_hashes = {name: sha(root / name) for name in summary["sources"]["source_hashes"]}
    require(final_hashes == summary["sources"]["source_hashes"], "Source files changed during verification")
    summary.update(source_hashes_unchanged=True, closed_loop_case_count=len(pairs),
                   all_closed_loop_reports_equal=all(pair["full_report_equal"] for pair in pairs),
                   fixed_closed_loop_audits=sum(pair["v16"]["audit_total"] for pair in pairs),
                   fixed_closed_loop_audit_errors=sum(pair["v16"]["audit_errors"] for pair in pairs),
                   fixed_closed_loop_illegal_commands=sum(pair["v16"]["incidents"] for pair in pairs),
                   ok=True)


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument("--judge", type=Path, help="Separately obtained local judge executable")
    parser.add_argument("--out", type=Path, help="New output directory; default ROOT/local_runs/v16_verify")
    parser.add_argument("--protocol-only", action="store_true", help="Skip judge-dependent closed-loop checks")
    parser.add_argument("--with-samples", action="store_true", help="Also verify both original sample directories if present")
    args = parser.parse_args()
    root = args.root.resolve()
    out = args.out.resolve() if args.out else root / "local_runs/v16_verify"
    summary = {"root": str(root), "output_directory": str(out), "protocol_only": args.protocol_only,
               "with_samples_requested": args.with_samples, "network_access": False,
               "official_submission_performed": False, "ok": False}
    try:
        # Refuse every existing destination, including an earlier completed run.
        out.mkdir(parents=True, exist_ok=False)
    except FileExistsError:
        print(json.dumps({"ok": False, "error": "Output directory already exists; choose a new --out", "out": str(out)}, ensure_ascii=False))
        return 1
    try:
        verify(args, root, out, summary)
    except Exception as error:
        summary.update(error_type=type(error).__name__, error=str(error))
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf8")
    public_summary = {key: summary.get(key) for key in ["ok", "closed_loop_case_count", "fixed_closed_loop_audits",
                     "fixed_closed_loop_audit_errors", "fixed_closed_loop_illegal_commands", "source_hashes_unchanged"]}
    public_summary.update(summary_file=str(out / "summary.json"),
                          long_protocol_all400_exact=summary.get("long_log_protocol", {}).get("v16", {}).get("all_answers_exact"))
    if "error" in summary:
        public_summary.update(error_type=summary["error_type"], error=summary["error"])
    print(json.dumps(public_summary, ensure_ascii=False))
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
