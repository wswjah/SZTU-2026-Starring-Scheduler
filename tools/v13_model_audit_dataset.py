"""Read-only reconstruction of existing training arrays/OOF metrics, no refit."""
from pathlib import Path
import hashlib
import json
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parent.parent
model_path=ROOT/"research/v13_model_tree.json"
model=json.loads(model_path.read_text(encoding="utf8"))
data_path=ROOT/"results/v13_model_dataset/admitted.csv"
assert hashlib.sha256(data_path.read_bytes()).hexdigest()==model["dataset_sha256"]
frame=pd.read_csv(data_path);arrays=np.load(ROOT/"results/v13_model_fit/arrays.npz")
x,y,w,g,oof,constant=[arrays[k]for k in ["x","y","weights","groups","oof","constant"]]
assert len(frame)==len(x)==41151
assert np.array_equal(frame[[f"f{i}"for i in range(18)]].to_numpy(dtype=np.float32),x)
assert np.isfinite(x).all()and np.isfinite(y).all()
value=np.maximum(1,frame["value"].to_numpy(dtype=np.float64))
expected_y=np.column_stack([frame["earned"].to_numpy()/value,
    np.clip((frame["earned"].to_numpy()-frame["cost"].to_numpy())/value,-2,1)])
assert np.array_equal(y,expected_y)
worlds=sorted(frame["case"].unique());assert worlds==model["worlds"]and len(worlds)==32
assert np.array_equal(g,frame["case"].map({name:i for i,name in enumerate(worlds)}).to_numpy())
assert np.all(frame["seen"]==1)and np.all(frame["first_tick"]>=1)
world_weights=np.asarray([w[g==i].sum()for i in range(32)])
assert np.allclose(world_weights,world_weights[0],rtol=1e-12,atol=1e-12)
tested=[]
for fold in model["folds"]:
    train_names=set(fold["train_worlds"]);test_names=set(fold["test_worlds"])
    assert not train_names&test_names and train_names|test_names==set(worlds)
    train=np.isin(g,[worlds.index(name)for name in train_names]);test=np.isin(g,[worlds.index(name)for name in test_names])
    expected=np.average(y[train],axis=0,weights=w[train])
    assert np.array_equal(constant[test],np.broadcast_to(expected,constant[test].shape))
    tested+=list(test_names)
assert sorted(tested)==worlds
names=["earned_fraction_mse","net_fraction_mse"]
metrics={name:float(np.average((y[:,i]-oof[:,i])**2,weights=w))for i,name in enumerate(names)}
base_metrics={name:float(np.average((y[:,i]-constant[:,i])**2,weights=w))for i,name in enumerate(names)}
assert metrics==model["grouped_oof"]and base_metrics==model["grouped_trainonly_constant"]
dataset=json.loads((ROOT/"research/v13_model_dataset.json").read_text(encoding="utf8"))
assert len(dataset["worlds"])==32
assert all(row["ledger_exact"]and row["full_report_equal"]for row in dataset["worlds"])
record={"model_sha256":hashlib.sha256(model_path.read_bytes()).hexdigest(),"dataset_sha256":model["dataset_sha256"],
        "rows":len(frame),"worlds":len(worlds),"feature_columns_exact_float32":True,"targets_reconstructed_exact":True,
        "only_seen_admitted_rows":True,"all_world_weights_equal":True,"all_folds_world_disjoint":True,
        "all_worlds_held_out_exactly_once":True,"fold_constants_reconstructed_from_training_worlds_only":True,
        "oof_mse_reconstructed_exact":True,"author_recorded_32_ledgers_and_full_reports_exact":True,
        "metrics":metrics,"constant_metrics":base_metrics,"model_refits":0,"interaction_benchmarks_run":0,
        "limitation":"Ledger equality flags reuse author's reconciliation artifact; this script independently checks arrays, labels, group splits, weights and fold-constant arithmetic without recollecting or retraining."}
out=ROOT/"results/v13_model_audit/dataset.json";out.parent.mkdir(parents=True,exist_ok=True)
out.write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding="utf8")
print(json.dumps({"rows":len(frame),"worlds":len(worlds),"all_checks_passed":True,"model_refits":0,"interaction_benchmarks_run":0}))
