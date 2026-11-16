"""Publish the expanded-B candidate with its untouched post-selection check."""
from pathlib import Path
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parent.parent


def load(path):
    return json.loads((ROOT / path).read_text(encoding="utf8"))


def dump(path, value):
    (ROOT / path).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf8")


def main():
    primary = load("research/v15_experiment_manifest.json")
    post = load("research/v15_postconfirmation_results.json")
    post_review = load("research/v15_postconfirmation_input_review.json")
    assert (ROOT / "research/v15_independent_review.md").is_file()
    policy = post["comparisons"]["v15_B128_120"]
    assert policy["post40"]["total_profit_increase_pct"] > 0
    version = load("versions/v15_B128_120/manifest.json")
    rows = load("results/v15_postconfirmation_v15_B128_120/summary.json")
    assert len(rows) == 40 and all(r["ok"] for r in rows)
    assert {r["exe_sha256"] for r in rows} == {version["exe_sha256"]}
    for field, sha in [("source", "source_sha256"), ("packed_source", "packed_sha256"), ("executable", "exe_sha256")]:
        assert hashlib.sha256(Path(version[field]).read_bytes()).hexdigest() == version[sha]
    decisions = dict(attempts=0, rejects=0, late=0, guard_returns=0)
    for file in (ROOT / "results/v15_postconfirmation_v15_B128_120").rglob("solver_stderr.txt"):
        match = re.search(r"V15_MODEL_POLICY attempts=(\d+) rejects=(\d+) late=(\d+) guard_returns=(\d+)", file.read_text())
        assert match
        for key, value in zip(decisions, match.groups()):
            decisions[key] += int(value)
    validation = version["validation"]
    # Rebuild from primary fixed evidence so the report operation is idempotent.
    base_rows = load("results/v15_train_v15_B128_120/summary.json")
    for split in ["holdout", "confirmation"]:
        base_rows += load(f"results/v15_{split}_v15_B128_120/summary.json")
    base_rows += load("results/v15_aux_v15_B128_120/summary.json")
    all_version_rows = base_rows+rows
    assert len(all_version_rows) == 254
    validation.update(main_runs=254, audit_total=sum(r["audit_total"] for r in all_version_rows),
        max_cpu_seconds=max(r["solver_cpu_seconds"] for r in all_version_rows),
        new120=policy["new120"], postconfirmation40=policy["post40"], post_gate_counts=decisions,
        new120_vs_oldA=policy["new120_vs_v14_mlp_A"], new120_vs_oldB=policy["new120_vs_v14_mlp_B"])
    version["local_selection_status"] = "Preferred experimental expanded-training candidate;three new40 blocks positive,120total+0.5126%;pressure4-0.4201%,tail regressions remain;no official score"
    dump("versions/v15_B128_120/manifest.json", version)
    primary["postconfirmation"] = post
    primary["postconfirmation_input_review"] = post_review
    primary["new_validation_worlds"] = 120
    primary["total_current_runs"] = primary["health"]["runs"]+post["health"]["runs"]
    primary["total_current_audits"] = primary["health"]["audit_total"]+post["health"]["audit_total"]
    primary["preferred_experimental_candidate"] = "versions/v15_B128_120/submit.cpp"
    primary["conclusion"] = "Expansion helpsB in this experiment:oldB32+0.1044% vs B128+0.5126% on120new worlds,with selectedB positive on untouchedpost40. A expansion flat,tree lower;data alone is not proven as sole cause becauseB also has more updates. No official score/AC established."
    dump("research/v15_experiment_manifest.json", primary)
    release = load("results/final_manifest.json")
    for field, record in release["artifacts"].items():
        assert hashlib.sha256((ROOT / field).read_bytes()).hexdigest() == record["sha256"]
    local = release["local_research"]
    local.update(date="2026-11-16", preferred_unsubmitted_candidate="versions/v15_B128_120/submit.cpp",
        packed_sha256=version["packed_sha256"], scope="Experimental128-world/164406-flow neuralB fixedstrict gate;99 parameters+8MiB fix/direct scanner unchanged",
        previous_neural_alternative="versions/v14_mlp_A/submit.cpp", neural_training_worlds=128,
        neural_policy_new120=policy["new120"], neural_postconfirmation40=policy["post40"],
        expandedB_vs_oldA120=policy["new120_vs_v14_mlp_A"], expandedB_vs_oldB120=policy["new120_vs_v14_mlp_B"],
        official_score_of_local_candidate=None, new_submissions_sent=0,
        submission_decision="Local validation/retraining only;no new submission authorization")
    # Label previous neural metrics explicitly rather than leaving stale generic keys.
    for key in ["neural_policy_fresh80", "neural_policy_worst", "neural_vs_tree80"]:
        if key in local:
            local["oldA_v14_"+key] = local.pop(key)
    for path in ["research/v15_experiment.md", "research/v15_training_report.md", "research/v15_independent_review.md"]:
        if path not in local["reports"]:
            local["reports"].append(path)
    dump("results/final_manifest.json", release)
    total = policy["new120"]
    appendix = ["", "## 追加40例独立确认与保留候选", "",
        "原80结果揭示扩训B较好后，另固定40个全新种子，只评baseline、原A、原B及扩训B。选择与输入在任何post结果前写入计划，权重/门槛均未改；这是选择后的独立确认，不是重新训练或用新数据选阈值。输入与全部历史seed/配置无重复，四程序哈希独立核验。", "",
        "| 固定模型 | 主80 | 后续40 | 同一批新120 | 升/降/平 |", "| --- | ---: | ---: | ---: | ---: |"]
    for name, label in [("v14_mlp_A", "原A32世界"), ("v14_mlp_B", "原B32世界"), ("v15_B128_120", "扩训B128世界")]:
        p = post["comparisons"][name]; a = primary["comparisons"][name]["new80"]; v = p["new120"]
        appendix.append(f"| {label} | {a['total_profit_increase_pct']:+.4f}% | {p['post40']['total_profit_increase_pct']:+.4f}% | {v['total_profit_increase_pct']:+.4f}% | {v['improved']}/{v['regressed']}/{v['unchanged']} |")
    appendix += ["", "扩训B三批40总利润分别+0.6456%/+0.4251%/+0.4787%。同一120例相对原B"+f"{policy['new120_vs_v14_mlp_B']['total_profit_increase_pct']:+.4f}%、相对原A{policy['new120_vs_v14_mlp_A']['total_profit_increase_pct']:+.4f}%，这些是本地生成世界的总利润差，不能换算为官方分数。", "",
        "扩训不是普遍增益：A120在主80与原A几乎持平，A4920略降，重训树也低于原树。B128同时增加了数据与更新数；本轮仅A做同更新数对照，不能断言B的全部增益由数据数量单独造成。它说明本次扩大数据并按原轮数重训B的组合有效。", "",
        "尾部与压力风险仍在：主80的极慢一例baseline6,956→原A1,324/原B−4,775/扩训B1,661；低利润基数会放大同比百分比，但绝对退步也保留。B的既有压力4例合计−0.4201%，没有因新120总量正收益就隐去这组。", "",
        f"最新实验提交候选versions/v15_B128_120/submit.cpp，{version['packed_bytes']:,}字节，SHA256 `{version['packed_sha256']}`。同一packed程序254次交互运行、{validation['audit_total']:,}次对账全对、零非法指令，包含128训练+120新验证+4压力+2样例；最高本机CPU{validation['max_cpu_seconds']:.6f}s，长日志400ANS仍精确。新权重参数数量维持458，运行时不需训练框架。", "",
        f"本轮总计{primary['total_current_runs']:,}次实际交互、{primary['total_current_audits']:,}次对账全对、零非法指令（非交互审计与直接协议另计）。旧A仍保留为备选，保守输入/扫描修复版也保留。根目录正式99分源码与默认程序哈希不变；本轮没有正式提交。", ""]
    path = ROOT / "research/v15_experiment.md"
    text = path.read_text(encoding="utf8").split("\n## 追加40例独立确认与保留候选\n")[0]
    path.write_text(text+"\n".join(appendix), encoding="utf8")
    marker = "<!-- v15 training expansion -->"
    update = "2026-11-16本地V15：新增96训练世界，训练32→128、入场记录41,151→164,406，固定重训两网络/浅树和同4920更新数对照，另新增120验证场景。扩训B在三批新40总利润+0.6456%/+0.4251%/+0.4787%，合计120+0.5126%；同场原A+0.3018%、原B+0.1044%。A扩训几乎持平，树略退步，不能假设更多数据普遍涨分。B既有压力4例−0.4201%，极慢场景仍退步；新候选 `versions/v15_B128_120/submit.cpp` 仅作实验备选，默认正式99分不改、没有提交。详见 `research/v15_experiment.md`。"
    for filename in ["README.md", "REPORT.md"]:
        path = ROOT / filename; text = path.read_text(encoding="utf8")
        if marker not in text:
            needle = "## 当前实现" if filename == "README.md" else "# 验证记录\n"
            replacement = marker+"\n"+update+"\n\n"+needle if filename == "README.md" else needle+"\n"+marker+"\n"+update+"\n"
            path.write_text(text.replace(needle, replacement, 1), encoding="utf8")
    print(json.dumps({"new_validation_worlds": 120, "training_worlds": 128,
        "preferred_experimental": "v15_B128_120", "packed_sha256": version["packed_sha256"],
        "new120_profit_pct": total["total_profit_increase_pct"], "up": total["improved"], "down": total["regressed"],
        "total_runs": primary["total_current_runs"], "total_audits": primary["total_current_audits"],
        "official_submission_sent": False, "defaults_unchanged": True}))


if __name__ == "__main__":
    main()
