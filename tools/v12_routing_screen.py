"""Exactly twelve predeclared routing/look-ahead single-axis policies."""
from pathlib import Path
import hashlib
import json
import re
import subprocess
import sys
from compare import compare, markdown

ROOT = Path(__file__).resolve().parent.parent
BASE = ROOT / "versions/v10_input_fix/main.cpp"
BASE_SHA = "b0854a70f54ccb47d287a48be37e447eb100147ca3f2e556c20c20498f705ae6"
BASELINE = ROOT / "results/v11_baseline_train"
OUT = ROOT / "results/v12_routing"
CONFIGS = {
    "pen_0": {"PEN": 0}, "pen_025": {"PEN": .25},
    "pen_05": {"PEN": .5}, "pen_0875": {"PEN": .875},
    "lookahead_0": {"LAK": 0}, "lookahead_025": {"LAK": .25},
    "lookahead_05": {"LAK": .5}, "lookahead_15": {"LAK": 1.5},
    "lookahead_2": {"LAK": 2}, "unknown_predecessor_0": {"GU": 0},
    "registry_rank_0": {"RF": 0}, "registry_rank_15": {"RF": 1.5},
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf8")


def evaluate(name, parameters):
    assert sha(BASE) == BASE_SHA
    original = source = BASE.read_text(encoding="utf8")
    for key, value in parameters.items():
        source, count = re.subn(rf"PRM\({key},\s*[^)]+\)", f"PRM({key}, {value})", source)
        assert count == 1, key
    normalize = lambda s: re.sub(r"PRM\((PEN|LAK|GU|RF),\s*[^)]+\)", r"PRM(\1,X)", s)
    assert normalize(source) == normalize(original)
    assert source.split("#include", 1)[0] == original.split("#include", 1)[0]
    assert "tok[1 << 23]" in source and "COMMAND_LIMIT = 20000" in source
    path = ROOT / "candidates/v12_routing" / f"{name}.cpp"
    assert not path.exists(), "Preserve experiment sources"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(source.encode("utf8"))
    exe = ROOT / "build" / f"v12_routing_{name}.exe"
    compiled = subprocess.run(["g++", "-std=c++17", "-O2", "-Wall", "-Wextra", str(path), "-o", str(exe)],
                              cwd=ROOT, capture_output=True, text=True)
    assert compiled.returncode == 0 and not compiled.stderr.strip(), compiled.stderr
    dest = OUT / name
    tested = subprocess.run([sys.executable, "tools/bench.py", "--exe", str(exe), "--cases", "cases/train",
                             "--out", str(dest), "--workers", "1"], cwd=ROOT, capture_output=True, text=True, encoding="utf8")
    assert tested.returncode == 0, tested.stdout + tested.stderr
    comparison = compare(BASELINE, dest)
    dump(dest / "comparison.json", comparison)
    (dest / "comparison.md").write_text(markdown(comparison), encoding="utf8")
    rows = [r for r in comparison["rows"] if not r["baseline_range_violations"] and not r["candidate_range_violations"]]
    worst = min((r for r in rows if r["profit_ratio"] is not None), key=lambda r: r["profit_ratio"])
    record = {"name": name, "parameters": parameters, "base": str(BASE), "base_sha256": BASE_SHA,
              "source": str(path), "source_sha256": sha(path), "executable": str(exe), "exe_sha256": sha(exe),
              "source_changes_only_declared_constant": True, "header_buffer_timeguard_budget_preserved": True,
              "scanner_added": False, "result_dir": str(dest), "valid_range": comparison["valid_range_summary"],
              "boundary": comparison["boundary_pressure_summary"], "all_health": comparison["candidate_health"],
              "worst": worst, "official_submission_sent": False}
    dump(dest / "manifest.json", record)
    v = record["valid_range"]
    print(json.dumps({"name": name, "pct": v["total_profit_increase_pct"], "equal_pct": v["equal_weight_increase_pct"],
                      "median": v["median_profit_ratio"], "up": v["improved"], "down": v["regressed"],
                      "equal": v["unchanged"], "worst": worst["profit_ratio"], "max_cpu": record["all_health"]["max_cpu_seconds"]}), flush=True)
    return record


def report(records):
    dump(ROOT / "research/v12_routing_results.json", records)
    runs = []
    for record in records:
        runs += json.loads((Path(record["result_dir"]) / "summary.json").read_text(encoding="utf8"))
    assert all(r["ok"] for r in runs)
    health = {"runs": len(runs), "audit_total": sum(r["audit_total"] for r in runs),
              "audit_errors": sum(r["audit_errors"] for r in runs),
              "illegal_commands": sum(r["incidents"] for r in runs),
              "max_cpu_seconds": max(r["solver_cpu_seconds"] for r in runs),
              "max_peak_memory_bytes": max(r["solver_peak_memory_bytes"] for r in runs),
              "all_runs_ok": all(r["ok"] for r in runs)}
    dump(ROOT / "research/v12_routing_health.json", health)
    lines = ["# V12 路由与前瞻参数粗筛", "", "2026-11-16。预先固定12个单轴配置，统一从未加scanner的v10_input_fix（8MiB输入修复、正式99分其余参数）出发，复用同口径未加scanner的results/v11_baseline_train。只使用train16，不读取V12新场景，不新增组合、额外轴或第13组。", "",
             "PEN调整离开前驱机架的额外延迟惩罚；LAK调整一层后继输入汇聚的前瞻代价。LAK=0跳过这部分计算，改变的是启发式目标与计算量，不把余下报价变为全局精确最优。GU=0仅关闭对尚未放置前驱的机架猜测，保留已运行/完成前驱的可见位置。RF仅调整机架预筛中的仓库费权重，实际候选报价与真实仓库账单没有被清零或乘权重。", "",
             "| 配置 | 修改 | 范围内总利润 | 等权平均变化 | 中位比 | 升/降/平 | 最差变化 | 边界总利润 | 最高CPU |", "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for record in records:
        v, b, worst = record["valid_range"], record["boundary"], record["worst"]
        lines.append(f"| {record['name']} | {record['parameters']} | {v['total_profit_increase_pct']:+.4f}% | {v['equal_weight_increase_pct']:+.4f}% | {v['median_profit_ratio']:.6f} | {v['improved']}/{v['regressed']}/{v['unchanged']} | {100*(worst['profit_ratio']-1):.2f}% | {b['total_profit_increase_pct']:+.4f}% | {record['all_health']['max_cpu_seconds']:.6f}s |")
    lines += ["", f"目前共{health['runs']}次实际运行、{health['audit_total']:,}次对账全部正确、零非法指令，最大本机CPU {health['max_cpu_seconds']:.6f}s，峰值内存{health['max_peak_memory_bytes']:,}字节。每组train16中的2个large日志量超保守3,000,000字符界限，保留原结果，但从范围内14例统计排除。", "",
              "所有候选仅改变声明的一项常量；原header、8MiB token、CPU时间保险、指令预算和真实对账实现不变。保留CPU保险，因此计算量变化可能经阶段降级改变动作；不能仅由总CPU<1秒判断完全没有降级，也不能将所有收益差异都归为纯策略改进。本轮未添加额外TS0配置，root统一安排后续控制与开发/独立验证。", "",
              "源码与二进制哈希、完整评测报告、每例CPU/内存、范围检查和最差场景均保存在candidates/v12_routing、results/v12_routing及research/v12_routing_results.json。没有修改默认或冻结版本，也没有访问学校或正式提交。", ""]
    (ROOT / "research/v12_routing_review.md").write_text("\n".join(lines), encoding="utf8")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf8")
    plan = ROOT / "research/v12_routing_plan.json"
    assert not plan.exists()
    dump(plan, {"date": "2026-11-16", "base": str(BASE), "base_sha256": BASE_SHA,
         "baseline": str(BASELINE), "scanner_added": False, "configs": CONFIGS,
         "fixed_before_outcomes": True, "maximum_variants": 12, "combinations_allowed": False,
         "training": "cases/train16 only,14 checked-range +2 large log boundary worlds",
         "official_submission_sent": False, "default_or_frozen_sources_modified": False})
    records = []
    for name, parameters in CONFIGS.items():
        records.append(evaluate(name, parameters))
        dump(OUT / "summary.json", records)
        report(records)


if __name__ == "__main__":
    main()
