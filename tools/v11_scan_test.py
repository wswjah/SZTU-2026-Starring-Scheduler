"""Exercise the actual integer reader across buffer boundaries and signed limits."""
from pathlib import Path
import hashlib
import json
import subprocess

ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/"results/v11_scan_test"
OUT.mkdir(parents=True,exist_ok=True)
exe=ROOT/"build/v11_scan_test.exe"
compiled=subprocess.run(["g++","-std=c++17","-O2","tools/v11_scan_test.cpp","-o",str(exe)],capture_output=True,text=True,cwd=ROOT)
assert compiled.returncode==0,compiled.stderr
values=[0,1,-1,9223372036854775807,-9223372036854775808,2147483647,-2147483648,999999999,-999999999,17,0,-0]
spellings=["0","+1","-1","9223372036854775807","-9223372036854775808","2147483647","-2147483648","999999999","-999999999","+17","+0","-0"]
records=[]
for crossing in [0,1,7,17,65486,65510,65530,65535,65536,65537,131065]:
    padding=b" "*crossing
    raw=padding+(" \r\n\t\v\f".join(spellings)+"\nTEXT -123\nDeAdBeEf +456 -789").encode("ascii")
    expected=[str(v)for v in values]+["TEXT","-123","DeAdBeEf","456","-789","0","0"]
    run=subprocess.run([str(exe)],input=raw,capture_output=True,cwd=ROOT,timeout=10)
    actual=run.stdout.decode("ascii").splitlines()
    assert run.returncode==0 and actual==expected,(crossing,run.returncode,actual,expected)
    records.append({"padding":crossing,"bytes":len(raw),"all_values_exact":True,"input_sha256":hashlib.sha256(raw).hexdigest()})
large=(ROOT/"results/v10_fix_input/large_huffman_protocol.in").read_bytes()
large_run=subprocess.run([str(ROOT/"build/v11_scan.exe")],input=large,capture_output=True,cwd=ROOT,timeout=20)
large_expected="".join(f"ANS {3000000 if tick<=20 else 0}\nEND\n"for tick in range(1,401)).encode("ascii")
assert large_run.returncode==0 and large_run.stdout.replace(b"\r\n",b"\n")==large_expected
record={"all_passed":True,"cases":records,"expected":expected,"signed_min_and_max":True,"optional_plus":True,
        "whitespace":"space CR LF TAB VT FF","EOF_returns_zero_twice":True,
        "numeric_tokens_cross_input_buffer_boundary":True,"text_hex_mixed_reads_exact":True,
        "six_million_hex_token_regression_exact":True,"large_protocol_answers":400,
        "compiler_stderr":compiled.stderr,"source_sha256":hashlib.sha256((ROOT/"candidates/v11_scan.cpp").read_bytes()).hexdigest()}
(OUT/"summary.json").write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding="utf8")
print(json.dumps({"all_passed":True,"cases":len(records)}))
