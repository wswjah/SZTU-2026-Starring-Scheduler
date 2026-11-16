"""Run actual-candidate transaction tests before any closed-loop benchmark."""
from pathlib import Path
import hashlib
import json
import subprocess

ROOT=Path(__file__).resolve().parent.parent
source=ROOT/"candidates/v12_order.cpp"
before=hashlib.sha256(source.read_bytes()).hexdigest()
exe=ROOT/"build/v12_order_tests.exe"
compiled=subprocess.run(["g++","-std=c++17","-O2","tools/v12_order_tests.cpp","-o",str(exe)],capture_output=True,text=True,cwd=ROOT)
assert compiled.returncode==0,compiled.stderr
run=subprocess.run([str(exe)],capture_output=True,text=True,cwd=ROOT,timeout=20)
assert run.returncode==0,(run.stdout,run.stderr)
assert hashlib.sha256(source.read_bytes()).hexdigest()==before
record={"all_passed":True,"source_sha256":before,"stdout":run.stdout,"stderr":run.stderr,
        "compiler_stderr":compiled.stderr,"test_exe_sha256":hashlib.sha256(exe.read_bytes()).hexdigest(),
        "coverage":["raw-scalar and real-state rollback","two actual order startup prices","forecast score","20k atomic prewarm boundaries0..7slots",
                    "busy-machine virtual reservation rollback","cache version ABA invalidation","reservation/quota/CPU/scope gates","only chosen commands committed","tie keeps original order","200 random multi-machine/cache/budget fixtures in both orders"],
        "source_unchanged":True,"official_submission_sent":False}
(ROOT/"results/v12_order_tests").mkdir(parents=True,exist_ok=True)
negative_controls=[]
for label,old,new,expected in [
    ("aba","        memset(v12OrderIv,0,sizeof v12OrderIv);","        ;","hypothetical registry quote versions invalidated"),
    ("ema","feeAvg=oldFee;",";","first order restores all logical state"),
]:
    text=source.read_text(encoding="utf8");assert text.count(old)==1
    negative=ROOT/f"results/v12_order_tests/negative_{label}.cpp";negative.write_text(text.replace(old,new),encoding="utf8")
    negative_exe=ROOT/f"build/v12_order_negative_{label}.exe"
    definition='V12_ORDER_AUDIT_SOURCE="../results/v12_order_tests/negative_'+label+'.cpp"'
    build=subprocess.run(["g++","-std=c++17","-O2","-D"+definition,"tools/v12_order_tests.cpp","-o",str(negative_exe)],capture_output=True,text=True,cwd=ROOT)
    assert build.returncode==0,build.stderr
    failed=subprocess.run([str(negative_exe)],capture_output=True,text=True,cwd=ROOT,timeout=20)
    assert failed.returncode!=0 and expected in failed.stderr,(label,failed.returncode,failed.stderr)
    negative_controls.append({"name":label,"exit_code":failed.returncode,"stderr":failed.stderr,"expected_failure_detected":True})
record["negative_controls"]=negative_controls
(ROOT/"results/v12_order_tests/summary.json").write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding="utf8")
manifest_path=ROOT/"research/v12_order_manifest.json"
manifest=json.loads(manifest_path.read_text(encoding="utf8"))
manifest.setdefault("pre_test_draft_sha256",manifest["source_sha256"])
manifest["source_sha256"]=before
manifest["exe_sha256"]=hashlib.sha256((ROOT/"build/v12_order.exe").read_bytes()).hexdigest()
manifest["transaction_tests"]="results/v12_order_tests/summary.json"
manifest["uninitialized_scalar_safety"]="Byte-copy Job scalar prefix only;Job pre/suc vectors are never mutated;Flow trivially-copyable representation restored via memcpy"
manifest_path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf8")
print(json.dumps({"all_passed":True,"stdout":run.stdout,"source_sha256":before}))
