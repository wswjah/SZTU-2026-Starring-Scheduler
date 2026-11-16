"""Exactly four predeclared PEN/RESV/warm-ranking interaction checks."""
from pathlib import Path
import hashlib
import json
import re
import subprocess
import sys
from compare import compare, markdown

ROOT = Path(__file__).resolve().parent.parent
BASELINE = ROOT / "results/v11_baseline_train"
BASES = {
    "fixed99": ("versions/v10_input_fix/main.cpp", "b0854a70f54ccb47d287a48be37e447eb100147ca3f2e556c20c20498f705ae6"),
    "warm_rank": ("candidates/v11_search/warm_rank.cpp", "dc5d793ac172a1a5b7359d2a6d9cd074c0a3b214b7ef3b4b657ddb46a5ec7e83"),
}
CONFIGS = {
    "pen075_resv15": ("fixed99", {"PEN": .75, "RESV": 15}),
    "warm_pen075": ("warm_rank", {"PEN": .75}),
    "warm_resv15": ("warm_rank", {"RESV": 15}),
    "warm_pen075_resv15": ("warm_rank", {"PEN": .75, "RESV": 15}),
}
OUT = ROOT / "results/v11_combinations"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf8")


def evaluate(name, base_name, changes):
    base, expected = BASES[base_name]
    base = ROOT / base
    assert sha(base) == expected
    original = source = base.read_text(encoding="utf8")
    for parameter, value in changes.items():
        source, count = re.subn(rf"PRM\({parameter},\s*[^)]+\)", f"PRM({parameter}, {value})", source)
        assert count == 1, parameter
    normalize = lambda s: re.sub(r"PRM\((PEN|RESV),\s*[^)]+\)", r"PRM(\1,X)", s)
    assert normalize(source) == normalize(original)
    assert source.split("#include", 1)[0] == original.split("#include", 1)[0]
    assert "tok[1 << 23]" in source and "COMMAND_LIMIT = 20000" in source
    if base_name == "warm_rank":
        assert "++c.ver;" in source
    path = ROOT / "candidates/v11_combinations" / f"{name}.cpp"
    assert not path.exists()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(source.encode("utf8"))
    exe = ROOT / "build" / f"v11_combination_{name}.exe"
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
    record = {"name": name, "base": str(base), "base_sha256": expected,
              "warm_rank": base_name == "warm_rank", "parameter_changes": changes,
              "source": str(path), "source_sha256": sha(path), "executable": str(exe), "exe_sha256": sha(exe),
              "original_header_unchanged": True, "buffer_timeguard_budget_preserved": True,
              "result_dir": str(dest), "valid_range": comparison["valid_range_summary"],
              "boundary": comparison["boundary_pressure_summary"], "all_health": comparison["candidate_health"],
              "worst": worst, "official_submission_sent": False}
    dump(dest / "manifest.json", record)
    v = record["valid_range"]
    print(json.dumps({"name": name, "pct": v["total_profit_increase_pct"], "equal_pct": v["equal_weight_increase_pct"],
                      "median": v["median_profit_ratio"], "up": v["improved"], "down": v["regressed"],
                      "equal": v["unchanged"], "worst": worst["profit_ratio"], "max_cpu": record["all_health"]["max_cpu_seconds"]}), flush=True)
    return record


def report(records):
    dump(ROOT / "research/v11_combinations_results.json", records)
    all_runs = []
    for record in records:
        all_runs += json.loads((Path(record["result_dir"]) / "summary.json").read_text(encoding="utf8"))
    assert all(r["ok"] for r in all_runs)
    health = {"runs": len(all_runs), "audit_total": sum(r["audit_total"] for r in all_runs),
              "audit_errors": sum(r["audit_errors"] for r in all_runs),
              "illegal_commands": sum(r["incidents"] for r in all_runs),
              "max_cpu_seconds": max(r["solver_cpu_seconds"] for r in all_runs)}
    dump(ROOT / "research/v11_combinations_health.json", health)
    lines = ["# V11 暖机器预筛、PEN与RESV互动检查", "", "在观察这些组合的结果之前固定4组，不增加其他轴或第五组。全部对照输入修复后的正式99分策略，train16中的14例范围内与2个large日志边界分别汇总。没有读取V11新场景、访问学校或提交。", "",
             "暖预筛版本以完整warm_rank源码为底座，包括FAIL时机器缓存版本递增的memo失效补丁。各组只额外修改PEN/RESV常量，原header、8MiB token容量、CPU保险、20k原子预算与原账本不变。", "",
             "| 组合 | 范围内总利润 | 等权平均变化 | 中位比 | 升/降/平 | 最差变化 | 边界总利润 | 最高CPU |", "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for record in records:
        v, b, worst = record["valid_range"], record["boundary"], record["worst"]
        lines.append(f"| {record['name']} | {v['total_profit_increase_pct']:+.4f}% | {v['equal_weight_increase_pct']:+.4f}% | {v['median_profit_ratio']:.6f} | {v['improved']}/{v['regressed']}/{v['unchanged']} | {100*(worst['profit_ratio']-1):.2f}% | {b['total_profit_increase_pct']:+.4f}% | {record['all_health']['max_cpu_seconds']:.6f}s |")
    lines += ["", f"共{health['runs']}次实跑、{health['audit_total']:,}次对账全对、0非法指令，本机最大CPU {health['max_cpu_seconds']:.6f}s。", "训练组合增益不能把单轴增益相加，也不能换算正式分数。CPU保险保持原逻辑，总CPU小于1秒不能证明从未阶段降级；先前warm_rank的large01 TS0控制已证实阶段保险能改变轨迹，本轮没有额外增加TS0组。root统一安排开发/独立验证。", ""]
    (ROOT / "research/v11_combinations_review.md").write_text("\n".join(lines), encoding="utf8")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf8")
    assert not (ROOT / "research/v11_combinations_plan.json").exists()
    dump(ROOT / "research/v11_combinations_plan.json", {"configs": CONFIGS, "bases": BASES,
         "case_set": "cases/train16 only", "baseline": str(BASELINE), "max_variants": 4,
         "extra_axis_or_variant_allowed": False, "official_submission_sent": False})
    records = []
    for name, (base_name, changes) in CONFIGS.items():
        records.append(evaluate(name, base_name, changes))
        dump(OUT / "summary.json", records)
        report(records)


if __name__ == "__main__":
    main()
