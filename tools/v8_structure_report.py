"""Summarize the two predeclared V8 structural forecasts without selecting on holdout."""
from pathlib import Path
import json
import re
from compare import compare, markdown

ROOT = Path(__file__).resolve().parent.parent
records = []
for name in ["quota", "contention"]:
    dest = ROOT / f"results/v8_structure_{name}"
    comparison = compare(ROOT / "results/v8_baseline_train", dest)
    (ROOT / f"research/v8_structure_{name}_comparison.json").write_text(json.dumps(comparison, indent=2), encoding="utf8")
    (ROOT / f"research/v8_structure_{name}_comparison.md").write_text(markdown(comparison), encoding="utf8")
    triggers = []
    for path in sorted(dest.glob("*/solver_stderr.txt")):
        text = path.read_text(encoding="utf8")
        match = re.fullmatch(r"v8_forecasts=(\d+) v8_bounds=(\d+) v8_extra=([\d.]+)\s*", text)
        assert match, (path, text)
        triggers.append({"case": path.parent.name, "forecasts": int(match[1]), "bound_triggered": int(match[2]), "added_ticks_sum": float(match[3])})
    records.append({"name": name, "comparison": comparison, "trigger_counts": triggers})
(ROOT / "research/v8_structure_results.json").write_text(json.dumps(records, indent=2), encoding="utf8")
lines = ["# V8 配额约束的完工时间估计", "",
         "仅本地试验。底座为冻结 V7，原正式96分版本与冻结候选均未改动。两版在看结果前指定；没有读取新40例的结果。", "",
         "现有估计只沿DAG求最长路径；并行分支共同占用租户及祖先配额时，工期还受到剩余核时/配额约束。", "",
         "A quota：rem=max(rem,work/max(1,路径最小配额))。B contention：有效配额再扣除0.5倍其他流程的当前运行占用。", "",
         "这里的下界针对当前配额，未来QUOTA或UNDO可改变它；B则是启发式拥塞估计。未改账本、缓存、命令协议、V6修复、计时兼容层或署名。", "",
         "| 版本 | 范围内14例总利润 | 升/降/平 | 全部16例最大CPU |", "| --- | ---: | ---: | ---: |"]
for record in records:
    summary = record["comparison"]["valid_range_summary"]
    candidate_health = record["comparison"]["candidate_health"]
    lines.append(f'| {record["name"]} | {summary["total_profit_increase_pct"]:+.6f}% | {summary["improved"]}/{summary["regressed"]}/{summary["unchanged"]} | {candidate_health["max_cpu_seconds"]:.6f}s |')
lines += ["", "32次实际运行均正常，0对账错、0非法指令；train中的两个large日志超3,000,000字符，保留作压力数据但不纳入范围内14例。", "",
          "A只改变fast_00的利润：14,279,308→14,387,386，其余15例完全持平。A在fast_00的85,154次预测中只触发31次，其余场景零触发。", "",
          "B只改变fast_00的利润：14,279,308→14,173,095。B在fast_00触发83次，heavy_00/large_01/unstable_01另有7/1/4次触发但利润未变。", "",
          "训练选择：保留A作为低影响备选，淘汰B。A的增益集中于一个场景，尚无稳定性证据，不应仅凭+0.194%直接合并正式候选。是否进入新40例由主任务统一决策。", "",
          "额外开销为每次流程重估沿租户祖先链遍历一次；无平方扫描。单次最大CPU及内存受运行差异影响，不把计时小差值称为性能退化或提速。", "",
          "没有正式提交，也没有改变默认源文件。详见v8_structure_manifest.json、v8_structure_results.json和两版完整对比。"]
(ROOT / "research/v8_structure_review.md").write_text("\n".join(lines) + "\n", encoding="utf8")
print(json.dumps([{ "name": r["name"], "valid": r["comparison"]["valid_range_summary"] } for r in records]))
