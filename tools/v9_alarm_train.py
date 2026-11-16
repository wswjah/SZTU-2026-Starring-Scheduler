"""Fit a small, world-grouped alarm survival tree from observational tapes."""
from pathlib import Path
import hashlib
import json
import re
import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score
from sklearn.model_selection import GroupKFold
from sklearn.tree import DecisionTreeRegressor

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "results/v9_alarm_model"
FEATURES = ["log_score3", "log_score8", "log_scoreW", "log_peak3", "log_peak8",
            "density8_relative", "density3_relative", "log_chars8", "log_lines8", "alarm_age"]
HORIZONS = np.asarray([3, 8, 16])


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf8")


def rolling_sum(a, window):
    prefix = np.concatenate([np.zeros_like(a[:1]), np.cumsum(a, axis=0)], axis=0)
    ends = np.arange(len(a)) + 1
    return prefix[ends] - prefix[np.maximum(0, ends-window)]


def rolling_peak(a, window):
    result = a.copy()
    for lag in range(1, window):
        result[lag:] = np.maximum(result[lag:], a[:-lag])
    return result


def read_world(path):
    with path.open(encoding="utf8") as stream:
        metadata = dict(part.split("=", 1) for part in stream.readline().split()[1:])
    frame = pd.read_csv(path, skiprows=1)
    T, M, W = [int(metadata[k]) for k in ["T", "M", "W"]]
    assert len(frame) == (T+1)*M
    assert np.array_equal(frame["tick"], np.repeat(np.arange(T+1), M))
    assert np.array_equal(frame["machine"], np.tile(np.arange(M), T+1))
    matrix = lambda name: frame[name].to_numpy().reshape(T+1, M)
    scores, chars, peaks, lines = [matrix(k) for k in ["alarm", "decoded_chars", "max_line_score", "loglines"]]
    s3, s8, sw = [rolling_sum(scores, k) for k in [3, 8, W]]
    c3, c8 = [rolling_sum(chars, k) for k in [3, 8]]
    p3, p8 = [rolling_peak(peaks, k) for k in [3, 8]]
    l8 = rolling_sum(lines, 8)
    total_score = np.cumsum(scores.sum(axis=1), dtype=np.float64)
    total_chars = np.cumsum(chars.sum(axis=1), dtype=np.float64)
    background = np.maximum(1e-6, total_score / (total_chars+1))[:, None]
    tick = np.arange(T+1)[:, None]
    last_alarm = np.maximum.accumulate(np.where(scores > 0, tick, -10000), axis=0)
    age = np.minimum(60, tick-last_alarm)
    features = np.stack([
        np.log1p(s3), np.log1p(s8), np.log1p(sw), np.log1p(p3), np.log1p(p8),
        np.minimum(100, s8/(c8+1)/background), np.minimum(100, s3/(c3+1)/background),
        np.log1p(c8), np.log1p(l8), age,
    ], axis=-1).astype(np.float32)
    assert np.isfinite(features).all()
    failures = matrix("fail")
    cumulative = np.cumsum(failures, axis=0)
    labels = np.stack([(cumulative[np.minimum(np.arange(T+1)+h, T)]-cumulative) > 0
                       for h in HORIZONS], axis=-1).astype(np.float64)
    # One common right-censoring mask preserves monotonic labels in every leaf.
    valid = ((tick >= 1) & (tick+16 <= T) & (matrix("up") == 1))
    assert np.all(labels[:, :, 0] <= labels[:, :, 1]) and np.all(labels[:, :, 1] <= labels[:, :, 2])
    return features[valid], labels[valid], {
        "T": T, "M": M, "W": W, "rows": int(valid.sum()), "failures": int(failures.sum()),
        "positive_rows": labels[valid].sum(axis=0).astype(int).tolist(),
        "raw_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }, features, valid


def make_tree():
    return DecisionTreeRegressor(max_depth=3, min_samples_leaf=500, random_state=915)


def metrics(y, predicted, weights):
    return {str(h): {"weighted_brier": float(np.average((y[:, i]-predicted[:, i])**2, weights=weights)),
                     "average_precision": float(average_precision_score(y[:, i], predicted[:, i], sample_weight=weights)),
                     "observed_event_probability": float(np.average(y[:, i], weights=weights)),
                     "mean_predicted_probability": float(np.average(predicted[:, i], weights=weights))}
            for i, h in enumerate(HORIZONS)}


def cpp_tree(model, background):
    tree = model.tree_
    ints = lambda a: ",".join(str(int(v)) for v in a)
    doubles = lambda a: ",".join(format(float(v), ".17g") for v in a)
    values = ",\n".join("{" + doubles(row[:, 0]) + "}" for row in tree.value)
    return f"""// Learned only from observed local train-world alarm tapes; horizons3/8/16.
static void v9Predict(const float* features,double* probabilities) {{
    static const int feature[]={{{ints(tree.feature)}}};
    static const int left[]={{{ints(tree.children_left)}}};
    static const int right[]={{{ints(tree.children_right)}}};
    static const double threshold[]={{{doubles(tree.threshold)}}};
    static const double value[][3]={{{values}}};
    int node=0;
    while(feature[node]>=0) node=features[feature[node]]<=threshold[node]?left[node]:right[node];
    F(k,3) probabilities[k]=value[node][k];
}}
static const double v9Background[3]={{{doubles(background)}}};
"""


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((ROOT / "research/v9_alarm_trace_manifest.json").read_text(encoding="utf8"))
    xs, ys, gs, worlds = [], [], [], []
    for index, entry in enumerate(sorted(manifest["tapes"], key=lambda r: r["case"])):
        x, y, info, _, _ = read_world(Path(entry["path"]))
        xs.append(x); ys.append(y); gs.append(np.full(len(y), index))
        worlds.append({"case": entry["case"], **info})
    x, y, groups = np.concatenate(xs), np.concatenate(ys), np.concatenate(gs)
    weights = np.ones(len(y))
    for index in np.unique(groups):
        weights[groups == index] /= (groups == index).sum()
    weights *= len(y)/len(worlds)
    oof, constant = np.empty_like(y), np.empty_like(y)
    fold_records = []
    for fold, (train, test) in enumerate(GroupKFold(4).split(x, y, groups)):
        model = make_tree().fit(x[train], y[train], sample_weight=weights[train])
        oof[test] = model.predict(x[test])
        constant[test] = np.average(y[train], axis=0, weights=weights[train])
        fold_records.append({"fold": fold, "train_worlds": [worlds[i]["case"] for i in np.unique(groups[train])],
                             "test_worlds": [worlds[i]["case"] for i in np.unique(groups[test])],
                             "tree_nodes": model.tree_.node_count})
        print(json.dumps({"fold_complete": fold, "rows": len(test)}), flush=True)
    assert np.all(oof[:, 0] <= oof[:, 1]+1e-12) and np.all(oof[:, 1] <= oof[:, 2]+1e-12)
    model = make_tree().fit(x, y, sample_weight=weights)
    background = np.average(y, axis=0, weights=weights)
    tree = model.tree_
    leaves = model.apply(x)
    leaf_stats = [{"leaf": int(leaf), "rows": int((leaves == leaf).sum()),
                   "world_count": int(len(np.unique(groups[leaves == leaf]))),
                   "positive_rows": y[leaves == leaf].sum(axis=0).astype(int).tolist(),
                   "probabilities": tree.value[leaf, :, 0].tolist(),
                   "note": "Positive rows overlap across preceding ticks; they are not independent failure events."}
                  for leaf in np.unique(leaves)]
    calibration = []
    boundaries = [0, .001, .005, .02, .1, .3, .7, 1.00001]
    for low, high in zip(boundaries[:-1], boundaries[1:]):
        mask = (oof[:, 1] >= low) & (oof[:, 1] < high)
        if mask.any():
            calibration.append({"horizon": 8, "lower": low, "upper": high, "rows": int(mask.sum()),
                                "worlds": int(len(np.unique(groups[mask]))),
                                "predicted": float(np.average(oof[mask, 1], weights=weights[mask])),
                                "observed": float(np.average(y[mask, 1], weights=weights[mask]))})
    per_world = [{"case": entry["case"], "model": metrics(y[groups == i], oof[groups == i], weights[groups == i]),
                  "constant": metrics(y[groups == i], constant[groups == i], weights[groups == i])}
                 for i, entry in enumerate(worlds)]
    record = {
        "features": FEATURES, "horizons": HORIZONS.tolist(), "rows": len(y), "worlds": worlds,
        "snapshot": "Current and previous observed logs only, after current events and before schedule",
        "labels": "UP machine at t, any FAIL in (t,t+h]; t>=1 and t+16<=T for all heads",
        "weights": "Each whole world has equal total training weight; no class balancing",
        "max_depth": 3, "min_samples_leaf": 500, "folds": fold_records,
        "grouped_oof": metrics(y, oof, weights), "grouped_constant": metrics(y, constant, weights),
        "per_world_oof": per_world, "oof_calibration8": calibration,
        "background_probability": background.tolist(), "leaf_stats": leaf_stats,
        "tree": {"feature": tree.feature.tolist(), "left": tree.children_left.tolist(),
                 "right": tree.children_right.tolist(), "threshold": tree.threshold.tolist(),
                 "value": tree.value[:, :, 0].tolist()},
        "feature_importance": dict(zip(FEATURES, model.feature_importances_.tolist())),
        "trace_manifest_sha256": hashlib.sha256((ROOT / "research/v9_alarm_trace_manifest.json").read_bytes()).hexdigest(),
        "future_values_used_at_runtime": False,
        "failure_cause": "FAIL includes collective power incidents; CSV cannot exactly separate individual causes",
    }
    dump(ROOT / "research/v9_alarm_model.json", record)
    cpp = cpp_tree(model, background)
    (ROOT / "candidates/v9_alarm_tree.inc").write_text(cpp, encoding="ascii")
    # Keep a bounded, deterministic snapshot for the runtime feature audit.
    samples = []
    for entry in [manifest["tapes"][0], manifest["tapes"][-1]]:
        _, _, info, features, _ = read_world(Path(entry["path"]))
        for tick, machine in [(1, 0), (10, 0), (50, 1), (100, 2), (info["T"]-1, info["M"]-1)]:
            samples.append({"case": entry["case"], "tick": tick, "machine": machine,
                            "features": features[tick, machine].tolist(),
                            "probabilities": model.predict(features[tick, machine].reshape(1, -1))[0].tolist()})
    dump(OUT / "feature_samples.json", samples)
    np.savez_compressed(OUT / "training_arrays.npz", x=x, y=y, groups=groups, weights=weights, oof=oof)
    print(json.dumps({"rows": len(y), "nodes": tree.node_count,
                      "features_used": [FEATURES[i] for i in sorted(set(tree.feature)-{-2})],
                      "oof": record["grouped_oof"], "constant": record["grouped_constant"]}), flush=True)


if __name__ == "__main__":
    main()
