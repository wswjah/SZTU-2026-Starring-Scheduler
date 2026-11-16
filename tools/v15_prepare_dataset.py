"""Reconcile fixed-policy traces and build the nested32+96 training dataset."""
from pathlib import Path
import csv
import hashlib
import json
import numpy as np
from compare import range_violations
from v13_model_common import ROOT, FEATURES


def load(path):
    return json.loads((ROOT / path).read_text(encoding="utf8"))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf8")


def parse_value(key, value):
    if key == "case":
        return value
    return float(value) if key.startswith("f") and key[1:].isdigit() else int(value)


def csv_rows(path):
    with path.open(newline="", encoding="utf8") as stream:
        return [{key: parse_value(key, value) for key, value in row.items()}
                for row in csv.DictReader(stream)]


def reconcile(prefix, baseline_path, trace_path, cases_path, count, baseline_sha, trace_sha):
    baseline_rows = load(baseline_path+"/summary.json")
    trace_rows = load(trace_path+"/summary.json")
    baseline = {r["case"]: r for r in baseline_rows}
    trace = {r["case"]: r for r in trace_rows}
    manifest = load(cases_path+"/manifest.json")
    inputs = {Path(row["file"]).stem: row for row in manifest}
    assert len(baseline) == len(trace) == len(inputs) == count
    assert baseline.keys() == trace.keys() == inputs.keys()
    assert {r["exe_sha256"] for r in baseline_rows} == {baseline_sha}
    assert {r["exe_sha256"] for r in trace_rows} == {trace_sha}
    all_rows, records = [], []
    for case in sorted(trace):
        run, control = trace[case], baseline[case]
        assert run["ok"] and control["ok"]
        assert run["judge_sha256"] == control["judge_sha256"]
        assert run["input_sha256"] == control["input_sha256"] == inputs[case]["sha256"]
        assert sha(run["input"]) == run["input_sha256"]
        assert run["report"] == control["report"], (prefix, case, "observational trace changed full report")
        log = Path(run["run_dir"]) / "solver_stderr.txt"
        lines = log.read_text(encoding="utf8").splitlines()
        metadata = [line for line in lines if line.startswith("V13_MODEL_META,")]
        headers = [line for line in lines if line.startswith("V13_MODEL_HEADER,")]
        assert len(metadata) == len(headers) == 1
        meta = dict(item.split("=", 1) for item in metadata[0].split(",")[1:])
        header = headers[0].split(",")[1:]
        values = [line.split(",")[1:] for line in lines if line.startswith("V13_MODEL,")]
        assert len(values) == int(meta["flows"]) and all(len(row) == len(header) for row in values)
        rows = [{key: parse_value(key, value) for key, value in zip(header, row)} for row in values]
        assert [r["flow"] for r in rows] == list(range(len(rows)))
        for row in rows:
            assert bool(row["seen"]) == (row["runs"] > 0)
            assert row["cost"] == row["run"]+row["pull"]+row["net"]
            assert row["seen"] or row["cost"] == row["earned"] == 0
            earned = 0
            if 0 <= row["finish"] <= int(meta["T"]):
                if row["finish"] <= row["deadline"]:
                    earned = row["value"]
                elif row["finish"] < row["deadline"]+row["grace"]:
                    earned = row["value"]*(row["deadline"]+row["grace"]-row["finish"])//row["grace"]
            assert earned == row["earned"], (prefix, case, row["flow"], "finish revenue")
        for key in ["earned", "cost", "run", "pull", "net"]:
            assert sum(r[key] for r in rows) == run[key], (prefix, case, key)
        assert sum(r["earned"]-r["cost"] for r in rows) == run["profit"]
        all_rows += [dict(case=prefix+"/"+case, T=int(meta["T"]), **row) for row in rows]
        records.append({"case": prefix+"/"+case, "input": run["input"], "input_sha256": run["input_sha256"],
            "flows": len(rows), "admitted": sum(r["seen"] for r in rows),
            "ledger_exact": True, "full_report_equal": True,
            "late": int(meta["late"]), "guard_returns": int(meta["guard_returns"]),
            "trace_sha256": sha(log), "trace_result": str(Path(run["run_dir"]) / "result.json"),
            "range_violations": range_violations(run)})
    return all_rows, records, baseline_rows, trace_rows


def main():
    output = ROOT / "results/v15_model_dataset"
    assert not output.exists(), "Do not silently replace a frozen training dataset"
    assert not (ROOT / "research/v15_dataset.json").exists()
    version = load("versions/v12_scan_input_fix/manifest.json")
    trace = load("research/v13_model_trace_manifest.json")
    assert sha(version["executable"]) == version["exe_sha256"]
    assert sha(trace["executable"]) == trace["exe_sha256"]
    assert sha(trace["source"]) == trace["source_sha256"]
    old_tree = load("research/v13_model_tree.json")
    old_admitted_path = ROOT / "results/v13_model_dataset/admitted.csv"
    assert sha(old_admitted_path) == old_tree["dataset_sha256"]
    old, old_worlds, old_base, old_trace = reconcile("v13", "results/v13_baseline_train32",
        "results/v13_model_trace", "cases/v13_train32", 32, version["exe_sha256"], trace["exe_sha256"])
    new, new_worlds, new_base, new_trace = reconcile("v15", "results/v15_train96_baseline",
        "results/v15_train96_trace", "cases/v15_train96", 96, version["exe_sha256"], trace["exe_sha256"])
    # The nested old data are preserved numerically rather than reinterpreted.
    old_all_csv = csv_rows(ROOT / "results/v13_model_dataset/all_flows.csv")
    old_admitted_csv = csv_rows(old_admitted_path)
    old_unprefixed = [dict(row, case=row["case"].split("/", 1)[1]) for row in old]
    assert old_unprefixed == old_all_csv
    assert [row for row in old_unprefixed if row["seen"]] == old_admitted_csv
    rows = old+new
    admitted = [row for row in rows if row["seen"]]
    world_names = sorted({row["case"] for row in rows})
    assert len(world_names) == 128 and len({row["case"] for row in admitted}) == 128
    indexes = {world: i for i, world in enumerate(world_names)}
    x = np.asarray([[row[f"f{i}"] for i in range(len(FEATURES))] for row in admitted], dtype=np.float32)
    value = np.maximum(1, np.asarray([row["value"] for row in admitted], dtype=np.float64))
    earned = np.asarray([row["earned"] for row in admitted], dtype=np.float64)
    cost = np.asarray([row["cost"] for row in admitted], dtype=np.float64)
    y = np.column_stack([earned/value, np.clip((earned-cost)/value, -2, 1)])
    groups = np.asarray([indexes[row["case"]] for row in admitted], dtype=np.int64)
    counts = np.bincount(groups, minlength=128)
    weights = len(admitted)/128/counts[groups]
    assert np.isfinite(x).all() and np.isfinite(y).all()
    assert np.allclose(np.bincount(groups, weights=weights), len(admitted)/128, rtol=1e-12)
    assert np.isclose(weights.mean(), 1, rtol=1e-12)
    output.mkdir(parents=True)
    for label, selected in [("all_flows", rows), ("admitted", admitted)]:
        with (output / (label+".csv")).open("w", newline="", encoding="utf8") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader(); writer.writerows(selected)
    np.savez_compressed(output / "arrays.npz", x=x, y=y, groups=groups, weights=weights,
        world_names=np.asarray(world_names), worlds=np.asarray(world_names))
    new_runs = new_base+new_trace
    record = {"date": "2026-11-16", "base_worlds": 32, "added_worlds": 96, "combined_worlds": 128,
        "all_flows": len(rows), "admitted": len(admitted), "old_admitted": len(old_admitted_csv),
        "new_admitted": sum(row["seen"] for row in new), "feature_names": FEATURES,
        "world_names": world_names, "world_records": old_worlds+new_worlds,
        "group_to_case": {str(i): world for i, world in enumerate(world_names)},
        "weighting": "Equal total admitted-flow weight per world;weights mean1;128 unique prefixed world keys",
        "world_weight_totals": np.bincount(groups, weights=weights).tolist(),
        "old_data_preserved_numerically": True, "all128_ledgers_exact": True,
        "all128_full_reports_equal": True, "never_started_used_as_negative_labels": False,
        "fresh_validation_accessed": False, "official_submission_sent": False,
        "dataset": str(output / "admitted.csv"), "dataset_sha256": sha(output / "admitted.csv"),
        "all_flows_csv": str(output / "all_flows.csv"), "all_flows_sha256": sha(output / "all_flows.csv"),
        "arrays": str(output / "arrays.npz"), "arrays_sha256": sha(output / "arrays.npz"),
        "old_admitted_sha256": sha(old_admitted_path),
        "new_cases_manifest_sha256": sha(ROOT / "cases/v15_train96/manifest.json"),
        "trace_source_sha256": trace["source_sha256"], "trace_exe_sha256": trace["exe_sha256"],
        "baseline_exe_sha256": version["exe_sha256"],
        "health": {"new_interactive_runs": len(new_runs), "new_interactive_audits": sum(r["audit_total"] for r in new_runs),
            "audit_errors": sum(r["audit_errors"] for r in new_runs), "illegal_commands": sum(r["incidents"] for r in new_runs),
            "all_runs_ok": all(r["ok"] for r in new_runs),
            "max_cpu_seconds": max(r["solver_cpu_seconds"] for r in new_runs),
            "max_peak_memory_bytes": max(r["solver_peak_memory_bytes"] for r in new_runs),
            "trace_late": sum(row["late"] for row in new_worlds),
            "trace_guard_returns": sum(row["guard_returns"] for row in new_worlds),
            "range_violations": {row["case"]: row["range_violations"] for row in new_worlds if row["range_violations"]}},
        "evidence_reused": "Original32 trace/baseline reports and CSV independently reread;new96 paired observations192 actual runs"}
    dump(ROOT / "research/v15_dataset.json", record)
    print(json.dumps({key: record[key] for key in ["combined_worlds", "all_flows", "admitted", "old_admitted", "new_admitted", "dataset_sha256", "arrays_sha256", "health"]}))


if __name__ == "__main__":
    main()
