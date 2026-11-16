"""Document the fixed128-world fits and exports without reading policy profits."""
from pathlib import Path
import hashlib
import json
from v13_model_common import ROOT


def main():
    plan=json.loads((ROOT/"research/v15_training_plan.json").read_text(encoding="utf8"))
    inputs=json.loads((ROOT/"research/v15_training_inputs.json").read_text(encoding="utf8"))
    fit=json.loads((ROOT/"research/v15_fit.json").read_text(encoding="utf8"))
    sources=json.loads((ROOT/"research/v15_models.json").read_text(encoding="utf8"))
    numeric=json.loads((ROOT/"research/v15_numeric.json").read_text(encoding="utf8"))
    assert len(fit["models"])==len(sources)==4 and numeric["all_passed"]
    models={name:json.loads((ROOT/f"research/v15_{name}.json").read_text(encoding="utf8"))for name in plan["models"]}
    for record in sources:
        assert hashlib.sha256(Path(record["source"]).read_bytes()).hexdigest()==record["source_sha256"]
        assert hashlib.sha256(Path(record["model_json"]).read_bytes()).hexdigest()==record["model_sha256"]
    total_seconds=sum(r["all_fit_wall_seconds"]for r in fit["models"])
    report={"date":"2026-11-16","inputs":inputs,"plan":plan,"fits":fit,"models":sources,"numeric":numeric,
            "all_fit_wall_seconds":total_seconds,"no_interactive_runs_by_training_agent":True,
            "fresh_policy_profits_read":False,"no_training_policy_or_threshold_selection":True,
            "training_report":"research/v15_training_report.md","official_submission_sent":False}
    (ROOT/"research/v15_training_results.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf8")
    ref=models["A128_120"]
    lines=["# V15：128世界扩训、固定步数对照与C++导出", "", "2026-11-16。本报告只记录训练和非交互数值核验，不读取任何V15策略训练利润或新80例利润；主任务负责实际packed程序的训练/新验证评测。", "",
           "## 数据与事先固定的四项比较", "", f"入场样本从旧32世界41,151条扩到128世界{inputs['rows']:,}条：原V13 32+新增96个训练世界。case分别显式前缀v13/与v15/，不会把同名文件误合为一个世界。每世界总权重相等，所以旧32恰占总权重1/4，不让样本量更大的世界压过其它世界。未入场流程未作为失败负标签。", "",
           "新数据沿用原18个首RUN前特征与原99分baseline的条件结果标签；不把标签视为反事实拒绝收益、因果动作价值或完工概率。数据代理保留每世界完整评测报告和独立账本核验，输入精确SHA见v15_training_inputs.json。", "",
           "在拟合前写定research/v15_training_plan.json。四项全部进入后续验证，不按训练利润挑模型或阈值：A128_120为18→16→2/120epoch/原25%收入混合门控；B128_120为18→16→8→2/120epoch/原strict门控；tree128为原depth3、minleaf500、seed131116/strict；A128_steps为同A结构/seed/25%门控、每次fit固定4,920更新。", "",
           "NN seedA141116/B141117、Adam lr0.003、weight_decay1e−4、batch1024不改。训练loss仍对raw输出做世界等权MSE，评估和实时推理再将earned截[0,1]、net截[-2,1]。NN使用float64训练/推理，原float32特征先转double；每折仅用训练世界的加权均值/std（下限1e−6）标准化，再截[-8,8]。tree保留原raw float32输入/双精度阈值与叶均值，不新增标准化或规则。", "",
           "## 实际训练预算", "", "| 模型 | 每折更新数 | 最终更新数 | 最终epoch起始/完整 | 拟合总秒数 |", "| --- | ---: | ---: | ---: | ---: |"]
    for entry in fit["models"]:
        name=entry["name"];m=models[name]
        if m["settings"]["kind"]=="mlp":
            updates="/".join(map(str,sorted(set(f["optimizer_updates"]for f in m["folds"]))))
            lines.append(f"| {name} | {updates} | {m['optimizer_updates']} | {m['epochs_started']}/{m['full_epochs_completed']} | {entry['all_fit_wall_seconds']:.2f} |")
        else:lines.append(f"| {name} | 非Adam | 非Adam | — | {entry['all_fit_wall_seconds']:.2f} |")
    lines += ["", f"全部20次fit（4模型×4折与全128）训练部分合计约{total_seconds:.2f}秒，单CPU线程/interop1，无early stopping、不挑epoch或seed。总时长不含Torch导入、编译或评测。", "",
              "A128_steps每次fit都精确4,920更新。最终fit与旧A32的120×ceil(41151/1024)更新数相同；新128的OOF折也固定4,920，但这不等于旧32折的预算。每次走完一个epoch后重新shuffle，到第4,920步立即停止，允许最后一个epoch不完整；完整/部分epoch及sample_presentations均保留。更新数相同不等于样本呈现次数完全相同，因为每epoch末尾batch大小不同。", "",
              "在相同128数据上，A120与Asteps的标准化、seed、结构和规则相同，主要分辨更多Adam更新带来的影响；与旧A32比较还含新增数据及其标准化变化，不能把所有差异只归于网络规模或训练时间。", "",
              "## 128世界分组折外预测", "", "4折按完整world分组，样本与标签不跨同世界泄漏。各fold常数均仅来自训练世界；所有模型都在同一128世界、相同权重下比较。", "",
              "| 方法 | earned/value MSE | net/value MSE |", "| --- | ---: | ---: |",
              f"| 现有启发式（clip） | {ref['heuristic_clipped']['earned_fraction_mse']:.7f} | {ref['heuristic_clipped']['net_fraction_mse']:.7f} |",
              f"| 各折训练均值常数 | {ref['grouped_trainonly_constant']['earned_fraction_mse']:.7f} | {ref['grouped_trainonly_constant']['net_fraction_mse']:.7f} |"]
    for name,m in models.items():
        p=m["grouped_oof"];lines.append(f"| {name} | {p['earned_fraction_mse']:.7f} | {p['net_fraction_mse']:.7f} |")
    lines += ["", "这些MSE不能直接与旧32世界的数值比较后宣称扩训变好或变坏，因为目标样本分布已经不同。模型文件另有v13旧32/v15新增96子集的同口径OOF指标。预测误差也不等于闭环调度利润，四项仍按预声明全部送往统一验证。", "",
              "## 导出与精度核验", "", "4份独立candidates/v15_models/*.cpp仅替换对应原gate里的predictor，并把诊断前缀统一为V15_MODEL_POLICY；原来源头、18特征helper、预约scalar字节回滚、8MiB缓冲区、整数扫描、CPU保险及20k指令护栏保持。NN参数与标准化常量直接内置C++，不依赖Torch运行时。", "",
              "| 模型 | 非交互query数 | C++/参考最大误差 | 保存最终预测误差 |", "| --- | ---: | ---: | ---: |"]
    for row in numeric["models"]:
        lines.append(f"| {row['name']} | {row['queries']} | {row['cpp_numpy_max_abs_error']:.3g} | {row['cpp_saved_final_prediction_error']:.3g} |")
    lines += ["", "NN测试包含真实样本、超出标准化夹紧范围与均值附近输入；tree包含全部叶和float32分裂阈值邻点。4种门控公式判定在测试中全部相同。浮点点积归约可有ulp差，不把NN误差小写成所有double位模式完全一致；原实际门控/特征代码本身未改。", "",
              "## 交付位置与范围", "", "research/v15_models.json为固定list4清单，列出源码/模型/exe哈希及policy_name，供主任务统一冻结。所有源在数值核验后保持稳定，训练代理没有跑任何交互、没有读取新场景利润，也没有更改默认/冻结版本或消耗正式提交。主任务packed exe与本报告unpacked exe区分保存，避免覆盖其哈希。", "",
              "主要记录：v15_training_plan.json、v15_training_inputs.json、v15_{name}.json、v15_fit.json、v15_models.json、v15_numeric.json、v15_training_results.json；可复现工具：tools/v15_train_models.py、v15_export_models.py、v15_model_numeric.py、v15_training_report.py。独立审查另见research/v15_independent_review.md。", ""]
    (ROOT/"research/v15_training_report.md").write_text("\n".join(lines),encoding="utf8")
    print(json.dumps({"models":list(models),"rows":inputs["rows"],"all_fit_wall_seconds":total_seconds,"numeric_passed":True,"no_fresh_profits_read":True}))


if __name__=="__main__":main()
