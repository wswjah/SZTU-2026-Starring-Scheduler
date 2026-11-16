"""Independently check real C++ features/tree/risk integration against Python."""
from pathlib import Path
import hashlib
import json
import subprocess
import numpy as np
from v9_alarm_train import read_world, make_tree

ROOT=Path(__file__).resolve().parent.parent
MODEL=ROOT/"research/v9_alarm_model.json"
SOURCE=ROOT/"candidates/v9_alarm_normal.cpp"
OUT=ROOT/"results/v9_alarm_audit"
OUT.mkdir(parents=True,exist_ok=True)


def interp(p,h):
    if h<=0:return 0.
    if h<=3:return p[0]*h/3
    if h<=8:return p[0]+(p[1]-p[0])*(h-3)/5
    if h<=16:return p[1]+(p[2]-p[1])*(h-8)/8
    return p[2]


def main():
    source_hash=hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    model=json.loads(MODEL.read_text(encoding="utf8"))
    arrays=np.load(ROOT/"results/v9_alarm_model/training_arrays.npz")
    tree=make_tree().fit(arrays["x"],arrays["y"],sample_weight=arrays["weights"])
    for key,actual in [("feature",tree.tree_.feature),("left",tree.tree_.children_left),
                       ("right",tree.tree_.children_right),("threshold",tree.tree_.threshold),
                       ("value",tree.tree_.value[:,:,0])]:
        np.testing.assert_array_equal(actual,np.asarray(model["tree"][key]))
    used=[1,2,4]
    manifest=json.loads((ROOT/"research/v9_alarm_trace_manifest.json").read_text(encoding="utf8"))
    tapes=sorted(manifest["tapes"],key=lambda r:r["case"])
    inputs=[str(len(tapes))]
    expected={}
    sample_records=[]
    rng=np.random.default_rng(915311)
    leaves_seen=set()
    for wi,entry in enumerate(tapes):
        path=Path(entry["path"])
        _,_,info,features,valid=read_world(path)
        T,M,W=[info[k] for k in ["T","M","W"]]
        pred=tree.predict(features.reshape(-1,10)).reshape(T+1,M,3)
        leaves=tree.apply(features.reshape(-1,10)).reshape(T+1,M)
        points={(t,min(x,M-1)) for t in [1,3,7,8,9,W,min(W+1,T),T-1,T] for x in [0,1,M-1]}
        indexes=np.argsort(pred[:,:,1].ravel(),kind="stable")[-16:]
        points.update((int(v//M),int(v%M)) for v in indexes if v//M>=1)
        for _ in range(16):points.add((int(rng.integers(1,T+1)),int(rng.integers(M))))
        for leaf in np.unique(leaves[1:]):
            candidates=np.argwhere((leaves==leaf)&(np.arange(T+1)[:,None]>=1))
            t,x=candidates[len(candidates)//2]
            points.add((int(t),int(x)));leaves_seen.add(int(leaf))
        points=sorted(points)
        rel=path.relative_to(ROOT).as_posix()
        inputs.append(f"{rel} {T} {M} {W} {len(points)}")
        for t,x in points:
            inputs.append(f"{t} {x}")
            expected[(wi,t,x)]=(features[t,x,used].astype(np.float64),pred[t,x])
            sample_records.append({"case":entry["case"],"tick":t,"machine":x,"leaf":int(leaves[t,x]),
                                   "features":features[t,x,used].tolist(),"probabilities":pred[t,x].tolist()})
    # Probe each internal threshold at neighbouring float32 values; ancestors
    # are set into their required intervals so these probes reach that node.
    synthetic=[]
    def descend(node,lower,upper):
        if tree.tree_.feature[node]<0:return
        feature=int(tree.tree_.feature[node]);threshold=float(tree.tree_.threshold[node])
        nearest=np.float32(threshold)
        for value in [np.nextafter(nearest,np.float32(-np.inf)),nearest,
                      np.nextafter(nearest,np.float32(np.inf))]:
            base=np.maximum(lower,np.minimum(upper,np.zeros(10,dtype=np.float32)))
            base[feature]=value
            if np.all(base>=lower) and np.all(base<=upper):synthetic.append(base)
        left_upper=upper.copy()
        left_upper[feature]=min(left_upper[feature],np.float32(threshold))
        if float(left_upper[feature])>threshold:
            left_upper[feature]=np.nextafter(left_upper[feature],np.float32(-np.inf))
        right_lower=lower.copy()
        right_lower[feature]=max(right_lower[feature],np.float32(threshold))
        if float(right_lower[feature])<=threshold:
            right_lower[feature]=np.nextafter(right_lower[feature],np.float32(np.inf))
        descend(tree.tree_.children_left[node],lower,left_upper)
        descend(tree.tree_.children_right[node],right_lower,upper)
    descend(0,np.full(10,-1e20,dtype=np.float32),np.full(10,1e20,dtype=np.float32))
    inputs.append(str(len(synthetic)))
    inputs.extend(" ".join(format(float(v),".9g") for v in row) for row in synthetic)
    request="\n".join(inputs)+"\n"
    (OUT/"request.txt").write_text(request,encoding="ascii")
    exe=ROOT/"build/v9_alarm_audit.exe"
    compiled=subprocess.run(["g++","-std=c++17","-O2","tools/v9_alarm_audit.cpp","-o",str(exe)],
                            capture_output=True,text=True,cwd=ROOT)
    assert compiled.returncode==0,compiled.stderr
    run=subprocess.run([str(exe)],input=request,capture_output=True,text=True,cwd=ROOT,timeout=60)
    (OUT/"output.txt").write_text(run.stdout,encoding="ascii")
    assert run.returncode==0,run.stderr
    seen=set();probes=set();interpolations=penalties=0;placement=False
    max_feature_error=max_probability_error=0.
    bg=np.asarray(model["background_probability"])
    for line in run.stdout.splitlines():
        values=line.split()
        if values[0]=="S":
            key=tuple(map(int,values[1:4]));features=np.asarray(list(map(float,values[4:7])));p=np.asarray(list(map(float,values[7:10])))
            want_x,want_p=expected[key]
            np.testing.assert_array_equal(features,want_x)
            np.testing.assert_allclose(p,want_p,rtol=0,atol=1e-15)
            max_feature_error=max(max_feature_error,float(np.max(np.abs(features-want_x))))
            max_probability_error=max(max_probability_error,float(np.max(np.abs(p-want_p))))
            seen.add(key)
        elif values[0]=="P":
            index=int(values[1]);p=np.asarray(list(map(float,values[2:])))
            np.testing.assert_allclose(p,tree.predict(synthetic[index].reshape(1,-1))[0],rtol=0,atol=1e-15)
            probes.add(index)
        elif values[0]=="I":
            h,value=map(float,values[1:]);assert abs(value-interp([.1,.3,.6],h))<1e-15
            interpolations+=1
        elif values[0]=="R":
            wait,prep,value=map(float,values[1:]);h=min(16,max(0,prep+10))
            want=0 if wait>0 else max(0,interp([.1,.3,.6],h)-interp(bg,h))*(12*h*.5+100)
            assert abs(value-want)<1e-12,(line,want)
            assert value>=0;penalties+=1
        elif values[0]=="B":assert float(values[1])==0
        elif values[0]=="C":placement=True
        else:raise AssertionError(line)
    assert seen==set(expected) and probes==set(range(len(synthetic)))
    assert placement and interpolations==9 and penalties==9
    assert leaves_seen==set(np.flatnonzero(tree.tree_.feature<0))
    source=SOURCE.read_text(encoding="utf8")
    assert source.count("cost+=v9RiskPenalty(x,wt,s,est,corePrice,th);")==1
    assert source.count("warm+=v9RiskPenalty(x,wt,tts[r],est,corePrice,th);")==1
    assert source.index("warm+=v9RiskPenalty")<source.index("int wm = PW")
    assert hashlib.sha256(SOURCE.read_bytes()).hexdigest()==source_hash
    record={"all_passed":True,"source":str(SOURCE),"source_sha256":source_hash,
            "model_sha256":hashlib.sha256(MODEL.read_bytes()).hexdigest(),
            "training_rows":len(arrays["y"]),"sklearn_refit_export_arrays_identical":True,
            "tapes_replayed":len(tapes),"runtime_feature_snapshots":len(expected),"used_features":used,
            "all_final_leaves_covered":sorted(leaves_seen),"threshold_float32_probes":len(synthetic),
            "max_feature_absolute_error":max_feature_error,"max_probability_absolute_error":max_probability_error,
            "interpolation_cases":interpolations,"risk_penalty_cases":penalties,
            "positive_reservations_have_zero_penalty":True,"nonnegative_excess_penalties":True,
            "actual_tryPlace_checks":["risk changes machine choice","risk can favor prewarm","real ledger preserved"],
            "normal_and_warm_are_both_charged_before_selection":True,
            "source_unchanged":True,"compiler_stderr":compiled.stderr,"test_stdout":"results/v9_alarm_audit/output.txt",
            "note":"log1p wrapper records the actual feature calls and returns the identical double expression; no candidate file was edited.",
            "sample_snapshots":sample_records}
    (ROOT/"results/v9_alarm_audit.json").write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding="utf8")
    print(json.dumps({k:v for k,v in record.items() if k not in ["sample_snapshots","compiler_stderr"]},ensure_ascii=False))


if __name__=="__main__":main()
