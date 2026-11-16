"""Publish local V13 evidence without touching official99 default artifacts."""
from pathlib import Path
import hashlib
import json
from compare import compare

ROOT = Path(__file__).resolve().parent.parent


def load(path):
    return json.loads((ROOT / path).read_text(encoding="utf8"))


def dump(path, value):
    (ROOT / path).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf8")


def main():
    primary = load("research/v13_experiment_manifest.json")
    production = load("results/v13_production_check/summary.json")
    candidate = load("versions/v13_model_fast/manifest.json")
    release = load("results/final_manifest.json")
    review = ROOT / "research/v13_model_independent_review.md"
    assert review.is_file()
    for field in ["main.cpp", "submit.cpp", "build/main.exe", "build/submit.exe"]:
        assert hashlib.sha256((ROOT / field).read_bytes()).hexdigest() == release["artifacts"][field]["sha256"]
    reference_aux = load("results/v13_aux_v13_model_strict/summary.json")
    assert len(reference_aux) == 6 and all(r["ok"] for r in reference_aux)
    baseline_aux = load("results/v13_aux_v12_scan_input_fix/summary.json")
    assert len(baseline_aux) == 6 and all(r["ok"] for r in baseline_aux)
    for name, rows in [("baseline", baseline_aux), ("model", load("results/v13_aux_v13_model_fast/summary.json"))]:
        directory = ROOT / "results/v13_aux_comparison" / name
        directory.mkdir(parents=True, exist_ok=True)
        normalized = [dict(r, case=Path(r["input"]).parent.name+"/"+r["case"]) for r in rows]
        (directory / "summary.json").write_text(json.dumps(normalized, ensure_ascii=False, indent=2), encoding="utf8")
    auxiliary_comparison = compare(ROOT / "results/v13_aux_comparison/baseline", ROOT / "results/v13_aux_comparison/model")
    dump("results/v13_aux_comparison/comparison.json", auxiliary_comparison)
    pressure = auxiliary_comparison["valid_range_summary"]
    assert pressure["case_count"] == 4
    primary["production"] = production
    primary["preferred_experimental_candidate"] = "versions/v13_model_fast/submit.cpp"
    primary["conservative_candidate"] = "versions/v12_scan_input_fix/submit.cpp"
    primary["auxiliary_comparison"] = auxiliary_comparison
    primary["all_interactive_runs"] = primary["health"]["runs"]+production["health"]["main_runs"]+len(reference_aux)+len(baseline_aux)
    primary["all_interactive_audits"] = primary["health"]["audits"]+production["health"]["audit_total"]+sum(r["audit_total"] for r in reference_aux+baseline_aux)
    primary["conclusion"] = "Fixed tiny model strict improves both fresh40 splits (+0.4575/+0.5036%) and combined80+0.4813%,52 up28 down,worst-6.06%. Fine parameters do not show stable gains. Production two-feature implementation exactly matches86 complete reports. Official score unknown; preserve official99 default and conservative input/scanner-only candidate."
    dump("research/v13_experiment_manifest.json", primary)
    local = release["local_research"]
    local.update(date="2026-11-16",
        preferred_unsubmitted_candidate="versions/v13_model_fast/submit.cpp",
        packed_sha256=candidate["packed_sha256"],
        scope="99 scheduling parameters plus8MiB repair/direct scanner and fixed tiny-model first-admission gate; experimental profit candidate",
        conservative_unsubmitted_candidate="versions/v12_scan_input_fix/submit.cpp",
        conservative_packed_sha256="59e5e2309c06871161bd2f7d27220233bab2b1b4ec94e3333e095ac2d7766aed",
        model_policy_fresh80=primary["comparisons"]["v13_model_strict"]["fresh80"],
        model_policy_worst=primary["comparisons"]["v13_model_strict"]["worst"],
        official_score_of_local_candidate=None, new_submissions_sent=0,
        submission_decision="User deferred submissions; current task local research only")
    for report in ["research/v13_experiment.md", "research/v13_model_experiment.md", "research/v13_model_independent_review.md"]:
        if report not in local["reports"]:
            local["reports"].append(report)
    dump("results/final_manifest.json", release)
    h = production["health"]
    appendix = f"""\n## 本轮保留候选\n\n相比99参数附近的细调，固定小模型在本轮两个新40例都保持正增益，合计新80总利润+0.4813%，52升28降，中位数+0.6536%。它只暂缓预计利润很低、规模至少3作业的新流程，让资源留给其它任务；不是运行中任务止损。最差单例−6.06%，standard合计略降，隐藏数据上的正式得分仍未知。\n\n另外将当前baseline在4个既有最大规模压力和2个原生样例同输入重跑，压力4例合计利润{pressure['total_profit_increase_pct']:+.4f}%（{pressure['improved']}升{pressure['regressed']}降），其中failures约−3.45%。模型在最大规模场景不普遍提高，必须保留这部分风险；压力数据是已知开发数据，不混入80例新验证。原生样例为历史短T初始化，单列健康检查。\n\n生产精简版versions/v13_model_fast/submit.cpp仅计算树实际用到的两个特征，删除另外16个特征、无用缓存字段与诊断计数，没有改树、阈值、预测保存时点或调度规则。逐特征/树/门控边界检查和独立审查通过。实际packed在已观测的新80例、最大规模压力4例、原生样例2例，共86例完整judge报告与原strict全部一致；这86次是实现等价复核，不再称第二批独立利润证据。最大本机CPU{h['max_cpu_seconds']:.6f}s，不据并行计时宣称精确提速。300万字符完整Huffman协议400答案仍精确。\n\n提交文件{candidate['packed_bytes']:,}字节，SHA256 `{candidate['packed_sha256']}`。优先实验候选是v13_model_fast；保守路线继续保留v12_scan_input_fix，只含输入/扫描修复。两者均未正式提交，根目录默认仍是正式99分。\n\n包含生产等价86次及原strict/baseline各额外6次压力/样例，本轮合计{primary['all_interactive_runs']:,}次实际交互、{primary['all_interactive_audits']:,}次对账全对、零非法指令。非交互harness和直接协议分别计数。\n"""
    path = ROOT / "research/v13_experiment.md"
    text = path.read_text(encoding="utf8")
    marker = "\n## 本轮保留候选\n"
    text = text.split(marker)[0]+appendix
    path.write_text(text, encoding="utf8")
    readme = ROOT / "README.md"
    text = readme.read_text(encoding="utf8")
    update = "2026-11-16本地V13有小幅进展：新32训练世界完成24组细调和4个固定小模型策略，最后3候选在两个新40例验证。细调没有稳定改进；小模型两批总利润分别+0.4575%/+0.5036%，合计80例+0.4813%（52升28降，最差−6.06%）。生产精简候选 `versions/v13_model_fast/submit.cpp` 只计算两个实际使用特征，与完整模型86例完整报告相同，保留缓冲区/扫描修复；保守路线 `versions/v12_scan_input_fix/` 继续保留。正式得分未测，默认99分未改，本轮未提交。详见 `research/v13_experiment.md`。"
    marker = "<!-- v13 local research -->"
    if marker not in text:
        text = text.replace("## 当前实现", marker+"\n"+update+"\n\n## 当前实现", 1)
        readme.write_text(text, encoding="utf8")
    report = ROOT / "REPORT.md"
    text = report.read_text(encoding="utf8")
    if marker not in text:
        text = text.replace("# 验证记录\n", "# 验证记录\n\n"+marker+"\n"+update+"\n", 1)
        report.write_text(text, encoding="utf8")
    print(json.dumps({"preferred_experimental_candidate": local["preferred_unsubmitted_candidate"],
        "packed_bytes": candidate["packed_bytes"], "packed_sha256": candidate["packed_sha256"],
        "total_runs": primary["all_interactive_runs"], "total_audits": primary["all_interactive_audits"],
        "official_submission_sent": False, "official_defaults_unchanged": True}))


if __name__ == "__main__":
    main()
