"""Independent float32 feature and actual exported C++ predictor audit.

No fitting or interaction benchmark is performed. Root authorized these fixed
fixtures; all real samples come from the existing training fit artifact.
"""
from pathlib import Path
import hashlib
import json
import math
import subprocess
import numpy as np

ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/"results/v13_model_audit"


def predict(tree,x,with_path=False):
    node=0;path=[]
    while tree["feature"][node]>=0:
        path.append(node);feature=tree["feature"][node]
        node=tree["left"][node] if float(x[feature])<=float(tree["threshold"][node]) else tree["right"][node]
    path.append(node)
    return (tree["value"][node],path) if with_path else tree["value"][node]


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    source=ROOT/"candidates/v13_model/trace.cpp";tree_inc=ROOT/"candidates/v13_model/tree.inc"
    before={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [source,tree_inc]}
    model=json.loads((ROOT/"research/v13_model_tree.json").read_text(encoding="utf8"));tree=model["tree"]
    exe=ROOT/"build/v13_model_audit_features.exe"
    command=["g++","-std=c++17","-O2","-Wall","-Wextra","tools/v13_model_audit_features.cpp","-o",str(exe)]
    compiled=subprocess.run(command,cwd=ROOT,capture_output=True,text=True)
    assert compiled.returncode==0,compiled.stderr
    ran=subprocess.run([str(exe)],cwd=ROOT,capture_output=True,text=True)
    assert ran.returncode==0,ran.stderr
    fixtures=[json.loads(line)for line in ran.stdout.splitlines()]
    for row in fixtures:
        grace=max(5,(row["deadline"]-row["arrival"])//3)
        window=max(1,min(row["T"],row["deadline"]+grace-1)-row["now"])
        path=[];tenant=row["tenant"]
        while tenant>=0:path.append(tenant);tenant=row["parents"][tenant]
        assert path==[1,3,0]
        quota=max(1,min(row["quota"][i]for i in path))
        headroom=min(row["quota"][i]-row["used"][i]for i in path)
        assert math.isclose(row["cached_rem"],row["raw_rem"]*(1+.03*math.log(row["n"])),rel_tol=1e-14)
        v=max(1,row["value"]);fee=row["zin"]*row["distance"]*row["Unet"]
        expected=np.asarray([
            row["n"],row["roots"]/row["n"],row["cost"]/v,row["cached_rem"]/window,
            row["rev"]/v,(row["rev"]-row["cost"])/v,row["work"]/(quota*window),headroom/quota,
            window/row["T"],row["now"]/row["T"],row["factor"],(row["deadline"]-row["now"])/window,
            row["cores"]/quota,row["preparation"]/window,fee/v,row["estimate"]*row["factor"]/window,
            (row["now"]-row["forecast_tick"])/row["T"],int(bool(row["warm"])),
        ],dtype=np.float32)
        actual=np.asarray(row["features"],dtype=np.float32)
        assert np.array_equal(actual,expected),(row["id"],actual,expected)
        assert row["prediction"]==predict(tree,expected)
        row.update({"python_features":expected.tolist(),"float32_exact":True,"window":window,
                    "path":path,"path_quota":quota,"headroom":headroom})
    samples=json.loads((ROOT/"results/v13_model_fit/samples.json").read_text(encoding="utf8"))
    vectors=[];labels=[]
    for sample in samples:
        vector=np.asarray(sample["features"],dtype=np.float32)
        assert predict(tree,vector)==sample["prediction"]
        vectors.append(vector);labels.append({"type":"fit_sample","row":sample["row"]})
    arrays=np.load(ROOT/"results/v13_model_fit/arrays.npz")
    x=arrays["x"]
    # For every internal node, use a training vector reaching it and test the
    # float32 values immediately around its exact exported double threshold.
    for node,feature in enumerate(tree["feature"]):
        if feature<0:continue
        representative=next(row for row in x if node in predict(tree,row,True)[1])
        centre=np.float32(tree["threshold"][node])
        for direction,value in [(-1,np.nextafter(centre,np.float32(-np.inf))),
                                (0,centre),(1,np.nextafter(centre,np.float32(np.inf)))]:
            vector=representative.copy();vector[feature]=value
            assert node in predict(tree,vector,True)[1]
            vectors.append(vector);labels.append({"type":"split_boundary","node":node,"direction":direction})
    expected=np.asarray([predict(tree,row)for row in vectors])
    input_text=str(len(vectors))+"\n"+"\n".join(" ".join(format(float(a),".9g")for a in row)for row in vectors)+"\n"
    ran_tree=subprocess.run([str(exe),"tree"],input=input_text,cwd=ROOT,capture_output=True,text=True)
    assert ran_tree.returncode==0,ran_tree.stderr
    actual=np.asarray([[float(a)for a in line.split()]for line in ran_tree.stdout.splitlines()])
    assert np.array_equal(actual,expected),(actual,expected)
    assert before=={str(p):hashlib.sha256(p.read_bytes()).hexdigest()for p in [source,tree_inc]}
    record={"actual_included_sources":before,"command":command,"compiler_stderr":compiled.stderr,
            "fixture_count":len(fixtures),"features_per_fixture":18,"all_72_float32_features_exact":True,
            "feature_fixture_details":fixtures,"tree_vectors":len(vectors),"fit_sample_vectors":len(samples),
            "split_boundary_vectors":len(vectors)-len(samples),"all_tree_predictions_exact":True,
            "tree_vector_descriptions":labels,"sources_unchanged":True,"interaction_benchmarks_run":0,
            "note":"Only four deterministic feature fixtures and existing training sample/split-boundary predictor queries; not a full replay of every pre-RUN state. Renamed included main may warn about its implicit return; production sources are unchanged."}
    (OUT/"features_tree.json").write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding="utf8")
    print(json.dumps({k:record[k]for k in ["fixture_count","all_72_float32_features_exact","tree_vectors","split_boundary_vectors","all_tree_predictions_exact","sources_unchanged","interaction_benchmarks_run"]}))


if __name__=="__main__":main()
