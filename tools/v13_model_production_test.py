"""Non-interactive exact source-to-source feature/prediction/gate equivalence."""
from pathlib import Path
import hashlib
import json
import subprocess
import numpy as np
from v13_model_common import ROOT

OUT=ROOT/"results/v13_model_production_test"


def predict(model,x):
    node=0;t=model["tree"]
    while t["feature"][node]>=0:
        f=t["feature"][node];node=t["left"][node]if x[f]<=t["threshold"][node]else t["right"][node]
    return t["value"][node],node


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    model=json.loads((ROOT/"research/v13_model_tree.json").read_text(encoding="utf8"))
    samples=json.loads((ROOT/"results/v13_model_fit/samples.json").read_text(encoding="utf8"))
    queries=[]
    def add(n,value,net,factor,prep=5,warm=1):
        denominator=max(1,value);revenue=max(2.,net+2)*denominator;cost=revenue-net*denominator
        queries.append((int(n),int(value),float(cost),float(revenue),float(factor),float(prep),int(warm)))
    for sample in samples:
        x=sample["features"];add(int(x[0]),10000,x[5],x[10],max(0.,x[13])*100,int(x[17]))
    rng=np.random.default_rng(131611)
    for _ in range(2000):
        add(rng.choice([1,2,3,4,20,128]),rng.choice([0,1,100,10000,999999999]),rng.uniform(-1,1.5),rng.uniform(.1,4),rng.uniform(0,50),rng.integers(2))
    # Target every split with feasible ancestor bounds, then float neighbours.
    tree=model["tree"]
    def visit(node,low,high):
        feature=tree["feature"][node]
        if feature<0:return
        threshold=tree["threshold"][node];nearest=np.float32(threshold)
        for value in [np.nextafter(nearest,np.float32(-np.inf)),nearest,np.nextafter(nearest,np.float32(np.inf))]:
            x=np.maximum(low,np.minimum(high,np.zeros(18,dtype=np.float32)));x[feature]=value
            if np.all(x>=low)and np.all(x<=high):
                for n in [1,2,3,4]:add(n,1,float(x[5]),float(x[10]))
        upper=high.copy();upper[feature]=min(upper[feature],np.float32(threshold))
        if float(upper[feature])>threshold:upper[feature]=np.nextafter(upper[feature],np.float32(-np.inf))
        lower=low.copy();lower[feature]=max(lower[feature],np.float32(threshold))
        if float(lower[feature])<=threshold:lower[feature]=np.nextafter(lower[feature],np.float32(np.inf))
        visit(tree["left"][node],low,upper);visit(tree["right"][node],lower,high)
    visit(0,np.full(18,-100,dtype=np.float32),np.full(18,100,dtype=np.float32))
    for margin in [np.float32(.4),np.nextafter(np.float32(.4),np.float32(-np.inf)),np.nextafter(np.float32(.4),np.float32(np.inf)),0.,.08]:
        for n in [1,2,3,4]:add(n,10000,float(margin),2.5)
    request=str(len(queries))+"\n"+"".join(f"{n} {v} {cost:.17g} {rev:.17g} {factor:.17g} {prep:.17g} {warm}\n"for n,v,cost,rev,factor,prep,warm in queries)
    (OUT/"request.txt").write_text(request,encoding="ascii")
    outputs=[];builds=[]
    for label,path,trimmed in [("original",ROOT/"candidates/v13_model/veto_strict.cpp",False),("production",ROOT/"candidates/v13_model/production.cpp",True)]:
        exe=ROOT/f"build/v13_model_production_test_{label}.exe"
        definition='V13_MODEL_PRODUCTION_SOURCE="../'+path.relative_to(ROOT).as_posix()+'"'
        command=["g++","-std=c++17","-O2","-D"+definition]
        if trimmed:command.append("-DV13_MODEL_PRODUCTION_TRIMMED")
        command += ["tools/v13_model_production_test.cpp","-o",str(exe)]
        compiled=subprocess.run(command,capture_output=True,text=True,cwd=ROOT)
        assert compiled.returncode==0,compiled.stderr
        run=subprocess.run([str(exe)],input=request,capture_output=True,text=True,cwd=ROOT,timeout=20)
        assert run.returncode==0,run.stderr
        outputs.append(run.stdout);(OUT/f"{label}.txt").write_text(run.stdout,encoding="ascii")
        builds.append({"label":label,"source_sha256":hashlib.sha256(path.read_bytes()).hexdigest(),"compiler_stderr":compiled.stderr})
    assert outputs[0]==outputs[1],"Original and production outputs differ"
    leaves=set();decisions={True:0,False:0}
    for line,query in zip(outputs[0].splitlines(),queries):
        i,bitsNet,bitsFactor,net,factor,earned,prednet,allow=line.split()
        n,value,cost,rev,tenant,prep,warm=query
        netWant=np.float32((rev-cost)/max(1,value));factorWant=np.float32(tenant)
        assert int(bitsNet)==int(netWant.view(np.uint32))and int(bitsFactor)==int(factorWant.view(np.uint32))
        x=np.zeros(18,dtype=np.float32);x[5]=netWant;x[10]=factorWant
        prediction,leaf=predict(model,x);leaves.add(leaf)
        np.testing.assert_allclose([float(earned),float(prednet)],prediction,rtol=0,atol=1e-15)
        expected=not(prediction[1]<.08 and netWant<.4 and n>=3)
        assert bool(int(allow))==expected
        decisions[expected]+=1
    assert len(outputs[0].splitlines())==len(queries)
    assert leaves==set(i for i,f in enumerate(tree["feature"])if f<0)
    assert all(decisions.values())
    record={"all_passed":True,"queries":len(queries),"original_production_text_outputs_identical":True,
            "used_feature_float32_bits_identical":True,"python_reference_predictions_and_gates_exact":True,
            "all_leaves_covered":sorted(leaves),"allow_count":decisions[True],"reject_count":decisions[False],
            "gate_boundaries":"jobs1/2/3/4,all reachable tree leaves,adjacentfloat32 splitvalues,forecastmargin.4 neighbours",
            "no_interactive_runs":True,"no_model_or_policy_changes":True,"builds":builds}
    (ROOT/"research/v13_model_production_test.json").write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding="utf8")
    print(json.dumps({k:v for k,v in record.items()if k!="builds"}))


if __name__=="__main__":main()
