"""Replace only the fixed tree predictor with either exported network;8 gates."""
from pathlib import Path
import hashlib
import json
import subprocess
from v13_model_common import ROOT,POLICIES


def main():
    directory=ROOT/"candidates/v14_mlp";directory.mkdir(parents=True,exist_ok=True)
    tree=(ROOT/"candidates/v13_model/tree.inc").read_text(encoding="ascii")
    records=[]
    for architecture in ["A","B"]:
        network=(directory/f"{architecture}.inc").read_text(encoding="ascii")
        for name,policy in POLICIES.items():
            original=ROOT/f"candidates/v13_model/{name}.cpp"
            source=original.read_text(encoding="utf8");assert source.count(tree)==1
            source=source.replace(tree,network).replace("V13_MODEL_POLICY attempts=","V14_MLP_POLICY attempts=")
            path=directory/f"{architecture}_{name}.cpp";exe=ROOT/f"build/v14_mlp_{architecture}_{name}.exe"
            assert not path.exists();path.write_bytes(source.encode("utf8"))
            build=subprocess.run(["g++","-std=c++17","-O2","-Wall","-Wextra",str(path),"-o",str(exe)],capture_output=True,text=True,cwd=ROOT)
            assert build.returncode==0 and not build.stderr,build.stderr
            records.append({"architecture":architecture,"name":f"{architecture}_{name}","policy_name":name,"policy":policy,
                            "source":str(path),"source_sha256":hashlib.sha256(path.read_bytes()).hexdigest(),
                            "executable":str(exe),"exe_sha256":hashlib.sha256(exe.read_bytes()).hexdigest(),
                            "original_policy_source":str(original),"only_predictor_replaced":True,
                            "model_sha256":hashlib.sha256((ROOT/f"research/v14_mlp_{architecture}.json").read_bytes()).hexdigest(),
                            "official_submission_sent":False})
    (ROOT/"research/v14_mlp_policies.json").write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding="utf8")
    print(json.dumps([{k:r[k]for k in ["architecture","name","source_sha256"]}for r in records]))


if __name__=="__main__":main()
