"""Record completed correctness probes and exact train report equivalence."""
from pathlib import Path
import hashlib
import json

ROOT=Path(__file__).resolve().parent.parent
old=json.loads((ROOT/"results/v8_report/production_train/summary.json").read_text(encoding="utf8"))
new=json.loads((ROOT/"results/v10_fix_input_train/summary.json").read_text(encoding="utf8"))
old={r["case"]:r for r in old};new={r["case"]:r for r in new}
assert old.keys()==new.keys() and len(old)==16
differences=[name for name in old if old[name]["report"]!=new[name]["report"]]
assert not differences
baseline=(ROOT/"versions/v8_fine/main.cpp").read_text(encoding="utf8")
fixed=(ROOT/"candidates/v10_fix_input.cpp").read_text(encoding="utf8")
assert fixed==baseline.replace("tok[1 << 22]","tok[1 << 23]")
record={"train_cases":16,"complete_judge_reports_identical":True,"report_differences":differences,
        "all_runs_ok":all(r["ok"] for r in new.values()),"audit_total":sum(r["audit_total"] for r in new.values()),
        "only_source_change":"tok[1<<22] to tok[1<<23]",
        "source_sha256":hashlib.sha256((ROOT/"candidates/v10_fix_input.cpp").read_bytes()).hexdigest(),
        "focused_probe":{"executed_command":"build/v10_correctness_probes.exe","exit_code":0,
                         "stdout":"slack_comparisons=12656\nLRU30000 operations and SLACK independent oracle passed\n",
                         "recording_note":"Recorded from completed root-task child tool execution, not rerun by this recorder.",
                         "exe_sha256":hashlib.sha256((ROOT/"build/v10_correctness_probes.exe").read_bytes()).hexdigest()},
        "network_protocol_probes":json.loads((ROOT/"results/v10_network_probe/summary.json").read_text(encoding="utf8")),
        "large_log_reproducer":"research/v10_fix_input_manifest.json",
        "formal_hidden_failure_cause_known":False,"official_submission_sent":False}
(ROOT/"results/v10_correctness_audit.json").write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding="utf8")
print(json.dumps({"train_complete_reports_identical":True,"audit_total":record["audit_total"],"network_queries":6000,
                  "lru_operations":30000,"slack_comparisons":12656}))
