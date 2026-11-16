"""Predeclared duration, learning and horizon neighbourhood from frozen99 V8."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import subprocess
import sys
from compare import compare, markdown

ROOT = Path(__file__).resolve().parent.parent
BASE = ROOT / "versions/v8_fine/main.cpp"
BASE_SHA = "b39a299e1983d1837393cdce80fce6ffbdaa209df170a7d865069df011514e3d"
BASELINE = ROOT / "results/v8_report/production_train"
OUT = ROOT / "results/v10_duration"
CONFIGS = {
    "prior_ratio_125": {"F0": 1.25}, "prior_ratio_175": {"F0": 1.75},
    "prior_weight_50": {"W0": 50}, "prior_weight_200": {"W0": 200},
    "tenant_shrink_15": {"W1": 15}, "tenant_shrink_60": {"W1": 60},
    "overdue_tail_015": {"OD": .15}, "overdue_tail_035": {"OD": .35},
    "path_growth_015": {"BB": .015}, "path_growth_045": {"BB": .045},
    "overhead_08": {"OVK": .8}, "overhead_12": {"OVK": 1.2},
    "horizon_10": {"HZ": 10}, "horizon_50": {"HZ": 50},
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf8")


def evaluate(name, changes):
    assert sha(BASE) == BASE_SHA
    source = BASE.read_text(encoding="utf8")
    for key, value in changes.items():
        source, count = re.subn(rf"PRM\({key},\s*[^)]+\)", f"PRM({key}, {value})", source)
        assert count == 1, key
    path = ROOT / "candidates/v10_duration" / f"{name}.cpp"
    assert not path.exists(), "Keep immutable experiment sources"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(source.encode("utf8"))
    exe = ROOT / "build" / f"v10_duration_{name}.exe"
    command = ["g++", "-std=c++17", "-O2", "-Wall", "-Wextra", str(path), "-o", str(exe)]
    compiled = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    assert compiled.returncode == 0 and not compiled.stderr.strip(), compiled.stderr
    dest = OUT / name
    command = [sys.executable, "tools/bench.py", "--exe", str(exe), "--cases", "cases/train",
               "--out", str(dest), "--workers", "1"]
    tested = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding="utf8")
    assert tested.returncode == 0, tested.stdout + tested.stderr
    value = compare(BASELINE, dest)
    dump(dest / "comparison.json", value)
    (dest / "comparison.md").write_text(markdown(value), encoding="utf8")
    rows = [r for r in value["rows"] if not r["baseline_range_violations"] and not r["candidate_range_violations"]]
    ratios = [r["profit_ratio"] for r in rows if r["profit_ratio"] is not None]
    worst = min((r for r in rows if r["profit_ratio"] is not None), key=lambda r: r["profit_ratio"])
    record = {"name": name, "parameters": changes, "source": str(path), "source_sha256": sha(path),
              "executable": str(exe), "exe_sha256": sha(exe), "base_source_sha256": BASE_SHA,
              "result_dir": str(dest), "valid_range": value["valid_range_summary"],
              "boundary": value["boundary_pressure_summary"], "all_health": value["candidate_health"],
              "worst_ratio": min(ratios), "worst_case": worst}
    dump(dest / "manifest.json", record)
    v = record["valid_range"]
    print(json.dumps({"name": name, "pct": v["total_profit_increase_pct"],
                      "equal_pct": v["equal_weight_increase_pct"], "median": v["median_profit_ratio"],
                      "up": v["improved"], "down": v["regressed"], "equal": v["unchanged"],
                      "worst": min(ratios), "max_cpu": record["all_health"]["max_cpu_seconds"]}), flush=True)
    return record


def report(records):
    dump(ROOT / "research/v10_duration_results.json", records)
    lines = ["# V10 时长、学习与末期参数筛选", "", "基于冻结正式99分V8，预先固定14个单轴配置；只用train16，不读取新留出集，不访问学校。范围内14例与2个日志边界large分列。Windows过程CPU时钟、署名、V6修复与其余参数保持原样。", "",
             "| 配置 | 修改 | 范围内总利润变化 | 等权平均变化 | 中位比 | 升/降/平 | 最差变化 | 边界总利润变化 | 最高CPU |",
             "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for row in records:
        v, b = row["valid_range"], row["boundary"]
        lines.append(f"| {row['name']} | {row['parameters']} | {v['total_profit_increase_pct']:+.3f}% | {v['equal_weight_increase_pct']:+.3f}% | {v['median_profit_ratio']:.5f} | {v['improved']}/{v['regressed']}/{v['unchanged']} | {100*(row['worst_ratio']-1):.2f}% | {b['total_profit_increase_pct']:+.3f}% | {row['all_health']['max_cpu_seconds']:.6f}s |")
    primary_runs = []
    for row in records:
        primary_runs += json.loads((Path(row["result_dir"]) / "summary.json").read_text(encoding="utf8"))
    assert all(r["ok"] for r in primary_runs)
    lines += ["", f"共{len(primary_runs)}次实际运行、{sum(r['audit_total'] for r in primary_runs):,}次对账全部正确、零非法指令。训练收益不是正式得分，尚未读取额外验证结果。所有结果与源码/二进制哈希完整保留在results/v10_duration和candidates/v10_duration。", ""]
    (ROOT / "research/v10_duration_review.md").write_text("\n".join(lines), encoding="utf8")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--screen", action="store_true")
    parser.add_argument("--combination", help="Name of one train-selected combination")
    parser.add_argument("--parameters", help="JSON changes for the one combination")
    args = parser.parse_args()
    if args.screen:
        assert not (ROOT / "research/v10_duration_plan.json").exists()
        dump(ROOT / "research/v10_duration_plan.json", {"base": str(BASE), "base_sha256": BASE_SHA,
             "configs": CONFIGS, "max_combinations": 1, "selection": "Train only, prefer positive aggregate with sensible equal-weight, median and worst-case behaviour; root owns validation.",
             "official_submission_authorized": False, "official_submission_sent": False})
        records = []
        for name, changes in CONFIGS.items():
            records.append(evaluate(name, changes))
            dump(OUT / "summary.json", records)
            report(records)
    if args.combination:
        assert not (OUT / "combination_manifest.json").exists(), "Only one combination is allowed"
        row = evaluate(args.combination, json.loads(args.parameters))
        dump(OUT / "combination_manifest.json", row)
        records = json.loads((OUT / "summary.json").read_text(encoding="utf8"))
        report(records + [row])


if __name__ == "__main__":
    main()
