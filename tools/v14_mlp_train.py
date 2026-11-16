"""Fixed float64 neural nets,world-only folds,120 epochs,then standalone C++ export."""
from pathlib import Path
import hashlib
import json
import time
import numpy as np
import torch
from torch import nn
from sklearn.model_selection import GroupKFold
from v13_model_common import ROOT,FEATURES


def dump(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding="utf8")


def metrics(y,p,w):
    return {name:float(np.average((y[:,i]-p[:,i])**2,weights=w))for i,name in enumerate(["earned_fraction_mse","net_fraction_mse"])}


def clipped(p):
    p=np.asarray(p).copy();p[:,0]=np.clip(p[:,0],0,1);p[:,1]=np.clip(p[:,1],-2,1)
    return p


def build(widths,seed):
    torch.manual_seed(seed)
    layers=[]
    for i,(a,b)in enumerate(zip(widths[:-1],widths[1:])):
        layers.append(nn.Linear(a,b,dtype=torch.float64))
        if i<len(widths)-2:layers.append(nn.ReLU())
    return nn.Sequential(*layers)


def fit(x,y,w,widths,seed,epochs,label):
    weights=w/w.mean()
    mean=np.average(x,axis=0,weights=weights)
    scale=np.maximum(1e-6,np.sqrt(np.average((x-mean)**2,axis=0,weights=weights)))
    z=np.clip((x-mean)/scale,-8,8)
    tx,ty,tw=[torch.from_numpy(np.ascontiguousarray(a,dtype=np.float64))for a in [z,y,weights]]
    model=build(widths,seed)
    optimizer=torch.optim.Adam(model.parameters(),lr=.003,weight_decay=1e-4)
    generator=torch.Generator(device="cpu").manual_seed(seed)
    started=time.perf_counter()
    for epoch in range(epochs):
        permutation=torch.randperm(len(y),generator=generator)
        for start in range(0,len(y),1024):
            indexes=permutation[start:start+1024]
            optimizer.zero_grad(set_to_none=True)
            raw=model(tx[indexes])
            loss=(((raw-ty[indexes])**2).mean(dim=1)*tw[indexes]).mean()
            loss.backward();optimizer.step()
    with torch.no_grad():
        train_raw=model(tx).numpy();train_mse=metrics(y,clipped(train_raw),weights)
    assert np.isfinite(train_raw).all()
    parameters=[{"weight":layer.weight.detach().numpy().tolist(),"bias":layer.bias.detach().numpy().tolist()}for layer in model if isinstance(layer,nn.Linear)]
    result={"widths":widths,"seed":seed,"epochs":epochs,"mean":mean.tolist(),"scale":scale.tolist(),"layers":parameters,
            "parameters":sum(p.numel()for p in model.parameters()),"train_mse_clipped":train_mse,"fit_wall_seconds":time.perf_counter()-started}
    print(json.dumps({"fit_complete":label,"seconds":result["fit_wall_seconds"],"train_mse":train_mse}),flush=True)
    return model,result


def inference(model,info,x):
    z=np.clip((x-np.asarray(info["mean"]))/np.asarray(info["scale"]),-8,8)
    with torch.no_grad():raw=model(torch.from_numpy(np.ascontiguousarray(z,dtype=np.float64))).numpy()
    return clipped(raw)


def cpp(info):
    fmt=lambda values:",".join(format(float(v),".17g")for v in np.asarray(values).ravel())
    declarations=["static void v13ModelPredict(const float* x,double* prediction) {",
                  "    static const double mean[18]={"+fmt(info["mean"])+"};",
                  "    static const double scale[18]={"+fmt(info["scale"])+"};",
                  "    double a0[18];F(i,18)a0[i]=min(8.,max(-8.,(double(x[i])-mean[i])/scale[i]));"]
    for index,layer in enumerate(info["layers"]):
        ins=info["widths"][index];outs=info["widths"][index+1];name=f"a{index+1}"
        declarations += [f"    static const double w{index}[{outs}][{ins}]={{"+fmt(layer["weight"])+"};",
                         f"    static const double b{index}[{outs}]={{"+fmt(layer["bias"])+"};",
                         f"    double {name}[{outs}];",
                         f"    F(o,{outs}){{double value=b{index}[o];F(i,{ins})value+=w{index}[o][i]*a{index}[i];{name}[o]="+("max(0.,value);}"if index<len(info["layers"])-1 else "value;}")]
    last=f"a{len(info['layers'])}"
    declarations += [f"    prediction[0]=min(1.,max(0.,{last}[0]));prediction[1]=min(1.,max(-2.,{last}[1]));","}"]
    return "\n".join(declarations)+"\n"


def main():
    plan=json.loads((ROOT/"research/v14_mlp_plan.json").read_text(encoding="utf8"))
    assert plan["amendments"][0]["before_any_fit_or_cv_results"]
    assert "raw linear outputs"in plan["loss"]
    out=ROOT/"results/v14_mlp_fit";assert not out.exists(),"No refitting an existing neural experiment"
    out.mkdir(parents=True)
    torch.set_num_threads(1);torch.set_num_interop_threads(1);torch.use_deterministic_algorithms(True)
    arrays=np.load(ROOT/"results/v13_model_fit/arrays.npz")
    x=arrays["x"].astype(np.float64);y=arrays["y"].astype(np.float64);weights=arrays["weights"].astype(np.float64);groups=arrays["groups"]
    assert len(np.unique(groups))==32 and x.shape[1]==18
    baseline_tree=json.loads((ROOT/"research/v13_model_tree.json").read_text(encoding="utf8"))
    architectures=[]
    for name,settings in plan["architectures"].items():
        widths,seed=settings["widths"],settings["seed"]
        oof=np.zeros_like(y);constant=np.zeros_like(y);folds=[]
        for fold,(train,test)in enumerate(GroupKFold(4).split(x,y,groups)):
            model,info=fit(x[train],y[train],weights[train],widths,seed,120,f"{name}/fold{fold}")
            oof[test]=inference(model,info,x[test]);constant[test]=np.average(y[train],axis=0,weights=weights[train])
            folds.append({"fold":fold,"train_groups":np.unique(groups[train]).tolist(),"test_groups":np.unique(groups[test]).tolist(),
                          "mean":info["mean"],"scale":info["scale"],"fit_wall_seconds":info["fit_wall_seconds"]})
        final,info=fit(x,y,weights,widths,seed,120,f"{name}/all32")
        final_prediction=inference(final,info,x)
        info.update(name=name,features=FEATURES,rows=len(y),worlds=32,folds=folds,
                    grouped_oof=metrics(y,oof,weights),grouped_trainonly_constant=metrics(y,constant,weights),
                    existing_heuristic_raw=baseline_tree["existing_heuristic_raw"],existing_heuristic_clipped=baseline_tree["existing_heuristic_clipped"],
                    shallow_tree_grouped_oof=baseline_tree["grouped_oof"],
                    data_sha256=plan["arrays_sha256"],plan_sha256=hashlib.sha256((ROOT/"research/v14_mlp_plan.json").read_bytes()).hexdigest(),
                    precision="float64 normalize/weights/activations;input originalfloat32 featurescastdouble",torch_version=torch.__version__,
                    no_epoch_selection=True,fresh_data_accessed=False,official_submission_sent=False)
        dump(ROOT/f"research/v14_mlp_{name}.json",info)
        directory=ROOT/"candidates/v14_mlp";directory.mkdir(parents=True,exist_ok=True)
        (directory/f"{name}.inc").write_text(cpp(info),encoding="ascii")
        np.savez_compressed(out/f"{name}_predictions.npz",oof=oof,final=final_prediction,constant=constant)
        indexes=set(np.random.default_rng(seed).choice(len(y),size=128,replace=False).tolist())
        for k in range(2):indexes.update(np.argsort(final_prediction[:,k])[:4].tolist());indexes.update(np.argsort(final_prediction[:,k])[-4:].tolist())
        dump(out/f"{name}_samples.json",[{"index":i,"features":x[i].tolist(),"prediction":final_prediction[i].tolist()}for i in sorted(indexes)])
        architectures.append({"name":name,"widths":widths,"parameters":info["parameters"],"grouped_oof":info["grouped_oof"],
                              "final_fit_wall_seconds":info["fit_wall_seconds"],"all_fit_wall_seconds":sum(f["fit_wall_seconds"]for f in folds)+info["fit_wall_seconds"],
                              "model_sha256":hashlib.sha256((ROOT/f"research/v14_mlp_{name}.json").read_bytes()).hexdigest()})
        dump(ROOT/"research/v14_mlp_fit.json",{"architectures":architectures,"fresh_data_accessed":False,"official_submission_sent":False})
        print(json.dumps({"architecture":name,"parameters":info["parameters"],"oof":info["grouped_oof"]}),flush=True)


if __name__=="__main__":main()
