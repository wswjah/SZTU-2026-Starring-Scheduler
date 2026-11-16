"""Read-only normalization, inference/export and integration audit; no refits/runs."""
from pathlib import Path
import hashlib
import json
import re
import numpy as np

ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/"results/v14_mlp_independent_audit"


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def forward(info,x):
    a=np.clip((x.astype(np.float64)-np.asarray(info["mean"]))/np.asarray(info["scale"]),-8,8)
    for i,layer in enumerate(info["layers"]):
        a=a@np.asarray(layer["weight"]).T+np.asarray(layer["bias"])
        if i<len(info["layers"])-1:a=np.maximum(a,0)
    a[:,0]=np.clip(a[:,0],0,1);a[:,1]=np.clip(a[:,1],-2,1)
    return a


def scalar_forward(info,x):
    a=[min(8.,max(-8.,(float(value)-mean)/scale))for value,mean,scale in zip(x,info["mean"],info["scale"])]
    for layer_index,layer in enumerate(info["layers"]):
        following=[]
        for row,bias in zip(layer["weight"],layer["bias"]):
            value=float(bias)
            for weight,activation in zip(row,a):value+=float(weight)*activation
            following.append(max(0.,value)if layer_index<len(info["layers"])-1 else value)
        a=following
    return [min(1.,max(0.,a[0])),min(1.,max(-2.,a[1]))]


def stats(x,w):
    weights=w/w.mean();mean=np.average(x,axis=0,weights=weights)
    scale=np.maximum(1e-6,np.sqrt(np.average((x-mean)**2,axis=0,weights=weights)))
    return mean,scale


def mse(y,p,w):
    return {name:float(np.average((y[:,i]-p[:,i])**2,weights=w))for i,name in enumerate(["earned_fraction_mse","net_fraction_mse"])}


def cpp_array(code,name,shape):
    dimensions="".join(r"\["+str(n)+r"\]"for n in shape)
    match=re.search(r"static const double "+name+dimensions+r"=\{([^}]+)\};",code)
    assert match,name
    return np.asarray([float(value)for value in match.group(1).split(",")]).reshape(shape)


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    plan=json.loads((ROOT/"research/v14_mlp_plan.json").read_text(encoding="utf8"))
    assert "raw linear outputs"in plan["loss"]and plan["epochs"]==120
    assert plan["amendments"][0]["before_any_fit_or_cv_results"]
    arrays_path=ROOT/"results/v13_model_fit/arrays.npz";assert sha(arrays_path)==plan["arrays_sha256"]
    arrays=np.load(arrays_path);x=arrays["x"].astype(np.float64);y=arrays["y"];w=arrays["weights"];groups=arrays["groups"]
    assert x.shape==(41151,18)and y.shape==(41151,2)and len(np.unique(groups))==32
    world_sums=[w[groups==g].sum()for g in np.unique(groups)]
    assert np.allclose(world_sums,world_sums[0],rtol=1e-12,atol=1e-12)
    model_records=[]
    for architecture in ["A","B"]:
        path=ROOT/f"research/v14_mlp_{architecture}.json";info=json.loads(path.read_text(encoding="utf8"))
        assert info["data_sha256"]==plan["arrays_sha256"]and info["epochs"]==120
        assert info["widths"]==plan["architectures"][architecture]["widths"]and info["seed"]==plan["architectures"][architecture]["seed"]
        assert info["plan_sha256"]==sha(ROOT/"research/v14_mlp_plan.json")
        predictions=np.load(ROOT/f"results/v14_mlp_fit/{architecture}_predictions.npz")
        tested=[];fold_records=[]
        for fold in info["folds"]:
            train_groups=set(fold["train_groups"]);test_groups=set(fold["test_groups"])
            assert not(train_groups&test_groups)and train_groups|test_groups==set(range(32))
            train=np.isin(groups,list(train_groups));test=np.isin(groups,list(test_groups))
            mean,scale=stats(x[train],w[train])
            assert np.array_equal(mean,np.asarray(fold["mean"]))
            assert np.array_equal(scale,np.asarray(fold["scale"]))
            expected_constant=np.average(y[train],axis=0,weights=w[train])
            assert np.array_equal(predictions["constant"][test],np.broadcast_to(expected_constant,predictions["constant"][test].shape))
            tested+=list(test_groups)
            fold_records.append({"fold":fold["fold"],"training_only_mean_scale_exact":True,"training_only_constant_exact":True})
        assert sorted(tested)==list(range(32))
        mean,scale=stats(x,w)
        assert np.array_equal(mean,np.asarray(info["mean"]))and np.array_equal(scale,np.asarray(info["scale"]))
        assert mse(y,predictions["oof"],w)==info["grouped_oof"]
        assert mse(y,predictions["constant"],w)==info["grouped_trainonly_constant"]
        recomputed=forward(info,x)
        final_error=float(np.max(np.abs(recomputed-predictions["final"])))
        assert final_error<1e-12
        code=(ROOT/f"candidates/v14_mlp/{architecture}.inc").read_text(encoding="ascii")
        assert np.array_equal(cpp_array(code,"mean",[18]),mean)and np.array_equal(cpp_array(code,"scale",[18]),scale)
        parameters=0
        for i,layer in enumerate(info["layers"]):
            inputs,outputs=info["widths"][i:i+2]
            weights=np.asarray(layer["weight"]);bias=np.asarray(layer["bias"])
            assert weights.shape==(outputs,inputs)and bias.shape==(outputs,)
            assert np.isfinite(weights).all()and np.isfinite(bias).all()
            assert np.array_equal(cpp_array(code,f"w{i}",[outputs,inputs]),weights)
            assert np.array_equal(cpp_array(code,f"b{i}",[outputs]),bias)
            parameters+=weights.size+bias.size
        assert parameters==info["parameters"]
        samples=json.loads((ROOT/f"results/v14_mlp_fit/{architecture}_samples.json").read_text(encoding="utf8"))
        queries=[row["features"]for row in samples];rng=np.random.default_rng(info["seed"])
        queries+=list(arrays["x"][rng.choice(len(x),size=1024,replace=False)])
        queries+=list((mean+rng.uniform(-12,12,size=(512,18))*scale).astype(np.float32))
        queries+=list((mean+rng.uniform(-1e-9,1e-9,size=(64,18))*scale).astype(np.float32))
        queries=np.asarray(queries,dtype=np.float32)
        cpp_output=np.loadtxt(ROOT/f"results/v14_mlp_numeric/{architecture}_output.txt")
        assert len(queries)==1744 and np.array_equal(cpp_output[:,0],np.arange(1744))
        expected=forward(info,queries);cpp_error=float(np.max(np.abs(cpp_output[:,1:3]-expected)))
        assert cpp_error<1e-12
        scalar=np.asarray([scalar_forward(info,row)for row in queries[:32]])
        scalar_error=float(np.max(np.abs(cpp_output[:32,1:3]-scalar)));assert scalar_error<1e-12
        px=queries.astype(np.float64)
        formula=np.column_stack([~((expected[:,1]<.02)&(px[:,5]<.25)&(px[:,0]>=3)),
                                 ~((expected[:,1]<.08)&(px[:,5]<.4)&(px[:,0]>=3)),
                                 .75*px[:,4]+.25*expected[:,0]>px[:,2]*1.05,
                                 .5*px[:,4]+.5*expected[:,0]>px[:,2]*1.05])
        assert np.array_equal(cpp_output[:,3:].astype(bool),formula)
        model_records.append({"architecture":architecture,"model_sha256":sha(path),"widths":info["widths"],"parameters":parameters,
                              "folds":fold_records,"final_mean_scale_exact":True,"oof_and_constant_mse_exact":True,
                              "cpp_mean_scale_weights_bias_literals_exact":True,"independent_final_torch_max_abs_error":final_error,
                              "existing_cpp_queries_reconstructed":len(queries),"independent_cpp_numpy_max_abs_error":cpp_error,
                              "scalar_bias_first_row_major_queries":32,"independent_cpp_scalar_max_abs_error":scalar_error,
                              "all_existing_numeric_formula_gate_decisions_match":True})
    tree=(ROOT/"candidates/v13_model/tree.inc").read_text(encoding="ascii")
    policies=json.loads((ROOT/"research/v14_mlp_policies.json").read_text(encoding="utf8"));assert len(policies)==8
    integration=[]
    for policy in policies:
        original=Path(policy["original_policy_source"]).read_text(encoding="utf8")
        network=(ROOT/f"candidates/v14_mlp/{policy['architecture']}.inc").read_text(encoding="ascii")
        expected=original.replace(tree,network).replace("V13_MODEL_POLICY attempts=","V14_MLP_POLICY attempts=")
        source=Path(policy["source"]);assert source.read_text(encoding="utf8")==expected
        assert sha(source)==policy["source_sha256"]
        integration.append({"name":policy["name"],"source_sha256":sha(source),"only_predictor_and_diagnostic_name_replaced":True})
    controls=json.loads((ROOT/"results/v14_mlp_disabled/summary.json").read_text(encoding="utf8"))
    base={row["case"]:row for row in json.loads((ROOT/"results/v13_baseline_train32/summary.json").read_text(encoding="utf8"))}
    assert len(controls)==4 and all(row["ok"]and row["report"]==base[row["case"]]["report"]for row in controls)
    record={"training_arrays_sha256":plan["arrays_sha256"],"same_admitted_v13_rows":41151,"training_worlds":32,
            "world_total_weights_equal":True,"raw_loss_source_checked":True,"fixed120_epochs_no_selection_source_checked":True,
            "pre_fit_loss_amendment_retained":True,"architectures":model_records,"policy_integrations":integration,
            "four_existing_disabled_reports_equal":True,"new_model_refits":0,"new_cpp_executions":0,
            "new_interaction_benchmarks":0,"fresh_outcomes_read":False,
            "numeric_gate_scope":"Existing numeric harness checks net veto formulas exactly; blend formulas use float32 x2/x4 ratios,not direct runtime raw-double forecast.Allow. Full policy sources retain raw original.Allow conditions unchanged; formula equality is not proof for every raw-double threshold edge.",
            "verdict":"No blocking implementation issue found in inspected training/export/integration;finite audits do not guarantee unseen-state or official-score behaviour."}
    (OUT/"audit.json").write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding="utf8")
    print(json.dumps({"worlds":32,"rows":41151,"architectures":model_records,"policy_integrations":len(integration),
                      "new_fits":0,"new_cpp_executions":0,"fresh_outcomes_read":False}))


if __name__=="__main__":main()
