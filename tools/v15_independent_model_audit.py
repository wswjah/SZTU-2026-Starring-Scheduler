"""Read-only verification of expanded training budgets,fold stats,export and gates."""
from pathlib import Path
import hashlib
import json
import math
import re
import numpy as np
from v14_mlp_independent_audit import forward,stats,mse,cpp_array,scalar_forward

ROOT=Path(__file__).resolve().parent.parent


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def budget(rows,settings,record):
    batches=math.ceil(rows/1024)
    if settings["steps"]is None:
        steps=settings["epochs"]*batches;started=full=settings["epochs"];presentations=rows*full
    else:
        steps=settings["steps"];full,remainder=divmod(steps,batches)
        started=full+bool(remainder);presentations=full*rows+remainder*1024
    assert record["optimizer_updates"]==steps
    assert record["epochs_started"]==started and record["full_epochs_completed"]==full
    assert record["sample_presentations"]==presentations
    return {"training_rows":rows,"batches_per_epoch":batches,"optimizer_updates":steps,
            "epochs_started":started,"full_epochs_completed":full,"sample_presentations":presentations}


def tree_forward(tree,x):
    result=np.zeros((len(x),2));leaves=np.zeros(len(x),dtype=np.int32);seen=set()
    pending=[(0,np.arange(len(x)))];depths=[(0,0)]
    while pending:
        node,indexes=pending.pop();assert node not in seen;seen.add(node)
        feature=tree["feature"][node]
        if feature<0:
            result[indexes]=tree["value"][node];leaves[indexes]=node
        else:
            assert 0<=feature<18
            # float32 features must compare against the exported double threshold.
            choose=x[indexes,feature].astype(np.float64)<=float(tree["threshold"][node])
            pending.append((tree["left"][node],indexes[choose]));pending.append((tree["right"][node],indexes[~choose]))
    assert seen==set(range(len(tree["feature"])))
    return result,leaves


def tree_literals(code,tree):
    for name,field in [("feature","feature"),("left","left"),("right","right")]:
        # left/right share a C++ declaration: "int left[]={...},right[]={...}".
        text=re.search(r"\b"+name+r"\[\]=\{([^}]+)\}",code).group(1)
        assert [int(v)for v in text.split(",")]==tree[field]
    text=re.search(r"static const double threshold\[\]=\{([^}]+)\}",code).group(1)
    assert [float(v)for v in text.split(",")]==tree["threshold"]
    text=re.search(r"static const double value\[\]\[2\]=\{(.*?)\};",code,re.S).group(1)
    values=[float(v)for v in text.replace("{","").replace("}","").split(",")]
    assert np.array_equal(np.asarray(values).reshape(-1,2),np.asarray(tree["value"]))


def main():
    plan_path=ROOT/"research/v15_training_plan.json";plan=json.loads(plan_path.read_text(encoding="utf8"))
    dataset=json.loads((ROOT/"research/v15_dataset.json").read_text(encoding="utf8"))
    path=ROOT/"results/v15_model_dataset/arrays.npz";assert sha(path)==dataset["arrays_sha256"]
    arrays=np.load(path);x=arrays["x"].astype(np.float64);y=arrays["y"];weights=arrays["weights"];groups=arrays["groups"]
    worlds=arrays["world_names"].astype(str).tolist();assert len(worlds)==128
    inputs=json.loads((ROOT/"research/v15_training_inputs.json").read_text(encoding="utf8"))
    assert inputs["arrays_sha256"]==dataset["arrays_sha256"]and inputs["plan_sha256"]==sha(plan_path)
    assert inputs["worlds"]==worlds and inputs["family_world_counts"]=={"v13":32,"v15":96}
    records=[]
    for name,settings in plan["models"].items():
        model_path=ROOT/f"research/v15_{name}.json";model=json.loads(model_path.read_text(encoding="utf8"))
        assert model["settings"]==settings and model["inputs"]==inputs
        saved=np.load(ROOT/f"results/v15_fit/{name}_predictions.npz")
        tested=[];fold_records=[]
        for fold in model["folds"]:
            train_worlds=set(fold["train_worlds"]);test_worlds=set(fold["test_worlds"])
            assert not(train_worlds&test_worlds)and train_worlds|test_worlds==set(worlds)
            train=np.isin(groups,[worlds.index(w)for w in train_worlds]);test=np.isin(groups,[worlds.index(w)for w in test_worlds])
            constant=np.average(y[train],axis=0,weights=weights[train])
            assert np.array_equal(saved["constant"][test],np.broadcast_to(constant,saved["constant"][test].shape))
            detail={"fold":fold["fold"],"train_worlds":len(train_worlds),"test_worlds":len(test_worlds),"train_constant_exact":True}
            if settings["kind"]=="mlp":
                mean,scale=stats(x[train],weights[train])
                assert np.array_equal(mean,fold["mean"])and np.array_equal(scale,fold["scale"])
                detail.update(train_normalization_exact=True,budget=budget(int(train.sum()),settings,fold))
            tested+=list(test_worlds);fold_records.append(detail)
        assert sorted(tested)==sorted(worlds)
        assert mse(y,saved["oof"],weights)==model["grouped_oof"]
        assert mse(y,saved["constant"],weights)==model["grouped_trainonly_constant"]
        for prefix in ["v13","v15"]:
            mask=np.isin(groups,[i for i,w in enumerate(worlds)if w.startswith(prefix+"/")])
            assert mse(y[mask],saved["oof"][mask],weights[mask])==model["family_oof"][prefix]
        code=(ROOT/f"candidates/v15_models/{name}.inc").read_text(encoding="ascii")
        entry={"name":name,"model_sha256":sha(model_path),"settings":settings,"folds":fold_records,
               "oof_constant_and_family_metrics_exact":True}
        if settings["kind"]=="mlp":
            mean,scale=stats(x,weights)
            assert np.array_equal(mean,model["mean"])and np.array_equal(scale,model["scale"])
            assert np.array_equal(cpp_array(code,"mean",[18]),mean)and np.array_equal(cpp_array(code,"scale",[18]),scale)
            parameters=0
            for i,layer in enumerate(model["layers"]):
                ins,outs=model["widths"][i:i+2];w=np.asarray(layer["weight"]);b=np.asarray(layer["bias"])
                assert w.shape==(outs,ins)and b.shape==(outs,)and np.isfinite(w).all()and np.isfinite(b).all()
                assert np.array_equal(cpp_array(code,f"w{i}",[outs,ins]),w)and np.array_equal(cpp_array(code,f"b{i}",[outs]),b)
                parameters+=w.size+b.size
            assert parameters==model["parameters"]
            p=forward(model,x);error=float(np.max(np.abs(p-saved["final"])));assert error<1e-12
            entry.update(final_budget=budget(len(y),settings,model),final_normalization_exact=True,
                         all_cpp_parameter_literals_exact=True,independent_numpy_saved_torch_max_abs_error=error)
        else:
            tree=model["tree"];p,leaves=tree_forward(tree,arrays["x"])
            assert np.array_equal(p,saved["final"]);tree_literals(code,tree)
            assert len(tree["feature"])<=15
            leaf_records=[]
            for leaf in np.unique(leaves):
                mask=leaves==leaf;assert mask.sum()>=settings["min_samples_leaf"]
                expected=np.average(y[mask],axis=0,weights=weights[mask])
                assert np.allclose(expected,tree["value"][leaf],rtol=1e-12,atol=1e-12)
                leaf_records.append({"leaf":int(leaf),"rows":int(mask.sum()),"worlds":len(np.unique(groups[mask]))})
            entry.update(tree_final_predictions_exact=True,tree_cpp_literals_exact=True,leaf_coverage=leaf_records)
        records.append(entry)
    policy_records=json.loads((ROOT/"research/v15_models.json").read_text(encoding="utf8"))
    assert len(policy_records)==4 and {r["name"]for r in policy_records}==set(plan["models"])
    old_tree=(ROOT/"candidates/v13_model/tree.inc").read_text(encoding="ascii");integrations=[]
    for record in policy_records:
        name=record["name"];assert record["policy_name"]==plan["models"][name]["policy_name"]
        original=Path(record["original_policy_source"]).read_text(encoding="utf8")
        predictor=(ROOT/f"candidates/v15_models/{name}.inc").read_text(encoding="ascii")
        expected=original.replace(old_tree,predictor).replace("V13_MODEL_POLICY attempts=","V15_MODEL_POLICY attempts=")
        source=Path(record["source"]);assert source.read_text(encoding="utf8")==expected and sha(source)==record["source_sha256"]
        integrations.append({"name":name,"policy_name":record["policy_name"],"source_sha256":sha(source),"only_predictor_and_diagnostic_prefix_changed":True})
    # Reconstruct the author's already-executed C++ query inputs, then compare
    # saved outputs without compiling or running another native program.
    numeric=json.loads((ROOT/"research/v15_numeric.json").read_text(encoding="utf8"));assert numeric["all_passed"]
    numeric_by_name={row["name"]:row for row in numeric["models"]};numeric_checks=[]
    for name,settings in plan["models"].items():
        model=json.loads((ROOT/f"research/v15_{name}.json").read_text(encoding="utf8"))
        samples=json.loads((ROOT/f"results/v15_fit/{name}_samples.json").read_text(encoding="utf8"))
        queries=[row["features"]for row in samples];rng=np.random.default_rng(settings["seed"])
        queries+=list(arrays["x"][rng.choice(len(x),size=1024,replace=False)])
        if settings["kind"]=="mlp":
            mean=np.asarray(model["mean"]);scale=np.asarray(model["scale"])
            queries+=list((mean+rng.uniform(-12,12,size=(512,18))*scale).astype(np.float32))
            queries+=list((mean+rng.uniform(-1e-9,1e-9,size=(64,18))*scale).astype(np.float32))
        else:
            tree=model["tree"]
            def visit(node,low,high):
                feature=tree["feature"][node]
                if feature<0:return
                threshold=tree["threshold"][node];center=np.float32(threshold)
                for value in [np.nextafter(center,np.float32(-np.inf)),center,np.nextafter(center,np.float32(np.inf))]:
                    row=np.maximum(low,np.minimum(high,np.zeros(18,dtype=np.float32)));row[feature]=value
                    if np.all(row>=low)and np.all(row<=high):queries.append(row)
                upper=high.copy();upper[feature]=min(upper[feature],center)
                if float(upper[feature])>threshold:upper[feature]=np.nextafter(upper[feature],np.float32(-np.inf))
                lower=low.copy();lower[feature]=max(lower[feature],center)
                if float(lower[feature])<=threshold:lower[feature]=np.nextafter(lower[feature],np.float32(np.inf))
                visit(tree["left"][node],low,upper);visit(tree["right"][node],lower,high)
            visit(0,np.full(18,-1e20,dtype=np.float32),np.full(18,1e20,dtype=np.float32))
        queries=np.asarray(queries,dtype=np.float32);actual=np.loadtxt(ROOT/f"results/v15_numeric/{name}.txt")
        assert len(queries)==numeric_by_name[name]["queries"]and np.array_equal(actual[:,0],np.arange(len(queries)))
        if settings["kind"]=="mlp":
            predicted=forward(model,queries)
            scalar=np.asarray([scalar_forward(model,row)for row in queries[:32]])
            scalar_error=float(np.max(np.abs(scalar-actual[:32,1:3])));assert scalar_error<1e-12
        else:
            predicted,query_leaves=tree_forward(model["tree"],queries);scalar_error=0.
            assert sorted(np.unique(query_leaves).tolist())==numeric_by_name[name]["all_leaves_covered"]
        error=float(np.max(np.abs(predicted-actual[:,1:3])));assert error<1e-12
        q=queries.astype(np.float64)
        formula=np.column_stack([~((predicted[:,1]<.02)&(q[:,5]<.25)&(q[:,0]>=3)),
                                 ~((predicted[:,1]<.08)&(q[:,5]<.4)&(q[:,0]>=3)),
                                 .75*q[:,4]+.25*predicted[:,0]>q[:,2]*1.05,
                                 .5*q[:,4]+.5*predicted[:,0]>q[:,2]*1.05])
        assert np.array_equal(actual[:,3:].astype(bool),formula)
        numeric_checks.append({"name":name,"existing_cpp_queries_reconstructed":len(queries),"cpp_numpy_max_abs_error":error,
                               "cpp_scalar_first32_max_abs_error":scalar_error,"all_numeric_formula_gates_equal":True})
    result={"inputs":inputs,"models":records,"integrations":integrations,
            "existing_numeric_cpp_rechecks":numeric_checks,
            "old32_full_update_budget":120*math.ceil(41151/1024),"all128_data_final_epoch_updates":120*math.ceil(len(y)/1024),
            "step_control_limit":"Only finalA128_steps matches oldA32full4920 updates. NewCVfolds also4920,notoldfold budgets;example presentations and normalization differ.",
            "numeric_gate_limit":"Blend numeric harness uses float32 x2/x4 ratio formulas,notdirect raw-double runtime forecast gate;source integration retainsoriginal raw conditions. Numeric formula equality alone is not every real-state threshold proof.",
            "new_fit_runs":0,"new_cpp_executions":0,"new_interactive_runs":0,"fresh_profits_read":False,"all_checks_passed":True}
    path=ROOT/"research/v15_model_independent_audit.json";path.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf8")
    print(json.dumps({"models":len(records),"all_checks_passed":True,"old32_full_updates":result["old32_full_update_budget"],
                      "all128_final_120epoch_updates":result["all128_data_final_epoch_updates"],"new_fit_runs":0,"new_interactive_runs":0,"fresh_profits_read":False}))


if __name__=="__main__":main()
