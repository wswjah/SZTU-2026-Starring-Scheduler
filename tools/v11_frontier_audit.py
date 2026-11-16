"""Actual-helper oracle tests plus a targeted WK>0 oldCost negative control."""
from pathlib import Path
import hashlib
import json
import subprocess

ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/"results/v11_frontier_audit"
OUT.mkdir(parents=True,exist_ok=True)


def run(label,source,expect_pass=True):
    exe=ROOT/f"build/v11_frontier_audit_{label}.exe"
    definition='V11_FRONTIER_AUDIT_SOURCE="'+source.relative_to(ROOT).as_posix().replace("candidates/","../candidates/",1).replace("results/","../results/",1)+'"'
    compiled=subprocess.run(["g++","-std=c++17","-O2","-D"+definition,"tools/v11_frontier_audit.cpp","-o",str(exe)],capture_output=True,text=True,cwd=ROOT)
    assert compiled.returncode==0,compiled.stderr
    tested=subprocess.run([str(exe)],capture_output=True,text=True,cwd=ROOT,timeout=20)
    if expect_pass:assert tested.returncode==0,(label,tested.stdout,tested.stderr)
    else:assert tested.returncode!=0 and "forecast cost replacement" in tested.stderr,(label,tested.stdout,tested.stderr)
    return {"label":label,"source":str(source),"source_sha256":hashlib.sha256(source.read_bytes()).hexdigest(),
            "expected_pass":expect_pass,"exit_code":tested.returncode,"stdout":tested.stdout,"stderr":tested.stderr,
            "compiler_stderr":compiled.stderr,"exe_sha256":hashlib.sha256(exe.read_bytes()).hexdigest()}


def main():
    records=[];hashes={}
    for mode in ["cost_only","cost_and_time"]:
        source=ROOT/f"candidates/v11_frontier/{mode}.cpp";hashes[str(source)]=hashlib.sha256(source.read_bytes()).hexdigest()
        records.append(run(mode,source))
        text=source.read_text(encoding="utf8")
        assert text.count("PRM(WK, 0);")==1
        copy=OUT/f"wk_{mode}.cpp";copy.write_text(text.replace("PRM(WK, 0);","PRM(WK, 0.5);"),encoding="utf8")
        records.append(run("wk_"+mode,copy))
    text=(OUT/"wk_cost_only.cpp").read_text(encoding="utf8")
    old="double oldCost=j.c*du[i]*price[rackDc[w.home]]+feeAvg+j.xf;"
    assert text.count(old)==1
    negative=OUT/"old_cost_negative.cpp"
    negative.write_text(text.replace(old,"double oldCost=j.c*(du[i]-WK*ovWait)*price[rackDc[w.home]]+feeAvg+j.xf;"),encoding="utf8")
    records.append(run("negative_old_cost",negative,False))
    assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in hashes.items())
    record={"date":"2026-11-16","all_expected_results_observed":True,"source_unchanged_during_tests":True,
            "candidate_sources":hashes,"tests":records,
            "coverage":["normal/warm cash and preparation","quota/free/physical/up/reachability rejection","FAIL epoch memo invalidation",
                        "rem/work/tail/theta full recomputation","no real state mutation","started/left scope guard",
                        "WK0 actual sources","WK0.5 private audit copies","oldCost negative control detects stale queue charge"],
            "official_submission_sent":False}
    (ROOT/"results/v11_frontier_audit.json").write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding="utf8")
    print(json.dumps({"all_expected_results_observed":True,"tests":[{"label":r["label"],"exit_code":r["exit_code"],"stdout":r["stdout"],"stderr":r["stderr"]}for r in records]}))


if __name__=="__main__":main()
