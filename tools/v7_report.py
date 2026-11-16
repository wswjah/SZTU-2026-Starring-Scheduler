"""Consolidate frozen V7 results without replacing the official 96-point release."""
from pathlib import Path
import hashlib
import json
import statistics
from compare import compare, markdown

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "results/v7_report"
OUT.mkdir(parents=True, exist_ok=True)


def read(path):
    return json.loads((ROOT / path / "summary.json").read_text(encoding="utf8"))


def save(label, rows):
    dest = OUT / label
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "summary.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf8")
    return dest


def record(label, old, new):
    value = compare(old, new)
    (OUT / f"{label}.json").write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf8")
    (OUT / f"{label}.md").write_text(markdown(value), encoding="utf8")
    return value


def main():
    primary = read("results/v7_final_main")
    baseline_train = ROOT / "results/v7_cpu_screen/baseline"
    baseline_other = read("results/v7_stress_samples_baseline")
    train = save("production_train", [r for r in primary if Path(r["input"]).parent.name == "train"])
    stress = save("production_stress", [r for r in primary if Path(r["input"]).parent.name == "stress"])
    old_stress = save("baseline_stress", [r for r in baseline_other if Path(r["input"]).parent.name == "stress"])
    training = record("training", baseline_train, train)
    pressure = record("stress", old_stress, stress)

    old_all, new_all = [], []
    for label, old_dir, new_dir in [
        ("validation", "results/v7_validation_cpu_baseline", "results/v7_validation_tuned"),
        ("confirmation", "results/v7_confirmation_baseline", "results/v7_confirmation_tuned"),
    ]:
        for dest, src in [(old_all, old_dir), (new_all, new_dir)]:
            for row in read(src):
                row = dict(row, case=label + "/" + row["case"])
                dest.append(row)
    fresh = record("fresh_combined", save("fresh_baseline", old_all), save("fresh_candidate", new_all))
    all_candidate = primary + read("results/v7_validation_tuned") + read("results/v7_confirmation_tuned")
    version_path = ROOT / "versions/v7_tuned/manifest.json"
    version = json.loads(version_path.read_text(encoding="utf8"))
    assert len(all_candidate) == 88 and all(r["ok"] for r in all_candidate)
    assert {r["exe_sha256"] for r in all_candidate} == {version["exe_sha256"]}
    assert hashlib.sha256(Path(version["packed_source"]).read_bytes()).hexdigest() == version["packed_sha256"]
    valid = fresh["valid_range_summary"]
    valid_rows = [r for r in fresh["rows"] if not r["baseline_range_violations"] and not r["candidate_range_violations"]]
    positive = [r for r in valid_rows if r["profit_ratio"] is not None]
    worst = min(positive, key=lambda r: r["profit_ratio"])
    validation = json.loads((ROOT / "results/v7_validation_tuned/comparison.json").read_text(encoding="utf8"))
    confirmation = json.loads((ROOT / "results/v7_confirmation_tuned/comparison.json").read_text(encoding="utf8"))
    version["validation"] = {
        "primary_runs": len(all_candidate), "all_ok": True,
        "audit_total": sum(r["audit_total"] for r in all_candidate),
        "audit_errors": sum(r["audit_errors"] for r in all_candidate),
        "illegal_commands": sum(r["incidents"] for r in all_candidate),
        "max_cpu_seconds": max(r["solver_cpu_seconds"] for r in all_candidate),
        "fresh_valid_case_count": valid["case_count"], "fresh_profit_increase_pct": valid["total_profit_increase_pct"],
        "fresh_improved": valid["improved"], "fresh_regressed": valid["regressed"], "worst_fresh_case": worst,
        "focused_checks": "results/v7_final_checks/summary.json", "results": "results/v7_report"}
    version_path.write_text(json.dumps(version, ensure_ascii=False, indent=2), encoding="utf8")
    manifest = {"candidate": version, "training": training["valid_range_summary"],
                "stress": pressure["valid_range_summary"], "validation": validation["valid_range_summary"],
                "confirmation": confirmation["valid_range_summary"], "fresh_combined": valid,
                "scope_policy": "Keep all boundary worlds; exclude them from valid-range totals. Native samples separate.",
                "baseline_96_files_unchanged": {
                    "main.cpp": hashlib.sha256((ROOT / "main.cpp").read_bytes()).hexdigest() == "65be27cdc374c30c8434b335c3895ebf661eca1a0d8e1394523237124df56fab",
                    "submit.cpp": hashlib.sha256((ROOT / "submit.cpp").read_bytes()).hexdigest() == "ec22e8889720e58ff2c05bbf8177778d53510e8ecff4236fac755f8ecaf6d703"}}
    assert all(manifest["baseline_96_files_unchanged"].values())
    (ROOT / "research/v7_experiment_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf8")
    screen = read("results/v7_cpu_screen")
    lines = ["# V7：96分底座上的有限调参与终局修正", "", "日期：2026-11-15。正式最高96分，V7尚未提交；当前新提交授权为0，最后核验余5次。", "",
             "## 本地比较口径", "",
             "发现MinGW/MSVCRT的clock()计墙钟，会把评测机和管道等待算入时间保险。sleep300ms实测旧clock增加0.314s、CPU增加0。",
             "[微软clock文档](https://learn.microsoft.com/en-us/cpp/c-runtime-library/reference/clock?view=msvc-170)说明该差异，",
             "[Linux clock手册](https://man7.org/linux/man-pages/man3/clock.3.html)定义为进程CPU时间。",
             "已用_WIN32 GetProcessTimes统一本机进程CPU，非Windows保留原clock表达式。适配只改善本机比较口径，不能当成正式利润改进。",
             "原墙钟实验保留；后续所有候选、基线均用相同CPU计时。三个控制世界的portable TS1与TS0完整报告一致，见v7_clock_semantics.md。", "",
             "## 已尝试的结构方向", "",
             "精确拉取估价两版、末任务精确救回/运行时长条件化没有足够稳定收益，未采用。最初极小波动有计时混杂，相关证伪与控制均保留。",
             "末tick清理单独测试16例收入逐例完全相同、拉取/网络费不变，只省运行费6937；已合入候选。预算与deferred DONE等定向测试通过。", "",
             "## 有限参数筛选", "",
             "14个单轴配置、3个预先指定组合，只用train16选择；14例范围内和2个日志边界单列。CPU修正后重跑全部配置，未用验证/确认集继续调参。", "",
             "| 配置 | 范围内总利润变化 | 升/降 | 中位利润比 | 最差利润比 |",
             "| --- | ---: | ---: | ---: | ---: |"]
    for r in screen:
        if r["name"] == "baseline":
            continue
        s = r["valid_range"]
        lines.append(f"| {r['name']} | {s['total_profit_increase_pct']:+.3f}% | {s['improved']}/{s['regressed']} | "
                     f"{s['median_profit_ratio']:.4f} | {r['worst_ratio']:.4f} |")
    lines += ["", "最终组合：SB 3→2、RK 12→16、KILLK 1→1.1、ADM 0→0.05，SP保持0.4。",
              "降低对已开工流程的额外倾斜、稍早止损、要求新流程5%预计费用余量，并扩大机架候选。",
              "另冻结仅RK16的温和对照，新验证总利润+0.774%，未继续调参，组合版仍优先。", "",
              "## 冻结后的验证", "",
              "| 集合 | 范围内例数 | 总利润变化 | 升/降 |",
              "| --- | ---: | ---: | ---: |"]
    for label, summary in [("最终生产版训练", training["valid_range_summary"]),
                            ("最大规模压力", pressure["valid_range_summary"]),
                            ("新种子及分布变化验证", validation["valid_range_summary"]),
                            ("独立新种子确认", confirmation["valid_range_summary"]),
                            ("两组合计", valid)]:
        lines.append(f"| {label} | {summary['case_count']} | {summary['total_profit_increase_pct']:+.3f}% | "
                     f"{summary['improved']}/{summary['regressed']} |")
    lines += ["", f"64例合计利润{valid['baseline_total_profit']:,}→{valid['candidate_total_profit']:,}。",
              f"最差为{worst['case']}：{worst['baseline_profit']:,}→{worst['candidate_profit']:,}（{100*(worst['profit_ratio']-1):.2f}%），不是逐例提升。",
              "shift_very_slow基线为负，其利润比未定义，只计绝对差，不编造正同比。",
              "最初very_fast及补充同名valid场景实际68455/64198 jobs超60000，两例完整保留作边界压力；另在看候选结果前新增稀疏fast场景，实际在范围。",
              "因此验证原始34例、其中范围内32；独立确认32全部在范围。训练两个large日志超3,000,000单列。", "",
              f"最终同一exe运行88次，{version['validation']['audit_total']:,}次对账全对，0非法指令；含2原生短样例和4个边界场景，不把88例全部称题面内。",
              f"本机最大CPU{version['validation']['max_cpu_seconds']:.6f}s，不保证正式时限或分数。真实生产packed文件通过后继、20k预算、延后终止、末tick回归。", "",
              "## 交付", "",
              f"候选：versions/v7_tuned/submit.cpp，{version['packed_bytes']}字节，SHA256 `{version['packed_sha256']}`。",
              "上游来源说明保留，打包逐token校验。默认main.cpp/submit.cpp仍为正式96分文件。",
              "所有数据、逐例结果、失败方向和控制保留；完整清单见v7_experiment_manifest.json。",
              "V7未提交，本地+1.06%不等于会多过一个测试点；当前看不到剩余4点详情。若正式验证，只建议先用1次机会。"]
    (ROOT / "research/v7_experiment.md").write_text("\n".join(lines) + "\n", encoding="utf8")
    print(json.dumps({"fresh_valid": valid["case_count"], "fresh_pct": valid["total_profit_increase_pct"],
                      "wins": valid["improved"], "losses": valid["regressed"],
                      "candidate_runs": len(all_candidate), "audits": version["validation"]["audit_total"],
                      "train_pct": training["valid_range_summary"]["total_profit_increase_pct"],
                      "stress_pct": pressure["valid_range_summary"]["total_profit_increase_pct"]}))


if __name__ == "__main__":
    main()
