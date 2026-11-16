"""Add existing heuristic forecasts as world-weighted evaluation baselines."""
import json
import numpy as np
from v13_model_common import ROOT

path=ROOT/"research/v13_model_tree.json"
record=json.loads(path.read_text(encoding="utf8"))
arrays=np.load(ROOT/"results/v13_model_fit/arrays.npz")
x,y,w=arrays["x"],arrays["y"],arrays["weights"]
heuristic=np.column_stack([x[:,4],x[:,5]]).astype(np.float64)
clipped=np.column_stack([np.clip(heuristic[:,0],0,1),np.clip(heuristic[:,1],-2,1)])
def metrics(p):return {name:float(np.average((y[:,i]-p[:,i])**2,weights=w))for i,name in enumerate(["earned_fraction_mse","net_fraction_mse"])}
record["existing_heuristic_raw"]=metrics(heuristic)
record["existing_heuristic_clipped"]=metrics(clipped)
record["existing_heuristic_definition"]="Features4/5 are actual cached baseline forecasts;earned clipped[0,1],net clipped[-2,1] only for clipped comparison,world weights unchanged"
path.write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding="utf8")
print(json.dumps({"model_oof":record["grouped_oof"],"heuristic_raw":record["existing_heuristic_raw"],"heuristic_clipped":record["existing_heuristic_clipped"]}))
