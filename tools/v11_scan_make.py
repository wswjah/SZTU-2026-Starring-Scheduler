"""Direct integer scanning; text/hex tokens and8MiB token buffer stay intact."""
from pathlib import Path
import hashlib
import json
import subprocess

ROOT=Path(__file__).resolve().parent.parent
BASE=ROOT/"versions/v10_input_fix/main.cpp"


def apply(source):
    old="""ll readInt() {
    readTok();
    return atoll(tok);
}"""
    new="""ll readInt() {
    int c=getch();
    while(c>=0&&c<=' ') c=getch();
    bool negative=c=='-';
    if(c=='-'||c=='+') c=getch();
    ll value=0;
    if(negative) {
        while(unsigned(c-'0')<10) value=value*10-(c-'0'),c=getch();
    } else {
        while(unsigned(c-'0')<10) value=value*10+(c-'0'),c=getch();
    }
    return value;
}"""
    assert source.count(old)==1,"Expected unique original integer reader"
    assert "tok[1 << 23]" in source,"Fixed8MiB text/hex buffer must carry forward"
    return source.replace(old,new)


def main():
    source=apply(BASE.read_text(encoding="utf8"))
    path=ROOT/"candidates/v11_scan.cpp"
    assert not path.exists(),"Never overwrite an existing experiment"
    path.write_bytes(source.encode("utf8"))
    exe=ROOT/"build/v11_scan.exe"
    compiled=subprocess.run(["g++","-std=c++17","-O2","-Wall","-Wextra",str(path),"-o",str(exe)],capture_output=True,text=True,cwd=ROOT)
    assert compiled.returncode==0 and not compiled.stderr,compiled.stderr
    record={"base":str(BASE),"base_sha256":hashlib.sha256(BASE.read_bytes()).hexdigest(),
            "source":str(path),"source_sha256":hashlib.sha256(path.read_bytes()).hexdigest(),
            "exe":str(exe),"exe_sha256":hashlib.sha256(exe.read_bytes()).hexdigest(),
            "text_reader_and_buffer_unchanged":True,"signed_limits_safe_for_representable_inputs":True,
            "official_submission_sent":False}
    (ROOT/"research/v11_scan_manifest.json").write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding="utf8")
    print(json.dumps(record,ensure_ascii=False))


if __name__=="__main__":main()
