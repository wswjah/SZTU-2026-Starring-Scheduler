"""Fit exactly four fixed expanded-data models;no policy/epoch selection."""
from pathlib import Path
import hashlib
import json
import math
import time
import numpy as np
import torch
from torch import nn
from sklearn.model_selection import GroupKFold
from v13_model_common import ROOT,FEATURES
from v13_model_train import tree_factory,tree_cpp
from v14_mlp_train import build,inference,cpp,dump,metrics,clipped


def fit_network(x,y,w,settings,label):
    weights=w/w.mean()
    mean=np.average(x,axis=0,weights=weights)
    scale=np.maximum(1e-6,np.sqrt(np.average((x-mean)**2,axis=0,weights=weights)))
    z=np.clip((x-mean)/scale,-8,8)
    tx,ty,tw=[torch.from_numpy(np.ascontiguousarray(a,dtype=np.float64))for a in [z,y,weights]]
    model=build(settings["widths"],settings["seed"])
    optimizer=torch.optim.Adam(model.parameters(),lr=.003,weight_decay=1e-4)
    generator=torch.Generator(device="cpu").manual_seed(settings["seed"])
    epoch=steps=full_epochs=presentations=0
    epoch_budget,step_budget=settings["epochs"],settings["steps"]
    start_time=time.perf_counter()
    while (step_budget is not None and steps<step_budget)or(epoch_budget is not None and epoch<epoch_budget):
        permutation=torch.randperm(len(y),generator=generator);epoch+=1;completed=True
        for offset in range(0,len(y),1024):
            if step_budget is not None and steps>=step_budget:
                completed=False;break
            indexes=permutation[offset:offset+1024]
            optimizer.zero_grad(set_to_none=True)
            raw=model(tx[indexes])
            loss=(((raw-ty[indexes])**2).mean(dim=1)*tw[indexes]).mean()
            loss.backward();optimizer.step();steps+=1;presentations+=len(indexes)
        full_epochs+=completed
    if step_budget is not None:assert steps==4920
    else:assert epoch==120 and steps==120*math.ceil(len(y)/1024)
    with torch.no_grad():train_raw=model(tx).numpy()
    assert np.isfinite(train_raw).all()
    info={"widths":settings["widths"],"seed":settings["seed"],"epoch_budget":epoch_budget,"step_budget":step_budget,
          "optimizer_updates":steps,"epochs_started":epoch,"full_epochs_completed":full_epochs,"sample_presentations":presentations,
          "rows":len(y),"mean":mean.tolist(),"scale":scale.tolist(),
          "layers":[{"weight":layer.weight.detach().numpy().tolist(),"bias":layer.bias.detach().numpy().tolist()}for layer in model if isinstance(layer,nn.Linear)],
          "parameters":sum(p.numel()for p in model.parameters()),"train_mse_clipped":metrics(y,clipped(train_raw),weights),
          "fit_wall_seconds":time.perf_counter()-start_time}
    print(json.dumps({"fit_complete":label,"seconds":info["fit_wall_seconds"],"updates":steps,"epochs_started":epoch,
                      "train_mse":info["train_mse_clipped"]}),flush=True)
    return model,info


def final_tree_info(tree):
    t=tree.tree_
    return {"feature":t.feature.tolist(),"left":t.children_left.tolist(),"right":t.children_right.tolist(),
            "threshold":t.threshold.tolist(),"value":t.value[:,:,0].tolist()}


def main():
    plan_path=ROOT/"research/v15_training_plan.json";plan=json.loads(plan_path.read_text(encoding="utf8"))
    dataset_dir=ROOT/"results/v15_model_dataset"
    assert (dataset_dir/"arrays.npz").is_file()and(dataset_dir/"admitted.csv").is_file(),"Wait for dataset-agent completion"
    output=ROOT/"results/v15_fit";assert not output.exists(),"Never refit an existing expanded-data experiment"
    output.mkdir(parents=True)
    directory=ROOT/"candidates/v15_models";directory.mkdir(parents=True,exist_ok=True)
    torch.set_num_threads(1);torch.set_num_interop_threads(1);torch.use_deterministic_algorithms(True)
    arrays=np.load(dataset_dir/"arrays.npz",allow_pickle=False)
    x=arrays["x"].astype(np.float64);y=arrays["y"].astype(np.float64);weights=arrays["weights"].astype(np.float64);groups=arrays["groups"]
    worlds=arrays["world_names"].astype(str).tolist()
    assert len(worlds)==128 and len(set(worlds))==128 and set(np.unique(groups))==set(range(128))
    assert x.shape==(len(y),18)and y.shape[1]==2 and np.isfinite(x).all()and np.isfinite(y).all()
    assert np.all((y[:,0]>=0)&(y[:,0]<=1))and np.all((y[:,1]>=-2)&(y[:,1]<=1))
    sums=np.asarray([weights[groups==g].sum()for g in range(128)])
    np.testing.assert_allclose(sums,sums.mean(),rtol=1e-10,atol=1e-8)
    inputs={"rows":len(y),"worlds":worlds,"feature_names":FEATURES,
            "arrays_sha256":hashlib.sha256((dataset_dir/"arrays.npz").read_bytes()).hexdigest(),
            "admitted_sha256":hashlib.sha256((dataset_dir/"admitted.csv").read_bytes()).hexdigest(),
            "plan_sha256":hashlib.sha256(plan_path.read_bytes()).hexdigest(),"per_world_weight_totals_equal":True,
            "family_world_counts":{"v13":sum(w.startswith("v13/")for w in worlds),"v15":sum(w.startswith("v15/")for w in worlds)}}
    assert inputs["family_world_counts"]=={"v13":32,"v15":96}
    dump(ROOT/"research/v15_training_inputs.json",inputs)
    heuristic=np.column_stack([x[:,4],x[:,5]]);heuristic_clipped=clipped(heuristic)
    summary=[]
    for name,settings in plan["models"].items():
        oof=np.zeros_like(y);constant=np.zeros_like(y);folds=[]
        for fold,(train,test)in enumerate(GroupKFold(4).split(x,y,groups)):
            if settings["kind"]=="mlp":
                model,info=fit_network(x[train],y[train],weights[train],settings,f"{name}/fold{fold}")
                oof[test]=inference(model,info,x[test])
                details={k:info[k]for k in ["mean","scale","optimizer_updates","epochs_started","full_epochs_completed","sample_presentations","fit_wall_seconds"]}
            else:
                started=time.perf_counter();model=tree_factory().fit(x[train].astype(np.float32),y[train],sample_weight=weights[train])
                oof[test]=model.predict(x[test].astype(np.float32));details={"nodes":model.tree_.node_count,"fit_wall_seconds":time.perf_counter()-started}
                print(json.dumps({"fit_complete":f"{name}/fold{fold}","nodes":model.tree_.node_count}),flush=True)
            constant[test]=np.average(y[train],axis=0,weights=weights[train])
            folds.append({"fold":fold,"train_worlds":[worlds[i]for i in np.unique(groups[train])],"test_worlds":[worlds[i]for i in np.unique(groups[test])],**details})
        if settings["kind"]=="mlp":
            final,info=fit_network(x,y,weights,settings,f"{name}/all128")
            final_prediction=inference(final,info,x);fragment=cpp(info)
        else:
            started=time.perf_counter();final=tree_factory().fit(x.astype(np.float32),y,sample_weight=weights)
            final_prediction=final.predict(x.astype(np.float32));fragment=tree_cpp(final)
            info={"kind":"tree","tree":final_tree_info(final),"nodes":final.tree_.node_count,"fit_wall_seconds":time.perf_counter()-started,
                  "train_mse_clipped":metrics(y,final_prediction,weights)}
        family_metrics={}
        for family in ["v13/","v15/"]:
            mask=np.isin(groups,[i for i,w in enumerate(worlds)if w.startswith(family)])
            family_metrics[family.rstrip("/")]=metrics(y[mask],oof[mask],weights[mask])
        info.update(name=name,settings=settings,features=FEATURES,training_rows=len(y),training_worlds=128,folds=folds,
                    grouped_oof=metrics(y,oof,weights),grouped_trainonly_constant=metrics(y,constant,weights),
                    heuristic_raw=metrics(y,heuristic,weights),heuristic_clipped=metrics(y,heuristic_clipped,weights),
                    family_oof=family_metrics,inputs=inputs,torch_version=torch.__version__,
                    no_epoch_or_policy_selection=True,fresh_data_accessed=False,official_submission_sent=False)
        dump(ROOT/f"research/v15_{name}.json",info)
        (directory/f"{name}.inc").write_text(fragment,encoding="ascii")
        np.savez_compressed(output/f"{name}_predictions.npz",oof=oof,final=final_prediction,constant=constant)
        rng=np.random.default_rng(settings["seed"])
        indexes=set(rng.choice(len(y),size=128,replace=False).tolist())
        for k in range(2):indexes.update(np.argsort(final_prediction[:,k])[:4].tolist());indexes.update(np.argsort(final_prediction[:,k])[-4:].tolist())
        if settings["kind"]=="tree":
            leaves=final.apply(x.astype(np.float32))
            for leaf in np.unique(leaves):indexes.add(int(np.flatnonzero(leaves==leaf)[0]))
        dump(output/f"{name}_samples.json",[{"index":i,"features":x[i].tolist(),"prediction":final_prediction[i].tolist()}for i in sorted(indexes)])
        summary.append({"name":name,"settings":settings,"grouped_oof":info["grouped_oof"],"family_oof":family_metrics,
                        "final_fit_wall_seconds":info["fit_wall_seconds"],"all_fit_wall_seconds":sum(f["fit_wall_seconds"]for f in folds)+info["fit_wall_seconds"],
                        "model_sha256":hashlib.sha256((ROOT/f"research/v15_{name}.json").read_bytes()).hexdigest()})
        dump(ROOT/"research/v15_fit.json",{"models":summary,"inputs":inputs,"fresh_data_accessed":False,"official_submission_sent":False})
        print(json.dumps({"model_complete":name,"oof":info["grouped_oof"]}),flush=True)


if __name__=="__main__":main()
