"""Report the fixed32-to128 training expansion on a shared unseen80 worlds."""
from pathlib import Path
import hashlib
import json
import re
import subprocess
from compare import compare, markdown

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "results/v15_report"


def load(path):
    return json.loads((ROOT / path).read_text(encoding="utf8"))


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf8")


def save(name, rows):
    path = OUT / name
    dump(path / "summary.json", rows)
    return path


def record(name, old, new):
    result = compare(old, new)
    dump(OUT / (name+".json"), result)
    (OUT / (name+".md")).write_text(markdown(result), encoding="utf8")
    return result


def counts(paths, prefix):
    total = dict(attempts=0, rejects=0, late=0, guard_returns=0)
    files = [file for directory in paths for file in directory.rglob("solver_stderr.txt")]
    for file in files:
        match = re.search(prefix+r" attempts=(\d+) rejects=(\d+) late=(\d+) guard_returns=(\d+)", file.read_text())
        assert match, str(file)
        for key, value in zip(total, match.groups()):
            total[key] += int(value)
    return dict(total, runs=len(files))


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    frozen = load("research/v15_frozen_models.json")
    refs = ["v13_model_fast", "v14_mlp_A", "v14_mlp_B"]
    new_names = [r["version"]["name"] for r in frozen["models"]]
    all_names = refs+new_names
    all_runs = load("results/v15_train96_baseline/summary.json")+load("results/v15_train96_trace/summary.json")
    old = []
    for split in ["holdout", "confirmation"]:
        rows = load(f"results/v15_{split}_baseline/summary.json")
        assert len(rows) == 40
        all_runs += rows
        old += [dict(r, case=split+"/"+r["case"]) for r in rows]
    baseline80 = save("baseline80", old)
    resultsets, protocol = {}, []
    transcript = (ROOT / "results/v10_fix_input/large_huffman_protocol.in").read_bytes()
    expected = "".join(f"ANS {3000000 if t<=20 else 0}\nEND\n" for t in range(1,401)).encode("ascii")
    for name in all_names:
        version = load(f"versions/{name}/manifest.json")
        assert hashlib.sha256(Path(version["packed_source"]).read_bytes()).hexdigest() == version["packed_sha256"]
        assert hashlib.sha256(Path(version["executable"]).read_bytes()).hexdigest() == version["exe_sha256"]
        fresh, splits, directories = [], {}, []
        for split in ["holdout", "confirmation"]:
            directory = ROOT / f"results/v15_{split}_{name}"
            rows = load(str(directory / "summary.json"))
            assert len(rows) == 40 and {r["exe_sha256"] for r in rows} == {version["exe_sha256"]}
            directories.append(directory)
            all_runs += rows
            fresh += [dict(r, case=split+"/"+r["case"]) for r in rows]
            splits[split] = record(name+"_"+split, ROOT / f"results/v15_{split}_baseline", directory)["valid_range_summary"]
        combined = record(name+"_new80", baseline80, save(name, fresh))
        worst = min((r for r in combined["rows"] if r["profit_ratio"] is not None), key=lambda r:r["profit_ratio"])
        groupings = {}
        for row in combined["rows"]:
            group = re.sub(r"_\d+$", "", row["case"].split("/",1)[1])
            groupings.setdefault(group, []).append(row)
        profiles = {key: {"cases": len(rows), "baseline_profit": sum(r["baseline_profit"] for r in rows),
            "delta": sum(r["delta"] for r in rows), "up": sum(r["delta"]>0 for r in rows),
            "down": sum(r["delta"]<0 for r in rows)} for key, rows in groupings.items()}
        resultsets[name] = {"splits": splits, "new80": combined["valid_range_summary"], "worst": worst,
            "health": combined["candidate_health"], "profiles": profiles}
        if name in new_names:
            train_dir = ROOT / f"results/v15_train_{name}"
            training = load(str(train_dir / "summary.json"))
            assert len(training) == 128 and {r["exe_sha256"] for r in training} == {version["exe_sha256"]}
            all_runs += training
            resultsets[name]["train128"] = load(str(train_dir / "comparison.json"))["valid_range_summary"]
            resultsets[name]["training_gate_counts"] = counts([train_dir / "raw"], "V15_MODEL_POLICY")
            resultsets[name]["validation_gate_counts"] = counts(directories, "V15_MODEL_POLICY")
            aux = load(f"results/v15_aux_{name}/summary.json")
            assert len(aux) == 6 and {r["exe_sha256"] for r in aux} == {version["exe_sha256"]}
            all_runs += aux
            normalize = lambda rows:[dict(r,case=Path(r["input"]).parent.name+"/"+r["case"])for r in rows]
            auxiliary = record(name+"_aux6", save("aux_baseline", normalize(load("results/v13_aux_v12_scan_input_fix/summary.json"))),
                save(name+"_aux6", normalize(aux)))
            resultsets[name]["pressure4"] = auxiliary["valid_range_summary"]
            tested = subprocess.run([version["executable"]], input=transcript, capture_output=True, cwd=ROOT, timeout=20)
            assert tested.returncode == 0 and tested.stdout.replace(b"\r\n", b"\n") == expected
            assert re.fullmatch(rb"V15_MODEL_POLICY attempts=0 rejects=0 late=\d+ guard_returns=\d+\r?\n", tested.stderr)
            protocol.append({"name": name, "all400_answers_exact": True,
                "method": "Separate full direct protocol replay;not a TPJ-generated world"})
            version["validation"] = {"main_runs": len(training)+len(fresh)+len(aux),
                "audit_total": sum(r["audit_total"] for r in training+fresh+aux), "audit_errors": 0, "illegal_commands": 0,
                "max_cpu_seconds": max(r["solver_cpu_seconds"] for r in training+fresh+aux),
                "new80": combined["valid_range_summary"], "new80_worst": worst,
                "split_summary": splits, "pressure4": resultsets[name]["pressure4"],
                "large_protocol400_exact": True, "report": "research/v15_experiment.md"}
            version["local_selection_status"] = "Fixed training-expansion experiment;official score unknown"
            dump(ROOT / f"versions/{name}/manifest.json", version)
        elif name.startswith("v14_"):
            resultsets[name]["validation_gate_counts"] = counts(directories, "V14_MLP_POLICY")
    for name, reference in [("v15_A128_120", "v14_mlp_A"), ("v15_A128_steps", "v14_mlp_A"),
                            ("v15_B128_120", "v14_mlp_B"), ("v15_tree128", "v13_model_fast")]:
        resultsets[name]["vs_original_model"] = record(name+"_vs_original80", OUT / reference, OUT / name)["valid_range_summary"]
    resultsets["v15_A128_120"]["vs_same_updates"] = record("A120_vs_A4920", OUT / "v15_A128_steps", OUT / "v15_A128_120")["valid_range_summary"]
    # Extend each fixed old model's verification history without retraining it.
    historical = {}
    for name in refs:
        old_all, model_all = [], []
        rounds = ["v14", "v15"] if name != "v13_model_fast" else ["v13", "v14", "v15"]
        for stage in rounds:
            candidate = "v13_model_strict" if stage == "v13" else name
            for split in ["holdout", "confirmation"]:
                old_all += [dict(r, case=stage+"/"+split+"/"+r["case"]) for r in load(f"results/{stage}_{split}_baseline/summary.json")]
                model_all += [dict(r, case=stage+"/"+split+"/"+r["case"]) for r in load(f"results/{stage}_{split}_{candidate}/summary.json")]
        historical[name] = record(name+"_all_new_worlds", save(name+"_historical_baseline", old_all), save(name+"_historical", model_all))["valid_range_summary"]
    assert len(all_runs) == 1368 and all(r["ok"] and r["audit_errors"] == 0 and r["incidents"] == 0 for r in all_runs)
    health = {"runs": len(all_runs), "audit_total": sum(r["audit_total"] for r in all_runs),
        "audit_errors": 0, "illegal_commands": 0, "max_cpu_seconds": max(r["solver_cpu_seconds"] for r in all_runs),
        "max_peak_memory_bytes": max(r["solver_peak_memory_bytes"] for r in all_runs),
        "scope": "New96 baseline/trace192 + oldrefs320 + four packed refits(train512+new320+aux24). Historical records read only,not recounted"}
    release = load("results/final_manifest.json")
    for name in ["main.cpp", "submit.cpp", "build/main.exe", "build/submit.exe"]:
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == release["artifacts"][name]["sha256"]
    manifest = {"date": "2026-11-16", "dataset": "research/v15_dataset.json", "frozen": frozen,
        "comparisons": resultsets, "historical_verification": historical, "health": health,
        "protocol": protocol, "independent_review": "research/v15_independent_review.md",
        "official_defaults_unchanged": True, "official_submission_sent": False}
    dump(ROOT / "research/v15_experiment_manifest.json", manifest)
    lines = ["# V15：新增验证与训练32→128", "", "2026-11-16。本轮仅本地研究，正式99分默认文件不改，未提交。", "",
        "## 实验设计", "", "新增80个全新验证场景（40+40），所有旧/新模型使用同一输入。训练集保留旧32，新增96，即128世界；新增仍为原8个profile各12个新种子，最终每profile16世界，没有把旧验证集转作训练。194,313全流程中164,406条实际入场，原41,151+新123,255；逐流程账本、finish取整收入、128完整报告全部核对。每世界总权重相等，旧32恰占1/4。", "",
        "固定重训A/B的结构、seed、18特征、120epoch/Adam参数及原门槛；浅树结构和strict也不变。另A4920更新对照与旧A32完整拟合的Adam更新次数相同。所有4源统一冻结后才读新验证利润，全部进验证，不按训练收益重新挑门槛/模型。", "",
        "A120最终19320更新；A4920最终4920更新，约30完整epoch+90batch。每个新fold的A4920也固定4920，这不等于旧32折的预算；匹配的是最终模型Adam步数，不是精确CPU/样本呈现数。", "",
        "## 同一批新80场景", "", "| 方案 | 训练世界 | 新40总利润 | 确认40总利润 | 合计80 | 升/降/平 | 最差单例 |", "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    labels = {"v13_model_fast": "旧浅树", "v14_mlp_A": "旧网络A", "v14_mlp_B": "旧网络B",
        "v15_A128_120": "扩训A120epoch", "v15_B128_120": "扩训B120epoch", "v15_tree128": "扩训浅树", "v15_A128_steps": "扩训A固定4920步"}
    for name in all_names:
        r = resultsets[name]; v = r["new80"]
        lines.append(f"| {labels[name]} | {128 if name in new_names else 32} | {r['splits']['holdout']['total_profit_increase_pct']:+.4f}% | {r['splits']['confirmation']['total_profit_increase_pct']:+.4f}% | {v['total_profit_increase_pct']:+.4f}% | {v['improved']}/{v['regressed']}/{v['unchanged']} | {100*(r['worst']['profit_ratio']-1):+.2f}% |")
    lines += ["", "增幅均相对保留99调度参数的输入/扫描修复基线，不等于官方得分。基线非正用例不计算同比，但仍纳入总利润与绝对升降；完整范围检查/边界结果保留在JSON。", "",
        "## 扩训直接对比原模型", "", "| 扩训模型 | 同场相对原模型总利润 | 升/降/平 | 既有压力4例相对99策略 |", "| --- | ---: | ---: | ---: |"]
    for name in new_names:
        r = resultsets[name]; v = r["vs_original_model"]
        lines.append(f"| {labels[name]} | {v['total_profit_increase_pct']:+.4f}% | {v['improved']}/{v['regressed']}/{v['unchanged']} | {r['pressure4']['total_profit_increase_pct']:+.4f}% |")
    lines += ["", "压力4例和2短T原生样例属于既有开发/健康测试，未混入全新80。训练128的闭环利润只作诊断，没有决定哪些重训源进验证；所有模型的训练/验证门控尝试、拒绝和保险触发次数都在manifest中。", "",
        "## 旧模型追加验证历史", "", "| 固定旧模型 | 累计新世界数 | 合计总利润增幅 | 升/降/平 |", "| --- | ---: | ---: | ---: |"]
    for name in refs:
        v = historical[name]
        lines.append(f"| {labels[name]} | {v['case_count']} | {v['total_profit_increase_pct']:+.4f}% | {v['improved']}/{v['regressed']}/{v['unchanged']} |")
    lines += ["", "这些是同一固定策略多个新种子的追加验证，不是每一轮挑最好的策略拼接。V13浅树使用完整实现、后续精简实现在86次完整报告核对等价后复用。神经网络160新世界、浅树240新世界的场景组成不同，不拿跨表百分比作同场排名。", "",
        "## 核验与文件", "", f"本轮{health['runs']:,}次实际交互、{health['audit_total']:,}次对账全对、零非法指令；本机最高CPU{health['max_cpu_seconds']:.6f}s，计时仅作健康记录。新增4个实际packed程序各214次运行（128训练+80新验证+4压力+2样例），另各完整回放300万解码字符/600万hex的400条精确ANS协议；协议与非交互数值审计单列。", "",
        "所有源保留8MiB修复、直接整数扫描、原99参数、CPU保险、20k与预约原始字节回滚；源码打包逐token一致，编译O2/Wall/Wextra无警告。C++部署不增加网络参数个数；更多数据增加离线训练成本，预测器尺寸不随样本数增长。", "",
        "数据清单research/v15_dataset.json；训练及模型research/v15_models.json；独立审查research/v15_independent_review.md；完整逐例对比results/v15_report/。候选在versions/v15_*/，默认仍为正式99分。", ""]
    (ROOT / "research/v15_experiment.md").write_text("\n".join(lines), encoding="utf8")
    print(json.dumps({"health": health, "new80": {name: {"pct": v["new80"]["total_profit_increase_pct"],
        "up": v["new80"]["improved"], "down": v["new80"]["regressed"], "worst": v["worst"]["profit_ratio"]} for name,v in resultsets.items()},
        "historical": {name: {"n":v["case_count"],"pct":v["total_profit_increase_pct"]}for name,v in historical.items()}}))


if __name__ == "__main__":
    main()
