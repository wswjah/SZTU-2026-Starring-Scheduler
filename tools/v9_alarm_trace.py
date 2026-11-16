"""Collect observational alarm tapes from the immutable V8 scheduler.

All snapshots are taken after current events, before scheduling. CSV output is
deferred until after the final END has been flushed. No model is fitted here.
"""
from pathlib import Path
import argparse
import csv
import hashlib
import json
import subprocess
from bench import run_case

ROOT = Path(__file__).resolve().parent.parent
BASE = ROOT / "versions/v8_fine/main.cpp"
EXPECTED = "b39a299e1983d1837393cdce80fce6ffbdaa209df170a7d865069df011514e3d"
SOURCE = ROOT / "candidates/v9_alarm_trace.cpp"
EXE = ROOT / "build/v9_alarm_trace.exe"
OUT = ROOT / "results/v9_alarm_trace"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf8")


def replace_once(source, old, new):
    assert source.count(old) == 1, old[:80]
    return source.replace(old, new)


def make():
    assert sha(BASE) == EXPECTED
    source = BASE.read_text(encoding="utf8")
    source = replace_once(source, "ll alarmAt[360][602];", """ll alarmAt[360][602];
// Observational tape: current events only, no future-derived decisions.
int v9LogLines[360][602], v9DecodedChars[360][602];
ll v9MaxLineScore[360][602];
unsigned char v9Up[360][602], v9Fail[360][602], v9UpEvent[360][602];
void v9Snapshot() {
    F(x,M) v9Up[x][now] = machUp[x];
}
void v9DumpTape() {
    double schedulingCpu = V7_SCHEDULER_USED(1);
    fprintf(stderr,"#V9_TRACE T=%d M=%d W=%d scheduling_cpu_seconds=%.9f\\n",T,M,W,schedulingCpu);
    fputs("tick,machine,up,dc,cpu,mem,alarm,loglines,decoded_chars,max_line_score,fail,up_event,last_fail_tick\\n",stderr);
    int lastFail[360];
    F(x,M) lastFail[x] = -1;
    for (int t=0;t<=T;++t) F(x,M) {
        if (v9Fail[x][t]) lastFail[x] = t;
        fprintf(stderr,"%d,%d,%d,%d,%d,%d,%lld,%d,%d,%lld,%d,%d,%d\\n",
            t,x,t?int(v9Up[x][t]):1,rackDc[machRack[x]],machCpu[x],machMem[x],
            alarmAt[x][t],v9LogLines[x][t],v9DecodedChars[x][t],v9MaxLineScore[x][t],
            int(v9Fail[x][t]),int(v9UpEvent[x][t]),lastFail[x]);
    }
}
""")
    source = replace_once(source, """            } else if (ev == "FAIL") {
                int x = readInt();""", """            } else if (ev == "FAIL") {
                int x = readInt();
                v9Fail[x][now] = 1;""")
    source = replace_once(source, """            } else if (ev == "UP") {
                int x = readInt();
                machUp[x] = 1;""", """            } else if (ev == "UP") {
                int x = readInt();
                v9UpEvent[x][now] = 1;
                machUp[x] = 1;""")
    source = replace_once(source, """                    if (u < 9) {
                        st = u < 8 ? acGo[st][u] : 0;""", """                    if (u < 9) {
                        ++v9DecodedChars[x][now];
                        st = u < 8 ? acGo[st][u] : 0;""")
    source = replace_once(source, """                alarmAt[x][now] += sc;""", """                alarmAt[x][now] += sc;
                ++v9LogLines[x][now];
                v9MaxLineScore[x][now] = max(v9MaxLineScore[x][now],sc);""")
    source = replace_once(source, """        commandsUsed = 0;
        schedule();""", """        commandsUsed = 0;
        v9Snapshot();
        schedule();""")
    source = replace_once(source, """        if (now == T) break;
    }
}""", """        if (now == T) break;
    }
    v9DumpTape();
}""")
    SOURCE.write_bytes(source.encode("utf8"))
    compile_result = subprocess.run(["g++", "-std=c++17", "-O2", "-Wall", "-Wextra", str(SOURCE), "-o", str(EXE)],
                                    cwd=ROOT, capture_output=True, text=True)
    assert compile_result.returncode == 0, compile_result.stderr
    assert not compile_result.stderr.strip(), compile_result.stderr
    record = {"base": str(BASE), "base_sha256": EXPECTED, "source": str(SOURCE), "source_sha256": sha(SOURCE),
              "exe": str(EXE), "exe_sha256": sha(EXE),
              "schema": "tick,machine,up,dc,cpu,mem,alarm,loglines,decoded_chars,max_line_score,fail,up_event,last_fail_tick",
              "csv": "results/v9_alarm_trace/<case>/solver_stderr.txt",
              "csv_prefix": "First line is #V9_TRACE metadata including T,M,W and scheduler CPU before export; second line is CSV header.",
              "snapshot_time": "After all observed tick events and audit generation, before schedule()",
              "dump_time": "After final END flush; all rows include initial tick0 and every machine, even down machines",
              "fit_or_future_inputs": False, "official_submission_sent": False}
    write(ROOT / "research/v9_alarm_trace_manifest.json", record)
    return record


def validate_tape(row):
    tape = Path(row["run_dir"]) / "solver_stderr.txt"
    with tape.open(encoding="utf8", newline="") as stream:
        metadata = stream.readline().strip()
        assert metadata.startswith("#V9_TRACE "), metadata
        cfg = dict(part.split("=", 1) for part in metadata.split()[1:])
        T, M = int(cfg["T"]), int(cfg["M"])
        reader = csv.DictReader(stream)
        rows = failures = up_events = logs = chars = alarms = 0
        for raw in reader:
            value = {k: int(v) for k, v in raw.items()}
            assert value["tick"] * M + value["machine"] == rows
            failures += value["fail"]
            up_events += value["up_event"]
            logs += value["loglines"]
            chars += value["decoded_chars"]
            alarms += value["alarm"]
            assert value["max_line_score"] <= value["alarm"]
            assert value["last_fail_tick"] <= value["tick"]
            rows += 1
        assert rows == (T + 1) * M
        assert logs == row["loglines"]
        assert chars == row["logchars"]
    return {"rows": rows, "T": T, "M": M, "W": int(cfg["W"]),
            "failures": failures, "up_events": up_events, "loglines": logs,
            "decoded_chars": chars, "alarm_sum": alarms,
            "scheduler_cpu_before_export": float(cfg["scheduling_cpu_seconds"]),
            "path": str(tape), "sha256": sha(tape)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--make-only", action="store_true")
    args = parser.parse_args()
    record = make()
    if args.make_only:
        print(json.dumps(record))
        return
    baseline = json.loads((ROOT / "results/v8_fine_production/summary.json").read_text(encoding="utf8"))
    baseline = {r["case"]: r for r in baseline if Path(r["input"]).parent.name == "train"}
    cases = [ROOT / "cases/train/standard_00.in", ROOT / "cases/train/light_00.in"]
    cases += [p for p in sorted((ROOT / "cases/train").glob("*.in")) if p not in cases]
    results, tapes, equivalence = [], [], []
    for case in cases:
        row = run_case(EXE, case, OUT, timeout=40)
        assert row["ok"], row
        tape = validate_tape(row)
        equal = {"case": row["case"], "full_report_equal": row["report"] == baseline[row["case"]]["report"],
                 "profit_delta": row["profit"] - baseline[row["case"]]["profit"]}
        results.append(row)
        tapes.append({"case": row["case"], **tape})
        equivalence.append(equal)
        write(OUT / "summary.json", results)
        write(OUT / "tapes.json", tapes)
        write(OUT / "equivalence.json", equivalence)
        print(json.dumps({"case": row["case"], "ok": row["ok"], "report_equal": equal["full_report_equal"],
                          "profit_delta": equal["profit_delta"], "rows": tape["rows"],
                          "failures": tape["failures"], "scheduler_cpu": tape["scheduler_cpu_before_export"]}), flush=True)
        if len(results) == 2:
            assert all(v["full_report_equal"] for v in equivalence), "First two shadow controls differ: investigate before full collection"
    record.update({"runs": len(results), "all_ok": all(r["ok"] for r in results),
                   "all_full_reports_equal": all(r["full_report_equal"] for r in equivalence),
                   "audit_total": sum(r["audit_total"] for r in results),
                   "rows": sum(r["rows"] for r in tapes), "failures": sum(r["failures"] for r in tapes),
                   "tapes": tapes, "equivalence": equivalence,
                   "solver_cpu_note": "bench CPU includes post-END CSV export; use tape scheduler_cpu_before_export when discussing scheduler cost"})
    write(ROOT / "research/v9_alarm_trace_manifest.json", record)
    report = "\n".join([
        "# V9 告警故障观测数据", "", "底座为冻结V8，只采集旁路观测，不改变调度策略、不拟合模型。",
        "事件处理完且schedule前，将本tick在线状态及告警/日志计数留在内存；最后END刷新后才向stderr导出CSV。包含tick0与下线机器，用于完整重建未来FAIL标签；未来事件没有进入在线特征。", "",
        f"训练16例全部正常，{record['audit_total']:,}次对账正确，0非法指令；共{record['rows']:,}行、{record['failures']:,}次FAIL。",
        f"完整judge报告逐例与V8生产程序相同：{record['all_full_reports_equal']}。前两例standard00/light00先核验，再完成其余14例。",
        "CSV第一行是#V9_TRACE元数据（T/M/W及导出前CPU），第二行为列名。bench统计含导出成本，不能将其当成正式调度耗时。每例日志行数、解码字符数与judge报告逐例相等。", "",
        "字段：tick,machine,up,dc,cpu,mem,alarm,loglines,decoded_chars,max_line_score,fail,up_event,last_fail_tick。alarm为本tick全部行的告警分和；max_line_score为本tick最大单行告警分；decoded_chars包括分隔符；fail/up_event为本tick已观察的事件。last_fail_tick可由历史事件重建，不包含未来。",
        "机器/场景编号只供联结，不宜当模型数值特征；可由原始磁带计算过去3/8/W tick窗口和距最近FAIL时间。训练时只将当前在线行作为风险起点，并将未来标签窗口被T截断的行删失处理。", "",
        "文件：results/v9_alarm_trace/<case>/solver_stderr.txt；tapes.json提供哈希和元数据；summary.json提供完整评测报告；equivalence.json提供逐例等价结果。未使用任何新留出集或学校隐藏数据。", ""])
    (ROOT / "research/v9_alarm_trace.md").write_text(report, encoding="utf8")
    print(json.dumps({k: record[k] for k in ["runs", "all_ok", "all_full_reports_equal", "rows", "failures", "audit_total"]}))


if __name__ == "__main__":
    main()
