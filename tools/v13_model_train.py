"""Fit a tiny current-policy conditional outcome tree with whole-world OOF."""
from pathlib import Path
import hashlib
import json
import numpy as np
import pandas as pd
from sklearn.model_selection import GroupKFold
from sklearn.tree import DecisionTreeRegressor
from v13_model_common import ROOT,FEATURES,POLICIES


def tree_factory():return DecisionTreeRegressor(max_depth=3,min_samples_leaf=500,random_state=131116)


def tree_cpp(tree):
    t=tree.tree_;ints=lambda a:",".join(str(int(x))for x in a);doubles=lambda a:",".join(format(float(x),".17g")for x in a)
    values=",\n".join("{"+doubles(row[:,0])+"}"for row in t.value)
    return """static void v13ModelPredict(const float* x,double* prediction) {
    static const int feature[]={FEATURE};
    static const int left[]={LEFT},right[]={RIGHT};
    static const double threshold[]={THRESHOLD};
    static const double value[][2]={VALUES};
    int node=0;
    while(feature[node]>=0)node=x[feature[node]]<=threshold[node]?left[node]:right[node];
    prediction[0]=value[node][0];prediction[1]=value[node][1];
}
""".replace("FEATURE",ints(t.feature)).replace("LEFT",ints(t.children_left)).replace("RIGHT",ints(t.children_right)).replace("THRESHOLD",doubles(t.threshold)).replace("VALUES",values)


def metrics(y,p,w):
    return {name:float(np.average((y[:,i]-p[:,i])**2,weights=w))for i,name in enumerate(["earned_fraction_mse","net_fraction_mse"])}


def main():
    dataset=ROOT/"results/v13_model_dataset/admitted.csv";frame=pd.read_csv(dataset)
    x=frame[[f"f{i}"for i in range(len(FEATURES))]].to_numpy(dtype=np.float32)
    value=np.maximum(1,frame["value"].to_numpy(dtype=np.float64))
    y=np.column_stack([frame["earned"].to_numpy()/value,np.clip((frame["earned"].to_numpy()-frame["cost"].to_numpy())/value,-2,1)])
    assert np.isfinite(x).all()and np.isfinite(y).all()
    worlds=sorted(frame["case"].unique());groups=frame["case"].map({name:i for i,name in enumerate(worlds)}).to_numpy()
    assert len(worlds)==32
    weights=np.ones(len(frame))
    for group in np.unique(groups):weights[groups==group]/=(groups==group).sum()
    weights*=len(frame)/len(worlds)
    oof=np.zeros_like(y);constant=np.zeros_like(y);folds=[]
    for fold,(train,test)in enumerate(GroupKFold(4).split(x,y,groups)):
        tree=tree_factory().fit(x[train],y[train],sample_weight=weights[train]);oof[test]=tree.predict(x[test])
        constant[test]=np.average(y[train],axis=0,weights=weights[train])
        folds.append({"fold":fold,"train_worlds":[worlds[i]for i in np.unique(groups[train])],"test_worlds":[worlds[i]for i in np.unique(groups[test])],"nodes":tree.tree_.node_count})
    tree=tree_factory().fit(x,y,sample_weight=weights);t=tree.tree_;leaves=tree.apply(x)
    record={"dataset_sha256":hashlib.sha256(dataset.read_bytes()).hexdigest(),"feature_names":FEATURES,
            "rows":len(frame),"worlds":worlds,"targets":["earned/value","clip(net/value,-2,1)"],"max_depth":3,"min_samples_leaf":500,
            "folds":folds,"weighting":"equal total weight per admitted-flow world,no class weighting",
            "grouped_oof":metrics(y,oof,weights),"grouped_trainonly_constant":metrics(y,constant,weights),
            "feature_importance":dict(zip(FEATURES,tree.feature_importances_.tolist())),
            "leaves":[{"leaf":int(leaf),"rows":int((leaves==leaf).sum()),"world_count":int(len(np.unique(groups[leaves==leaf]))),
                       "prediction":t.value[leaf,:,0].tolist()}for leaf in np.unique(leaves)],
            "tree":{"feature":t.feature.tolist(),"left":t.children_left.tolist(),"right":t.children_right.tolist(),"threshold":t.threshold.tolist(),"value":t.value[:,:,0].tolist()},
            "policy_plan":POLICIES,"meaning":"Conditional outcomes of admitted flows under current99 baseline,not causal action values or completion probabilities",
            "unadmitted_rows_used":False,"future_inputs_at_runtime":False,"official_submission_sent":False}
    path=ROOT/"research/v13_model_tree.json";assert not path.exists();path.write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding="utf8")
    (ROOT/"candidates/v13_model/tree.inc").write_text(tree_cpp(tree),encoding="ascii")
    directory=ROOT/"results/v13_model_fit";directory.mkdir(parents=True,exist_ok=True)
    np.savez_compressed(directory/"arrays.npz",x=x,y=y,weights=weights,groups=groups,oof=oof,constant=constant)
    sample_indexes=set(np.random.default_rng(131116).choice(len(frame),size=min(64,len(frame)),replace=False).tolist())
    for leaf in np.unique(leaves):sample_indexes.add(int(np.flatnonzero(leaves==leaf)[0]))
    samples=[{"row":i,"case":frame.iloc[i]["case"],"features":x[i].tolist(),"prediction":tree.predict(x[i:i+1])[0].tolist()}for i in sorted(sample_indexes)]
    (directory/"samples.json").write_text(json.dumps(samples,ensure_ascii=False,indent=2),encoding="utf8")
    print(json.dumps({"rows":len(frame),"nodes":t.node_count,"oof":record["grouped_oof"],"constant":record["grouped_trainonly_constant"],"used_features":[FEATURES[i]for i in sorted(set(t.feature)-{-2})]}),flush=True)


if __name__=="__main__":main()
