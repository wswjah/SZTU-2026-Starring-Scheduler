"""Non-interactive exact model/reference checks for all four expanded models."""
from pathlib import Path
import hashlib
import json
import subprocess
import numpy as np
from v13_model_common import ROOT
from v14_mlp_numeric import inference


def tree_prediction(info,x):
    tree=info["tree"];output=[];leaves=[]
    for row in x:
        node=0
        while tree["feature"][node]>=0:
            node=tree["left"][node]if row[tree["feature"][node]]<=tree["threshold"][node]else tree["right"][node]
        output.append(tree["value"][node]);leaves.append(node)
    return np.asarray(output),leaves


def main():
    records=json.loads((ROOT/"research/v15_models.json").read_text(encoding="utf8"))
    arrays=np.load(ROOT/"results/v15_model_dataset/arrays.npz",allow_pickle=False);x=arrays["x"]
    out=ROOT/"results/v15_numeric";out.mkdir(parents=True,exist_ok=True)
    results=[]
    for record in records:
        name=record["name"];info=json.loads(Path(record["model_json"]).read_text(encoding="utf8"))
        samples=json.loads((ROOT/f"results/v15_fit/{name}_samples.json").read_text(encoding="utf8"))
        rng=np.random.default_rng(info["settings"]["seed"])
        queries=[row["features"]for row in samples];queries+=list(x[rng.choice(len(x),size=1024,replace=False)])
        if info["settings"]["kind"]=="mlp":
            mean=np.asarray(info["mean"]);scale=np.asarray(info["scale"])
            queries+=list((mean+rng.uniform(-12,12,(512,18))*scale).astype(np.float32))
            queries+=list((mean+rng.uniform(-1e-9,1e-9,(64,18))*scale).astype(np.float32))
        else:
            tree=info["tree"]
            def visit(node,low,high):
                feature=tree["feature"][node]
                if feature<0:return
                threshold=tree["threshold"][node];center=np.float32(threshold)
                for value in [np.nextafter(center,np.float32(-np.inf)),center,np.nextafter(center,np.float32(np.inf))]:
                    row=np.maximum(low,np.minimum(high,np.zeros(18,dtype=np.float32)));row[feature]=value
                    if np.all(row>=low)and np.all(row<=high):queries.append(row)
                upper=high.copy();upper[feature]=min(upper[feature],center)
                if float(upper[feature])>threshold:upper[feature]=np.nextafter(upper[feature],np.float32(-np.inf))
                lower=low.copy();lower[feature]=max(lower[feature],center)
                if float(lower[feature])<=threshold:lower[feature]=np.nextafter(lower[feature],np.float32(np.inf))
                visit(tree["left"][node],low,upper);visit(tree["right"][node],lower,high)
            visit(0,np.full(18,-1e20,dtype=np.float32),np.full(18,1e20,dtype=np.float32))
        queries=np.asarray(queries,dtype=np.float32)
        request=str(len(queries))+"\n"+"".join(" ".join(format(float(v),".9g")for v in row)+"\n"for row in queries)
        exe=ROOT/f"build/v15_numeric_{name}.exe"
        definition='V14_MLP_AUDIT_SOURCE="../candidates/v15_models/'+name+'.cpp"'
        compiled=subprocess.run(["g++","-std=c++17","-O2","-D"+definition,"tools/v14_mlp_numeric.cpp","-o",str(exe)],capture_output=True,text=True,cwd=ROOT)
        assert compiled.returncode==0,compiled.stderr
        run=subprocess.run([str(exe)],input=request,capture_output=True,text=True,cwd=ROOT,timeout=20)
        assert run.returncode==0,run.stderr
        actual=np.asarray([list(map(float,line.split()))for line in run.stdout.splitlines()]);got=actual[:,1:3]
        if info["settings"]["kind"]=="mlp":expected=inference(info,queries);leaves=None
        else:expected,leaves=tree_prediction(info,queries)
        tolerance=1e-12 if leaves is None else 1e-15
        error=float(np.max(np.abs(got-expected)));assert error<tolerance,(name,error)
        saved=np.asarray([row["prediction"]for row in samples]);saved_error=float(np.max(np.abs(got[:len(samples)]-saved)));assert saved_error<tolerance,(name,saved_error)
        p=queries.astype(np.float64)
        gates=np.column_stack([~((expected[:,1]<.02)&(p[:,5]<.25)&(p[:,0]>=3)),
                               ~((expected[:,1]<.08)&(p[:,5]<.4)&(p[:,0]>=3)),
                               .75*p[:,4]+.25*expected[:,0]>p[:,2]*1.05,
                               .5*p[:,4]+.5*expected[:,0]>p[:,2]*1.05])
        assert np.array_equal(actual[:,3:].astype(bool),gates)
        if leaves is not None:assert set(leaves)==set(i for i,f in enumerate(info["tree"]["feature"])if f<0)
        (out/f"{name}.txt").write_text(run.stdout,encoding="ascii")
        results.append({"name":name,"queries":len(queries),"cpp_numpy_max_abs_error":error,"cpp_saved_final_prediction_error":saved_error,
                        "all4_formula_gates_equal":True,"all_leaves_covered":sorted(set(leaves))if leaves is not None else None,
                        "source_sha256":record["source_sha256"],"compiler_stderr":compiled.stderr})
    summary={"all_passed":True,"models":results,"no_interactive_runs":True,"fresh_data_accessed":False,"official_submission_sent":False}
    (ROOT/"research/v15_numeric.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf8")
    print(json.dumps({"all_passed":True,"models":[{k:v for k,v in r.items()if k!="compiler_stderr"}for r in results]}))


if __name__=="__main__":main()
