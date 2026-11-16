"""Two output-preserving performance candidates on the fixed-buffer base."""
from pathlib import Path
import hashlib
import json
import subprocess

ROOT=Path(__file__).resolve().parent.parent
BASE=ROOT/"versions/v10_input_fix/main.cpp"


def replace_once(source,old,new):
    assert source.count(old)==1,old[:100]
    return source.replace(old,new)


def apply_memo(source):
    old="""            ll qreg = 0, qrack = 0;
            for (int l : imageLayers[j.img])
                if (!machCache[x].in[l]) (rackCache[r].in[l] ? qrack : qreg) += layerSize[l];"""
    new="""            // This quote intentionally uses membership only, exactly as before.
            // Exact LRU preview would require an independent order version.
            struct MembershipQuote { int machineVersion,rackVersion; ll reg,rack; };
            static MembershipQuote memo[120][360];
            MembershipQuote& saved=memo[j.img][x];
            if(saved.machineVersion!=machCache[x].ver+1 || saved.rackVersion!=rackCache[r].ver+1) {
                saved.machineVersion=machCache[x].ver+1;
                saved.rackVersion=rackCache[r].ver+1;
                saved.reg=saved.rack=0;
                for(int l:imageLayers[j.img])
                    if(!machCache[x].in[l]) (rackCache[r].in[l]?saved.rack:saved.reg)+=layerSize[l];
            }
            ll qreg=saved.reg,qrack=saved.rack;"""
    source=replace_once(source,old,new)
    source=replace_once(source,"                c.q.clear(), c.sum = 0;","                c.q.clear(), c.sum = 0;\n                ++c.ver;  // Invalidate membership quotes after machine failure.")
    return source


def apply_o3(source):
    anchor="#include <bits/stdc++.h>"
    return replace_once(source,anchor,'#pragma GCC optimize("O3")\n'+anchor)


def build(name,source):
    path=ROOT/f"candidates/v11_perf_{name}.cpp"
    assert not path.exists(),"Do not replace prior experiments"
    path.write_bytes(source.encode("utf8"))
    exe=ROOT/f"build/v11_perf_{name}.exe"
    run=subprocess.run(["g++","-std=c++17","-O2","-Wall","-Wextra",str(path),"-o",str(exe)],capture_output=True,text=True,cwd=ROOT)
    assert run.returncode==0 and not run.stderr,run.stderr
    return {"name":name,"source":str(path),"source_sha256":hashlib.sha256(path.read_bytes()).hexdigest(),
            "exe":str(exe),"exe_sha256":hashlib.sha256(exe.read_bytes()).hexdigest()}


def main():
    source=BASE.read_text(encoding="utf8")
    records=[build("memo",apply_memo(source)),build("o3",apply_o3(source))]
    (ROOT/"research/v11_perf_candidates.json").write_text(json.dumps({"base":str(BASE),"base_sha256":hashlib.sha256(BASE.read_bytes()).hexdigest(),"candidates":records,"official_submission_sent":False},ensure_ascii=False,indent=2),encoding="utf8")
    print(json.dumps([{k:r[k] for k in ["name","source_sha256"]}for r in records]))


if __name__=="__main__":main()
