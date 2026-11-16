"""Summarize coarse routing, real rollout, and frozen input/performance control."""
from pathlib import Path
import hashlib
import json
import subprocess
from compare import compare, markdown

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "results/v12_report"


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
    combined = {}
    comparisons = {}
    versions = {}
    for name in ["v12_pen0875_scan", "v12_scan_input_fix"]:
        old, new = [], []
        all_rows = []
        equality = []
        for split in ["holdout", "confirmation"]:
            baseline = load(f"results/v12_{split}_baseline/summary.json")
            candidate = load(f"results/v12_{split}_{name}/summary.json")
            all_rows += candidate
            indexed = {r["case"]: r for r in baseline}
            equality += [{"case": f"{split}/"+r["case"], "full_report_equal": r["report"] == indexed[r["case"]]["report"]}
                         for r in candidate]
            comparisons[name+"_"+split] = record(name+"_"+split,
                ROOT / f"results/v12_{split}_baseline", ROOT / f"results/v12_{split}_{name}")
            old += [dict(r, case=f"{split}/"+r["case"]) for r in baseline]
            new += [dict(r, case=f"{split}/"+r["case"]) for r in candidate]
        combined[name] = record(name+"_fresh80", save("baseline80", old), save(name+"_fresh80", new))
        assert combined[name]["valid_range_summary"]["case_count"] == 80
        if name == "v12_pen0875_scan":
            all_rows += load("results/v12_pen0875_scan_production/summary.json")
        assert all(r["ok"] for r in all_rows)
        path = ROOT / f"versions/{name}/manifest.json"
        version = json.loads(path.read_text(encoding="utf8"))
        assert {r["exe_sha256"] for r in all_rows} == {version["exe_sha256"]}
        assert hashlib.sha256(Path(version["packed_source"]).read_bytes()).hexdigest() == version["packed_sha256"]
        version["validation"] = {"main_runs": len(all_rows), "audit_total": sum(r["audit_total"] for r in all_rows),
            "audit_errors": sum(r["audit_errors"] for r in all_rows), "illegal_commands": sum(r["incidents"] for r in all_rows),
            "max_cpu_seconds": max(r["solver_cpu_seconds"] for r in all_rows),
            "max_peak_memory_bytes": max(r["solver_peak_memory_bytes"] for r in all_rows),
            "fresh80_profit_increase_pct": combined[name]["valid_range_summary"]["total_profit_increase_pct"],
            "fresh80_full_reports_equal": sum(r["full_report_equal"] for r in equality),
            "scope": "PEN candidate100runs includes2 old train boundary worlds;control80all pass available bounds",
            "report": "research/v12_experiment.md"}
        if name == "v12_scan_input_fix":
            assert all(r["full_report_equal"] for r in equality)
            version["local_selection_status"] = "Preferred conservative combined input repair and measured scanner optimization;99 scheduling parameters retained"
        else:
            version["local_selection_status"] = "Not preferred: fresh80 aggregate regression;retain as a fully recorded failed parameter trial"
        dump(path, version)
        dump(OUT / (name+"_full_report_equality.json"), equality)
        versions[name] = version

    raw = (ROOT / "results/v10_fix_input/large_huffman_protocol.in").read_bytes()
    expected = "".join(f"ANS {3000000 if t<=20 else 0}\nEND\n" for t in range(1,401)).encode("ascii")
    # Actual packed files retain the large-token repair after final packaging.
    protocols = []
    for name, version in versions.items():
        tested = subprocess.run([version["executable"]], input=raw, capture_output=True, timeout=20, cwd=ROOT)
        assert tested.returncode == 0 and not tested.stderr
        assert tested.stdout.replace(b"\r\n", b"\n") == expected
        protocols.append({"version": name, "answers_exact": 400, "encoded_hex_characters": 6000000,
                          "decoded_characters": 3000000, "method": "Direct complete protocol replay,separate from TPJ worlds"})
    dump(OUT / "packed_large_protocols.json", protocols)
    release = load("results/final_manifest.json")
    assert release["official_score"] == 99 and release["remaining_submissions"] == 4
    for name in ["main.cpp", "submit.cpp"]:
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == release["artifacts"][name]["sha256"]
    routing = load("research/v12_routing_results.json")
    rollout = load("research/v12_order_results.json")
    development = [load(f"results/v12_development/{name}/manifest.json") for name in ["pen_0875", "pen_0"]]
    manifest = {"date": "2026-11-16", "official_best": 99, "last_verified_submissions_used": 6,
        "last_verified_remaining": 4, "submission_decision": "User deferred submissions;no new code POST",
        "versions": versions, "comparisons": {k: v["valid_range_summary"] for k, v in comparisons.items()},
        "fresh80": {k: v["valid_range_summary"] for k, v in combined.items()},
        "routing_trials": routing, "development": development,
        "rollout": "research/v12_order_results.json", "rollout_tests": "results/v12_order_tests/summary.json",
        "independent_rollout_review": "research/v12_order_independent_review.md",
        "scanner_paired_performance": "research/v11_scan_results.json", "large_input_protocols": protocols,
        "selection": "PEN.875 selected using old development80 before V12results;control source existed unchanged before all V12results,packed afterward as ablation without fitting;rollout rejected on train",
        "conclusion": "No stable profit improvement from the heavier schemes tested. Retain99policy with8MiB input fix and output-equivalent direct scanner;PEN.75 older candidate had only tiny mixed fresh gain."}
    dump(ROOT / "research/v12_experiment_manifest.json", manifest)
    lines = ["# V12：更大参数跨度和真实双顺序搜索", "", "2026-11-16。正式最高99分、最后核验已用6次剩4次；用户要求暂不提交，本轮没有网页提交。缓冲区修复持续保留，正式默认源码不改。", "",
             "## 当前建议", "", "当前最稳妥的组合保留正式99分的所有调度参数，仅合入8MiB输入缓冲区修复和直接整数读取。实际packed程序在80个新场景中，与99策略加缓冲区修复的基线完整judge报告80/80完全一致，保持利润/费用/完成数/对账/指令结果。",
             "直接整数读取此前在隔离压力配对累计CPU小幅减少2.50%；计量粒度15.625ms，不承诺其它机器精确同幅提速。超长Huffman编码完整协议由本次实际packed程序再次验证，400条ALARM精确。该协议不是TPJ生成世界，与80个场景分别计数。", "",
             "## V12新场景对比", "", "| 程序 | 新40例总利润 | 确认40例总利润 | 合计80例 | 升/降/平 |", "| --- | ---: | ---: | ---: | ---: |"]
    for name, label in [("v12_pen0875_scan", "PEN.875+扫描+输入修复"), ("v12_scan_input_fix", "原99参数+扫描+输入修复")]:
        a = comparisons[name+"_holdout"]["valid_range_summary"]
        b = comparisons[name+"_confirmation"]["valid_range_summary"]
        v = combined[name]["valid_range_summary"]
        lines.append(f"| {label} | {a['total_profit_increase_pct']:+.4f}% | {b['total_profit_increase_pct']:+.4f}% | {v['total_profit_increase_pct']:+.4f}% | {v['improved']}/{v['regressed']}/{v['unchanged']} |")
    lines += ["", "PEN.875虽然旧开发80总利润+0.277%，新数据未维持；不因旧集较好就继续推荐。原99参数控制源在V12开始前已经固定并通过训练/压力等价，之后打包作归因控制，没有依据新数据拟合它的参数。", "",
              "前一V11轻量PEN.75候选在另80个新场景只有+0.0728%（43升36降1平），最差−5.91%。两参数使用不同新种子，不能把百分比直接当同数据头对头排名；PEN.75也仅保留弱证据备选。", "",
              "## 12组路由与前瞻粗扫", "", "| 配置 | 修改 | 14例训练总利润 | 升/降/平 |", "| --- | --- | ---: | ---: |"]
    for r in routing:
        v = r["valid_range"]
        lines.append(f"| {r['name']} | {r['parameters']} | {v['total_profit_increase_pct']:+.4f}% | {v['improved']}/{v['regressed']}/{v['unchanged']} |")
    lines += ["", "12组×16例共192次、335,436次对账全对、零非法；范围内14例均为总利润负收益。原训练两个large日志量超保守范围，完整保留、另列。LAK=0全部14例下降，说明当前一层前瞻有用；简单扩大或取消它都没有稳定提升。", "",
              "PEN.875与PEN0额外各在旧开发80例复核：前者+0.2773%/39升39降2平、最差−10.30%；后者−0.4937%/33升47降。开发结果用于选择，并未称作新验证。", "",
              "## 真正调用原调度的两顺序尝试", "", "新结构仅针对恰两个ready且规模/配额/机器/预约条件允许的流程，在私有事务中分别调用原tryPlace(A/B)与(B/A)，完整回滚后只执行选中的顺序。触及机器/机架使用局部journal，避免复制全局60000作业；原命令预算和时间保险保留，额外搜索有CPU gate。",
              "实际搜索13,872对、换序1,288次，确实触发；可构造实例启动费170降为110。但训练范围内14例总利润−0.4596%，4升10降、最差−3.53%，因此未进入新场景或最终候选。",
              "4,270项事务测试包含200组随机多机器/缓存/预算fixture的400次正逆回滚；漏掉IV失效或feeAvg恢复的两个负对照均准确失败。另有独立只读源码审查，未见公共状态回滚遗漏或假设命令泄漏。内存容量、缓存重算和消耗的CPU不能回滚，会影响执行时间；局部两任务优化也无法穷尽其它流程的未来收益。", "",
              "## 交付", ""]
    for name, version in versions.items():
        h = version["validation"]
        lines.append(f"- {name}: {version['packed_bytes']:,}字节，SHA256 `{version['packed_sha256']}`。实际packed程序{h['main_runs']}次主运行，{h['audit_total']:,}次对账全对、零非法；最高本机CPU{h['max_cpu_seconds']:.6f}s。")
    lines += ["", "PEN候选100次含训练2个旧日志边界；控制候选80例均通过现有可观测范围检查。缺失的数值字段上界不作穷举证明，不把本机耗时等同正式时限。生产源token核对、编译无警告；文件头继承99分已有内容，没有新增注释。",
              "推荐作为未来合并基础的是versions/v12_scan_input_fix/submit.cpp；弱调参备选保留在versions/v11_pen_scan/，失败的PEN.875另存versions/v12_pen0875_scan/。根目录main.cpp/submit.cpp和默认程序仍对应正式99分544054，剩余机会本轮未用。", "",
              "完整记录：v12_experiment_manifest.json、v12_routing_review.md、v12_order_review.md、v12_order_independent_review.md、results/v12_report/。", ""]
    (ROOT / "research/v12_experiment.md").write_text("\n".join(lines), encoding="utf8")
    print(json.dumps({"fresh80": {k: {j: v["valid_range_summary"][j] for j in ["case_count", "total_profit_increase_pct", "improved", "regressed", "unchanged"]} for k, v in combined.items()},
                      "preferred": "v12_scan_input_fix", "official_submission_sent": False}))


if __name__ == "__main__":
    main()
