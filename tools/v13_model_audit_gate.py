"""Fixed actual-policy decision/state tests, no interaction or model refitting."""
from pathlib import Path
import hashlib
import json
import math
import subprocess
import numpy as np
from v13_model_audit_features import predict

ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/"results/v13_model_audit"


def main():
    tree=json.loads((ROOT/"research/v13_model_tree.json").read_text(encoding="utf8"))["tree"]
    policies=json.loads((ROOT/"research/v13_model_policies.json").read_text(encoding="utf8"))
    decision_rows=[]
    for n in [1,2,3,7]:
        for factor in [1.,1.5]:
            for net in [-.1,0,.05,.08670411,.08670413,.15,.25,.4,.6,.8,.9]:
                decision_rows.append({"n":n,"factor":factor,"cost":100.,"rev":100.+1000*net,"kind":"grid"})
    low_vector=np.zeros(18,dtype=np.float32);low_vector[5]=.05;low_vector[10]=1.5
    earned=predict(tree,low_vector)[0]
    for weight in [.25,.5]:
        cost=1000*((1-weight)*.05+weight*earned)/(weight+.05)
        centre=(cost*1.05-weight*earned*1000)/(1-weight)
        for direction in [-1,0,1]:
            rev=centre
            if direction:
                for _ in range(32):rev=math.nextafter(rev,math.inf if direction>0 else -math.inf)
            decision_rows.append({"n":3,"factor":1.5,"cost":cost,"rev":rev,"kind":"blend_threshold","weight":weight,"direction":direction})
    records=[]
    for index,policy in enumerate(policies):
        name=policy["name"];source=Path(policy["source"]);before=hashlib.sha256(source.read_bytes()).hexdigest()
        assert before==policy["source_sha256"]
        exe=ROOT/f"build/v13_model_audit_gate_{name}.exe"
        command=["g++","-std=c++17","-O2","-Wall","-Wextra",f'-DV13_MODEL_AUDIT_SOURCE="../candidates/v13_model/{name}.cpp"',f"-DV13_MODEL_AUDIT_KIND={index}","tools/v13_model_audit_gate.cpp","-o",str(exe)]
        compiled=subprocess.run(command,cwd=ROOT,capture_output=True,text=True)
        assert compiled.returncode==0,compiled.stderr
        state_run=subprocess.run([str(exe)],cwd=ROOT,capture_output=True,text=True)
        assert state_run.returncode==0,state_run.stderr
        input_text=str(len(decision_rows))+"\n"+"\n".join(f"{r['n']} {r['factor']:.17g} {r['cost']:.17g} {r['rev']:.17g}"for r in decision_rows)+"\n"
        ran=subprocess.run([str(exe),"decisions"],input=input_text,cwd=ROOT,capture_output=True,text=True)
        assert ran.returncode==0,ran.stderr
        outputs=[line.split()for line in ran.stdout.splitlines()]
        assert len(outputs)==len(decision_rows)
        rejected=0
        for row,output in zip(decision_rows,outputs):
            x=np.zeros(18,dtype=np.float32);x[5]=(row["rev"]-row["cost"])/1000;x[10]=row["factor"]
            expected_prediction=predict(tree,x)
            assert [float(a)for a in output[1:3]]==expected_prediction
            assert np.float32(output[3])==x[5]and np.float32(output[4])==x[10]
            rule=policy["policy"]
            if rule["type"]=="net_veto":
                expected=not(expected_prediction[1]<rule["net_threshold"]and float(x[5])<rule["forecast_net_threshold"]and row["n"]>=rule["min_jobs"])
            else:
                weight=rule["model_weight"]
                expected=(1-weight)*row["rev"]+weight*expected_prediction[0]*1000>row["cost"]*1.05
            assert bool(int(output[0]))==expected,(name,row,output,expected)
            rejected+=not expected
        assert hashlib.sha256(source.read_bytes()).hexdigest()==before
        records.append({"policy":name,"source_sha256":before,"source_unchanged":True,"compile_command":command,"compiler_stderr":compiled.stderr,
                        "state_exit_code":state_run.returncode,"state_stdout":state_run.stdout,
                        "decision_queries":len(outputs),"all_actual_cpp_decisions_match_independent_python":True,"query_rejections":rejected})
    result={"policies":records,"decision_rows":decision_rows,"interaction_benchmarks_run":0,
            "decision_queries":sum(r["decision_queries"]for r in records),"all_passed":True,
            "light_is_analytic_noop":min(v[1]for f,v in zip(tree["feature"],tree["value"])if f<0)>.02,
            "note":"The nonzero raw prefix fixture tests restoration without typed-reading old reservation values. Renamed included solver main may produce its implicit-return warning; candidates are unchanged."}
    (OUT/"gate.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf8")
    print(json.dumps({"all_passed":True,"policies":len(records),"decision_queries":result["decision_queries"],"interaction_benchmarks_run":0,"light_is_analytic_noop":result["light_is_analytic_noop"]}))


if __name__=="__main__":main()
