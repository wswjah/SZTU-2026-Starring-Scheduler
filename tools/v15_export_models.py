"""Four fixed models replace corresponding existing gates;no threshold selection."""
from pathlib import Path
import hashlib
import json
import subprocess
from v13_model_common import ROOT


def main():
    plan=json.loads((ROOT/"research/v15_training_plan.json").read_text(encoding="utf8"))
    old_predictor=(ROOT/"candidates/v13_model/tree.inc").read_text(encoding="ascii")
    records=[]
    for name,settings in plan["models"].items():
        model_path=ROOT/f"research/v15_{name}.json";assert model_path.is_file()
        predictor=(ROOT/f"candidates/v15_models/{name}.inc").read_text(encoding="ascii")
        policy=settings["policy_name"];original=ROOT/f"candidates/v13_model/{policy}.cpp"
        source=original.read_text(encoding="utf8");assert source.count(old_predictor)==1
        source=source.replace(old_predictor,predictor).replace("V13_MODEL_POLICY attempts=","V15_MODEL_POLICY attempts=")
        path=ROOT/f"candidates/v15_models/{name}.cpp";exe=ROOT/f"build/v15_{name}.exe"
        assert not path.exists();path.write_bytes(source.encode("utf8"))
        compiled=subprocess.run(["g++","-std=c++17","-O2","-Wall","-Wextra",str(path),"-o",str(exe)],capture_output=True,text=True,cwd=ROOT)
        assert compiled.returncode==0 and not compiled.stderr,compiled.stderr
        record={"name":name,"source":str(path),"source_sha256":hashlib.sha256(path.read_bytes()).hexdigest(),"source_bytes":path.stat().st_size,
                "executable":str(exe),"exe_sha256":hashlib.sha256(exe.read_bytes()).hexdigest(),
                "model_json":str(model_path),"model_sha256":hashlib.sha256(model_path.read_bytes()).hexdigest(),
                "policy_name":policy,"settings":settings,"original_policy_source":str(original),
                "only_predictor_replaced":True,"diagnostic_prefix":"V15_MODEL_POLICY",
                "original_header_and_byte_rollback_preserved":True,"all4_enter_validation_without_training_selection":True,
                "fresh_data_accessed":False,"official_submission_sent":False}
        records.append(record)
    (ROOT/"research/v15_models.json").write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding="utf8")
    print(json.dumps([{k:r[k]for k in ["name","source_sha256","policy_name"]}for r in records]))


if __name__=="__main__":main()
