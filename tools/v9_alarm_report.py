"""Record alarm prediction results, failed closed-loop policies and official99."""
from pathlib import Path
import hashlib
import json
from compare import compare, markdown

ROOT = Path(__file__).resolve().parent.parent


def load(path):
    return json.loads((ROOT / path).read_text(encoding="utf8"))


def dump(path, value):
    (ROOT / path).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf8")


def main():
    model = load("research/v9_alarm_model.json")
    trace = load("research/v9_alarm_trace_manifest.json")
    first = load("results/v9_alarm_screen/summary.json")
    second = load("research/v9_alarm_refine_results.json")
    records = first+second
    assert len(records) == 5
    all_runs = []
    for record in records:
        all_runs += load(f"results/v9_alarm_screen/{record['name']}/summary.json")
        assert record["valid_range"]["total_profit_increase_pct"] < 0
    assert len(all_runs) == 80 and all(r["ok"] for r in all_runs)
    disabled = load("results/v9_alarm_disabled/summary.json")
    baseline = load("results/v9_alarm_baseline_train/summary.json")
    original = {r["case"]: r for r in baseline}
    equivalence = [{"case": r["case"], "full_judge_report_equal": r["report"] == original[r["case"]]["report"],
                    "input_sha256_equal": r["input_sha256"] == original[r["case"]]["input_sha256"],
                    "judge_sha256_equal": r["judge_sha256"] == original[r["case"]]["judge_sha256"]}
                   for r in disabled]
    assert len(equivalence) == 16 and all(all(v for k, v in r.items() if k != "case") for r in equivalence)
    dump("results/v9_alarm_disabled/equivalence.json", equivalence)
    comparison = compare(ROOT / "results/v9_alarm_baseline_train", ROOT / "results/v9_alarm_disabled")
    dump("results/v9_alarm_disabled/comparison.json", comparison)
    (ROOT / "results/v9_alarm_disabled/comparison.md").write_text(markdown(comparison), encoding="utf8")
    audit = load("results/v9_alarm_audit.json")
    release = load("results/final_manifest.json")
    assert release["official_score"] == 99 and release["official_submission_id"] == 544054
    assert hashlib.sha256((ROOT / "submit.cpp").read_bytes()).hexdigest() == release["artifacts"]["submit.cpp"]["sha256"]
    assert hashlib.sha256((ROOT / "main.cpp").read_bytes()).hexdigest() == release["artifacts"]["main.cpp"]["sha256"]
    health = {"closed_loop_candidate_runs": len(all_runs),
              "candidate_audit_total": sum(r["audit_total"] for r in all_runs),
              "candidate_audit_errors": sum(r["audit_errors"] for r in all_runs),
              "candidate_illegal_commands": sum(r["incidents"] for r in all_runs),
              "candidate_max_cpu_seconds": max(r["solver_cpu_seconds"] for r in all_runs),
              "disabled_control_runs": len(disabled), "disabled_full_reports_equal": True,
              "trace_runs": trace["runs"], "trace_full_reports_equal": trace["all_full_reports_equal"],
              "prediction_implementation_audit": "results/v9_alarm_audit.json"}
    record = {"date": "2026-11-15", "base": "versions/v8_fine/main.cpp", "official_best": 99,
              "official_submission_id": 544054, "remaining_submissions": 4,
              "alarm_research_official_submissions": 0,
              "model": "research/v9_alarm_model.json", "candidate_results": records, "health": health,
              "grouped_prediction_results": model["grouped_oof"], "grouped_constant": model["grouped_constant"],
              "decision": "Do not merge any alarm policy: all5 train aggregate profits negative despite predictive information",
              "new_world_validation": "Not run: no candidate passed train-only selection; no hidden tests or official case details accessed",
              "limitations": ["World-level CV uses16 local generated worlds", "Overlapping labels are not independent failures",
                              "Tree selects raw score scales, potential distribution drift", "FAIL cause not exactly labeled",
                              "Expected interruption loss is a heuristic; predictive lift does not imply profit lift"],
              "implementation_audit": "research/v9_alarm_implementation_audit.md"}
    events = ROOT / "research/v9_alarm_events.json"
    if events.exists():
        record["event_level_diagnosis"] = "research/v9_alarm_events.json"
    dump("research/v9_alarm_experiment_manifest.json", record)
    lines = ["# V9：告警预测与风险调度试验", "", "2026-11-15。正式V8提交544054为99分，已用6次、剩4次。告警研究仅本地运行，没有新正式提交。", "",
             "## 结论", "", "日志中确实有提前故障信息；但本轮五种风险选机策略在训练总利润上全部退步，因此不进入正式99分代码。没有通过训练筛选的候选，也就没有继续用新世界挑一个报喜。", "",
             "## 数据、训练与预测结果", "", f"以正式99分源码作旁路记录，train16共{trace['rows']:,}行原始机器/tick磁带，{trace['failures']:,}次FAIL。记录前后16份完整judge报告逐字一致，{trace['audit_total']:,}次对账全对。",
             f"删除当前离线和未来观察不足的行后，得到{model['rows']:,}行。标签为未来3/8/16tick内任意FAIL，统一t+16<=T，不含当前FAIL；只用当前及过去日志特征。",
             "固定共享深度3概率树、最小叶500行，按整世界4折验证，每世界训练总权重相同，不做类别平衡。最终15节点，只读8tick告警总量、题面W窗告警总量、8tick最大单行告警的log1p值。", "",
             "| 未来窗口 | 分组预测Brier | 训练折常数Brier | Brier改善 | AP | 实际故障基率 |", "| --- | ---: | ---: | ---: | ---: | ---: |"]
    for horizon in ["3", "8", "16"]:
        a, b = model["grouped_oof"][horizon], model["grouped_constant"][horizon]
        improvement = 100*(1-a["weighted_brier"]/b["weighted_brier"])
        lines.append(f"| {horizon}tick | {a['weighted_brier']:.8f} | {b['weighted_brier']:.8f} | {improvement:.2f}% | {a['average_precision']:.4f} | {100*a['observed_event_probability']:.3f}% |")
    lines += ["", "Brier越低越好；AP是排序诊断，不等于在某固定门槛下的故障命中率。相邻tick可指向同一FAIL，不能把百万样本说成百万独立事件。CSV的FAIL包含集体故障，不能精确断言每次来源。", "",
              "## 如何影响调度", "", "模型概率在3/8/16三个点线性插值，只对当前可立即运行的机器按未来最多16tick计超额风险；预约机器不把当前告警外推到未来。",
              "以训练总体背景率为基准，只给高于背景的风险加费用，估计一次中断造成的核时、重启费和延迟损失。普通启动和RUN/KILL/RUN预热分别使用各自准备时间加罚，不把风险罚写入真实账本。半窗口中断和feeAvg重启成本仍为启发式。", "",
              "先固定0.5/1/2三种权重；全部负收益后只追加两项有边界的检验：0.25权重，以及原估价完全相等时才按风险择机。没有继续无上限寻参。", "",
              "| 配置 | 14个范围内训练总利润 | 升/降/平 | 等权平均利润变化 |", "| --- | ---: | ---: | ---: |"]
    for r in records:
        v = r["valid_range"]
        lines.append(f"| {r['name']} | {v['total_profit_increase_pct']:+.4f}% | {v['improved']}/{v['regressed']}/{v['unchanged']} | {v['equal_weight_increase_pct']:+.4f}% |")
    lines += ["", "train中两个large超保守3,000,000日志字符界限，完整结果保留，未计14例范围内利润。预测有信息仍不保证净收益增加；避险会改变等待、缓存与其他任务轨迹，本轮未做逐决策因果分解，不能把全部退步归因于某一项费用。", "",
              "## 实现与控制验证", "", f"五候选共{health['closed_loop_candidate_runs']}次闭环运行、{health['candidate_audit_total']:,}次对账全对、0非法指令；最大本机CPU {health['candidate_max_cpu_seconds']:.6f}s。",
              "关闭风险估价、保留观测计算的控制版16份完整judge报告逐例与99分基线一致，避免把新增诊断/计算触发时间保险误当策略变化。",
              "独立审计直接include真实C++候选：1,064个快照的3个实际float输入和3个概率与Python误差全0；21个阈值边界、9个插值、9个风险费及实际换机/预热/账本检查通过。", "",
              "全部模型/源码/对比保留：v9_alarm_model.json、v9_alarm_candidates.json、v9_alarm_refine_results.json、results/v9_alarm_screen/。实现审计见v9_alarm_implementation_audit.md，数据见v9_alarm_trace.md。",
              "当前main.cpp/submit.cpp仍与正式99分回执完全一致；告警候选没有提交。下一步若继续，应优先改善决策损失估价或收集故障导致的真实任务损失，而不是把预测概率提高当作已经提分。", ""]
    if events.exists():
        lines += ["## 事件级补充审计", "",
                  "20,129个16tick正行指向1,266个不同机器FAIL事件，且不同机器FAIL也可能有共同原因。按同DC同tick至少一半机器且不少于3台FAIL的启发式，标出706个疑似集体机器FAIL；这不是精确原因标签。",
                  "分组OOF预测p8>=30%的行仅占0.177%，预测均值45.47%、实际39.60%，显示高端有过信；p8>=10%的行占0.876%，预测23.41%、实际22.30%。8tick Brier在15/16世界改善。",
                  "最终最高风险叶覆盖15个世界、154个不同未来FAIL，仅2个被标疑似集体；这些是训练内叶诊断，不能替代分组OOF证据。全部叶子事件数不可简单相加，因为同一FAIL在前兆演变中可能跨多个叶子。完整定义见v9_alarm_events.md/.json。", ""]
    (ROOT / "research/v9_alarm_experiment.md").write_text("\n".join(lines), encoding="utf8")
    print(json.dumps({"official_best": 99, "remaining": 4, "health": health,
                      "policies": [{"name": r["name"], "profit_pct": r["valid_range"]["total_profit_increase_pct"]} for r in records]}))


if __name__ == "__main__":
    main()
