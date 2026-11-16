"""Record the rejected donor experiment and the already-executed focused test."""
from pathlib import Path
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parent.parent
comparison = json.loads((ROOT / "research/v8_donor_comparison.json").read_text(encoding="utf8"))
rows = json.loads((ROOT / "results/v8_donor_train/summary.json").read_text(encoding="utf8"))
totals = {key: 0 for key in ["uses", "saved", "checks"]}
for row in rows:
    stderr = (Path(row["run_dir"]) / "solver_stderr.txt").read_text(encoding="utf8")
    for key in totals:
        match = re.search(rf"v8_donor_{key}=(\d+)", stderr)
        assert match, (row["case"], key)
        totals[key] += int(match.group(1))
assert totals["uses"] == 261 and totals["saved"] == 16339
record = {"train_comparison": comparison, "diagnostics": totals,
          "runs": len(rows), "audit_total": sum(r["audit_total"] for r in rows),
          "all_ok": all(r["ok"] for r in rows),
          "focused_test": {"harness": "tools/v8_donor_tests.cpp",
                           "compiler_command": "g++ -std=c++17 -O2 tools/v8_donor_tests.cpp -o build/v8_donor_tests.exe",
                           "executed_command": "build/v8_donor_tests.exe",
                           "exit_code": 0,
                           "stdout": "donor focused regressions passed: quota, resources, connectivity, atomic budget, state and ledger\n",
                           "recording_note": "Recorded from the root agent's completed tool execution, not rerun by this recorder.",
                           "compiler_note": "Harness renames solver main, producing a missing-return warning in that renamed function; production candidate compile has no warnings.",
                           "exe_sha256": hashlib.sha256((ROOT / "build/v8_donor_tests.exe").read_bytes()).hexdigest()},
          "decision": "Reject based on train-only aggregate regression; no holdout or combination evaluated",
          "official_submission_sent": False}
(ROOT / "research/v8_donor_results.json").write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf8")
v = comparison["valid_range_summary"]
(ROOT / "research/v8_donor_review.md").write_text(f"""# V8 同镜像替身预热

候选基于V7，按每镜像最多4个待运行供体筛选。只有供体机器资源、租户及祖先配额、输入可达性均满足，并且输入传输费更低，才采用供体RUN/KILL再目标RUN。缓存镜像相同，实际账单仍由真实runJob/killNow按各租户维护，供体ready/预约字段恢复，三条命令先整批预留预算。

训练16例中261次使用，直接减少额外传输费16,339。闭环范围内14例总利润却{v['total_profit_increase_pct']:+.4f}%，{v['improved']}升{v['regressed']}降{v['unchanged']}平。局部省费改变后续资源、缓存和优先级轨迹，不能保证总利润增加，因此淘汰；未进入组合或留出测试。

16次实跑全部对账正确、零非法。实际候选的定向测试覆盖不同租户、叶/祖先配额不足、CPU/内存不足、不可达输入、供体状态改变、命令余额2/3、供体ready与预约恢复、缓存/真实收费/占用账本，均通过。测试入口改名导致编译器对原隐式main返回给出警告；候选生产编译没有该警告。

源码、训练完整比较、诊断及测试证据见v8_donor_manifest.json、v8_donor_comparison.json、v8_donor_results.json。本实验无正式提交。
""", encoding="utf8")
print(json.dumps({"all_ok": record["all_ok"], "runs": len(rows), "diagnostics": totals,
                  "train_profit_pct": v["total_profit_increase_pct"], "focused_test_recorded": True}))
