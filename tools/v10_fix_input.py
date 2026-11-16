"""Reproduce the legal large-Huffman-log token overflow; harden only its buffer."""
from pathlib import Path
import hashlib
import heapq
import json
import subprocess
import sys

ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/"results/v10_fix_input"
BASE=ROOT/"versions/v8_fine/main.cpp"


def huffman_codes(frequencies):
    heap=[(weight,i,{i:""}) for i,weight in enumerate(frequencies)]
    heapq.heapify(heap)
    for node in range(9,17):
        a=heapq.heappop(heap);b=heapq.heappop(heap)
        codes={k:"0"+v for k,v in a[2].items()}|{k:"1"+v for k,v in b[2].items()}
        heapq.heappush(heap,(a[0]+b[0],node,codes))
    return heap[0][2]


def run_program(exe,data):
    run=subprocess.run([str(exe)],input=data,capture_output=True,cwd=ROOT,timeout=20)
    return {"exit_code":run.returncode,"stdout_bytes":len(run.stdout),"stderr":run.stderr.decode("utf8",errors="replace")[:2000],
            "stdout_sha256":hashlib.sha256(run.stdout).hexdigest()},run.stdout


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    source=BASE.read_text(encoding="utf8")
    old="char inbuf[1 << 16], tok[1 << 22];"
    assert source.count(old)==1
    candidate=source.replace(old,"char inbuf[1 << 16], tok[1 << 23];")
    path=ROOT/"candidates/v10_fix_input.cpp"
    if path.exists():
        assert path.read_bytes()==candidate.encode("utf8"),"Never overwrite a different prior experiment"
    else:
        path.write_bytes(candidate.encode("utf8"))
    exe=ROOT/"build/v10_fix_input.exe"
    compile_result=subprocess.run(["g++","-std=c++17","-O2","-Wall","-Wextra",str(path),"-o",str(exe)],capture_output=True,text=True,cwd=ROOT)
    assert compile_result.returncode==0 and not compile_result.stderr,compile_result.stderr
    frequencies=[1,1,2,3,5,8,13,21,34]
    codes=huffman_codes(frequencies)
    assert len(codes[0])==8
    count=3_000_000
    encoded=bytes([int(codes[0],2)]).hex()*count
    assert len(encoded)==6_000_000
    initialization=["400 2 2 2 2 30 1 1 1 20 1","1 1 1 1 1","1 1",
                    "0 0 1","1 1 1","0 1 1 1","1 1 1 1","0 1 1","-1 100"]
    initialization += ["0 1"]*29
    initialization += ["1","1 0"," ".join(map(str,frequencies)),"a 1"]
    transcript="\n".join(initialization)+f"\nTICK 1 1 1\nLOG 0 {8*count} {encoded}\nALARM 0\n"
    transcript += "".join(f"TICK {tick} 0 1\nALARM 0\n" for tick in range(2,401))
    data=transcript.encode("ascii")
    (OUT/"large_huffman_protocol.in").write_bytes(data)
    expected="".join(f"ANS {count if tick<=20 else 0}\nEND\n" for tick in range(1,401)).encode("ascii")
    baseline,baseline_out=run_program(ROOT/"build/v8_fine.exe",data)
    fixed,fixed_out=run_program(exe,data)
    baseline["all_answers_exact"]=baseline_out.replace(b"\r\n",b"\n")==expected
    fixed["all_answers_exact"]=fixed_out.replace(b"\r\n",b"\n")==expected
    baseline["first_audit"]=baseline_out.splitlines()[0].decode("ascii",errors="replace") if baseline_out else None
    fixed["first_audit"]=fixed_out.splitlines()[0].decode("ascii",errors="replace") if fixed_out else None
    (OUT/"baseline_stdout.txt").write_bytes(baseline_out)
    (OUT/"fixed_stdout.txt").write_bytes(fixed_out)
    assert not baseline["all_answers_exact"],"Expected original overflow did not reproduce"
    assert fixed["exit_code"]==0 and fixed["all_answers_exact"],fixed
    record={"base":str(BASE),"base_sha256":hashlib.sha256(BASE.read_bytes()).hexdigest(),
            "source":str(path),"source_sha256":hashlib.sha256(path.read_bytes()).hexdigest(),
            "exe":str(exe),"exe_sha256":hashlib.sha256(exe.read_bytes()).hexdigest(),
            "change":"tok capacity4MiB to8MiB; all program tokens identical except one exponent",
            "decoded_log_characters":count,"huffman_code_for_a":codes[0],"encoded_hex_length":len(encoded),
            "bounds":{"T":400,"D":2,"N":2,"R":2,"M":2,"K":30,"L":1,"I":1,"P":1,"W":20,"E":1,"jobs":0,"audits":400},
            "baseline":baseline,"fixed":fixed,"expected_first_audit":"ANS 3000000",
            "expected_all_audits":"400 answers:3,000,000 for ticks1..20,zero for ticks21..400; every response END,CRLF normalized",
            "method":"Direct complete protocol transcript with manually exact ALARM answers; not an official interactor run or official hidden data.",
            "official_submission_sent":False}
    (ROOT/"research/v10_fix_input_manifest.json").write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding="utf8")
    print(json.dumps({"baseline":baseline,"fixed":fixed,"encoded_hex_length":len(encoded)},ensure_ascii=False))
    bench=subprocess.run([sys.executable,"tools/bench.py","--exe",str(exe),"--cases","cases/train","--out","results/v10_fix_input_train","--workers","1"],
                         capture_output=True,text=True,encoding="utf8",cwd=ROOT)
    assert bench.returncode==0,bench.stdout+bench.stderr
    print("Fixed-buffer candidate passed train16",flush=True)


if __name__=="__main__":main()
