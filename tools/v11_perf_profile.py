"""Profile the current fixed-buffer scheduler, retaining complete result evidence."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys
from bench import run_case

ROOT=Path(__file__).resolve().parent.parent
BASE=ROOT/"versions/v10_input_fix/main.cpp"


def replace(source,old,new):
    assert source.count(old)==1,old[:100]
    return source.replace(old,new)


def main():
    source=BASE.read_text(encoding="utf8")
    support=r'''
struct V11Measurement { unsigned long long calls=0,samples=0,nanos=0; };
V11Measurement v11Schedule,v11Place,v11Estimate,v11Transfer,v11Wait,v11CacheHit,v11CachePut,v11Decode;
unsigned long long v11QuoteCalls,v11QuoteVersionHits,v11QuoteLayers;
struct V11Scope {
    V11Measurement& measure; bool sample;
    std::chrono::steady_clock::time_point start;
    V11Scope(V11Measurement& m,unsigned mask):measure(m),sample((m.calls++&mask)==0) {
        if(sample)start=std::chrono::steady_clock::now();
    }
    ~V11Scope(){if(sample){++measure.samples;measure.nanos+=std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::steady_clock::now()-start).count();}}
};
'''
    source=replace(source,"// ---------------- caches ----------------",support+"\n// ---------------- caches ----------------")
    for anchor,name,mask in [
        ("bool cacheHit(Cache& c, int l) {","v11CacheHit",255),
        ("void cachePut(Cache& c, int l) {","v11CachePut",255),
        ("bool transferCost(Job& j, int r, ll& tt, ll& tf, ll& away) {","v11Transfer",127),
        ("void flowEstimate(Flow& w, double& rem, double& work, double& cost) {","v11Estimate",31),
        ("double waitFor(int x, int c, int m, double lim) {","v11Wait",127),
        ("void tryPlace(int ji) {","v11Place",31),
        ("void schedule() {","v11Schedule",0),
        ('            } else if (ev == "LOG") {',"v11Decode",63),
    ]:
        source=replace(source,anchor,anchor+f"\n    V11Scope v11Scope({name},{mask});")
    quote="""            ll qreg = 0, qrack = 0;
            for (int l : imageLayers[j.img])"""
    stats="""            static int mv[120][360],rv[120][360];
            ++v11QuoteCalls;v11QuoteLayers+=imageLayers[j.img].size();
            if(mv[j.img][x]==machCache[x].ver+1&&rv[j.img][x]==rackCache[r].ver+1)++v11QuoteVersionHits;
            mv[j.img][x]=machCache[x].ver+1;rv[j.img][x]=rackCache[r].ver+1;
            ll qreg = 0, qrack = 0;
            for (int l : imageLayers[j.img])"""
    source=replace(source,quote,stats)
    # Count-only invalidation is needed to estimate real memo reuse after FAIL.
    source=replace(source,"                c.q.clear(), c.sum = 0;","                c.q.clear(), c.sum = 0;\n                ++c.ver;")
    ending="        if (now == T) break;\n    }\n}"
    dump=r'''
    auto v11dump=[](const char* name,const V11Measurement& m){
        fprintf(stderr,"V11_PROFILE %s calls=%llu samples=%llu sample_ns=%llu estimate_ns=%llu\n",name,m.calls,m.samples,m.nanos,m.samples?m.nanos*m.calls/m.samples:0);
    };
    v11dump("schedule",v11Schedule);v11dump("tryPlace",v11Place);v11dump("flowEstimate",v11Estimate);
    v11dump("transferCost",v11Transfer);v11dump("waitFor",v11Wait);v11dump("cacheHit",v11CacheHit);v11dump("cachePut",v11CachePut);v11dump("decode",v11Decode);
    fprintf(stderr,"V11_QUOTES calls=%llu version_hits=%llu layers=%llu\n",v11QuoteCalls,v11QuoteVersionHits,v11QuoteLayers);
'''
    source=replace(source,ending,"        if (now == T) break;\n    }\n"+dump+"}")
    path=ROOT/"candidates/v11_perf_profile.cpp"
    assert not path.exists()
    path.write_bytes(source.encode("utf8"))
    exe=ROOT/"build/v11_perf_profile.exe"
    subprocess.run(["g++","-std=c++17","-O2",str(path),"-o",str(exe)],check=True,cwd=ROOT)
    out=ROOT/"results/v11_perf_profile"
    rows=[]
    for case in ["cases/train/fast_00.in","cases/train/large_01.in","cases/stress/max_topology.in"]:
        row=run_case(exe,ROOT/case,out)
        rows.append(row)
        print(json.dumps({k:row[k] for k in ["case","ok","profit","solver_cpu_seconds"]}),flush=True)
    (out/"summary.json").write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding="utf8")
    (ROOT/"research/v11_perf_profile_manifest.json").write_text(json.dumps({"base":str(BASE),"base_sha256":hashlib.sha256(BASE.read_bytes()).hexdigest(),"source":str(path),"source_sha256":hashlib.sha256(path.read_bytes()).hexdigest(),"results":str(out),"official_submission_sent":False},indent=2),encoding="utf8")


if __name__=="__main__":main()
