"""Summarize34 tuning trials and the isolated input-boundary repair."""
from pathlib import Path
import difflib
import hashlib
import json

ROOT = Path(__file__).resolve().parent.parent


def load(path):
    return json.loads((ROOT / path).read_text(encoding="utf8"))


def dump(path, value):
    (ROOT / path).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf8")


def main():
    root_trials = load("results/v10_fine/summary.json")
    duration_trials = load("results/v10_duration/summary.json")
    development = load("results/v10_development/summary.json")
    assert len(root_trials) == 20 and len(duration_trials) == 14 and len(development) == 3
    version = load("versions/v10_input_fix/manifest.json")
    verified = load("results/v10_input_verification/summary.json")
    assert {k: v["valid_range"]["case_count"] for k, v in verified["groups"].items()} == {"train": 14, "stress": 4, "v10_holdout": 40}
    correct = load("results/v10_correctness_audit.json")
    release = load("results/final_manifest.json")
    assert release["official_score"] == 99 and release["remaining_submissions"] == 4
    assert hashlib.sha256((ROOT / "main.cpp").read_bytes()).hexdigest() == release["artifacts"]["main.cpp"]["sha256"]
    assert hashlib.sha256((ROOT / "submit.cpp").read_bytes()).hexdigest() == release["artifacts"]["submit.cpp"]["sha256"]
    assert version["packed_differing_byte_count"] == 1 and version["header_identical_to_official99"]
    original = (ROOT / "versions/v8_fine/main.cpp").read_text(encoding="utf8").splitlines(keepends=True)
    repaired = Path(version["source"]).read_text(encoding="utf8").splitlines(keepends=True)
    patch = "".join(difflib.unified_diff(original, repaired, fromfile="official99/main.cpp", tofile="v10_input_fix/main.cpp", n=3))
    (ROOT / "research/v10_input_fix.patch").write_text(patch, encoding="utf8")
    all_trials = root_trials+duration_trials
    health = {"parameter_configs": 34, "parameter_runs": 34*16,
              "development_policies": 3, "development_runs": 3*80,
              "fixed_actual_packed_exe": verified["health"],
              "long_log_all400_answers_exact": verified["large_protocol"]["all_400_answers_exact"]}
    manifest = {"date": "2026-11-15", "official_best": 99, "remaining_submissions": 4,
                "candidate": version, "parameter_trials": all_trials, "development": development,
                "health": health, "correctness_audit": "research/v10_correctness_audit.md",
                "decision": "Prefer the isolated proven buffer repair; no parameter overlay in this submission candidate",
                "reason": "Tuning gains are small/unstable, but valid-scale complete protocol reproduces incorrect ALARM in original99 and exact answers after buffer fix",
                "candidate_official_submission_sent": False,
                "hidden_failure_cause_known": False}
    dump("research/v10_experiment_manifest.json", manifest)
    lines = ["# V10：99分之后的调参及输入边界修复", "", "2026-11-15。正式最高99分，提交544054；最后核验已用6次、剩4次。本轮没有网页提交。", "",
             "## 推荐候选：只修复一个确定的越界", "", "题面约束日志解码后总长3MB，9符号赫夫曼树最长码可达8bit；3,000,000字符可编码为6,000,000个十六进制字符。原tok只有4MiB，读取整条编码时越界。",
             "按题面声明规模构造完整400tick协议：唯一模式a权重1，日志为3,000,000个a。原正式99程序首条ALARM错为2,995,859；仅扩大tok至8MiB，400条答案全部正确。编码输入由本地脚本构造，未通过TPJ认证，也不是正式隐藏数据。",
             "单改8MiB也覆盖把3MB解释成3MiB时最多6MiB的hex编码，并留出NUL。其它未声明上界的token不作无限长度保证。", "",
             "```diff", "-char inbuf[1 << 16], tok[1 << 22];", "+char inbuf[1 << 16], tok[1 << 23];", "```", "",
             "候选所有调度常量与99分版本相同。packed文件只差一个字节，没有新增注释；原99分提交文件已有的三行来源说明完整保留。可直接查看v10_input_fix.patch和候选文件开头，避免把注释当成未展示的提交内容。", "",
             "## 实际冻结提交文件的验证", "", f"`versions/v10_input_fix/submit.cpp`，{version['packed_bytes']:,}字节，SHA256 `{version['packed_sha256']}`。",
             f"同一实际packed编译程序60次TPJ运行（16训练、4压力、40个新种子/分布变化），{verified['health']['audit_total']:,}次对账全对、0非法；60份完整judge报告逐例与正式99基线相同，收益、成本、完成数等字段全部不变。",
             f"本机最高CPU {verified['health']['max_cpu_seconds']:.6f}s，峰值内存 {verified['health']['max_peak_memory_bytes']/1024**2:.2f}MiB；训练2个large为旧日志边界例，另外58例通过现有可观测范围检查，不把未记录字段说成已核验。",
             "此外，实际packed程序也直接重放上述600万hex字符完整协议，400条答案全部精确。该构造是直接协议测试，和TPJ60次运行分别计数。",
             "完整正确性审计另含6,000道网络/配额/告警oracle、30,000次LRU操作、12,656次SLACK比较，未见其它新增确定错误；这些测试不证明全部合法输入或正式1秒时限。", "",
             "## 34组参数筛选", "", "基线统一为冻结99分版本、进程CPU时钟。20个优先级/接纳/止损/放置邻域和14个时长/学习/末期邻域预先固定，只用train16筛选；训练2large日志超范围，利润按14例报告。", "",
             "| 配置 | 变更 | 14例总利润变化 | 等权变化 | 升/降/平 |", "| --- | --- | ---: | ---: | ---: |"]
    for row in all_trials:
        v = row["valid_range"]
        lines.append(f"| {row['name']} | {row['parameters']} | {v['total_profit_increase_pct']:+.4f}% | {v['equal_weight_increase_pct']:+.4f}% | {v['improved']}/{v['regressed']}/{v['unchanged']} |")
    lines += ["", "34×16=544次调参交互完整保留，不从单例挑收益。没有两个轴同时满足预期稳定性，未使用计划允许的组合名额。", "",
              "## 旧80世界仅作开发复核", "", "V8已使用过的40验证+40确认，本轮明确降为开发数据，不称新的独立验证。按训练表现预先选择三项后复核，无后续按开发结果加新配置。", "",
              "| 变更 | 80例总利润变化 | 升/降/平 | 中位利润比 | 最差变化 |", "| --- | ---: | ---: | ---: | ---: |"]
    for row in development:
        v = row["valid_range"]
        lines.append(f"| {row['name']} | {v['total_profit_increase_pct']:+.4f}% | {v['improved']}/{v['regressed']}/{v['unchanged']} | {v['median_profit_ratio']:.6f} | {100*(row['worst']['profit_ratio']-1):.2f}% |")
    lines += ["", "RESV15和PEN.75仅有很小总利润增益，并存在退步；BB.045开发总利润下降。当前优先保留99分调度参数，先独立修复已证实的输入边界，避免把两种原因混在一次正式验证中。上述三项均未进入新40例或正式提交。", "",
              "## 正式状态与复现", "", "当前main.cpp、submit.cpp仍是已提交99分的原文件。新修复在versions/v10_input_fix/独立冻结，没有新提交授权、没有消耗机会。最后1组详情隐藏，不能声称已定位其原因或保证本修复会AC。", "",
              "复现：tools/v10_fix_input.py、v10_verify_frozen.py；本轮调参：v10_fine.py、v10_duration_screen.py、v10_development.py；完整证据：v10_experiment_manifest.json、v10_correctness_audit.md、results/v10_input_verification/。", ""]
    (ROOT / "research/v10_experiment.md").write_text("\n".join(lines), encoding="utf8")
    print(json.dumps({"candidate": version["name"], "packed_sha256": version["packed_sha256"],
                      "parameter_trials": 34, "development_trials": 3,
                      "fixed_full_report_equivalence": 60, "official_submission_sent": False}))


if __name__ == "__main__":
    main()
