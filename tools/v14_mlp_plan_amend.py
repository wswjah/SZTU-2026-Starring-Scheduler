"""Clarify raw-output training loss before the first fit, preserving initial text."""
import json
from v13_model_common import ROOT

path=ROOT/"research/v14_mlp_plan.json"
record=json.loads(path.read_text(encoding="utf8"))
assert not (ROOT/"research/v14_mlp_fit.json").exists()
assert "amendments"not in record
record["loss_initial"]=record["loss"]
record["loss"]="Equal-world weighted MSE on raw linear outputs;targets clipped;prediction clipping only for evaluation/inference/gates"
record["amendments"]=[{"date":"2026-11-16","before_any_fit_or_cv_results":True,"field":"loss",
                       "original":record["loss_initial"],"effective":record["loss"],
                       "reason":"Root clarified original intent:clip evaluation/gates only,avoid zero gradients beyond clipped output bounds;no results observed"}]
path.write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding="utf8")
print("Recorded raw-output-loss clarification before any fit")
