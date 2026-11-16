"""Verify the unchanged-policy reduction using actual production C++ functions."""
from pathlib import Path
import hashlib
import json
import runpy
import subprocess
import numpy as np
from v13_model_audit_features import predict

ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/"results/v13_model_audit"


def main():
    strict=ROOT/"candidates/v13_model/veto_strict.cpp";production=ROOT/"candidates/v13_model/production.cpp"
    original=strict.read_text(encoding="utf8");reduced=production.read_text(encoding="utf8")
    assert hashlib.sha256(strict.read_bytes()).hexdigest()=="560c63b3dbcbe6341b315b1b56ef36f0d41dd902d12216bb5cb12ba3d4d5d55c"
    before={str(p):hashlib.sha256(p.read_bytes()).hexdigest()for p in [strict,production]}
    ns=runpy.run_path(str(ROOT/"tools/v13_model_production.py"),run_name="v13_independent_reduction_readonly")
    assert ns["make"](original)==reduced
    tree_inc=(ROOT/"candidates/v13_model/tree.inc").read_text(encoding="ascii")
    assert tree_inc in original and tree_inc in reduced
    condition="bool allow=!(prediction[1]<0.08&&x[5]<0.4&&flows[jobs[ji].wf].n>=3);"
    assert condition in original and condition in reduced
    assert "x[5]=float((p.rev-p.cost)/value);"in reduced and "x[10]=float(tenFactor(w.tenant));"in reduced
    assert "float x[18]{};"in reduced
    model=json.loads((ROOT/"research/v13_model_tree.json").read_text(encoding="utf8"));tree=model["tree"]
    assert set(tree["feature"])-{-2}=={5,10}
    gate=json.loads((OUT/"gate.json").read_text(encoding="utf8"));rows=gate["decision_rows"]
    exe=ROOT/"build/v13_model_audit_production.exe"
    command=["g++","-std=c++17","-O2","-Wall","-Wextra",'-DV13_MODEL_AUDIT_SOURCE="../candidates/v13_model/production.cpp"',"-DV13_MODEL_AUDIT_KIND=1","-DV13_MODEL_AUDIT_PRODUCTION=1","tools/v13_model_audit_gate.cpp","-o",str(exe)]
    compiled=subprocess.run(command,cwd=ROOT,capture_output=True,text=True)
    assert compiled.returncode==0,compiled.stderr
    state_run=subprocess.run([str(exe)],cwd=ROOT,capture_output=True,text=True)
    assert state_run.returncode==0,state_run.stderr
    input_text=str(len(rows))+"\n"+"\n".join(f"{r['n']} {r['factor']:.17g} {r['cost']:.17g} {r['rev']:.17g}"for r in rows)+"\n"
    ran=subprocess.run([str(exe),"decisions"],input=input_text,cwd=ROOT,capture_output=True,text=True)
    assert ran.returncode==0,ran.stderr
    outputs=[line.split()for line in ran.stdout.splitlines()];assert len(outputs)==len(rows)
    for row,output in zip(rows,outputs):
        x=np.zeros(18,dtype=np.float32);x[5]=(row["rev"]-row["cost"])/1000;x[10]=row["factor"]
        expected=predict(tree,x)
        assert [float(a)for a in output[1:3]]==expected
        assert np.float32(output[3])==x[5]and np.float32(output[4])==x[10]
        allow=not(expected[1]<.08 and float(x[5])<.4 and row["n"]>=3)
        assert bool(int(output[0]))==allow
    assert before=={str(p):hashlib.sha256(p.read_bytes()).hexdigest()for p in [strict,production]}
    record={"sources":before,"generator_reproduces_production_exactly":True,"tree_inc_and_gate_condition_identical":True,
            "used_features":[5,10],"two_float32_formulas_identical":True,"all_other_runtime_slots_zero_initialized":True,
            "actual_production_state_cases_passed":True,"state_stdout":state_run.stdout,
            "production_decision_queries":len(rows),"all_predictions_features_and_decisions_match_full_strict_reference":True,
            "compile_command":command,"compiler_stderr":compiled.stderr,"candidate_sources_unchanged":True,
            "interaction_benchmarks_run":0,"note":"This proves fixed-function/state cases, not complete CPU-insurance trajectory equivalence; root owns production80 full-report comparison."}
    (OUT/"production.json").write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding="utf8")
    print(json.dumps({"production_decisions":len(rows),"all_checks_passed":True,"sources_unchanged":True,"interaction_benchmarks_run":0}))


if __name__=="__main__":main()
