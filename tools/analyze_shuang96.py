"""Reproducible local comparison of the attributed Shuang-su snapshot."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf8")

sys.path.insert(0, str(Path(__file__).resolve().parent))
from compare import compare, markdown

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "results/shuang96_comparison"


def read(path):
    return json.loads((ROOT / path / "summary.json").read_text(encoding="utf8"))


def save_rows(label, group, rows):
    path = OUT / label / group / "summary.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    selected = [r for r in rows if Path(r["input"]).parent.name == group]
    assert selected, (label, group)
    path.write_text(json.dumps(selected, ensure_ascii=False, indent=2), encoding="utf8")
    return path


def main():
    sources = {
        "official85": read("results/v3_final_aggressive/train")
        + read("results/v3_final_aggressive/stress")
        + read("results/v4_baseline_confirmation"),
        "v4": read("results/v4_production")
        + read("results/v4_production_confirmation"),
        "shuang_warm": read("results/shuang96_submit"),
        "shuang_nowarm": read("results/shuang96_nowarm"),
    }
    groups = ["train", "stress", "v4_confirmation"]
    paths = {(label, group): save_rows(label, group, rows)
             for label, rows in sources.items() for group in groups}
    lines = ["# Shuang-su 96分代码：本项目本地对照", "",
             "日期：2026-11-15。学校正式分数与以下本地利润独立；未提交同学代码。",
             "固定仓库快照，原样编译 submit.cpp / submit_nowarm.cpp，不调参。",
             "训练中2个日志边界场景保留，但不纳入范围内14例汇总。",
             "同输入与评测机哈希由 compare.py 检查；CPU不是同期配对性能实验。", "",
             "| 比较（后者相对前者） | 集合 | 范围内例数 | 总利润变化 | 升/降/平 |",
             "| --- | --- | ---: | ---: | --- |"]
    results = {}
    for before, after in [("official85", "shuang_warm"),
                          ("v4", "shuang_warm"),
                          ("shuang_nowarm", "shuang_warm"),
                          ("v4", "shuang_nowarm")]:
        for group in groups:
            key = f"{before}_to_{after}_{group}"
            value = compare(paths[before, group], paths[after, group])
            results[key] = value
            (OUT / f"{key}.json").write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf8")
            (OUT / f"{key}.md").write_text(markdown(value), encoding="utf8")
            s = value["valid_range_summary"]
            lines.append(f"| {before} → {after} | {group} | {s['case_count']} | "
                         f"{s['total_profit_increase_pct']:+.3f}% | "
                         f"{s['improved']}/{s['regressed']}/{s['unchanged']} |")
    snapshot = ROOT / "reference/shuang96"
    commit = subprocess.check_output(["git", "-C", str(snapshot), "rev-parse", "HEAD"], text=True).strip()
    manifest = {"commit": commit,
                "repository": "https://github.com/Shuang-su/SZTU-2026-data-structure-final-homework",
                "date": "2026-11-15", "official_submission_of_reference_sent": False,
                "files": {}, "comparisons": results}
    warm_source = (snapshot / "submit.cpp").read_text()
    nowarm_source = (snapshot / "submit_nowarm.cpp").read_text()
    differences = [(i, a, b) for i, (a, b) in enumerate(zip(warm_source, nowarm_source)) if a != b]
    assert len(warm_source) == len(nowarm_source) and len(differences) == 1
    assert differences[0][1:] == ("1", "0")
    manifest["warm_ablation_source_difference"] = {
        "same_length": True, "changed_characters": 1,
        "change": "PW default from 1 to 0", "offset": differences[0][0]}
    for source in ["submit.cpp", "submit_nowarm.cpp", "main.cpp", "sol.cpp"]:
        raw = subprocess.check_output(["git", "-C", str(snapshot), "show", f"HEAD:{source}"])
        working = (snapshot / source).read_bytes()
        manifest["files"][source] = {
            "git_blob_bytes": len(raw), "git_blob_sha256": hashlib.sha256(raw).hexdigest(),
            "working_tree_bytes": len(working), "working_tree_sha256": hashlib.sha256(working).hexdigest()}
    for label in ["shuang_warm", "shuang_nowarm"]:
        rows = sources[label]
        manifest[label] = {"runs": len(rows), "all_ok": all(r["ok"] for r in rows),
                           "audits": sum(r["audit_total"] for r in rows),
                           "audit_errors": sum(r["audit_errors"] for r in rows),
                           "incidents": sum(r["incidents"] for r in rows),
                           "max_cpu_seconds": max(r["solver_cpu_seconds"] for r in rows),
                           "exe_sha256": sorted(set(r["exe_sha256"] for r in rows))}
    (OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf8")
    lines += ["", f"快照：`{commit}`。", "",
              "工作树按本机 Git 设置转成 CRLF；另存原始 Git blob 的字节数和哈希，避免误认代码变更。", "",
              "每版完整52例（含训练边界2例），全部结果保留于 results/shuang96_submit 与 results/shuang96_nowarm。", "",
              "详细逐例、范围、错误和时间记录：results/shuang96_comparison/manifest.json。"]
    (ROOT / "research/shuang96_local_comparison.md").write_text("\n".join(lines) + "\n", encoding="utf8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
