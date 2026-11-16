"""Compare every frozen V13 candidate on the two unchanged fresh splits."""
from pathlib import Path
import hashlib
import json
import re
import statistics
import subprocess
from compare import compare, markdown

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "results/v13_report"


def load(path):
    return json.loads((ROOT / path).read_text(encoding="utf8"))


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf8")


def save(name, rows):
    directory = OUT / name
    dump(directory / "summary.json", rows)
    return directory


def record(name, old, new):
    value = compare(old, new)
    dump(OUT / (name+".json"), value)
    (OUT / (name+".md")).write_text(markdown(value), encoding="utf8")
    return value


def main():
    selection = load("research/v13_frozen_selection.json")
    fine = load("results/v13_fine/summary.json")
    model = load("research/v13_model_screen.json")
    assert len(fine) == 24 and len(model["candidates"]) == 4
    OUT.mkdir(parents=True, exist_ok=True)
    comparisons, protocols, versions = {}, [], {}
    all_runs = load("results/v13_baseline_train32/summary.json")
    for row in fine:
        all_runs += load(f"results/v13_fine/{row['name']}/summary.json")
    for row in model["candidates"]:
        all_runs += load(f"results/v13_model_policies/{row['name']}/summary.json")
    all_runs += load("results/v13_model_trace/summary.json")
    all_runs += load("results/v13_model_disabled/summary.json")
    baselines = {}
    for split in ["holdout", "confirmation"]:
        baselines[split] = load(f"results/v13_{split}_baseline/summary.json")
        assert len(baselines[split]) == 40
        all_runs += baselines[split]
    baseline80 = [dict(r, case=split+"/"+r["case"]) for split in baselines for r in baselines[split]]
    baseline_dir = save("baseline80", baseline80)
    raw = (ROOT / "results/v10_fix_input/large_huffman_protocol.in").read_bytes()
    expected = "".join(f"ANS {3000000 if t <= 20 else 0}\nEND\n" for t in range(1, 401)).encode("ascii")
    for original in selection["candidates"]:
        name = original["name"]
        path = ROOT / f"versions/{name}/manifest.json"
        version = json.loads(path.read_text(encoding="utf8"))
        for field, sha in [("packed_source", "packed_sha256"), ("executable", "exe_sha256")]:
            assert hashlib.sha256(Path(version[field]).read_bytes()).hexdigest() == original[sha]
        fresh, split_values = [], {}
        for split in ["holdout", "confirmation"]:
            directory = ROOT / f"results/v13_{split}_{name}"
            rows = load(str(directory / "summary.json"))
            assert len(rows) == 40 and {r["exe_sha256"] for r in rows} == {original["exe_sha256"]}
            all_runs += rows
            fresh += [dict(r, case=split+"/"+r["case"]) for r in rows]
            value = record(name+"_"+split, ROOT / f"results/v13_{split}_baseline", directory)
            split_values[split] = value["valid_range_summary"]
        combined = record(name+"_fresh80", baseline_dir, save(name+"_fresh80", fresh))
        assert combined["valid_range_summary"]["case_count"] == 80
        new = {r["case"]: r for r in fresh}
        old = {r["case"]: r for r in baseline80}
        earned_norm = statistics.mean((new[k]["profit"]-old[k]["profit"])/max(1, old[k]["earned"]) for k in old)
        worst = min((r for r in combined["rows"] if r["profit_ratio"] is not None), key=lambda r: r["profit_ratio"])
        groups = {}
        for row in combined["rows"]:
            group = re.sub(r"_\d+$", "", row["case"].split("/", 1)[1])
            groups.setdefault(group, []).append(row)
        by_profile = {group: {"cases": len(rows), "baseline_profit": sum(r["baseline_profit"] for r in rows),
            "delta": sum(r["delta"] for r in rows), "up": sum(r["delta"] > 0 for r in rows),
            "down": sum(r["delta"] < 0 for r in rows)} for group, rows in groups.items()}
        attempts = rejects = late = returns = 0
        if name == "v13_model_strict":
            for split in ["holdout", "confirmation"]:
                directory = ROOT / f"results/v13_{split}_{name}"
                logs = list(directory.rglob("solver_stderr.txt"))
                assert len(logs) == 40
                for file in logs:
                    match = re.search(r"V13_MODEL_POLICY attempts=(\d+) rejects=(\d+) late=(\d+) guard_returns=(\d+)", file.read_text())
                    assert match, str(file)
                    a, b, c, d = map(int, match.groups())
                    attempts += a; rejects += b; late += c; returns += d
        protocol = subprocess.run([version["executable"]], input=raw, capture_output=True, cwd=ROOT, timeout=20)
        assert protocol.returncode == 0 and protocol.stdout.replace(b"\r\n", b"\n") == expected
        if name != "v13_model_strict":
            assert not protocol.stderr
        protocols.append({"name": name, "all400_answers_exact": True,
            "input_sha256": hashlib.sha256(raw).hexdigest(), "method": "Direct full protocol replay; not TPJ-generated world"})
        health = {"main_runs": 80, "audit_total": sum(r["audit_total"] for r in fresh),
            "audit_errors": sum(r["audit_errors"] for r in fresh), "illegal_commands": sum(r["incidents"] for r in fresh),
            "max_cpu_seconds": max(r["solver_cpu_seconds"] for r in fresh),
            "max_peak_memory_bytes": max(r["solver_peak_memory_bytes"] for r in fresh),
            "available_range_checks_passed": not combined["candidate_health"]["range_violations"]}
        version["validation"] = {**health, "split_summary": split_values,
            "fresh80": combined["valid_range_summary"], "worst": worst,
            "mean_profit_delta_per_baseline_earned": earned_norm,
            "large_protocol400_exact": True, "report": "research/v13_experiment.md"}
        version["local_selection_status"] = "Research candidate only; no automatic replacement of official99/default"
        dump(path, version)
        versions[name] = version
        comparisons[name] = {"splits": split_values, "fresh80": combined["valid_range_summary"],
            "worst": worst, "mean_profit_delta_per_baseline_earned": earned_norm,
            "by_profile": by_profile, "health": health,
            "model_decisions": {"attempts": attempts, "rejects": rejects, "late": late, "guard_returns": returns} if name == "v13_model_strict" else None}
    release = load("results/final_manifest.json")
    assert release["official_score"] == 99
    for field in ["main.cpp", "submit.cpp", "build/main.exe", "build/submit.exe"]:
        assert hashlib.sha256((ROOT / field).read_bytes()).hexdigest() == release["artifacts"][field]["sha256"]
    assert all(r["ok"] and r["audit_errors"] == 0 and r["incidents"] == 0 for r in all_runs)
    health = {"runs": len(all_runs), "audits": sum(r["audit_total"] for r in all_runs),
        "audit_errors": 0, "illegal_commands": 0,
        "max_cpu_seconds": max(r["solver_cpu_seconds"] for r in all_runs),
        "max_peak_memory_bytes": max(r["solver_peak_memory_bytes"] for r in all_runs),
        "scope": "32 new training and80 fresh worlds,1282 interactive runs expected; protocol and noninteractive harness counted separately"}
    assert len(all_runs) == 1282
    manifest = {"date": "2026-11-16", "official_best": 99,
        "last_verified_used": 6, "last_verified_remaining": 4, "official_submission_sent": False,
        "fine_trials": "results/v13_fine/summary.json", "model_trials": "research/v13_model_results.json",
        "selection": selection, "comparisons": comparisons, "health": health,
        "large_protocols": protocols, "independent_review": "research/v13_model_independent_review.md",
        "default_artifacts_unchanged": True}
    dump(ROOT / "research/v13_experiment_manifest.json", manifest)
    lines = ["# V13：细粒度调参和首入场小模型", "", "2026-11-16。正式最高99分，本轮未提交、未改根目录默认程序。所有候选保留8MiB输入修复、直接整数扫描、原CPU保险和20k指令限制。", "",
        "## 新数据与筛选", "", "本轮另生成32个训练世界（8种profile各4个种子），不用旧16例继续挑参。24组细调（18单轴、6预声明联合）加4个预声明模型策略均在训练32例实测。最后仅冻结3个候选，然后完整运行两个未参与训练/选参的新40例；第二个40例未按第一个的结果改参数。每份40例含32个新种子和8个分布变化场景。", "",
        "KILLK1.09是唯一训练总利润为正的细调，但22/32例下降；ADM.055训练总利润略降，却20/32例提高且最差较小。因此二者分别作为总量和广度候选，与模型strict共同复核；没有把训练排序视作可靠收益。", "",
        "## 冻结候选的新场景结果", "", "| 候选 | 训练32总利润 | 新40 | 确认40 | 新80合计 | 新80升/降/平 | 最差单例 |", "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    train = {"v13_kill109": next(r["valid_range"] for r in fine if r["name"] == "kill_109"),
             "v13_admit055": next(r["valid_range"] for r in fine if r["name"] == "admit_055"),
             "v13_model_strict": next(r["valid_range"] for r in model["candidates"] if r["name"] == "veto_strict")}
    for name, label in [("v13_kill109", "KILLK1.09"), ("v13_admit055", "ADM.055"), ("v13_model_strict", "小模型strict")]:
        v = comparisons[name]; a = v["splits"]["holdout"]; b = v["splits"]["confirmation"]; c = v["fresh80"]
        lines.append(f"| {label} | {train[name]['total_profit_increase_pct']:+.4f}% | {a['total_profit_increase_pct']:+.4f}% | {b['total_profit_increase_pct']:+.4f}% | {c['total_profit_increase_pct']:+.4f}% | {c['improved']}/{c['regressed']}/{c['unchanged']} | {100*(v['worst']['profit_ratio']-1):+.2f}% |")
    lines += ["", "上述80例全部通过现有可观测范围检查；缺失字段不作穷举证明。基线利润非正用例不计算利润比，但不丢弃，仍计入总利润/绝对差值/升降。总利润增幅也不是每例同比的等权平均，更不能换算为正式分数。", "",
        "## 小模型究竟学到了什么", "", "按当前99策略新采41,151条实际入场流程，逐流程CPU、启动、传输费用和最终收益均与judge对齐；诊断32例完整报告不变。按完整世界做4折验证，固定深度3、最小叶500，最终树15节点，只用了预计净收益比例、租户时长倍率两个特征。没有ID/种子或未来可见信息，C++内置树无需外部模型。", "",
        "预测收益MSE相对现有估价降低约10.24%，预测净收益仅降低约0.88%。改进预测精度不直接等于改进调度利润；训练标签是原策略接纳后的条件结果，没有被拒任务的反事实收益。世界分组交叉验证也不能代表所有隐藏分布。", "",
        "模型仅在未开始流程的首个完整RUN批次之前决定是否暂缓，不改运行中流程。四策略训练总利润：light0%、strict+0.0880%、收入混合25%−0.2226%、50%−0.3742%。light阈值小于所有叶的净收益，实际上全域不拒绝，32例完整报告与基线相同；它不能算一次有效利润改进。strict只会拒绝最低收益叶，门槛在相邻叶值之间细调仍是同一策略。", "",
        "独立审核对实际C++导出进行了72项float32特征和93个树向量精确对比，另检验预约/未初始化字段的原始字节回滚、已开始和失败重试流程、预算/预热原子限制。详细测试与局限见v13_model_independent_review.md。", "",
        "## 所有细调训练结果", "", "| 配置 | 修改 | 训练32总利润 | 升/降/平 |", "| --- | --- | ---: | ---: |"]
    for row in fine:
        v = row["valid_range"]
        lines.append(f"| {row['name']} | {row['parameters']} | {v['total_profit_increase_pct']:+.4f}% | {v['improved']}/{v['regressed']}/{v['unchanged']} |")
    lines += ["", "## 健康与交付", "",
        f"本轮共{health['runs']:,}次实际交互运行，{health['audits']:,}次对账全对，零非法指令。训练32与新80使用不同冻结种子。实际packed的3候选各80例均运行，另完整回放300万解码字符/600万hex字符协议，400条ANS均精确；直接协议回放与TPJ世界分别计数。",
        f"本机最大CPU{health['max_cpu_seconds']:.6f}s，最大峰值内存{health['max_peak_memory_bytes']:,}字节；并行策略筛选的计时仅作健康记录，不能当隔离卡常对比或正式时限保证。源码打包逐token等价，O2/Wall/Wextra无警告，文件头沿用99分版本，未新增头注释。", "",
        "根目录main.cpp/submit.cpp及默认exe哈希保持正式99分544054。未消耗正式提交；最后核验已用6次剩4次。正式最后1组失败原因仍未知。", "",
        "完整机器结果research/v13_experiment_manifest.json；逐例和profile结果results/v13_report/；模型训练与闭环research/v13_model_experiment.md。", ""]
    (ROOT / "research/v13_experiment.md").write_text("\n".join(lines), encoding="utf8")
    print(json.dumps({"health": health, "fresh80": {k: {"split40": v['splits']['holdout']['total_profit_increase_pct'],
        "confirmation40": v['splits']['confirmation']['total_profit_increase_pct'],
        "pct": v['fresh80']['total_profit_increase_pct'], "up": v['fresh80']['improved'],
        "down": v['fresh80']['regressed'], "worst": v['worst']['profit_ratio']} for k, v in comparisons.items()}}))


if __name__ == "__main__":
    main()
