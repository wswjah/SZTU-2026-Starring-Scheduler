"""Predeclare the four expanded-data models before merged data/fits/outcomes."""
from pathlib import Path
import json
from v13_model_common import ROOT,FEATURES,POLICIES

path=ROOT/"research/v15_training_plan.json"
assert not path.exists(),"Never replace an expanded-training predeclaration"
models={
    "A128_120":{"kind":"mlp","widths":[18,16,2],"seed":141116,"epochs":120,"steps":None,"policy_name":"rev_blend25"},
    "B128_120":{"kind":"mlp","widths":[18,16,8,2],"seed":141117,"epochs":120,"steps":None,"policy_name":"veto_strict"},
    "tree128":{"kind":"tree","max_depth":3,"min_samples_leaf":500,"seed":131116,"policy_name":"veto_strict"},
    "A128_steps":{"kind":"mlp","widths":[18,16,2],"seed":141116,"epochs":None,"steps":4920,"policy_name":"rev_blend25"},
}
record={"date":"2026-11-16","dataset":"results/v15_model_dataset/arrays.npz","admitted":"results/v15_model_dataset/admitted.csv",
        "expected_worlds":128,"composition":"OriginalV13 32 plus96 newtrainingworlds,8profiles×12newseeds;explicitv13/v15 keys",
        "features":FEATURES,"targets":["earned/value","clip(net/value,-2,1)"],"models":models,
        "policies":{name:POLICIES[settings["policy_name"]]for name,settings in models.items()},
        "all4_enter_fresh_validation":True,"no_train_threshold_or_architecture_selection":True,
        "optimizer":"Adam,lr0.003,weight_decay1e-4,batch1024","training_loss":"Raw linear outputs,world-weighted2-output MSE;targets clipped",
        "normalization":"Equal-totalworld-weight trainingfold mean/std,std floor1e-6,inputs clipped[-8,8],float64;originalfloat32features castdouble",
        "evaluation":"Output earned clipped[0,1],net clipped[-2,1];same4foldGroupKFold wholeworlds,train-onlyconstants/norm",
        "fixed_step_control":"FinalA128_steps4920 updates equalsoldA32full120*ceil(41151/1024);eachnewfold also4920 explicitly differsfromoldfold updatebudgets;freshshuffle each epoch untilstep4920",
        "reproducibility":"Fixedseeds resetforeachfit,torchCPU1thread/interop1,noearlystopping,noepochselection,noextrasweeps",
        "export":"C++ inlined predictor replacing corresponding originalfixedgate only;originalheader/18helper/rawprefixrollback/8MiB/scanner/CPUinsurance/20k preserved;diagnosticprefixV15_MODEL_POLICY",
        "fit_waits_for_dataset_agent_ready":True,"fresh_data_accessed":False,"official_submission_sent":False}
path.write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding="utf8")
print(json.dumps({"predeclared":True,"models":list(models),"expected_worlds":128}))
