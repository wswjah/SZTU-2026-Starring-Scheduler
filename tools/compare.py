"""Compare reproducible practice-run summaries without treating profit as OJ score."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import statistics
import sys

DECIMAL_LOG_LIMIT = 3_000_000
BINARY_LOG_LIMIT = 3 * 1024 * 1024


def _scope_metrics(value):
    metrics = {key: value[key] for key in ["jobs", "audit_total", "logchars", "M"] if key in value}
    if "M" not in metrics:
        match = re.search(r"\bM=(\d+)", value.get("report", ""))
        if match:
            metrics["M"] = int(match.group(1))
    source = Path(value.get("input", ""))
    problems = []
    if source.is_file():
        data = source.read_bytes()
        if value.get("input_sha256") and hashlib.sha256(data).hexdigest() != value["input_sha256"]:
            return metrics, ["input_sha256 does not match current input file"]
        lines = data.decode("ascii", errors="replace").splitlines()
        if lines and lines[0].split()[0].isdigit():
            fields = list(map(int, lines[0].split()))
            metrics.update(dict(zip(["T", "D", "N", "R", "M", "K", "L", "I", "P", "W", "E"], fields)))
        else:
            config = {}
            for line in lines:
                parts = line.split()
                if len(parts) == 2:
                    try:
                        config[parts[0]] = float(parts[1])
                    except ValueError:
                        pass
            for output, parameter in [("T", "T"), ("D", "D"), ("K", "NT"), ("L", "NL"),
                                      ("I", "NI"), ("W", "W")]:
                if parameter in config:
                    metrics[output] = int(config[parameter])
            if {"D", "nodes_per_dc"} <= config.keys():
                metrics["N"] = int(config["D"] * config["nodes_per_dc"])
            if {"D", "racks_per_dc"} <= config.keys():
                metrics["R"] = int(config["D"] * config["racks_per_dc"])
            if {"p_noise", "p_signal"} <= config.keys():
                metrics["P"] = int(config["p_noise"] + config["p_signal"])
            manifest_path = source.parent / "manifest.json"
            if manifest_path.is_file():
                manifest = json.loads(manifest_path.read_text(encoding="utf8"))
                if isinstance(manifest, list):
                    for item in manifest:
                        if item.get("file") == source.name:
                            metrics.update(item.get("actual_initialization", {}))
                            break
    return metrics, problems


def load_results(source):
    source = Path(source)
    if source.is_dir():
        if (source / "summary.json").is_file():
            source = source / "summary.json"
        else:
            values = [json.loads(path.read_text(encoding="utf8"))
                      for path in sorted(source.rglob("result.json"))]
            return _index(values, source)
    values = json.loads(source.read_text(encoding="utf8"))
    if isinstance(values, dict):
        values = values.get("results", [values])
    return _index(values, source)


def _index(values, source):
    results = {}
    for value in values:
        name = value["case"]
        if name in results:
            raise ValueError(f"Duplicate case {name!r} in {source}; compare train/holdout separately")
        results[name] = value
    if not results:
        raise ValueError(f"No results in {source}")
    return results


def range_violations(value):
    metrics, problems = _scope_metrics(value)
    limits = {"T": 600, "D": 5, "N": 600, "R": 30, "M": 360, "E": 1000,
              "K": 200, "L": 400, "I": 120, "P": 10060, "W": 60,
              "jobs": 60000, "audit_total": 3500, "logchars": DECIMAL_LOG_LIMIT}
    problems += [f"{key}={metrics[key]} > {limit}" for key, limit in limits.items()
                 if key in metrics and metrics[key] > limit]
    for key, lower in [("T", 400), ("D", 2), ("K", 30), ("W", 20)]:
        if key in metrics and metrics[key] < lower:
            problems.append(f"{key}={metrics[key]} < {lower}")
    if metrics.get("logchars", 0) > BINARY_LOG_LIMIT:
        problems.append(f"logchars={metrics['logchars']} also > 3 MiB ({BINARY_LOG_LIMIT})")
    return problems


def _aggregate(rows):
    a = sum(row["baseline_profit"] for row in rows)
    b = sum(row["candidate_profit"] for row in rows)
    ratios = [row["profit_ratio"] for row in rows if row["profit_ratio"] is not None]
    return {
        "case_count": len(rows), "cases": [row["case"] for row in rows],
        "baseline_total_profit": a, "candidate_total_profit": b,
        "total_profit_delta": b-a, "total_profit_increase_pct": 100*(b/a-1) if a > 0 else None,
        "mean_profit_ratio": statistics.mean(ratios) if ratios else None,
        "median_profit_ratio": statistics.median(ratios) if ratios else None,
        "equal_weight_increase_pct": 100*(statistics.mean(ratios)-1) if ratios else None,
        "ratio_undefined_cases": [row["case"] for row in rows if row["profit_ratio"] is None],
        "improved": sum(row["delta"] > 0 for row in rows),
        "regressed": sum(row["delta"] < 0 for row in rows),
        "unchanged": sum(row["delta"] == 0 for row in rows),
    }


def _health(values):
    return {
        "all_runs_ok": all(value.get("ok") is True for value in values),
        "all_audits_correct": all(value.get("audit_errors") == 0 for value in values),
        "all_commands_legal": all(value.get("incidents") == 0 for value in values),
        "audit_errors": sum(value.get("audit_errors", 0) for value in values),
        "illegal_commands": sum(value.get("incidents", 0) for value in values),
        "max_cpu_seconds": max((value.get("solver_cpu_seconds", 0) for value in values), default=0),
        "max_peak_memory_bytes": max((value.get("solver_peak_memory_bytes", 0) for value in values), default=0),
        "over_one_second": [value["case"] for value in values if value.get("solver_cpu_seconds", 0) > 1],
        "range_violations": {value["case"]: range_violations(value) for value in values if range_violations(value)},
    }


def compare(baseline, candidate, allow_partial=False):
    old, new = load_results(baseline), load_results(candidate)
    if not allow_partial and old.keys() != new.keys():
        raise ValueError(f"Case sets differ: baseline only {sorted(old.keys()-new.keys())}; candidate only {sorted(new.keys()-old.keys())}")
    cases = sorted(old.keys() & new.keys())
    rows = []
    for name in cases:
        first, second = old[name], new[name]
        if first.get("input_sha256") and second.get("input_sha256") and first["input_sha256"] != second["input_sha256"]:
            raise ValueError(f"Input hashes differ for {name}; comparison is not reproducible")
        if first.get("judge_sha256") and second.get("judge_sha256") and first["judge_sha256"] != second["judge_sha256"]:
            raise ValueError(f"Judge hashes differ for {name}")
        a, b = first["profit"], second["profit"]
        rows.append({"case": name, "baseline_profit": a, "candidate_profit": b,
                     "delta": b-a, "profit_ratio": b/a if a > 0 else None,
                     "baseline_cpu_seconds": first.get("solver_cpu_seconds"),
                     "candidate_cpu_seconds": second.get("solver_cpu_seconds"),
                     "baseline_range_violations": range_violations(first),
                     "candidate_range_violations": range_violations(second)})
    valid = [row for row in rows if not row["baseline_range_violations"] and not row["candidate_range_violations"]]
    pressure = [row for row in rows if row not in valid]
    valid_summary = _aggregate(valid)
    valid_summary.update(baseline_health=_health([old[row["case"]] for row in valid]),
                         candidate_health=_health([new[row["case"]] for row in valid]))
    return {
        "baseline": str(Path(baseline).resolve()), "candidate": str(Path(candidate).resolve()),
        **_aggregate(rows),
        "scope_policy": {"log_limit": DECIMAL_LOG_LIMIT, "binary_log_limit_reference": BINARY_LOG_LIMIT,
                         "description": "Conservatively interpret 3 MB as 3,000,000 decoded characters. Exclude a case from valid_range_summary if either run exceeds any checked bound; retain all cases in overall totals.",
                         "static_evidence": "Parameter input and available actual initialization manifest; fields absent from both remain unchecked."},
        "valid_range_summary": valid_summary,
        "boundary_pressure_summary": _aggregate(pressure),
        "baseline_health": _health([old[name] for name in cases]),
        "candidate_health": _health([new[name] for name in cases]),
        "unmatched_baseline_cases": sorted(old.keys()-new.keys()),
        "unmatched_candidate_cases": sorted(new.keys()-old.keys()), "rows": rows,
    }


def markdown(result):
    percent = lambda value: "未定义" if value is None else f"{value:+.2f}%"
    ratio = lambda value: "未定义" if value is None else f"{value:.4f}"
    old, new = result["baseline_health"], result["candidate_health"]
    valid = result["valid_range_summary"]
    text = ["# 本地利润对比", "", "本地生成场景的利润差异不等于 OJ 分数变化。", "",
        f"比较 {result['case_count']} 例；提升 {result['improved']} 例、下降 {result['regressed']} 例、持平 {result['unchanged']} 例。", "",
        f"日志保守按 3 MB = {DECIMAL_LOG_LIMIT:,} 个解码字符核验，同时标出超过 3 MiB = {BINARY_LOG_LIMIT:,} 的情况。边界压力例保留在全部结果中，另从范围内汇总排除。", "",
        f"已核验范围内共 {valid['case_count']} 例：利润 {valid['baseline_total_profit']:,} → {valid['candidate_total_profit']:,}（{percent(valid['total_profit_increase_pct'])}），等权平均利润比 {ratio(valid['mean_profit_ratio'])}，中位比 {ratio(valid['median_profit_ratio'])}；提升 {valid['improved']}、下降 {valid['regressed']}、持平 {valid['unchanged']}。", "",
        "以下表格为全部结果（含边界压力例）；完整静态边数等信息缺失时不声称已核验该字段。", "",
        "| 指标 | 基线 | 候选 |", "| --- | ---: | ---: |",
        f"| 总利润 | {result['baseline_total_profit']:,} | {result['candidate_total_profit']:,} |",
        f"| 总利润增幅 | — | {percent(result['total_profit_increase_pct'])} |",
        f"| 各例等权平均利润比 | 1 | {ratio(result['mean_profit_ratio'])} |",
        f"| 各例利润比中位数 | 1 | {ratio(result['median_profit_ratio'])} |",
        f"| 对账错误 | {old['audit_errors']} | {new['audit_errors']} |",
        f"| 非法指令 | {old['illegal_commands']} | {new['illegal_commands']} |",
        f"| 最大本机 CPU 秒数 | {old['max_cpu_seconds']:.4f} | {new['max_cpu_seconds']:.4f} |",
        f"| 最大峰值内存 MiB | {old['max_peak_memory_bytes']/1024**2:.2f} | {new['max_peak_memory_bytes']/1024**2:.2f} |", ""]
    if result["ratio_undefined_cases"]:
        text += ["基线利润非正的用例不计算利润比，仍计入总利润：" + ", ".join(result["ratio_undefined_cases"]), ""]
    for label, health in [("基线", old), ("候选", new)]:
        if not health["all_runs_ok"]:
            text += [f"{label}存在失败或缺失验证的运行，须检查原始结果。", ""]
        if health["over_one_second"]:
            text += [f"{label}本机 CPU 超过 1 秒：" + ", ".join(health["over_one_second"]), ""]
        if health["range_violations"]:
            text += [f"{label}存在边界或范围外压力数据（保留在全部统计，从范围内汇总排除）：", ""]
            for name, violations in health["range_violations"].items():
                text.append(f"- {name}: " + "; ".join(violations))
            text.append("")
    text += ["| 用例 | 基线利润 | 候选利润 | 利润变化 | 候选 CPU 秒 |",
             "| --- | ---: | ---: | ---: | ---: |"]
    for row in result["rows"]:
        gain = None if row["profit_ratio"] is None else 100*(row["profit_ratio"]-1)
        cpu = row["candidate_cpu_seconds"]
        text.append(f"| {row['case']} | {row['baseline_profit']:,} | {row['candidate_profit']:,} | {percent(gain)} | {cpu:.4f} |" if cpu is not None else f"| {row['case']} | {row['baseline_profit']:,} | {row['candidate_profit']:,} | {percent(gain)} | 未测量 |")
    return "\n".join(text) + "\n"


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline")
    parser.add_argument("candidate")
    parser.add_argument("--json", type=Path, dest="json_path")
    parser.add_argument("--md", type=Path, dest="markdown_path")
    parser.add_argument("--allow-partial", action="store_true")
    args = parser.parse_args()
    result = compare(args.baseline, args.candidate, args.allow_partial)
    report = markdown(result)
    for path, data in [(args.json_path, json.dumps(result, ensure_ascii=False, indent=2)),
                       (args.markdown_path, report)]:
        if path:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(data, encoding="utf8")
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
