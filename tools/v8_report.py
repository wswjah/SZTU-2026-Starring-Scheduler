"""Collect V8 train selection and unchanged-finalist confirmation evidence."""
from pathlib import Path
import hashlib
import json
import re
from compare import compare, markdown

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "results/v8_report"
OUT.mkdir(parents=True, exist_ok=True)


def load(path):
    return json.loads((ROOT / path / "summary.json").read_text(encoding="utf8"))


def dump(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf8")


def save(name, rows):
    directory = OUT / name
    dump(directory / "summary.json", rows)
    return directory


def record(name, baseline, candidate):
    value = compare(baseline, candidate)
    dump(OUT / f"{name}.json", value)
    (OUT / f"{name}.md").write_text(markdown(value), encoding="utf8")
    return value


def main():
    production = load("results/v8_fine_production")
    train = save("production_train", [r for r in production if Path(r["input"]).parent.name == "train"])
    stress = save("production_stress", [r for r in production if Path(r["input"]).parent.name == "stress"])
    old = load("results/v7_final_main")
    old_stress = save("v7_stress", [r for r in old if Path(r["input"]).parent.name == "stress"])
    old96 = load("results/v7_stress_samples_baseline")
    old96_stress = save("96_stress", [r for r in old96 if Path(r["input"]).parent.name == "stress"])
    reports = {
        "train_vs_v7": record("train_vs_v7", ROOT / "results/v8_baseline_train", train),
        "train_vs_96": record("train_vs_96", ROOT / "results/v7_cpu_screen/baseline", train),
        "stress_vs_v7": record("stress_vs_v7", old_stress, stress),
        "stress_vs_96": record("stress_vs_96", old96_stress, stress),
    }
    combined = {"v7": [], "96": [], "fine": []}
    for split in ["holdout", "confirmation"]:
        for baseline in ["v7", "96"]:
            reports[f"{split}_vs_{baseline}"] = record(f"{split}_vs_{baseline}",
                ROOT / f"results/v8_{split}_{baseline}", ROOT / f"results/v8_{split}_fine")
        for version in combined:
            combined[version] += [dict(r, case=f"{split}/" + r["case"])
                                  for r in load(f"results/v8_{split}_{version}")]
    destinations = {k: save("fresh_" + k, rows) for k, rows in combined.items()}
    for baseline in ["v7", "96"]:
        reports[f"fresh_vs_{baseline}"] = record(f"fresh_vs_{baseline}", destinations[baseline], destinations["fine"])
    version_path = ROOT / "versions/v8_fine/manifest.json"
    version = json.loads(version_path.read_text(encoding="utf8"))
    assert hashlib.sha256(Path(version["packed_source"]).read_bytes()).hexdigest() == version["packed_sha256"]
    all_runs = production + load("results/v8_holdout_fine") + load("results/v8_confirmation_fine")
    assert len(all_runs) == 100 and all(r["ok"] for r in all_runs)
    assert {r["exe_sha256"] for r in all_runs} == {version["exe_sha256"]}
    for base in ["v7", "96"]:
        assert reports[f"fresh_vs_{base}"]["valid_range_summary"]["case_count"] == 80
    parent_source = (ROOT / "versions/v7_tuned/main.cpp").read_text(encoding="utf8")
    child_source = Path(version["source"]).read_text(encoding="utf8")
    normalize = lambda s: re.sub(r"PRM\((TH0|SL),\s*[^)]+\)", r"PRM(\1, X)", s)
    assert normalize(parent_source) == normalize(child_source), "Fine candidate must change just two constants"
    unchanged = {"main.cpp": "65be27cdc374c30c8434b335c3895ebf661eca1a0d8e1394523237124df56fab",
                 "submit.cpp": "ec22e8889720e58ff2c05bbf8177778d53510e8ecff4236fac755f8ecaf6d703",
                 "versions/v7_tuned/submit.cpp": "42660750b67aa0d38641c13f22b36132d32adfc763634fe1b9441c133d7bad14"}
    assert all(hashlib.sha256((ROOT / p).read_bytes()).hexdigest() == h for p, h in unchanged.items())
    validation = {
        "primary_runs": len(all_runs), "audit_total": sum(r["audit_total"] for r in all_runs),
        "audit_errors": sum(r["audit_errors"] for r in all_runs),
        "illegal_commands": sum(r["incidents"] for r in all_runs),
        "max_cpu_seconds": max(r["solver_cpu_seconds"] for r in all_runs),
        "fresh_valid_cases": 80,
        "fresh_vs_v7": reports["fresh_vs_v7"]["valid_range_summary"],
        "fresh_vs_96": reports["fresh_vs_96"]["valid_range_summary"],
        "result_manifest": "research/v8_experiment_manifest.json",
    }
    version["validation"] = validation
    dump(version_path, version)
    screen = load("results/v8_fine")
    combinations = [json.loads((ROOT / f"results/v8_combinations/{name}/manifest.json").read_text(encoding="utf8"))
                    for name in ["conservative_pair", "priority_pair"]]
    structural = []
    for name, path in [
        ("quota", "research/v8_structure_quota_comparison.json"),
        ("contention", "research/v8_structure_contention_comparison.json"),
        ("path_noise", "results/v8_duration/path_noise/comparison.json"),
        ("refresh_running", "results/v8_duration/refresh_running/comparison.json"),
        ("donor", "research/v8_donor_comparison.json"),
    ]:
        value = json.loads((ROOT / path).read_text(encoding="utf8"))
        structural.append({"name": name, "result": path, "valid_range": value["valid_range_summary"]})
    manifest = {"candidate": version, "fine_screen": screen, "combinations": combinations,
                "structures": structural, "comparisons": {k: v["valid_range_summary"] for k, v in reports.items()},
                "default96_and_v7_unchanged": unchanged,
                "scope": "100 production-executable runs: train16, stress4, fresh80; train has2 boundary logs. Available range checks pass for all80 fresh worlds, unobserved limits not certified.",
                "selection": "17 fixed single axes,2 train-only combinations. Only priority_pair frozen and evaluated on holdout. Confirmation used no code or parameter changes. Structural candidates not added.",
                "official_best": 96, "last_verified_submissions_used": 5, "last_verified_remaining": 5,
                "official_submission_sent": False, "official_submission_authorized": False}
    dump(ROOT / "research/v8_experiment_manifest.json", manifest)
    pct = lambda v: f"{v['total_profit_increase_pct']:+.3f}%"
    lines = ["# V8：更细的参数邻域与五项结构试验", "", "2026-11-15。正式最高96分；本轮仅本地试验，没有消耗提交。", "",
             "在V7上预定17个单轴邻域、最多2个组合，只用train16选择。V7原有验证结果没有被用作新鲜V8证据。",
             "40个新种子/分布变化场景在候选选择前生成；最终参数冻结后测这40例，再以另一组40例作独立确认，期间未改代码或参数。", "",
             "## 当前候选", "", "V7之上仅TH0 5→4、SL 1→1.25，其余常量和逻辑完全一致。前者降低放置估价中的等待时间基础惩罚，后者更降低宽松截止流程的优先级。",
             "效果依赖闭环调度，组合增幅不能把两项单轴增幅相加。", "",
             "| 集合 | 例数 | 相对V7总利润 | 升/降 | 相对正式96策略总利润 |", "| --- | ---: | ---: | ---: | ---: |"]
    for split, title in [("train", "训练范围内"), ("stress", "压力"), ("holdout", "新场景"), ("confirmation", "独立确认"), ("fresh", "新场景合计")]:
        a, b = reports[f"{split}_vs_v7"]["valid_range_summary"], reports[f"{split}_vs_96"]["valid_range_summary"]
        lines.append(f"| {title} | {a['case_count']} | {pct(a)} | {a['improved']}/{a['regressed']} | {pct(b)} |")
    fresh = reports["fresh_vs_v7"]
    positive_rows = [r for r in fresh["rows"] if r["profit_ratio"] is not None]
    worst = min(positive_rows, key=lambda r: r["profit_ratio"])
    against96 = min((r for r in reports["fresh_vs_96"]["rows"] if r["profit_ratio"] is not None), key=lambda r: r["profit_ratio"])
    lines += ["", f"80例相对V7最差为{worst['case']}，{worst['baseline_profit']:,}→{worst['candidate_profit']:,}（{100*(worst['profit_ratio']-1):.2f}%）；相对96最差为{against96['case']}（{100*(against96['profit_ratio']-1):.2f}%）。",
              "基线利润非正不计算比值，仍计入绝对利润与升降计数。本地总利润与正式通过点数不同，不能把利润百分比换算成加分。", "",
              "## 所有细调结果（相对V7）", "", "| 配置 | 修改 | 14例总利润 | 等权平均 | 升/降 | 最差变化 |", "| --- | --- | ---: | ---: | ---: | ---: |"]
    for r in screen + combinations:
        v = r["valid_range"]
        ratios = [x["profit_ratio"] for x in json.loads((Path(r["result_dir"]) / "comparison.json").read_text(encoding="utf8"))["rows"] if not x["baseline_range_violations"] and x["profit_ratio"] is not None]
        lines.append(f"| {r['name']} | {r['parameters']} | {pct(v)} | {v['equal_weight_increase_pct']:+.3f}% | {v['improved']}/{v['regressed']} | {100*(min(ratios)-1):.2f}% |")
    lines += ["", "## 结构方向的完整结果", "", "| 方向 | 14例总利润 | 升/降/平 | 结论 |", "| --- | ---: | ---: | --- |"]
    reasons = {"quota": "只改变1例，证据薄弱", "contention": "退步", "path_noise": "等权平均略降，最差退步10.86%", "refresh_running": "退步", "donor": "直接省传输费但总利润退步"}
    for r in structural:
        v = r["valid_range"]
        lines.append(f"| {r['name']} | {pct(v)} | {v['improved']}/{v['regressed']}/{v['unchanged']} | {reasons[r['name']]} |")
    lines += ["", "配额核时下界、并行时长波动、运行中结束预测刷新、替身预热均保留源码和失败数据，没有拼到最终版。替身预热16例共261次使用、直接传输费省16,339，仍不敌调度轨迹变化；合法性/预算/不同租户账本/状态恢复定向测试通过。", "",
              "## 验证与交付", "", f"最终同一packed编译程序100次运行，{validation['audit_total']:,}次对账全对，0非法指令，最大本机CPU {validation['max_cpu_seconds']:.6f}s。",
              "包含train16中的2个日志边界世界；80个新场景全部通过现有可观测范围检查，不将缺失字段说成已核验。源文件逐token验证、生产编译无警告，未增加模型或运行依赖。",
              f"候选 `versions/v8_fine/submit.cpp`，{version['packed_bytes']:,}字节，SHA256 `{version['packed_sha256']}`。",
              "根目录main.cpp/submit.cpp仍是正式96分文件，V7冻结文件也未改。V8没有新提交授权；最后核验已用5次、剩5次。", "",
              "## 下一项值得研究的想法", "", "当前96/V7/V8都精确维护告警供对账，但选机没有使用告警预测故障。下一项可先做旁路诊断：用过去可见的日志/告警统计校准短期故障风险，再把预计重算费用加到选机成本。不能直接把高告警当即将故障，也不能用未来FAIL作实时输入；必须按完整世界分组训练和新种子闭环验证。该方向本轮尚未实现，不能声称提分。", ""]
    (ROOT / "research/v8_experiment.md").write_text("\n".join(lines), encoding="utf8")
    print(json.dumps({"validation": {k: v for k, v in validation.items() if not k.startswith("fresh_vs")},
                      "fresh_vs_v7": reports["fresh_vs_v7"]["valid_range_summary"],
                      "fresh_vs_96": reports["fresh_vs_96"]["valid_range_summary"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
