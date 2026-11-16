"""Consolidate the three train-only expensive placement-search experiments."""
from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parent.parent
records = json.loads((ROOT / "research/v11_search_results.json").read_text(encoding="utf8"))
controls = json.loads((ROOT / "results/v11_search/controls/summary.json").read_text(encoding="utf8"))
primary = []
for record in records:
    primary += json.loads((Path(record["result_dir"]) / "summary.json").read_text(encoding="utf8"))
    assert hashlib.sha256(Path(record["source"]).read_bytes()).hexdigest() == record["source_sha256"]
    assert hashlib.sha256(Path(record["executable"]).read_bytes()).hexdigest() == record["exe_sha256"]
assert len(primary) == 48 and all(row["ok"] for row in primary)
manifest = {"primary_runs": len(primary), "audit_total": sum(row["audit_total"] for row in primary),
            "audit_errors": sum(row["audit_errors"] for row in primary),
            "illegal_commands": sum(row["incidents"] for row in primary),
            "max_cpu_seconds": max(row["solver_cpu_seconds"] for row in primary),
            "results": records, "controls": controls,
            "selection": "warm_rank is the only positive aggregate training variant; root owns independent development/holdout evaluation",
            "scope": "Each variant uses train16,14 checked-range +2 large decoded-log boundary worlds",
            "official_submission_sent": False, "default_or_frozen_sources_modified": False}
(ROOT / "research/v11_search_review.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf8")
lines = ["# V11 更昂贵的放置搜索", "", "基于冻结v10_input_fix（正式99分策略及8MiB输入token修复），在看结果前固定3个变体。只使用train16，范围内14例和2个large日志边界例分别汇总；没有新增提交或读取V11新场景。", "",
         "full_racks：RK从16提升到30，枚举全部机架；warm_rank：仍保留16架，但用该架在线且可容纳目标需求机器的最少仓库缺层费排序，避免架缓存冷、机器缓存暖时的误排；full_wide：全30架并将前瞻从8后继×5输入扩至16×12。", "",
         "warm_rank按镜像、机器、架缓存版本和机器缓存版本记忆静态缺层量。FAIL清空机器缓存时同时递增元数据版本，避免新memo留住旧暖缓存；实际层拉取、真实收费、RUN/KILL、预算与资源对账逻辑保持原样。这里没有采用精确LRU报价，只改善静态预筛估价。", "",
         "full_wide同步修改qr/qz/qm/qf矩阵、nq/sj数组、后继ns截断及输入k截断；仍在任何数组访问之前检查ns上限，外部输入与各前驱插入均受12列容量限制。", "",
         "| 配置 | 范围内总利润 | 等权平均变化 | 中位比 | 升/降/平 | 最差变化 | 边界总利润 | 最高CPU |", "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
for record in records:
    v, b, worst = record["valid_range"], record["boundary"], record["worst"]
    lines.append(f"| {record['name']} | {v['total_profit_increase_pct']:+.4f}% | {v['equal_weight_increase_pct']:+.4f}% | {v['median_profit_ratio']:.6f} | {v['improved']}/{v['regressed']}/{v['unchanged']} | {100*(worst['profit_ratio']-1):.2f}% | {b['total_profit_increase_pct']:+.4f}% | {record['all_health']['max_cpu_seconds']:.6f}s |")
lines += ["", f"三版共48次实跑，{manifest['audit_total']:,}次对账全对，零非法。warm_rank训练总利润提高0.2764%，但只3升4降7平，不是逐例稳定优势；其余两版范围内总利润均下降，暂不推荐。", "",
          "## 时间保险控制", "", "保留原CPU保险，不能从总CPU低于1秒推断从未降级。另将基线/warm_rank的TS设为0，仅在fast00、standard00、large01三例对照：", "",
          "| 程序 | 场景 | TS0与TS1完整报告相同 | TS0利润−TS1利润 |", "| --- | --- | --- | ---: |"]
for control in controls["cpu_controls"]:
    for row in control["rows"]:
        lines.append(f"| {control['name']} | {row['case']} | {row['ts1_full_report_equal']} | {row['ts1_profit_delta']:+,} |")
lines += ["", "warm_rank在large01存在−24,775的差异，说明阶段CPU保险确实能在总CPU小于0.6秒时改变轨迹。该例是训练日志边界，不计范围内14例，但其余12个范围内场景没有做TS0对照；不能将所有利润差异都断言为纯放置策略收益。", "",
          "## 定向回归", "", "实际warm_rank源码通过17架构造：第17架只有机器缓存暖且架缓存冷时，可进入16架候选并一次RUN无仓库费；机器缓存按FAIL方式清空并递增版本后，旧暖估价正确失效，恢复原子预热且资源/配额/真实费用一致。",
          "实际full_wide源码通过现有0/1/7/8/9/16/64/1000后继、20k指令预算与延后KILL生命周期回归。测试入口重命名原main会产生缺返回警告；三份实际候选生产编译均无警告。没有声称通过缺失的UBSan。", "",
          "唯一正收益备选：candidates/v11_search/warm_rank.cpp；SHA256 dc5d793ac172a1a5b7359d2a6d9cd074c0a3b214b7ef3b4b657ddb46a5ec7e83。完整比较、CPU/内存和哈希在results/v11_search；控制证据在controls/summary.json。根目录、冻结源码、提交记录未修改。", ""]
(ROOT / "research/v11_search_review.md").write_text("\n".join(lines), encoding="utf8")
print(json.dumps({key: manifest[key] for key in ["primary_runs", "audit_total", "audit_errors", "illegal_commands", "max_cpu_seconds"]}))
