"""Same-image cheaper-input donor prewarming, isolated from quota forecasts."""
from pathlib import Path
import hashlib
import json
import subprocess

ROOT = Path(__file__).resolve().parent.parent
BASE = ROOT / "versions/v7_tuned/main.cpp"
source = BASE.read_text(encoding="utf8")
source = source.replace("void tryPlace(int ji) {", """// Keep only a small current-tick donor pool; every use rechecks changing state.
vector<tuple<ll,int,int,int>> v8Donors[120];
ll v8DonorUses, v8DonorSaved, v8DonorChecks;
void collectV8Donors() {
    F(im,I) v8Donors[im].clear();
    F(wi,flows.size()) {
        Flow& w = flows[wi];
        if (w.dead || !w.left) continue;
        F(i,w.n) {
            int ji = w.first + i;
            Job& j = jobs[ji];
            if (j.state || j.need) continue;
            ll bytes = j.s < 0 ? 0 : j.zin;
            for (int p : j.pre) bytes += jobs[p].zout;
            // Lexicographic fields avoid overflow from scaling input sizes.
            auto& pool = v8Donors[j.img];
            tuple<ll,int,int,int> item(bytes,j.c,j.m,ji);
            auto at = lower_bound(pool.begin(),pool.end(),item);
            pool.insert(at,item);
            if (pool.size() > 4) pool.pop_back();
        }
    }
}
int cheaperV8Donor(int ji,int x,ll targetFee,ll& extraFee) {
    Job& target = jobs[ji];
    int best = -1, rack = machRack[x];
    extraFee = targetFee;
    if (!targetFee) return -1;
    for (auto& item : v8Donors[target.img]) {
        ++v8DonorChecks;
        int di = get<3>(item);
        Job& donor = jobs[di];
        Flow& flow = flows[donor.wf];
        if (di == ji || donor.state || donor.need || flow.dead || !flow.left ||
            donor.c > target.c || donor.m > target.m ||
            donor.c > freeCpu[x] || donor.m > freeMem[x]) continue;
        bool quotaOk = true;
        for (int a = flow.tenant; a >= 0; a = tenPar[a])
            if (tenUsed[a] + donor.c > tenQuota[a]) { quotaOk = false; break; }
        if (!quotaOk) continue;
        ll tt,tf,away;
        if (transferCost(donor,rack,tt,tf,away) && tf < extraFee)
            extraFee = tf, best = di;
    }
    return best;
}

void tryPlace(int ji) {""", 1)
source = source.replace("int bx = -1, bwarm = 0;", "int bx = -1, bwarm = 0, bdonor = -1;", 1)
anchor = """            double warm = cr.first + qreg * Ureg + tfs[r] + th * wt;
            int wm = PW > 0 && warm < cost;
            if (wm) cost = warm, s = tts[r];
            if (cost < best) best = cost, bx = x, bw = wt, bs = s, bwarm = wm;"""
assert source.count(anchor) == 1
source = source.replace(anchor, """            ll extraFee = tfs[r];
            int donor = -1;
            // Reservations cannot promise that a donor will still be ready later.
            if (PW > 0 && wt == 0 && freeCpu[x] >= j.c && freeMem[x] >= j.m)
                donor = cheaperV8Donor(ji,x,tfs[r],extraFee);
            double warm = cr.first + qreg * Ureg + extraFee + th * wt;
            int wm = PW > 0 && warm < cost;
            if (wm) cost = warm, s = tts[r];
            if (cost < best) best = cost, bx = x, bw = wt, bs = s, bwarm = wm, bdonor = donor;""")
anchor = """    if (bwarm && !bw) {
        runJob(ji, bx);
        fee0 = runFee;
        killNow(ji);
        j.ready = rdy;
    }"""
assert source.count(anchor) == 1
source = source.replace(anchor, """    if (bwarm && !bw) {
        int di = bdonor < 0 ? ji : bdonor;
        Job& donor = jobs[di];
        int oldReady = donor.ready, oldResM = donor.resM, oldResAt = donor.resAt, oldResT = donor.resT;
        double oldResEnd = donor.resEnd;
        if (di != ji) {
            ll tt,tf,away,dt,df,da;
            transferCost(j,machRack[bx],tt,tf,away);
            transferCost(donor,machRack[bx],dt,df,da);
            ++v8DonorUses; v8DonorSaved += tf - df;
        }
        runJob(di, bx);
        fee0 = runFee;
        killNow(di);
        donor.ready = oldReady;
        donor.resM = oldResM; donor.resAt = oldResAt; donor.resT = oldResT; donor.resEnd = oldResEnd;
        j.ready = rdy;
    }""")
anchor = "    sort(order.begin(), order.end());\n    for (auto& o : order) {"
assert source.count(anchor) == 1
source = source.replace(anchor, "    sort(order.begin(), order.end());\n    collectV8Donors();\n    for (auto& o : order) {")
ending = "        if (now == T) break;\n    }\n}"
assert source.count(ending) == 1
source = source.replace(ending, "        if (now == T) break;\n    }\n"
    '    fprintf(stderr,"v8_donor_uses=%lld v8_donor_saved=%lld v8_donor_checks=%lld\\n",v8DonorUses,v8DonorSaved,v8DonorChecks);\n}')
path = ROOT / "candidates/v8_donor.cpp"
exe = ROOT / "build/v8_donor.exe"
path.write_bytes(source.encode("utf8"))
subprocess.run(["g++", "-std=c++17", "-O2", "-Wall", "-Wextra", str(path), "-o", str(exe)], check=True)
record = {"source": str(path), "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
          "executable": str(exe), "exe_sha256": hashlib.sha256(exe.read_bytes()).hexdigest(),
          "base": str(BASE), "base_sha256": hashlib.sha256(BASE.read_bytes()).hexdigest(),
          "pool_per_image": 4, "donor_resources_le_target": True, "official_submission_sent": False}
(ROOT / "research/v8_donor_manifest.json").write_text(json.dumps(record, indent=2), encoding="utf8")
print(json.dumps(record))
