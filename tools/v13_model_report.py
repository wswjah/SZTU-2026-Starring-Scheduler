"""Report current-policy ML calibration and every predeclared closed-loop result."""
from pathlib import Path
import hashlib
import json
import re
from v13_model_common import ROOT,FEATURES,POLICIES


def main():
    dataset=json.loads((ROOT/"research/v13_model_dataset.json").read_text(encoding="utf8"))
    model=json.loads((ROOT/"research/v13_model_tree.json").read_text(encoding="utf8"))
    screen=json.loads((ROOT/"research/v13_model_screen.json").read_text(encoding="utf8"))
    assert set(r["name"]for r in screen["candidates"])==set(POLICIES)
    diagnostics=[];all_runs=[]
    for label in ["results/v13_model_trace","results/v13_model_disabled"]:
        all_runs+=json.loads((ROOT/label/"summary.json").read_text(encoding="utf8"))
    for record in screen["candidates"]:
        assert hashlib.sha256(Path(record["source"]).read_bytes()).hexdigest()==record["source_sha256"]
        rows=json.loads((Path(record["result_dir"])/"summary.json").read_text(encoding="utf8"))
        all_runs+=rows
        per_world=[]
        for row in rows:
            text=(Path(row["run_dir"])/"solver_stderr.txt").read_text(encoding="utf8")
            match=re.search(r"V13_MODEL_POLICY attempts=(\d+) rejects=(\d+) late=(\d+) guard_returns=(\d+)",text)
            assert match
            per_world.append({"case":row["case"],**dict(zip(["attempts","rejects","late","guard_returns"],map(int,match.groups())))})
        comparison=json.loads((Path(record["result_dir"])/"comparison.json").read_text(encoding="utf8"))
        ratios=[r for r in comparison["rows"]if not r["baseline_range_violations"]and r["profit_ratio"]is not None]
        diagnostic={"name":record["name"],"totals":{k:sum(r[k]for r in per_world)for k in ["attempts","rejects","late","guard_returns"]},
                    "per_world":per_world,"worst_ratio":min(ratios,key=lambda r:r["profit_ratio"]),
                    "full_reports_equal":sum(r["report"]==old["report"]for r in rows for old in json.loads((ROOT/"results/v13_baseline_train32/summary.json").read_text(encoding="utf8"))if r["case"]==old["case"])}
        diagnostics.append(diagnostic)
    assert len(all_runs)==162 and all(r["ok"]for r in all_runs)
    health={"actual_runs":162,"all_runs_ok":True,"audit_total":sum(r["audit_total"]for r in all_runs),
            "audit_errors":sum(r["audit_errors"]for r in all_runs),"illegal_commands":sum(r["incidents"]for r in all_runs),
            "max_cpu_seconds":max(r["solver_cpu_seconds"]for r in all_runs),"max_peak_memory_bytes":max(r["solver_peak_memory_bytes"]for r in all_runs)}
    output={"dataset":dataset,"model":model,"closed_loop":screen,"diagnostics":diagnostics,"health":health,
            "all_existing_headers_preserved":True,"training":"cases/v13_train32 only,32 completeworlds",
            "fresh_data_accessed":False,"official_submission_sent":False,"report":"research/v13_model_experiment.md",
            "decision":"strict has only a small train gain;others zero/negative. Root may decide whether a fixed finalist deserves fresh validation;no additional fitting or thresholds."}
    (ROOT/"research/v13_model_results.json").write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding="utf8")
    mse=model["grouped_oof"];heur=model["existing_heuristic_clipped"];const=model["grouped_trainonly_constant"]
    lines=["# V13：当前99分策略的首入场小模型", "", "2026-11-16。底座为versions/v12_scan_input_fix/main.cpp，保留8MiB修复、直接整数扫描与99分调度参数。没有使用旧85分V4数据或告警模型，没有正式提交。", "",
           "## 实际闭环结果", "", "先预声明18个特征、固定深度3/最小叶500和4个策略，再收集32个新种子训练世界。全部策略仅在这32例评估，没有读V13holdout/confirmation或追加阈值。", "",
           "| 策略 | 32例总利润 | 升/降/平 | gate拒绝次数 | 最差正基线比值变化 |", "| --- | ---: | ---: | ---: | ---: |"]
    for record,diag in zip(screen["candidates"],diagnostics):
        v=record["valid_range"]
        lines.append(f"| {record['name']} | {v['total_profit_increase_pct']:+.4f}% | {v['improved']}/{v['regressed']}/{v['unchanged']} | {diag['totals']['rejects']:,} | {100*(diag['worst_ratio']['profit_ratio']-1):.2f}% |")
    lines += ["", "light没有实质拒绝；strict训练总利润仅小幅提高，不能据此宣称可靠提分。两种收入混合校准退步。正基线用例之外，baseline slow_00本来亏损，仍计入绝对利润与升降，不给负基线编造正同比。完整最差/逐例记录保留在各comparison.json。", "",
              "## 诊断数据和标签", "", f"诊断32例与原基线的完整judge报告逐字相同；{dataset['all_flows']:,}条流程中{dataset['admitted']:,}条实际首入场。每条流程独立累计真实runJob的registry/transfer费用、每次release的CPU费用及最终仍运行作业T+1费用，按实际finish取整收益。每世界的run/pull/net/cost/earned/profit与judge逐项精确一致。", "",
              "first_seen在完整批次提交前、预算满足且选中机器可立即执行时捕获一次，发生在任何预热RUN之前；不依赖两次预热RUN之间仍为false的w.started。never-started只用于全账本核验，未作为失败训练标签。", "",
              "原schedule真实重估时保存BB后的rem、work、cost、五情景rev及tick；捕获时只读取该缓存和当前可见状态，没有额外flowEstimate，不改变jobTheta/Tail。特征中的selected prep是原放置报价的估计bs，可能与真实LRU执行后的prep不同；实际费用标签始终使用runJob真值。", "",
              "18个特征按顺序为："+", ".join(FEATURES)+"。root_fraction在WF到达时由完整已知DAG计算；quota/headroom、租户factor、当前时间、输入传输费和选中预热动作都在首RUN前可见。forecast_age明确保留旧预测的年龄。", "",
              "root在trace32已经产出后建议加入时长学习置信度。本轮按事先计划保留18schema，没有看结果后改feature或重采来挑更好数字；该方向可另开独立试验。", "",
              "## 小模型及校准证据", "", "标签为实际earned/value和clip((earned−cost)/value,−2,1)。这是当前baseline策略下已接纳流程的条件结果，不是完工概率、反事实拒绝收益或因果动作价值。训练使用32个完整世界4折分组，世界总权重相同；没有随机拆同世界样本，也不使用ID/seed特征。每折常数只按训练世界均值生成。", "",
              "最终共享树15节点、8叶，只选择forecast_net_per_value和tenant_duration_factor；C++内置常量数组，不依赖运行时Python或模型文件。", "",
              "| 世界等权MSE | 模型折外 | 现有启发式（clip） | 折内训练均值常数 |", "| --- | ---: | ---: | ---: |",
              f"| earned/value | {mse['earned_fraction_mse']:.7f} | {heur['earned_fraction_mse']:.7f} | {const['earned_fraction_mse']:.7f} |",
              f"| net/value | {mse['net_fraction_mse']:.7f} | {heur['net_fraction_mse']:.7f} | {const['net_fraction_mse']:.7f} |", "",
              "现有启发式raw MSE也完整列于tree.json；收入raw/clip相同，net raw与clip接近。模型对net相比现有估价只改善约0.88%，远小于对常数的改善；闭环利润没有因此显著增长。每profile的多个新种子分在不同world folds，交叉验证不等于留出全新参数分布。", "",
              "## 四项预声明策略与安全范围", "", "veto_light：n>=3、modelNet<0.02且forecastNet/value<0.25才拒绝。veto_strict：相同范围，阈值为0.08/0.40。rev_blend25/50：用25%/50%模型earned预测混合原forecastRev，混合收入没有超过forecastCost*(1+ADM)则拒绝。没有对运行中流程施加模型止损。", "",
              "gate位于首个真实RUN之前且只在!started时执行。拒绝恢复进入tryPlace前的作业scalar/reservation原始字节，不typed读取原来未初始化的resM/resAt/resEnd，不改pre/suc向量、缓存、账单、配额或命令输出。普通合法性、真实费用和20k预热原子护栏仍由原代码执行。", "",
              "disabled控制保留完整forecast cache、特征helper和树推理，仅关闭gate，以volatile sink确保计算保留；fast_00、standard_00两个完整世界报告精确等价。该控制只有2个世界，不能称为32例disabled验证；补充证据是light在32例一次也未拒绝，完整报告32/32逐字相同。所有4策略合计的原CPU保险late/guard_returns计数均为0，本轮闭环差异没有依赖已观察到的保险触发来解释。", "",
              f"本分支共{health['actual_runs']}次实际评测（trace32、disabled2、4策略×32），{health['audit_total']:,}次对账全对、0非法指令。本机最大CPU {health['max_cpu_seconds']:.6f}s，峰值内存{health['max_peak_memory_bytes']:,}字节；这些是健康记录，不是正式时限保证。", "",
              "## 位置", "", "预声明research/v13_model_plan.json；数据与对账research/v13_model_dataset.json、results/v13_model_dataset/；训练与树research/v13_model_tree.json、results/v13_model_fit/；4候选research/v13_model_policies.json、candidates/v13_model/；闭环及诊断research/v13_model_screen.json、v13_model_results.json。", "",
              "工具按v13_model_common/trace/prepare/train/metrics/policies/screen/report分工，可复现当前分支；所有上游来源头注释保留。默认与已冻结文件未改，未消费提交次数。", ""]
    for name in ["v13_model_review.md","v13_model_experiment.md"]:
        (ROOT/"research"/name).write_text("\n".join(lines),encoding="utf8")
    print(json.dumps({"health":health,"diagnostics":[{"name":r["name"],"totals":r["totals"],"worst":r["worst_ratio"]["case"],"worst_ratio":r["worst_ratio"]["profit_ratio"]}for r in diagnostics]}))


if __name__=="__main__":main()
