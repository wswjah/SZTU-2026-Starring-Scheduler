"""Summarize fixed neural-model fits,all8 gates,andtrain-only finalist selection."""
from pathlib import Path
import hashlib
import json
import re
from v13_model_common import ROOT


def main():
    plan=json.loads((ROOT/"research/v14_mlp_plan.json").read_text(encoding="utf8"))
    fit=json.loads((ROOT/"research/v14_mlp_fit.json").read_text(encoding="utf8"))
    screen=json.loads((ROOT/"research/v14_mlp_screen.json").read_text(encoding="utf8"))
    selected=json.loads((ROOT/"research/v14_mlp_selected.json").read_text(encoding="utf8"))
    numeric=json.loads((ROOT/"research/v14_mlp_numeric.json").read_text(encoding="utf8"))
    assert len(screen["candidates"])==8 and numeric["all_passed"]
    all_rows=json.loads((ROOT/"results/v14_mlp_disabled/summary.json").read_text(encoding="utf8"))
    diagnostics=[]
    for record in screen["candidates"]:
        assert hashlib.sha256(Path(record["source"]).read_bytes()).hexdigest()==record["source_sha256"]
        rows=json.loads((Path(record["result_dir"])/"summary.json").read_text(encoding="utf8"));all_rows+=rows
        details=[]
        for row in rows:
            text=(Path(row["run_dir"])/"solver_stderr.txt").read_text(encoding="utf8")
            values=re.search(r"V14_MLP_POLICY attempts=(\d+) rejects=(\d+) late=(\d+) guard_returns=(\d+)",text)
            assert values,row["case"]
            details.append({"case":row["case"],**dict(zip(["attempts","rejects","late","guard_returns"],map(int,values.groups())))})
        comparison=json.loads((Path(record["result_dir"])/"comparison.json").read_text(encoding="utf8"))
        valid_ratios=[r for r in comparison["rows"]if not r["baseline_range_violations"]and r["profit_ratio"]is not None]
        diagnostics.append({"name":record["name"],"per_world":details,"totals":{k:sum(r[k]for r in details)for k in ["attempts","rejects","late","guard_returns"]},
                            "worst_positive_baseline":min(valid_ratios,key=lambda r:r["profit_ratio"])})
    assert len(all_rows)==260 and all(r["ok"]for r in all_rows)
    health={"interactive_runs":260,"all_ok":True,"audit_total":sum(r["audit_total"]for r in all_rows),
            "audit_errors":sum(r["audit_errors"]for r in all_rows),"illegal_commands":sum(r["incidents"]for r in all_rows),
            "max_cpu_seconds":max(r["solver_cpu_seconds"]for r in all_rows),"max_peak_memory_bytes":max(r["solver_peak_memory_bytes"]for r in all_rows)}
    result={"plan":plan,"fits":fit,"screen":screen,"selected":selected,"numeric":numeric,"health":health,"diagnostics":diagnostics,
            "fresh_data_accessed":False,"official_submission_sent":False,"report":"research/v14_mlp_experiment.md"}
    (ROOT/"research/v14_mlp_results.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf8")
    models={r["name"]:json.loads((ROOT/f"research/v14_mlp_{r['name']}.json").read_text(encoding="utf8"))for r in fit["architectures"]}
    shallow=models["A"]["shallow_tree_grouped_oof"];heuristic=models["A"]["existing_heuristic_clipped"]
    lines=["# V14：两个固定小神经网络的本地训练与门控试验", "", "2026-11-16。工程可行性已实测：两个网络都能在本机CPU训练，导出为纯C++双精度权重，不需要运行时Torch、GPU或外部模型文件。预测误差改善是否能转化成调度利润，另用固定门控闭环检验。", "",
           "## 事先固定的协议", "", "只使用V13新训练32个完整世界的41,151条实际入场流程及原18列特征/标签，没有旧85分数据，没有新增未入场负标签，没有读取V14新验证/确认结果。A为18→16 ReLU→2（338参数），B为18→16 ReLU→8 ReLU→2（458参数）；seed分别141116/141117。", "",
           "每次拟合固定120epoch、Adam lr0.003、weight_decay1e−4、batch1024、float64，单CPU线程/interop1，无早停、不挑epoch或seed。特征仍按原float32公式产生，再转double；均值/标准差仅从该训练折按世界总权重相等计算，std下限1e−6，标准化截至[-8,8]。4折完整世界GroupKFold，不把同世界流程随机拆开。", "",
           "最初计划文字把clip写入训练loss。主任务在首次fit前澄清，已保留初始文字并记录amendment：训练用raw线性输出weighted MSE，targets仍clip，输出clip仅用于报告和实时门控，以避免界外梯度为零。该修订发生在看到任何网络fit/CV结果之前，其余超参保持原定。", "",
           "## 折外预测误差", "", "| 模型 | earned/value MSE | net/value MSE |", "| --- | ---: | ---: |",
           f"| 当前启发式（同范围clip） | {heuristic['earned_fraction_mse']:.7f} | {heuristic['net_fraction_mse']:.7f} |",
           f"| V13浅树 | {shallow['earned_fraction_mse']:.7f} | {shallow['net_fraction_mse']:.7f} |"]
    for name in ["A","B"]:
        m=models[name]["grouped_oof"];lines.append(f"| 网络{name} | {m['earned_fraction_mse']:.7f} | {m['net_fraction_mse']:.7f} |")
    fit_seconds=sum(r["all_fit_wall_seconds"]for r in fit["architectures"])
    lines += ["", f"全部10次固定拟合（每架构4折+全32）实际训练部分合计约{fit_seconds:.2f}秒，不含Torch导入、C++编译和交互评测。两网络对现有启发式/浅树的MSE都有改善，但它们仍在预测baseline策略条件下的结果，不是拒绝动作的因果收益或完工概率。", "",
              "## 所有预声明门控闭环结果", "", "每网络使用V13原四个固定规则：light/strict净收益门槛、25%/50%收入混合，不追加新阈值或调轴。只作用于!started且资源/完整命令预算可执行后的首RUN之前；普通特征helper、原预约scalar字节回滚、99分参数及输入修复保留。", "",
              "| 策略 | 32例总利润变化 | 升/降 | 尝试/拒绝次数 | late/guard返回 | 最差正基线变化 |", "| --- | ---: | ---: | ---: | ---: | ---: |"]
    for record,diag in zip(screen["candidates"],diagnostics):
        v=record["valid_range"];d=diag["totals"]
        lines.append(f"| {record['name']} | {v['total_profit_increase_pct']:+.4f}% | {v['improved']}/{v['regressed']} | {d['attempts']:,}/{d['rejects']:,} | {d['late']}/{d['guard_returns']} | {100*(diag['worst_positive_baseline']['profit_ratio']-1):.2f}% |")
    lines += ["", "baseline slow_00本来利润为负，不计算其同比率，仍保留绝对利润与升降。当前数据均通过现有范围检查，未把缺失静态字段说成已验证。late/guard统计来自真实CPU保险；没有据这些统计追加策略。", "",
              "## 训练集选择与验证边界", "", "严格按预声明，每架构只保留训练aggregate利润最高且为正的一项："]
    for item in selected:
        lines += [f"- {item['name']}：训练{item['training_profit_increase_pct']:+.4f}%，源码SHA256 `{item['source_sha256']}`。"]
    if not selected:lines += ["没有正收益项，selected.json为空。"]
    lines += ["", "入选清单research/v14_mlp_selected.json在读取任何V14新利润前写定。后续由主任务统一冻结、打包并在新的40+40上检验；本分支没有接触那些结果，训练收益不能当正式提分。", "",
              "## 导出与健康检查", "", "C++内置训练均值/std与层参数，按double做标准化、ReLU和输出clip。两网络各1,744个原语query（真实样本、标准化边界外和均值附近）与NumPy/保存Torch输出对照，最大绝对差约1.55e−15/8.88e−16，4门控公式判定全相同。浮点点积归约次序可有ulp差，不把它写成所有double位模式完全相等；实际输入helper和门控代码仅替换预测函数。", "",
              f"每架构两个完整世界的disabled控制保留相同helper/网络计算而只关闭gate，4份报告与基线精确一致；这不是32例disabled证明。共{health['interactive_runs']}次实际交互评测（8×32+4控制），{health['audit_total']:,}次对账全对、0非法。本机最大CPU {health['max_cpu_seconds']:.6f}秒，峰值内存{health['max_peak_memory_bytes']:,}字节；正式1秒限制仍需看实际部署机器。", "",
              "默认与冻结源未改，没有正式提交。所有来源头保留，无变量混淆。计划/修订、拟合参数、OOF、8源、逐例数据、选择与诊断分别见research/v14_mlp_plan.json、v14_mlp_{A,B}.json、v14_mlp_fit.json、v14_mlp_policies.json、v14_mlp_screen.json、v14_mlp_selected.json、v14_mlp_results.json；工具在tools/v14_mlp_*。", ""]
    (ROOT/"research/v14_mlp_experiment.md").write_text("\n".join(lines),encoding="utf8")
    print(json.dumps({"health":health,"selected":[r["name"]for r in selected],"diagnostics":[{"name":r["name"],"totals":r["totals"]}for r in diagnostics]}))


if __name__=="__main__":main()
