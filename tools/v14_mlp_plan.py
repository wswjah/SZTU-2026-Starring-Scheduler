"""Write the fixed neural-network experiment protocol before any fit/outcome."""
from pathlib import Path
import hashlib
import json
from v13_model_common import ROOT,FEATURES,POLICIES

path=ROOT/"research/v14_mlp_plan.json"
assert not path.exists(),"Never replace a neural-network predeclaration"
dataset=ROOT/"results/v13_model_dataset/admitted.csv"
arrays=ROOT/"results/v13_model_fit/arrays.npz"
record={"date":"2026-11-16","dataset":str(dataset),"dataset_sha256":hashlib.sha256(dataset.read_bytes()).hexdigest(),
        "arrays":str(arrays),"arrays_sha256":hashlib.sha256(arrays.read_bytes()).hexdigest(),
        "training_worlds":"SameV13 train32 admittedflows only;never-started not negative labels;no new validation read",
        "features":FEATURES,"input_precision":"Original18 float32 feature formula cast to float64;normalization and network all float64",
        "targets":["earned/value clipped[0,1]","net/value clipped[-2,1]"],
        "architectures":{"A":{"widths":[18,16,2],"seed":141116},"B":{"widths":[18,16,8,2],"seed":141117}},
        "activation":"ReLU after each hidden layer,linear last layer,then output clip[0,1]/[-2,1]",
        "epochs":120,"optimizer":"Adam (notAdamW)","learning_rate":.003,"weight_decay":1e-4,"batch_size":1024,
        "initialization":"PyTorch nn.Linear defaultuniform initialization directly in float64,fixedseed reset for each fit,no seed selection",
        "loss":"Equal-world weighted MSE averaged across2 outputs after clipping predictions;batch weighted mean with globaltrain weights mean1",
        "normalization":"Trainingfold weightedmean/std with equal totalweight perworld,std floor1e-6,standardized inputs clipped[-8,8]",
        "cross_validation":"SameGroupKFold4 bycompleteworld;fixed120epochs,no earlystopping or epochselection;fold-only normalization and constants",
        "policies_per_architecture":POLICIES,"closed_loop":"Exactly8 pretrained fixedpolicies onV13 train32,no extra threshold/grid",
        "selection":"Atmost1 positive aggregate-profit policy perarchitecture selected usingtrain32 before rootfresh40+40 evaluation",
        "implementation":"Torch ifinstalled elseNumPyAdam;no framework installation;singleCPUthread plusinterop1",
        "export":"Self-contained C++ double means/std/weights,originalfeaturehelper/rawscalar rejection rollback/99params/inputfixes retained",
        "fresh_data_accessed":False,"official_submission_sent":False}
path.write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding="utf8")
print(json.dumps({"predeclared":True,"architectures":record["architectures"],"torch_threads":1}))
