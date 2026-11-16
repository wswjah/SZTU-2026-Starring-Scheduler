"""Consolidate neural-vs-tree profits, risks, packed evidence and local handoff."""
from pathlib import Path
import hashlib
import json
import re
import subprocess
from compare import compare, markdown

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "results/v14_report"


def load(path):
    return json.loads((ROOT / path).read_text(encoding="utf8"))


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf8")


def save(name, rows):
    directory = OUT / name
    dump(directory / "summary.json", rows)
    return directory


def comparison(name, old, new):
    value = compare(old, new)
    dump(OUT / (name+".json"), value)
    (OUT / (name+".md")).write_text(markdown(value), encoding="utf8")
    return value


def main():
    selection = load("research/v14_frozen_selection.json")
    training = load("research/v14_mlp_screen.json")
    fit = load("research/v14_mlp_fit.json")
    assert len(selection["candidates"]) == 2 and len(training["candidates"]) == 8
    OUT.mkdir(parents=True, exist_ok=True)
    all_runs = load("results/v14_mlp_disabled/summary.json")
    assert len(all_runs) == 4
    for row in training["candidates"]:
        all_runs += load(str(Path(row["result_dir"]) / "summary.json"))
    baseline = {}
    for split in ["holdout", "confirmation"]:
        baseline[split] = load(f"results/v14_{split}_baseline/summary.json")
        assert len(baseline[split]) == 40
        all_runs += baseline[split]
    old = [dict(r, case=s+"/"+r["case"]) for s in baseline for r in baseline[s]]
    baseline_dir = save("baseline80", old)
    results, protocols = {}, []
    raw = (ROOT / "results/v10_fix_input/large_huffman_protocol.in").read_bytes()
    expected = "".join(f"ANS {3000000 if t <= 20 else 0}\nEND\n" for t in range(1,401)).encode("ascii")
    for name in ["v13_model_fast", "v14_mlp_A", "v14_mlp_B"]:
        fresh, splits = [], {}
        version = load(f"versions/{name}/manifest.json")
        assert hashlib.sha256(Path(version["packed_source"]).read_bytes()).hexdigest() == version["packed_sha256"]
        assert hashlib.sha256(Path(version["executable"]).read_bytes()).hexdigest() == version["exe_sha256"]
        counts = dict(attempts=0, rejects=0, late=0, guard_returns=0)
        for split in ["holdout", "confirmation"]:
            directory = ROOT / f"results/v14_{split}_{name}"
            rows = load(str(directory / "summary.json"))
            assert len(rows) == 40 and {r["exe_sha256"] for r in rows} == {version["exe_sha256"]}
            all_runs += rows
            fresh += [dict(r, case=split+"/"+r["case"]) for r in rows]
            splits[split] = comparison(name+"_"+split, ROOT / f"results/v14_{split}_baseline", directory)["valid_range_summary"]
            if name.startswith("v14_"):
                logs = list(directory.rglob("solver_stderr.txt")); assert len(logs) == 40
                for file in logs:
                    match = re.search(r"V14_MLP_POLICY attempts=(\d+) rejects=(\d+) late=(\d+) guard_returns=(\d+)", file.read_text())
                    assert match
                    for key, value in zip(counts, match.groups()):
                        counts[key] += int(value)
        combined = comparison(name+"_fresh80", baseline_dir, save(name, fresh))
        assert combined["valid_range_summary"]["case_count"] == 80
        worst = min((r for r in combined["rows"] if r["profit_ratio"] is not None), key=lambda r: r["profit_ratio"])
        aux = load(f"results/v13_aux_{name}/summary.json")
        base_aux = load("results/v13_aux_v12_scan_input_fix/summary.json")
        for key, rows in [("baseline", base_aux), (name, aux)]:
            save("aux_"+key, [dict(r, case=Path(r["input"]).parent.name+"/"+r["case"]) for r in rows])
        auxiliary = comparison(name+"_aux6", OUT / "aux_baseline", OUT / ("aux_"+name))
        assert auxiliary["valid_range_summary"]["case_count"] == 4
        if name.startswith("v14_"):
            all_runs += aux
            test = subprocess.run([version["executable"]], input=raw, capture_output=True, cwd=ROOT, timeout=20)
            assert test.returncode == 0 and test.stdout.replace(b"\r\n", b"\n") == expected
            assert re.fullmatch(rb"V14_MLP_POLICY attempts=0 rejects=0 late=\d+ guard_returns=\d+\r?\n", test.stderr)
            protocols.append({"name": name, "all400_answers_exact": True,
                "method": "Separate direct full protocol replay;not a TPJ-generated world"})
            version["validation"] = {"main_runs": 86, "fresh80": combined["valid_range_summary"],
                "split_summary": splits, "worst": worst, "pressure4": auxiliary["valid_range_summary"],
                "audit_total": sum(r["audit_total"] for r in fresh+aux),
                "audit_errors": 0, "illegal_commands": 0, "large_protocol400_exact": True,
                "max_cpu_seconds": max(r["solver_cpu_seconds"] for r in fresh+aux),
                "max_peak_memory_bytes": max(r["solver_peak_memory_bytes"] for r in fresh+aux),
                "report": "research/v14_experiment.md", "model_gate_counts": counts}
            version["local_selection_status"] = "Experimental neural profit candidate;no official score established"
            dump(ROOT / f"versions/{name}/manifest.json", version)
        results[name] = {"splits": splits, "fresh80": combined["valid_range_summary"],
            "worst": worst, "health": combined["candidate_health"], "pressure4": auxiliary["valid_range_summary"],
            "model_gate_counts": counts if name.startswith("v14_") else None}
    for name in ["v14_mlp_A", "v14_mlp_B"]:
        value = comparison(name+"_vs_tree80", OUT / "v13_model_fast", OUT / name)
        results[name]["vs_tree80"] = value["valid_range_summary"]
    old160 = load("results/v13_report/baseline80/summary.json")
    tree160 = load("results/v13_report/v13_model_strict_fresh80/summary.json")
    old160 = [dict(r, case="v13/"+r["case"]) for r in old160]+[dict(r, case="v14/"+r["case"]) for r in old]
    tree160 = [dict(r, case="v13/"+r["case"]) for r in tree160]+[dict(r, case="v14/"+r["case"]) for r in load("results/v14_report/v13_model_fast/summary.json")]
    combined160 = comparison("tree_fresh160", save("baseline160", old160), save("tree160", tree160))
    assert len(all_runs) == 592 and all(r["ok"] and r["audit_errors"] == 0 and r["incidents"] == 0 for r in all_runs)
    health = {"runs": len(all_runs), "audits": sum(r["audit_total"] for r in all_runs),
        "audit_errors": 0, "illegal_commands": 0, "max_cpu_seconds": max(r["solver_cpu_seconds"] for r in all_runs),
        "max_peak_memory_bytes": max(r["solver_peak_memory_bytes"] for r in all_runs),
        "scope": "Train256+disabled4+fixed references160+frozen neural160+known pressure/sample12;protocol/numerical harness separate"}
    v13 = load("research/v13_experiment_manifest.json")
    manifest = {"date": "2026-11-16", "training": "research/v14_mlp_results.json",
        "selection": selection, "fit": fit, "comparisons": results, "health": health,
        "tree_fresh160": combined160["valid_range_summary"], "large_protocols": protocols,
        "combined_v13_v14_runs": v13["all_interactive_runs"]+health["runs"],
        "combined_v13_v14_audits": v13["all_interactive_audits"]+health["audits"],
        "independent_review": "research/v14_mlp_independent_review.md",
        "official_submission_sent": False, "defaults_unchanged": True,
        "interpretation": "Neural A improves aggregate vs99 on both fresh40 splits and pressure4,only+0.0881% vs tiny-tree80;no robust dominance or official AC established",
        "preferred_experimental_candidate": "versions/v14_mlp_A/submit.cpp",
        "tiny_tree_alternative": "versions/v13_model_fast/submit.cpp",
        "conservative_alternative": "versions/v12_scan_input_fix/submit.cpp"}
    dump(ROOT / "research/v14_experiment_manifest.json", manifest)
    lines = ["# V14：小神经网络可行性与利润实测", "", "2026-11-16。本轮未正式提交，默认仍为99分源码；新网络已完成训练、C++导出、真实闭环和新场景检验。", "",
        "## 结论", "", "小神经网络的训练和部署已经验证可行，也测到了小幅正收益。A在新80场景比99策略总利润+0.4945%，比同场景浅树仅+0.0881%，44升36降；它尚未形成对浅树的稳定支配。A最大规模既有压力4例合计+0.2838%，3升1降，但failures仍−3.69%；新80单例最差−22.19%，不能把平均利润增益理解为每点更好或AC保证。", "",
        "## 同一批全新80场景", "", "| 程序 | 新40 | 确认40 | 合计80 | 升/降/平 | 最差单例 | 既有压力4例 |", "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for name, label in [("v13_model_fast", "浅树15节点"), ("v14_mlp_A", "网络A 18→16→2"), ("v14_mlp_B", "网络B 18→16→8→2")]:
        v = results[name]; s = v["fresh80"]
        lines.append(f"| {label} | {v['splits']['holdout']['total_profit_increase_pct']:+.4f}% | {v['splits']['confirmation']['total_profit_increase_pct']:+.4f}% | {s['total_profit_increase_pct']:+.4f}% | {s['improved']}/{s['regressed']}/{s['unchanged']} | {100*(v['worst']['profit_ratio']-1):+.2f}% | {v['pressure4']['total_profit_increase_pct']:+.4f}% |")
    t = combined160["valid_range_summary"]
    lines += ["", "上述表内三种策略使用相同V14新80输入、同一修复/扫描基线。V13浅树+0.4813%来自另80例，不能和此表网络数字直接比较；同一浅树跨两轮160新例合计"+f"{t['total_profit_increase_pct']:+.4f}%（{t['improved']}升{t['regressed']}降），V14最差单例已到−18.90%，不能继续只引用V13的−6.06%。", "",
        "两个网络都在看V14任何利润前统一冻结：每架构仅从4个固定门控选训练总利润最高的正收益项。A选25%收入混合，B选strict；不是依据留出结果挑门槛。新80均通过现有可观测范围检查，所有用例保留。4压力和2短T原生样例属于已有健康/开发验证，不混进新80。", "",
        "## 模型与训练", "", "使用V13新32世界的41,151条实际入场流程、18个可见特征和原策略条件收益标签。A338参数、B458参数，ReLU隐层、2输出，等世界权重、4折完整世界分组；标准化只拟合训练折，输入规范化裁剪到[-8,8]。固定120epoch、Adam学习率.003/weight_decay1e-4、batch1024、各一个固定seed；10次fit合计约24秒，未挑epoch/早停/追加网络。", "",
        "初始计划关于clip-loss的歧义在任何fit/CV结果前已澄清并留下amendment：训练raw线性输出MSE，标签仍clip，报告与推理才clip输出。没有根据结果更换loss。", "",
        "| 等世界OOF MSE | 收益比例 | 净收益比例 |", "| --- | ---: | ---: |", "| 浅树 | 0.1266447 | 0.1135720 |"]
    for model in fit["architectures"]:
        m = model["grouped_oof"]
        lines.append(f"| 网络{model['name']} | {m['earned_fraction_mse']:.7f} | {m['net_fraction_mse']:.7f} |")
    lines += ["", "网络净收益误差比浅树约低4.6%～4.7%；按原低利润入场区域进一步诊断也有改善，但这不代表反事实动作价值。标签没有告诉模型被拒流程的真实机会成本；模型更准与资源调度更好仍需分别检验。", "",
        "## 全部8个训练门控", "", "| 配置 | 训练32总利润 | 升/降/平 |", "| --- | ---: | ---: |"]
    for row in training["candidates"]:
        s = row["valid_range"]
        lines.append(f"| {row['name']} | {s['total_profit_increase_pct']:+.4f}% | {s['improved']}/{s['regressed']}/{s['unchanged']} |")
    lines += ["", "8策略训练全部late/guard_returns=0，利润变化并非该保险触发；4disabled控制完整报告相同，每架构只有2个世界，局限保留。新验证神经网络的计数与CPU健康完整写入manifest。", "",
        "## C++与核验", "", "标准化、矩阵、偏置、ReLU和裁剪均导出C++双精度常量/循环，部署不需要PyTorch或外部权重文件。18个输入仍按原float32生成后转double。每网络1744个实际C++查询对NumPy最大误差<1.6e-15，对保存Torch样本<4e-16，测试中按比例特征重组的四门控公式判定相同；这不是直接调用raw forecast门控的边界证明。独立审计逐字核对8份集成源码仅替换预测器/诊断名，原raw forecast门槛、特征与预约回滚保留。浮点归约次序可带来ULP差异，不承诺所有实数边界逐位一致。", "",
        "独立复算两网络每折与最终标准化、train-only常数、世界等权及OOF指标均精确；全41,151条Torch final输出的独立NumPy重算最大误差<4.8e-16，C++所有均值/尺度/矩阵/偏置字面量与JSON完全相同。详见v14_mlp_independent_review.md与results/v14_mlp_independent_audit/audit.json。", "",
        "实际packed A29,016字节、B31,634字节，均小于64,000字节限制；各80新场景+4压力+2样例共86次真实运行，对账全对/指令合法。两份代码均再通过300万解码字符、600万hex字符完整协议400答案精确回放；直接协议不计TPJ世界。所有版本保留8MiB修复、直接整数扫描、99参数、CPU保险、预约回滚和20k原子护栏。", "",
        f"V14共{health['runs']}次实际交互、{health['audits']:,}次对账全对，零非法指令。连同V13细调/浅树/生产核验，总计{manifest['combined_v13_v14_runs']:,}次交互、{manifest['combined_v13_v14_audits']:,}次对账全对。本轮本机最大CPU{health['max_cpu_seconds']:.6f}s，计时作为健康记录，不能当正式时限或独立提速结论。", "",
        "## 保留文件", "", "最新利润实验候选versions/v14_mlp_A/submit.cpp；较多新场景参考versions/v13_model_fast/submit.cpp；保守输入/扫描修复versions/v12_scan_input_fix/submit.cpp。B网络保留在versions/v14_mlp_B/，无新训练或隐式推广。", "",
        "根目录main.cpp/submit.cpp及默认exe仍与正式99分544054哈希一致，没有新增正式提交。训练框架和C++部署可行度高；能否比浅树稳定多赚、能否通过官方最后一点，目前证据仍不足。", ""]
    (ROOT / "research/v14_experiment.md").write_text("\n".join(lines), encoding="utf8")
    release = load("results/final_manifest.json")
    for field in ["main.cpp", "submit.cpp", "build/main.exe", "build/submit.exe"]:
        assert hashlib.sha256((ROOT / field).read_bytes()).hexdigest() == release["artifacts"][field]["sha256"]
    candidate = load("versions/v14_mlp_A/manifest.json")
    local = release["local_research"]
    if "model_policy_fresh80" in local:
        local["tiny_tree_v13_fresh80"] = local.pop("model_policy_fresh80")
    if "model_policy_worst" in local:
        local["tiny_tree_v13_worst"] = local.pop("model_policy_worst")
    local.update(preferred_unsubmitted_candidate="versions/v14_mlp_A/submit.cpp", packed_sha256=candidate["packed_sha256"],
        scope="Experimental338-parameter neural revenue25% admission gate,99 parameters with8MiB repair/direct scanner",
        tiny_tree_alternative="versions/v13_model_fast/submit.cpp", conservative_unsubmitted_candidate="versions/v12_scan_input_fix/submit.cpp",
        neural_policy_fresh80=results["v14_mlp_A"]["fresh80"], neural_policy_worst=results["v14_mlp_A"]["worst"],
        neural_vs_tree80=results["v14_mlp_A"]["vs_tree80"], official_score_of_local_candidate=None,
        new_submissions_sent=0, submission_decision="Local research only;user deferred submissions")
    for report in ["research/v14_experiment.md", "research/v14_mlp_experiment.md", "research/v14_mlp_independent_review.md"]:
        if report not in local["reports"]:
            local["reports"].append(report)
    dump(ROOT / "results/final_manifest.json", release)
    update = "2026-11-16本地V14：实际训练两种338/458参数小神经网络，固定10次拟合约24秒、8门控×32训练，统一冻结后在另80新场景与浅树同场比较。A总利润+0.4945%，B+0.2671%，同场浅树+0.4061%；A只比浅树多约0.0881%，最差单例−22.19%，未建立稳定支配或正式AC。A另4既有压力合计+0.2838%但failures−3.69%。最新实验候选 `versions/v14_mlp_A/submit.cpp`，浅树和输入修复版均保留；默认仍为正式99分，没有提交。详见 `research/v14_experiment.md`。"
    marker = "<!-- v14 neural research -->"
    for file in ["README.md", "REPORT.md"]:
        path = ROOT / file; text = path.read_text(encoding="utf8")
        if marker not in text:
            needle = "## 当前实现" if file == "README.md" else "# 验证记录\n"
            replacement = marker+"\n"+update+"\n\n"+needle if file == "README.md" else needle+"\n"+marker+"\n"+update+"\n"
            text = text.replace(needle, replacement, 1); path.write_text(text, encoding="utf8")
    print(json.dumps({"health": health, "total_runs": manifest["combined_v13_v14_runs"],
        "total_audits": manifest["combined_v13_v14_audits"], "preferred_experimental": "v14_mlp_A",
        "tree160_pct": t["total_profit_increase_pct"], "official_submission_sent": False}))


if __name__ == "__main__":
    main()
