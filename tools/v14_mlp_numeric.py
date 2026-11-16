"""Compare exported C++ float64 inference with NumPy and saved torch outputs."""
from pathlib import Path
import hashlib
import json
import subprocess
import numpy as np
from v13_model_common import ROOT


def inference(info,x):
    a=np.clip((x.astype(np.float64)-np.asarray(info["mean"]))/np.asarray(info["scale"]),-8,8)
    for i,layer in enumerate(info["layers"]):
        a=a@np.asarray(layer["weight"]).T+np.asarray(layer["bias"])
        if i<len(info["layers"])-1:a=np.maximum(a,0)
    a[:,0]=np.clip(a[:,0],0,1);a[:,1]=np.clip(a[:,1],-2,1)
    return a


def main():
    out=ROOT/"results/v14_mlp_numeric";out.mkdir(parents=True,exist_ok=True)
    arrays=np.load(ROOT/"results/v13_model_fit/arrays.npz");x=arrays["x"]
    records=[]
    for architecture in ["A","B"]:
        info=json.loads((ROOT/f"research/v14_mlp_{architecture}.json").read_text(encoding="utf8"))
        samples=json.loads((ROOT/f"results/v14_mlp_fit/{architecture}_samples.json").read_text(encoding="utf8"))
        queries=[row["features"]for row in samples]
        rng=np.random.default_rng(info["seed"])
        mean=np.asarray(info["mean"]);scale=np.asarray(info["scale"])
        queries+=list(x[rng.choice(len(x),size=1024,replace=False)])
        # Values beyond both standardization clamps, plus near activation inputs.
        queries+=list((mean+rng.uniform(-12,12,size=(512,18))*scale).astype(np.float32))
        queries+=list((mean+rng.uniform(-1e-9,1e-9,size=(64,18))*scale).astype(np.float32))
        queries=np.asarray(queries,dtype=np.float32)
        request=str(len(queries))+"\n"+"".join(" ".join(format(float(v),".9g")for v in row)+"\n"for row in queries)
        exe=ROOT/f"build/v14_mlp_numeric_{architecture}.exe"
        definition='V14_MLP_AUDIT_SOURCE="../candidates/v14_mlp/'+architecture+'_veto_strict.cpp"'
        build=subprocess.run(["g++","-std=c++17","-O2","-D"+definition,"tools/v14_mlp_numeric.cpp","-o",str(exe)],capture_output=True,text=True,cwd=ROOT)
        assert build.returncode==0,build.stderr
        run=subprocess.run([str(exe)],input=request,capture_output=True,text=True,cwd=ROOT,timeout=20)
        assert run.returncode==0,run.stderr
        raw=np.asarray([list(map(float,line.split()))for line in run.stdout.splitlines()])
        expected=inference(info,queries);got=raw[:,1:3]
        error=float(np.max(np.abs(got-expected)));assert error<1e-12,(architecture,error)
        saved=np.asarray([row["prediction"]for row in samples]);torch_error=float(np.max(np.abs(got[:len(samples)]-saved)))
        assert torch_error<1e-12,(architecture,torch_error)
        px=queries.astype(np.float64)
        gates=np.column_stack([~((expected[:,1]<.02)&(px[:,5]<.25)&(px[:,0]>=3)),
                               ~((expected[:,1]<.08)&(px[:,5]<.4)&(px[:,0]>=3)),
                               .75*px[:,4]+.25*expected[:,0]>px[:,2]*1.05,
                               .5*px[:,4]+.5*expected[:,0]>px[:,2]*1.05])
        assert np.array_equal(raw[:,3:].astype(bool),gates)
        (out/f"{architecture}_output.txt").write_text(run.stdout,encoding="ascii")
        records.append({"architecture":architecture,"queries":len(queries),"cpp_numpy_max_abs_error":error,
                        "cpp_savedtorch_max_abs_error":torch_error,"all4_formula_gates_equal":True,
                        "note":"Float64 dot reduction order can differ byulps;predictions agree within1e-12 and all tested gate decisions exactly.",
                        "source_sha256":hashlib.sha256((ROOT/f"candidates/v14_mlp/{architecture}_veto_strict.cpp").read_bytes()).hexdigest(),
                        "compiler_stderr":build.stderr})
    record={"all_passed":True,"architectures":records,"no_interactive_runs":True}
    (ROOT/"research/v14_mlp_numeric.json").write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding="utf8")
    print(json.dumps({"all_passed":True,"architectures":[{k:v for k,v in row.items()if k not in ["compiler_stderr"]}for row in records]}))


if __name__=="__main__":main()
