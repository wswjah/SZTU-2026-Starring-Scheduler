"""Export a cached alarm risk tree and three predeclared placement strengths."""
from pathlib import Path
import hashlib
import json
import subprocess

ROOT = Path(__file__).resolve().parent.parent
BASE = ROOT / "versions/v8_fine/main.cpp"


def replace_once(source, old, new):
    assert source.count(old) == 1, old[:90]
    return source.replace(old, new)


def make(strength, name):
    source = BASE.read_text(encoding="utf8")
    model = json.loads((ROOT / "research/v9_alarm_model.json").read_text(encoding="utf8"))
    assert set(model["tree"]["feature"]) - {-2} == {1, 2, 4}, "Only exported used features are computed"
    declaration = "ll alarmAt[360][602];"
    source = replace_once(source, declaration, declaration + "\nll v9LinePeak[360][602];\ndouble v9Probabilities[360][3];")
    fragment = (ROOT / "candidates/v9_alarm_tree.inc").read_text(encoding="ascii")
    fragment += """
// Calculate only the three features selected by the fixed train-only tree.
// Windows and Linux both cast the model input to float before tree thresholds.
void v9UpdateAlarmRisk() {
    F(x,M) {
        ll sum8=0,sumW=0,peak8=0;
        for(int t=max(1,now-max(8,W)+1);t<=now;++t) {
            if(t>now-W) sumW+=alarmAt[x][t];
            if(t>now-8) sum8+=alarmAt[x][t],peak8=max(peak8,v9LinePeak[x][t]);
        }
        float features[10]={};
        features[1]=float(log1p(double(sum8)));
        features[2]=float(log1p(double(sumW)));
        features[4]=float(log1p(double(peak8)));
        v9Predict(features,v9Probabilities[x]);
    }
}
double v9Interpolated(const double* probabilities,double horizon) {
    if(horizon<=0) return 0;
    if(horizon<=3) return probabilities[0]*horizon/3;
    if(horizon<=8) return probabilities[0]+(probabilities[1]-probabilities[0])*(horizon-3)/5;
    if(horizon<=16) return probabilities[1]+(probabilities[2]-probabilities[1])*(horizon-8)/8;
    return probabilities[2];
}
double v9RiskPenalty(int machine,double wait,double prep,double estimated,double corePrice,double theta) {
#ifdef V9_RISK_DISABLED
    return 0;
#else
    // A future reservation cannot assume today's warning persists until release.
    if(wait>0) return 0;
    double horizon=min(16.,max(0.,prep+estimated));
    double excess=max(0.,v9Interpolated(v9Probabilities[machine],horizon)-v9Interpolated(v9Background,horizon));
    // Only next-16-tick excess risk is priced; feeAvg is a rough restart estimate.
    // Half-horizon interruption and additive expected loss remain heuristics.
    return V9_STRENGTH*excess*((corePrice+theta)*horizon*.5+max(0.,feeAvg));
#endif
}
"""
    fragment = fragment.replace("V9_STRENGTH", str(strength))
    anchor = "void tryPlace(int ji) {"
    source = replace_once(source, anchor, fragment + "\n" + anchor)
    anchor = """            double warm = cr.first + qreg * Ureg + tfs[r] + th * wt;
            int wm = PW > 0 && warm < cost;"""
    source = replace_once(source, anchor, """            double warm = cr.first + qreg * Ureg + tfs[r] + th * wt;
            double corePrice=j.c*price[rackDc[r]];
            cost+=v9RiskPenalty(x,wt,s,est,corePrice,th);
            warm+=v9RiskPenalty(x,wt,tts[r],est,corePrice,th);
            int wm = PW > 0 && warm < cost;""")
    source = replace_once(source, "                alarmAt[x][now] += sc;", """                alarmAt[x][now] += sc;
                v9LinePeak[x][now]=max(v9LinePeak[x][now],sc);""")
    source = replace_once(source, """        commandsUsed = 0;
        schedule();""", """        commandsUsed = 0;
        v9UpdateAlarmRisk();
        schedule();""")
    path = ROOT / f"candidates/v9_alarm_{name}.cpp"
    assert not path.exists(), "Do not overwrite frozen experiment sources"
    path.write_bytes(source.encode("utf8"))
    exe = ROOT / f"build/v9_alarm_{name}.exe"
    command = ["g++", "-std=c++17", "-O2", "-Wall", "-Wextra", str(path), "-o", str(exe)]
    compiled = subprocess.run(command, capture_output=True, text=True, cwd=ROOT)
    assert compiled.returncode == 0, compiled.stderr
    assert not compiled.stderr, compiled.stderr
    record = {"name": name, "strength": strength, "base": str(BASE),
              "base_sha256": hashlib.sha256(BASE.read_bytes()).hexdigest(),
              "source": str(path), "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
              "executable": str(exe), "exe_sha256": hashlib.sha256(exe.read_bytes()).hexdigest(),
              "model_sha256": hashlib.sha256((ROOT / "research/v9_alarm_model.json").read_bytes()).hexdigest(),
              "observed_inputs_only": True, "official_submission_sent": False}
    return record


def main():
    records = [make(strength, name) for strength, name in [(.5, "mild"), (1, "normal"), (2, "strong")]]
    (ROOT / "research/v9_alarm_candidates.json").write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf8")
    print(json.dumps([{k: r[k] for k in ["name", "strength", "source_sha256"]} for r in records]))


if __name__ == "__main__":
    main()
