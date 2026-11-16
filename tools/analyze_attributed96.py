"""Record local validation for the attributed bounds/budget derivative."""
from pathlib import Path
import hashlib
import json
import sys
from compare import compare, markdown

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf8")
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "results/v6_attributed96_comparison"
VERSION = ROOT / "versions/v6_attributed96"


def read(path):
    return json.loads((ROOT / path / "summary.json").read_text(encoding="utf8"))


def main():
    rows = read("results/v6_attributed96")
    assert len(rows) == 54 and all(r["ok"] for r in rows)
    baseline = {"train": ROOT / "results/v3_final_aggressive/train",
                "stress": ROOT / "results/v3_final_aggressive/stress",
                "v4_confirmation": ROOT / "results/v4_baseline_confirmation"}
    comparisons = {}
    for group, base in baseline.items():
        target = OUT / group
        target.mkdir(parents=True, exist_ok=True)
        subset = [r for r in rows if Path(r["input"]).parent.name == group]
        (target / "summary.json").write_text(json.dumps(subset, ensure_ascii=False, indent=2), encoding="utf8")
        result = compare(base, target)
        comparisons[group] = result["valid_range_summary"]
        (target / "comparison.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf8")
        (target / "comparison.md").write_text(markdown(result), encoding="utf8")
    exe = ROOT / "build/v6_attributed96.exe"
    digest = hashlib.sha256(exe.read_bytes()).hexdigest()
    assert {r["exe_sha256"] for r in rows} == {digest}
    manifest = json.loads((VERSION / "manifest.json").read_text(encoding="utf8"))
    manifest["executable"] = {"path": str(exe), "sha256": digest, "bytes": exe.stat().st_size}
    manifest["validation"] = {"runs": len(rows), "all_ok": True,
                              "audit_total": sum(r["audit_total"] for r in rows),
                              "audit_errors": sum(r["audit_errors"] for r in rows),
                              "incidents": sum(r["incidents"] for r in rows),
                              "max_cpu_seconds": max(r["solver_cpu_seconds"] for r in rows),
                              "comparison_by_group": comparisons,
                              "results": "results/v6_attributed96/summary.json"}
    (VERSION / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf8")
    text = ["# 署名96分派生版：修复与验证", "",
            "基于 Shuang-su 公开仓库 commit a35a23f3a8a3c623ff9c62af15e680143264de5e 的 main.cpp。",
            "可读源码与提交文件均保留来源说明，不重命名以混淆来源，不承诺查重结果。", "",
            "实质修改：在后继 scratch 数组访问前检查8行边界；统计所有RUN/KILL；",
            "预留完整预热三指令；用延后队列保存超出每tick 20000预算的终止请求。",
            "延后请求在下一tick的CPU保险前处理，已DONE/FAIL作业跳过；ANS/END不计预算。", "",
            "| 集合 | 范围内例数 | 相对本项目85分版总利润 | 升/降/平 |",
            "| --- | ---: | ---: | --- |"]
    for group, r in comparisons.items():
        text.append(f"| {group} | {r['case_count']} | {r['total_profit_increase_pct']:+.3f}% | "
                    f"{r['improved']}/{r['regressed']}/{r['unchanged']} |")
    official_path = ROOT / "research/official_v6_attributed96.json"
    official = json.loads(official_path.read_text(encoding="utf8")) if official_path.exists() else {}
    official_score = official.get("final_status", {}).get("exam_score")
    text += ["", f"54次本地闭环，{manifest['validation']['audit_total']}次对账全部正确，0非法指令；",
             f"最大本机CPU {manifest['validation']['max_cpu_seconds']:.6f}s，不能换算为正式得分。",
             "训练large两例日志超保守范围的记录仍保留，未计入14例范围内汇总。", "",
             "上游可读main.cpp与其压缩submit.cpp并未建立输出等价；上游存在数组越界，",
             "且有CPU时间驱动的降级，因此不同二进制或执行环境可能改变动作。",
             "本项目提交的是本轮冻结、完整验证过的派生文件。", "",
             f"提交源码：{manifest['packed_source']['bytes']}字节，SHA256 `{manifest['packed_source']['sha256']}`。",
             f"程序SHA256 `{digest}`。", "",
             "正式记录独立保存；此处本地结果不能视为学校通过点数。"]
    if official_score is not None:
        text += ["", f"正式结果：提交{official['solution_id']}得{official_score}分。当前96分记录为本账号实测；",
                 "已登录核验最高自动分96、已用5次、剩余5次。来源保留，不把上游算法称为本项目从零原创。",
                 "详情仍不可见，余下测试点失分原因未知。正式回执见research/official_v6_attributed96.json/.md。"]
    if (ROOT / "results/v6_attributed96_focused/summary.json").exists():
        text += ["", "定向回归见results/v6_attributed96_focused/summary.json：真实tryPlace覆盖0至1000后继、",
                 "19997/19998/19999/20000指令边界、延后终止跨tick以及DONE/FAIL过期、账本/资源核验。",
                 "修复版与checked scratch数组副本通过，恢复原晚检查的负对照准确捕获索引8越界。",
                 "MinGW缺libubsan，因此不宣称UBSan通过。"]
    (ROOT / "research/v6_attributed96_review.md").write_text("\n".join(text) + "\n", encoding="utf8")
    print(json.dumps(manifest["validation"], ensure_ascii=False))


if __name__ == "__main__":
    main()
