"""Run an already compiled scheduler against the official local interactor.

API: run_case(exe, case_path, out_dir, timeout=30, env=None) -> result dict.
The files for each run are written under out_dir / case_path.stem.
No recompilation, credentials, network requests, or OJ submission are involved.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import ctypes
from ctypes import wintypes
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time

ROOT = Path(__file__).resolve().parent.parent


def _sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _usage(process):
    """Read Windows kernel accounting, including the lifetime memory peak."""
    if os.name != "nt":
        return {}
    creation, exit_time, kernel, user = (wintypes.FILETIME() for _ in range(4))
    get_times = ctypes.windll.kernel32.GetProcessTimes
    get_times.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
    get_times.restype = wintypes.BOOL
    handle = wintypes.HANDLE(int(process._handle))
    output = {}
    if get_times(handle, ctypes.byref(creation), ctypes.byref(exit_time),
                 ctypes.byref(kernel), ctypes.byref(user)):
        unpack = lambda value: ((value.dwHighDateTime << 32) | value.dwLowDateTime) / 10_000_000
        output.update(cpu_seconds=unpack(kernel) + unpack(user),
                      user_seconds=unpack(user), kernel_seconds=unpack(kernel))

    class MemoryCounters(ctypes.Structure):
        _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD)] + [
            (name, ctypes.c_size_t) for name in ["PeakWorkingSetSize", "WorkingSetSize",
            "QuotaPeakPagedPoolUsage", "QuotaPagedPoolUsage", "QuotaPeakNonPagedPoolUsage",
            "QuotaNonPagedPoolUsage", "PagefileUsage", "PeakPagefileUsage"]]

    counters = MemoryCounters()
    counters.cb = ctypes.sizeof(counters)
    get_memory = ctypes.windll.psapi.GetProcessMemoryInfo
    get_memory.argtypes = [wintypes.HANDLE, ctypes.POINTER(MemoryCounters), wintypes.DWORD]
    get_memory.restype = wintypes.BOOL
    if get_memory(handle, ctypes.byref(counters), counters.cb):
        output["peak_memory_bytes"] = counters.PeakWorkingSetSize
    return output


def run_case(exe, case_path, out_dir, timeout=30, env=None, judge=None):
    exe, case_path = Path(exe).resolve(), Path(case_path).resolve()
    judge = Path(judge or ROOT / "tpj_win.exe").resolve()
    run_dir = Path(out_dir).resolve() / case_path.stem
    run_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(case_path, run_dir / "input.in")
    (run_dir / "empty.out").write_bytes(b"")
    report_path = run_dir / "tpj_tout.tmp"
    if report_path.exists():
        report_path.unlink()
    result = {"case": case_path.stem, "input": str(case_path), "executable": str(exe),
              "run_dir": str(run_dir), "timeout": False,
              "input_sha256": _sha256(case_path), "exe_sha256": _sha256(exe),
              "judge_sha256": _sha256(judge), "env": dict(env or {})}
    solver_environment = os.environ.copy()
    if env:
        solver_environment.update({str(k): str(v) for k, v in env.items()})
    judge_to_solver_r, judge_to_solver_w = os.pipe()
    solver_to_judge_r, solver_to_judge_w = os.pipe()
    solver = interactor = None
    started = time.perf_counter()
    with (run_dir / "solver_stderr.txt").open("wb") as solver_err, \
         (run_dir / "judge_stderr.txt").open("wb") as judge_err:
        try:
            solver = subprocess.Popen([str(exe)], stdin=judge_to_solver_r,
                stdout=solver_to_judge_w, stderr=solver_err, cwd=run_dir,
                env=solver_environment)
            interactor = subprocess.Popen([str(judge), "./input.in", "./tpj_tout.tmp", "./empty.out"],
                stdin=solver_to_judge_r, stdout=judge_to_solver_w, stderr=judge_err, cwd=run_dir)
        finally:
            for descriptor in [judge_to_solver_r, judge_to_solver_w,
                               solver_to_judge_r, solver_to_judge_w]:
                os.close(descriptor)
        try:
            while solver.poll() is None or interactor.poll() is None:
                if time.perf_counter() - started > timeout:
                    result["timeout"] = True
                    break
                time.sleep(.005)
        finally:
            for process in [solver, interactor]:
                if process is not None and process.poll() is None:
                    process.kill()
            for process in [solver, interactor]:
                if process is not None:
                    process.wait()
    result["wall_seconds"] = time.perf_counter() - started
    for label, process in [("solver", solver), ("judge", interactor)]:
        result[label + "_exit_code"] = process.returncode
        result.update({label + "_" + key: value for key, value in _usage(process).items()})
    report = report_path.read_text(encoding="utf8", errors="replace") if report_path.exists() else ""
    result["report"] = report.strip()
    for key, value in re.findall(r"\b([A-Za-z][A-Za-z0-9_]*)=(-?\d+(?:/\d+)?)", report):
        if "/" in value:
            result[key] = value
            first, second = map(int, value.split("/"))
            if key == "badaudits":
                result["audit_errors"], result["audit_total"] = first, second
            elif key == "wf":
                result["workflows_completed"], result["workflows_total"] = first, second
        else:
            result[key] = int(value)
    result["ok"] = (not result["timeout"] and result.get("solver_exit_code") == 0
                    and result.get("judge_exit_code") == 0
                    and "profit" in result and result.get("audit_errors") == 0
                    and result.get("incidents") == 0)
    (run_dir / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf8")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", required=True)
    parser.add_argument("--cases", nargs="+", required=True, help="Input files or directories of .in parameter files")
    parser.add_argument("--out", required=True)
    parser.add_argument("--timeout", type=float, default=30)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--env", action="append", default=[], metavar="NAME=VALUE")
    args = parser.parse_args()
    environment = dict(item.split("=", 1) for item in args.env)
    cases = []
    for item in args.cases:
        path = Path(item)
        cases.extend(sorted(path.glob("*.in")) if path.is_dir() else [path])
    results = []
    duplicate_stems = len({case.stem for case in cases}) != len(cases)
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        pending = {pool.submit(run_case, args.exe, case,
            Path(args.out)/case.parent.name if duplicate_stems else args.out,
            args.timeout, environment): case for case in cases}
        for future in concurrent.futures.as_completed(pending):
            result = future.result()
            results.append(result)
            print(json.dumps({key: result.get(key) for key in ["case", "ok", "profit", "audit_errors",
                "incidents", "solver_cpu_seconds", "wall_seconds"]}, ensure_ascii=False), flush=True)
    results.sort(key=lambda value: value["case"])
    destination = Path(args.out)
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "summary.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf8")
    return 0 if all(value["ok"] for value in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
