"""Collect V11 higher-effort trials and unchanged-candidate fresh results."""
from pathlib import Path
import hashlib
import json
from compare import compare, markdown

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "results/v11_report"


def load(path):
    return json.loads((ROOT / path).read_text(encoding="utf8"))


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf8")


def save(name, rows):
    directory = OUT / name
    dump(directory / "summary.json", rows)
    return directory


def record(name, old, new):
    value = compare(old, new)
    dump(OUT / f"{name}.json", value)
    (OUT / f"{name}.md").write_text(markdown(value), encoding="utf8")
    return value


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    all_old, all_new = [], []
    comparisons = {}
    for split in ["holdout", "confirmation"]:
        for target, path in [(all_old, f"results/v11_{split}_baseline/summary.json"),
                             (all_new, f"results/v11_{split}_v11_pen_scan/summary.json")]:
            target += [dict(r, case=f"{split}/"+r["case"]) for r in load(path)]
        comparisons[split] = record(split,
            ROOT / f"results/v11_{split}_baseline", ROOT / f"results/v11_{split}_v11_pen_scan")
    comparisons["fresh80"] = record("fresh80", save("baseline80", all_old), save("candidate80", all_new))
    comparisons["warm_holdout"] = record("warm_holdout", ROOT / "results/v11_holdout_baseline",
                                          ROOT / "results/v11_holdout_v11_warm_pen_scan")
    baseline = load("results/v10_input_fix_production/summary.json")
    for name in ["v11_pen_scan", "v11_warm_pen_scan"]:
        rows = load(f"results/{name}_production/summary.json")
        for group in ["train", "stress"]:
            comparisons[name+"_"+group] = record(name+"_"+group,
                save("baseline_"+group, [r for r in baseline if Path(r["input"]).parent.name == group]),
                save(name+"_"+group, [r for r in rows if Path(r["input"]).parent.name == group]))
    versions = {}
    for name, splits in [("v11_pen_scan", ["holdout", "confirmation"]), ("v11_warm_pen_scan", ["holdout"])]:
        path = ROOT / f"versions/{name}/manifest.json"
        version = json.loads(path.read_text(encoding="utf8"))
        rows = load(f"results/{name}_production/summary.json")
        for split in splits:
            rows += load(f"results/v11_{split}_{name}/summary.json")
        assert all(r["ok"] for r in rows)
        assert {r["exe_sha256"] for r in rows} == {version["exe_sha256"]}
        assert hashlib.sha256(Path(version["packed_source"]).read_bytes()).hexdigest() == version["packed_sha256"]
        validation = {"main_runs": len(rows), "audit_total": sum(r["audit_total"] for r in rows),
                      "audit_errors": sum(r["audit_errors"] for r in rows), "illegal_commands": sum(r["incidents"] for r in rows),
                      "max_cpu_seconds": max(r["solver_cpu_seconds"] for r in rows),
                      "max_peak_memory_bytes": max(r["solver_peak_memory_bytes"] for r in rows),
                      "scope": "Production train16 includes2 old boundary worlds;stress4 and fresh worlds checked separately",
                      "fresh_comparison": "results/v11_report/fresh80.json" if name == "v11_pen_scan" else "results/v11_report/warm_holdout.json"}
        version["validation"] = validation
        version["local_selection_status"] = "Weak small-gain candidate; official score unknown" if name == "v11_pen_scan" else "Not preferred: heavier and fresh40 profit regression"
        dump(path, version)
        versions[name] = version
    release = load("results/final_manifest.json")
    assert release["official_score"] == 99
    for name in ["main.cpp", "submit.cpp"]:
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == release["artifacts"][name]["sha256"]
    trial_sources = {
        "parameters": "results/v11_parameters/summary.json",
        "search": "research/v11_search_results.json",
        "pull": "research/v11_pull_results.json",
        "combinations": "research/v11_combinations_results.json",
        "frontier": "research/v11_frontier_results.json",
        "performance": "research/v11_perf_results.json",
        "scanner": "research/v11_scan_results.json",
    }
    development = [load(f"results/v11_development/{name}/manifest.json")
                   for name in ["warm_rank", "queue_025", "warm_pen075", "warm_resv15"]]
    manifest = {"date": "2026-11-16", "official_best": 99, "last_verified_remaining": 4,
                "versions": versions, "comparisons": {k: v["valid_range_summary"] for k, v in comparisons.items()},
                "trial_sources": trial_sources, "development": development,
                "new_submission_sent": False, "buffer_fix_retained": True,
                "selection": "16 parameter policies,3 rack searches,2 exact pull,4 interactions,2 frontier forecasts; oldV8development then2 frozen finalists. Fresh40 selected lighter source for unchanged confirmation40. No fresh fitting.",
                "conclusion": "Heavier variants tested did not improve fresh profit;direct scanner yielded small paired CPU gain. PEN.75 package fresh80 aggregate gain is small and mixed, not a demonstrated AC improvement."}
    dump(ROOT / "research/v11_experiment_manifest.json", manifest)
    fresh = comparisons["fresh80"]["valid_range_summary"]
    worst = min((r for r in comparisons["fresh80"]["rows"] if r["profit_ratio"] is not None), key=lambda r: r["profit_ratio"])
    lines = ["# V11：用更多计算换收益的实测", "", "2026-11-15至16。正式99分不变，最后核验还剩4次；本轮无正式提交。所有新候选保留8MiB缓冲区修复，没有新增提交头注释。", "",
             "## 结果", "", "加大搜索、精确模拟和更频繁重估没有自动提高全局利润。当前较轻的PEN.75+直接整数扫描候选在80个新场景上只有很小净增益，存在退步，不把它称为已找到AC。", "",
             "| 集合/程序 | 例数 | 相对99策略总利润 | 升/降/平 |", "| --- | ---: | ---: | ---: |"]
    for label, key in [("轻量候选新场景", "holdout"), ("轻量候选独立确认", "confirmation"),
                       ("轻量候选新场景合计", "fresh80"), ("较贵暖预筛候选新场景", "warm_holdout")]:
        v = comparisons[key]["valid_range_summary"]
        lines.append(f"| {label} | {v['case_count']} | {v['total_profit_increase_pct']:+.4f}% | {v['improved']}/{v['regressed']}/{v['unchanged']} |")
    lines += ["", f"轻量候选80例总利润 {fresh['baseline_total_profit']:,}→{fresh['candidate_total_profit']:,}，最差{worst['case']}下降{100*(1-worst['profit_ratio']):.2f}%。",
              "基线非正的场景不计算利润比，仍计入总利润和升降。V8的旧80例在本轮只算开发数据；V11新40种子在筛选之前生成，确认40种子在读取新结果之前生成，确认期间未改候选。", "",
              "## 更贵的计算做了什么", "", "| 方向 | 范围内14训练总利润 | 观察 |", "| --- | ---: | --- |",
              "| 全30机架搜索 | −0.884% | 扩大候选并未带来更高全局收益 |",
              "| 全30架+16后继×12输入前瞻 | −0.318% | 计算更细仍不稳定 |",
              "| 机器缓存感知的机架预筛 | +0.276% | 旧开发80变为−0.101%，未独立采用 |",
              "| 精确LRU费用/准备时间 | −0.971% | 范围内无时间保险混杂 |",
              "| 只精确费用 | −1.356% | 同样退步 |",
              "| 就绪前沿按可行机器重估费用 | −0.881% | 所有16例late/保险返回均0 |",
              "| 同时重估工期/费用 | −1.006% | 所有16例late/保险返回均0 |", "",
              "前沿估价是单作业独立报价，并不是整批同时可行的联合排程；更准确的局部现金估价也不保证整局收益更高。实现审计补正WK非零时旧成本扣除的问题，实际WK0源行为不变；两候选和WK0.5控制共8088项检查通过，负对照准确失败。",
              "搜索分支的large01曾出现TS0与TS1不同（该例是日志边界压力），说明总CPU小于1秒也不能证明阶段保险从未改变轨迹。真实生产策略表现按保留保险的源评价，不能把该例波动一概当纯策略改进。", "",
              "## 卡常", "", "| 修改 | 隔离或交错压力累计CPU变化 | 决定 |", "| --- | ---: | --- |",
              "| 成员报价memo | +7.21% | 不采用 |", "| 通用O3 pragma | +5.29% | 不采用 |",
              "| 直接整数读取 | −2.50% | 可合并的小优化 |", "",
              "直接扫描去掉数字写入tok再atoll的步骤，负向累积支持LL_MIN。11组原语、跨64KiB边界、混合文本、600万hex日志均通过。16个训练完整报告、24次压力配对完整报告与基线相同。计时粒度15.625ms，不能保证跨机器也精确快2.5%。", "",
              "## 其它有限调参", "", "16种重估频率/预约/紧迫度/排队配置，4组预先固定交互全部保留结果；没有额外按新鲜测试结果重选参数。详见各trial_sources清单。前轮PEN.75开发80增益0.212%是轻量候选的选择理由，新80只有更小增益，因此证据较弱。", "",
              "## 交付及状态", ""]
    for name, version in versions.items():
        h = version["validation"]
        lines.append(f"- {name}: {version['packed_bytes']:,}字节，SHA256 `{version['packed_sha256']}`；同一packed程序{h['main_runs']}次主验证、{h['audit_total']:,}次对账全对、0非法，最高本机CPU{h['max_cpu_seconds']:.6f}s。")
    lines += ["", "轻量候选100次主验证中含训练2个旧日志边界；重候选60次同样含2个边界。其它场景通过现有可观测范围检查，不声称未给字段已穷尽验证。源token逐项校验、生产编译无警告。",
              "主候选仍在versions/v11_pen_scan/，比较候选在versions/v11_warm_pen_scan/。正式main.cpp、submit.cpp和默认程序仍精确对应99分544054。用户要求暂不提交，本轮没有新提交授权或代码POST。", "",
              "后续继续做独立V12探索时，上述V11新数据将明确改列开发数据，不能再标成新候选的独立验证。", ""]
    (ROOT / "research/v11_experiment.md").write_text("\n".join(lines), encoding="utf8")
    print(json.dumps({"fresh80": {k: fresh[k] for k in ["case_count", "total_profit_increase_pct", "improved", "regressed", "unchanged", "median_profit_ratio"]},
                      "max_cpu": versions["v11_pen_scan"]["validation"]["max_cpu_seconds"], "official_submission_sent": False}))


if __name__ == "__main__":
    main()
