"""Independently rebuild128-world arrays and reconcile CSV totals, no solver runs."""
from pathlib import Path
import hashlib
import json
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parent.parent


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    record=json.loads((ROOT/"research/v15_dataset.json").read_text(encoding="utf8"))
    input_check=json.loads((ROOT/"research/v15_input_independent_audit.json").read_text(encoding="utf8"))
    all_path=Path(record["all_flows_csv"]);data_path=Path(record["dataset"]);array_path=Path(record["arrays"])
    assert sha(all_path)==record["all_flows_sha256"]and sha(data_path)==record["dataset_sha256"]and sha(array_path)==record["arrays_sha256"]
    all_frame=pd.read_csv(all_path);frame=pd.read_csv(data_path);arrays=np.load(array_path)
    assert len(all_frame)==194313 and len(frame)==164406
    assert frame.equals(all_frame.loc[all_frame["seen"]==1].reset_index(drop=True))
    assert (all_frame["seen"].astype(bool)==(all_frame["runs"]>0)).all()
    assert (all_frame["cost"]==all_frame["run"]+all_frame["pull"]+all_frame["net"]).all()
    unseen=all_frame["seen"]==0
    assert (all_frame.loc[unseen,"cost"]==0).all()and (all_frame.loc[unseen,"earned"]==0).all()
    old=frame.loc[frame["case"].str.startswith("v13/")].copy().reset_index(drop=True)
    old["case"]=old["case"].str.split("/",n=1).str[1]
    old_original=pd.read_csv(ROOT/"results/v13_model_dataset/admitted.csv")
    assert len(old)==41151 and old.equals(old_original)
    old_all=all_frame.loc[all_frame["case"].str.startswith("v13/")].copy().reset_index(drop=True)
    old_all["case"]=old_all["case"].str.split("/",n=1).str[1]
    assert old_all.equals(pd.read_csv(ROOT/"results/v13_model_dataset/all_flows.csv"))
    names=sorted(frame["case"].unique());assert len(names)==128and set(names)==set(input_check["expected_world_keys"])
    assert names==record["world_names"]and np.array_equal(arrays["world_names"],names)and np.array_equal(arrays["worlds"],names)
    assert record["group_to_case"]=={str(i):name for i,name in enumerate(names)}
    x=frame[[f"f{i}"for i in range(18)]].to_numpy(dtype=np.float32)
    value=np.maximum(1,frame["value"].to_numpy(dtype=np.float64))
    y=np.column_stack([frame["earned"].to_numpy()/value,np.clip((frame["earned"].to_numpy()-frame["cost"].to_numpy())/value,-2,1)])
    groups=frame["case"].map({name:i for i,name in enumerate(names)}).to_numpy()
    counts=np.bincount(groups,minlength=128);weights=len(frame)/128/counts[groups]
    assert np.array_equal(x,arrays["x"])and np.array_equal(y,arrays["y"])
    assert np.array_equal(groups,arrays["groups"])and np.array_equal(weights,arrays["weights"])
    totals=np.bincount(groups,weights=weights,minlength=128)
    assert np.allclose(totals,len(frame)/128,rtol=1e-12)
    old_mask=frame["case"].str.startswith("v13/").to_numpy()
    assert np.isclose(weights[old_mask].sum()/weights.sum(),.25,rtol=1e-12)
    controls={}
    for prefix,path in [("v13","results/v13_baseline_train32/summary.json"),("v15","results/v15_train96_baseline/summary.json")]:
        for row in json.loads((ROOT/path).read_text(encoding="utf8")):controls[prefix+"/"+row["case"]]=row
    assert set(controls)==set(names)
    for case,rows in all_frame.groupby("case",sort=False):
        baseline=controls[case]
        for field in ["earned","cost","run","pull","net"]:assert int(rows[field].sum())==baseline[field],(case,field)
        assert int(rows["earned"].sum()-rows["cost"].sum())==baseline["profit"]
        assert rows["flow"].tolist()==list(range(len(rows)))
        for raw in rows[["finish","T","deadline","grace","value","earned"]].itertuples(index=False,name=None):
            finish,T,deadline,grace,worth,earned=map(int,raw);expected=0
            if 0<=finish<=T:
                if finish<=deadline:expected=worth
                elif finish<deadline+grace:expected=worth*(deadline+grace-finish)//grace
            assert earned==expected
    result={"all_flows":len(all_frame),"admitted":len(frame),"worlds":len(names),"old_admitted":len(old),
            "new_admitted":len(frame)-len(old),"dataset_sha256":record["dataset_sha256"],"arrays_sha256":record["arrays_sha256"],
            "old32_all_and_admitted_csv_numerically_exact":True,"only_admitted_used_for_training":True,
            "all_x_y_groups_weights_rebuilt_exact":True,"all128_world_keys_expected_and_unique":True,
            "world_names_group_map_exact":True,"equal_global128_world_weights":True,
            "old32_total_weight_fraction":float(weights[old_mask].sum()/weights.sum()),
            "all128_csv_totals_match_baseline_reports":True,"all_finish_integer_revenues_recomputed_exact":True,
            "trace_full_report_equal_evidence":"Dataset agent reconciled immutable trace;this audit independently reaggregates CSV against baseline rather than rerunning interaction",
            "new_model_refits":0,"new_interactive_runs":0,"fresh_profit_accessed":False}
    path=ROOT/"research/v15_dataset_independent_audit.json";path.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf8")
    print(json.dumps({key:result[key]for key in ["worlds","all_flows","admitted","old_admitted","new_admitted","old32_total_weight_fraction","all_x_y_groups_weights_rebuilt_exact","all128_csv_totals_match_baseline_reports"]}))


if __name__=="__main__":main()
