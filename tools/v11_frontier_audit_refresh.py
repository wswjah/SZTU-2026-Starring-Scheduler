"""Recompile the one-line generic oldCost fix; retain previous experiment hashes."""
from pathlib import Path
import hashlib
import json
import subprocess

ROOT=Path(__file__).resolve().parent.parent
path=ROOT/"research/v11_frontier_manifest.json"
records=json.loads(path.read_text(encoding="utf8"))
for record in records:
    source=Path(record["source"]);exe=Path(record["executable"])
    assert "j.c*du[i]*price[rackDc[w.home]]+feeAvg+j.xf" in source.read_text(encoding="utf8")
    record["before_old_cost_fix"]={"source_sha256":record["source_sha256"],"exe_sha256":record["exe_sha256"]}
    compiled=subprocess.run(["g++","-std=c++17","-O2","-Wall","-Wextra",str(source),"-o",str(exe)],capture_output=True,text=True,cwd=ROOT)
    assert compiled.returncode==0 and not compiled.stderr,compiled.stderr
    record.update(source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),exe_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),
                  audit_date="2026-11-16",correctness_fix="Subtract full original pending-job cost including WK queue term before replacement;WK0 behavior unchanged")
path.write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding="utf8")
print(json.dumps([{k:r[k]for k in ["name","source_sha256","exe_sha256"]}for r in records]))
