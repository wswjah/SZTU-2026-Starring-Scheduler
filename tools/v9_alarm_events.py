"""Offline event-level audit of the existing alarm tree and OOF predictions.

No observations, model fitting, scheduling changes or benchmark reruns occur.
"""
from pathlib import Path
import hashlib
import json
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
MODEL_PATH = ROOT / "research/v9_alarm_model.json"
ARRAY_PATH = ROOT / "results/v9_alarm_model/training_arrays.npz"
TRACE_PATH = ROOT / "research/v9_alarm_trace_manifest.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def leaf_ids(x, tree):
    result = np.zeros(len(x), dtype=np.int32)
    pending = [(0, np.arange(len(x)))]
    while pending:
        node, indices = pending.pop()
        feature = tree["feature"][node]
        if feature < 0:
            result[indices] = node
        else:
            left = x[indices, feature] <= tree["threshold"][node]
            pending.append((tree["left"][node], indices[left]))
            pending.append((tree["right"][node], indices[~left]))
    return result


def main():
    model = json.loads(MODEL_PATH.read_text(encoding="utf8"))
    trace = json.loads(TRACE_PATH.read_text(encoding="utf8"))
    arrays = np.load(ARRAY_PATH)
    x, y, groups, weights, oof = [arrays[k] for k in ["x", "y", "groups", "weights", "oof"]]
    leaves = leaf_ids(x, model["tree"])
    final_prediction = np.asarray(model["tree"]["value"])[leaves]
    assert np.all(final_prediction[:, 0] <= final_prediction[:, 1])
    assert np.all(final_prediction[:, 1] <= final_prediction[:, 2])
    used_features = sorted(set(model["tree"]["feature"]) - {-2})
    assert used_features == [1, 2, 4]
    case_order = [entry["case"] for entry in model["worlds"]]
    tapes = {entry["case"]: entry for entry in trace["tapes"]}
    event_code = np.full(len(y), -1, dtype=np.int64)
    event_delay = np.full(len(y), 10000, dtype=np.int32)
    future_collective = np.zeros(len(y), dtype=bool)
    all_events, collective_events = set(), set()
    world_records, collective_clusters = [], []

    for group, case in enumerate(case_order):
        entry = tapes[case]
        frame = pd.read_csv(entry["path"], skiprows=1,
                            usecols=["tick", "machine", "up", "dc", "fail"])
        T, M = entry["T"], entry["M"]
        assert len(frame) == (T + 1) * M
        fail = frame["fail"].to_numpy().reshape(T + 1, M).astype(bool)
        up = frame["up"].to_numpy().reshape(T + 1, M)
        dc = frame["dc"].to_numpy().reshape(T + 1, M)[0]
        tick = np.arange(T + 1)[:, None]
        valid = (tick >= 1) & (tick + 16 <= T) & (up == 1)
        next_fail = np.full((T + 1, M), T + 1, dtype=np.int32)
        next_row = np.full(M, T + 1, dtype=np.int32)
        for t in range(T, -1, -1):
            next_fail[t] = next_row
            next_row = np.where(fail[t], t, next_row)
        collective = np.zeros_like(fail)
        for d in np.unique(dc):
            machines = np.where(dc == d)[0]
            threshold = max(3, (len(machines) + 1) // 2)
            for t in np.where(fail[:, machines].sum(axis=1) >= threshold)[0]:
                failed_machines = machines[fail[t, machines]]
                collective[t, failed_machines] = True
                collective_clusters.append({"case": case, "dc": int(d), "tick": int(t),
                                            "failed_machines": len(failed_machines),
                                            "dc_machines": len(machines), "threshold": threshold})
        for t, machine in zip(*np.where(fail)):
            code = (group << 32) | (int(machine) << 16) | int(t)
            all_events.add(code)
            if collective[t, machine]:
                collective_events.add(code)

        idx = np.where(groups == group)[0]
        assert len(idx) == valid.sum() == model["worlds"][group]["rows"]
        row_t, row_machine = np.where(valid)
        future = next_fail[valid]
        delay = future - row_t
        for h, column in [(3, 0), (8, 1), (16, 2)]:
            assert np.array_equal(delay <= h, y[idx, column].astype(bool))
        positive = delay <= 16
        codes = (np.int64(group) << 32) | (row_machine.astype(np.int64) << 16) | future
        event_code[idx] = np.where(positive, codes, -1)
        event_delay[idx] = delay
        future_collective[idx] = positive & collective[np.minimum(future, T), row_machine]
        world_records.append({"case": case, "valid_rows": len(idx),
                              "raw_failure_events": int(fail.sum()),
                              "positive_rows": y[idx].sum(axis=0).astype(int).tolist(),
                              "unique_first_future16_events": int(len(np.unique(codes[positive]))),
                              "suspected_collective_failure_events": int(collective.sum())})

    assert len(all_events) == trace["failures"] == 1266
    assert np.array_equal(event_delay <= 16, y[:, 2].astype(bool))
    unique_leaves = sorted(np.unique(leaves).tolist())
    leaf_records = []
    for leaf in unique_leaves:
        mask = leaves == leaf
        expected = next(row for row in model["leaf_stats"] if row["leaf"] == leaf)
        assert int(mask.sum()) == expected["rows"]
        assert np.array_equal(y[mask].sum(axis=0).astype(int), expected["positive_rows"])
        events_by_horizon = [int(len(np.unique(event_code[mask & (event_delay <= h)]))) for h in [3, 8, 16]]
        events16 = set(event_code[mask & (event_delay <= 16)].tolist())
        assert -1 not in events16
        positive_worlds = np.unique(groups[mask & (event_delay <= 16)])
        leaf_records.append({"leaf": leaf, "rows": int(mask.sum()),
                             "world_count": int(len(np.unique(groups[mask]))),
                             "positive_world_count16": int(len(positive_worlds)),
                             "positive_rows": y[mask].sum(axis=0).astype(int).tolist(),
                             "unique_first_future_failure_events": events_by_horizon,
                             "suspected_collective_events16": len(events16 & collective_events),
                             "other_or_unknown_events16": len(events16 - collective_events),
                             "final_fitted_probabilities": model["tree"]["value"][leaf],
                             "observed_event_probability_unweighted": y[mask].mean(axis=0).tolist()})

    calibration = []
    boundaries = [0, .001, .005, .02, .1, .3, .7, 1.00001]
    for low, high in zip(boundaries[:-1], boundaries[1:]):
        mask = (oof[:, 1] >= low) & (oof[:, 1] < high)
        if not mask.any():
            continue
        calibration.append({"lower": low, "upper": high, "rows": int(mask.sum()),
                            "row_fraction": float(mask.mean()),
                            "world_equal_weight_fraction": float(weights[mask].sum() / weights.sum()),
                            "worlds": int(len(np.unique(groups[mask]))),
                            "predicted_probability8": float(np.average(oof[mask, 1], weights=weights[mask])),
                            "observed_probability8": float(np.average(y[mask, 1], weights=weights[mask])),
                            "positive_rows8": int(y[mask, 1].sum()),
                            "unique_first_future8_failure_events": int(len(np.unique(event_code[mask & (event_delay <= 8)])))})

    high_risk = []
    for cutoff in [.02, .1, .3]:
        mask = oof[:, 1] >= cutoff
        high_risk.append({"cutoff8": cutoff, "rows": int(mask.sum()), "row_fraction": float(mask.mean()),
                          "world_equal_weight_fraction": float(weights[mask].sum() / weights.sum()),
                          "predicted_probability8": float(np.average(oof[mask, 1], weights=weights[mask])),
                          "observed_probability8": float(np.average(y[mask, 1], weights=weights[mask])),
                          "positive_rows8": int(y[mask, 1].sum()),
                          "unique_first_future8_failure_events": int(len(np.unique(event_code[mask & (event_delay <= 8)]))),
                          "unique_first_future16_failure_events": int(len(np.unique(event_code[mask & (event_delay <= 16)])))})

    per_world = []
    for entry in model["per_world_oof"]:
        by_horizon = {}
        for horizon in ["3", "8", "16"]:
            m, c = entry["model"][horizon], entry["constant"][horizon]
            by_horizon[horizon] = {"model_brier": m["weighted_brier"], "constant_brier": c["weighted_brier"],
                                   "brier_improvement_absolute": c["weighted_brier"] - m["weighted_brier"],
                                   "brier_improvement_relative": 1-m["weighted_brier"]/c["weighted_brier"],
                                   "model_ap": m["average_precision"], "constant_ap": c["average_precision"],
                                   "ap_improvement_absolute": m["average_precision"] - c["average_precision"]}
        per_world.append({"case": entry["case"], "horizons": by_horizon})

    record = {"sources": {"model": str(MODEL_PATH), "model_sha256": sha(MODEL_PATH),
                           "arrays": str(ARRAY_PATH), "arrays_sha256": sha(ARRAY_PATH)},
              "fit_performed": False, "new_observations_collected": False,
              "tree_used_feature_indices": used_features,
              "tree_used_features": [model["features"][i] for i in used_features],
              "rows": len(y), "positive_rows": y.sum(axis=0).astype(int).tolist(),
              "unique_recorded_machine_failure_events": len(all_events),
              "unique_first_future16_failure_events_represented": int(len(np.unique(event_code[event_code >= 0]))),
              "worlds": world_records, "leaves": leaf_records, "oof_calibration8": calibration,
              "oof_high_risk8": high_risk, "per_world_oof_improvement": per_world,
              "suspected_collective": {"heuristic": "same world, DC, tick has FAIL on >=max(3,ceil(DC machine count/2)) machines",
                                       "clusters": collective_clusters, "cluster_count": len(collective_clusters),
                                       "machine_failure_events": len(collective_events),
                                       "other_or_unknown_machine_failure_events": len(all_events - collective_events),
                                       "positive_rows16": int(((event_delay <= 16) & future_collective).sum()),
                                       "caveat": "Heuristic only: no DCDOWN tape, and smaller shared-cause clusters can remain in other/unknown. Distinct machine FAIL events are not statistically independent."},
              "caveats": ["Positive forecast rows overlap; one event can contribute up to16 prior rows.",
                          "A failure can be represented in multiple final leaves at different preceding times; leaf event counts do not form a partition.",
                          "OOF predictions come from four whole-world held-out folds. Final-tree leaf counts are in-sample diagnostics, not additional validation.",
                          "Future FAIL linkage and collective markers are offline audit labels only, never runtime features."]}
    (ROOT / "research/v9_alarm_events.json").write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf8")
    lines = ["# V9 告警树的事件级与OOF审计", "", "复用现有训练数组、分组OOF预测与最终树，没有重训或新增观测。按原始磁带重建当前在线且t+16<=T行的首个未来FAIL，逐元素确认3/8/16标签与原训练数组一致。", "",
             f"{len(y):,}条有效预测行对应3/8/16窗口正行分别为{record['positive_rows']}；原始磁带只有{len(all_events):,}个不同的(world,machine,FAIL tick)事件。不同机器FAIL事件仍可能有共同原因，不能称为独立样本。", "",
             "最终15节点树只使用索引1/2/4，即log_score8、log_scoreW、log_peak8；以下统计覆盖它的所有8个叶子。", "",
             "| 叶子 | 行数 | 世界数 | 16正行 | 16正世界数 | 不同未来FAIL数(3/8/16) | 疑似集体事件数(16) |", "| --- | ---: | ---: | ---: | ---: | --- | ---: |"]
    for entry in leaf_records:
        lines.append(f"| {entry['leaf']} | {entry['rows']:,} | {entry['world_count']} | {entry['positive_rows'][2]:,} | {entry['positive_world_count16']} | {entry['unique_first_future_failure_events']} | {entry['suspected_collective_events16']} |")
    lines += ["", "同一FAIL可能在前16个tick跨越多个叶子，所以各叶事件数不能相加当总事件数。叶统计是最终树的训练内诊断，独立预测证据来自按世界分组的OOF。", "",
              "| OOF 8tick预测概率区间 | 行数 | 行比例 | 世界数 | 预测概率 | 实际概率 | 不同未来8tick FAIL |", "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for entry in calibration:
        lines.append(f"| [{entry['lower']},{entry['upper']}) | {entry['rows']:,} | {100*entry['row_fraction']:.3f}% | {entry['worlds']} | {entry['predicted_probability8']:.4f} | {entry['observed_probability8']:.4f} | {entry['unique_first_future8_failure_events']} |")
    lines += ["", "| OOF高风险门槛(p8) | 行数 | 行比例 | 预测概率 | 实际概率 | 不同未来8tick FAIL |", "| --- | ---: | ---: | ---: | ---: | ---: |"]
    for entry in high_risk:
        lines.append(f"| >= {entry['cutoff8']} | {entry['rows']:,} | {100*entry['row_fraction']:.3f}% | {entry['predicted_probability8']:.4f} | {entry['observed_probability8']:.4f} | {entry['unique_first_future8_failure_events']} |")
    lines += ["", "| 世界 | 8tick Brier相对改善 | 8tick AP提高 |", "| --- | ---: | ---: |"]
    for entry in per_world:
        value = entry["horizons"]["8"]
        lines.append(f"| {entry['case']} | {100*value['brier_improvement_relative']:+.2f}% | {value['ap_improvement_absolute']:+.4f} |")
    lines += ["", f"按“同DC同tick至少max(3,该DC机器数一半向上取整)台FAIL”的事后启发式，识别{len(collective_clusters)}个疑似集体故障簇，涉及{len(collective_events)}个机器FAIL，其余{len(all_events-collective_events)}个归为其他/未知。",
              "磁带没有记录DCDOWN事件，因此此分类不能当真实故障原因；小规模共同原因故障也可能留在其他/未知。故障树可能预测的是单机前兆或共同故障前兆的混合，利润改进仍须闭环检验。未给只有正标签的原因分组编造可比较的总体Brier。", ""]
    (ROOT / "research/v9_alarm_events.md").write_text("\n".join(lines), encoding="utf8")
    print(json.dumps({"rows": len(y), "positive_rows": record["positive_rows"],
                      "unique_failures": len(all_events), "collective_clusters": len(collective_clusters),
                      "suspected_collective_events": len(collective_events), "high_risk8": high_risk,
                      "worlds_brier8_improved": sum(r["horizons"]["8"]["brier_improvement_absolute"] > 0 for r in per_world)}))


if __name__ == "__main__":
    main()
