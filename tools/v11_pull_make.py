"""Two predeclared exact-LRU quote experiments from the buffered99 source."""
from pathlib import Path
import hashlib
import json
import subprocess

ROOT = Path(__file__).resolve().parent.parent
BASE = ROOT / "versions/v10_input_fix/main.cpp"
EXPECTED = "b0854a70f54ccb47d287a48be37e447eb100147ca3f2e556c20c20498f705ae6"

HELPERS = r'''
struct V11PullAmounts { ll registry = 0, rack = 0; };
struct V11PullPair { V11PullAmounts first, second; };
ll v11ImageBytes[120];
bool v11RepeatedLayer[120];
ll v11Previews, v11ExactPreviews, v11FirstMismatch, v11WarmResidual;
ll v11GuardSamples, v11LateSamples, v11GuardReturns;
double v11MaximumUsed;
V11PullAmounts v11PullLayers(Cache& machine, Cache& rack, int image) {
    V11PullAmounts q;
    for (int layer : imageLayers[image]) {
        if (cacheHit(machine, layer)) continue;
        if (cacheHit(rack, layer)) q.rack += layerSize[layer];
        else q.registry += layerSize[layer], cachePut(rack, layer);
        cachePut(machine, layer);
    }
    return q;
}
V11PullPair v11PreviewImage(const Cache& sourceMachine, const Cache& sourceRack, int image) {
    Cache machine = sourceMachine, rack = sourceRack;
    V11PullPair pulls;
    pulls.first = v11PullLayers(machine, rack, image);
    // A complete pass leaves all distinct image layers resident if they fit.
    if (v11ImageBytes[image] > sourceMachine.cap)
        pulls.second = v11PullLayers(machine, rack, image);
    return pulls;
}
'''

PRICE = r'''            ll qreg = 0, qrack = 0;
            for (int l : imageLayers[j.img])
                if (!machCache[x].in[l]) (rackCache[r].in[l] ? qrack : qreg) += layerSize[l];
            ++v11Previews;
            ll naiveQreg = qreg, naiveQrack = qrack;
            ll qreg2 = 0, qrack2 = 0;
            bool exact = v11RepeatedLayer[j.img] ||
                         v11ImageBytes[j.img] > machCache[x].cap ||
                         machCache[x].sum + qreg + qrack > machCache[x].cap ||
                         rackCache[r].sum + qreg > rackCache[r].cap;
            if (exact) {
                ++v11ExactPreviews;
                auto pulls = v11PreviewImage(machCache[x], rackCache[r], j.img);
                if (pulls.first.registry != qreg || pulls.first.rack != qrack) ++v11FirstMismatch;
                qreg = pulls.first.registry; qrack = pulls.first.rack;
                qreg2 = pulls.second.registry; qrack2 = pulls.second.rack;
                if (qreg2 || qrack2) ++v11WarmResidual;
            }
            ll s = max(tts[r], (NORMAL_REG + Breg - 1) / Breg + (NORMAL_RACK + Brack - 1) / Brack);
            double cost = cr.first + qreg * Ureg + (j.c * price[rackDc[r]] + th) * (s - tts[r]) + th * wt;
            ll warmPrep = max(tts[r], (qreg2 + Breg - 1) / Breg + (qrack2 + Brack - 1) / Brack);
            double warm = cr.first + (qreg + qreg2) * Ureg + tfs[r] +
                          (j.c * price[rackDc[r]] + th) * (warmPrep - tts[r]) + th * wt;
            int wm = PW > 0 && warm < cost;
            if (wm) cost = warm, s = warmPrep;
            if (cost < best) best = cost, bx = x, bw = wt, bs = s, bwarm = wm;'''


def replace_once(source, old, new):
    assert source.count(old) == 1, old[:80]
    return source.replace(old, new)


def make_source(variant):
    source = BASE.read_text(encoding="utf8")
    source = replace_once(source, "// ---------------- network ----------------", HELPERS + "\n// ---------------- network ----------------")
    start = source.index("            ll qreg = 0, qrack = 0;", source.index("void tryPlace"))
    end_line = "            if (cost < best) best = cost, bx = x, bw = wt, bs = s, bwarm = wm;"
    end = source.index(end_line, start) + len(end_line)
    price = PRICE.replace("NORMAL_REG", "qreg" if variant == "hybrid" else "naiveQreg").replace("NORMAL_RACK", "qrack" if variant == "hybrid" else "naiveQrack")
    if variant == "hybrid":
        price = price.replace("            ll naiveQreg = qreg, naiveQrack = qrack;\n", "")
    source = source[:start] + price + source[end:]
    source = replace_once(source, """        int k = readInt();
        while (k--) imageLayers[i].push_back(readInt());""", """        int k = readInt();
        bool seen[400]{};
        while (k--) {
            int layer = readInt();
            imageLayers[i].push_back(layer);
            if (seen[layer]) v11RepeatedLayer[i] = true;
            else v11ImageBytes[i] += layerSize[layer], seen[layer] = true;
        }""")
    source = replace_once(source, """    double used = V7_SCHEDULER_USED(TS), late = used - .08 - .62 * now / T;
    if (used > .93 || (late > 0 && now % (1 << min(5, int(late / .04))))) return;""", """    double used = V7_SCHEDULER_USED(TS), late = used - .08 - .62 * now / T;
    ++v11GuardSamples; v11LateSamples += late >= 0;
    v11MaximumUsed = max(v11MaximumUsed, used);
    if (used > .93 || (late > 0 && now % (1 << min(5, int(late / .04))))) { ++v11GuardReturns; return; }""")
    source = replace_once(source, """        if (now == T) break;
    }
}""", """        if (now == T) break;
    }
    fprintf(stderr,"V11_PULL previews=%lld exact=%lld first_mismatch=%lld warm_residual=%lld guard_samples=%lld late_samples=%lld guard_returns=%lld max_used=%.9f\\n",v11Previews,v11ExactPreviews,v11FirstMismatch,v11WarmResidual,v11GuardSamples,v11LateSamples,v11GuardReturns,v11MaximumUsed);
}""")
    return source


def main():
    assert hashlib.sha256(BASE.read_bytes()).hexdigest() == EXPECTED
    out = ROOT / "candidates/v11_pull"
    out.mkdir(parents=True, exist_ok=True)
    records = []
    for name in ["hybrid", "fee_only"]:
        source = make_source(name)
        path, exe = out / f"{name}.cpp", ROOT / f"build/v11_pull_{name}.exe"
        assert not path.exists(), "Do not replace an existing experiment"
        path.write_bytes(source.encode("utf8"))
        result = subprocess.run(["g++", "-std=c++17", "-O2", "-Wall", "-Wextra", str(path), "-o", str(exe)], cwd=ROOT, capture_output=True, text=True)
        assert result.returncode == 0 and not result.stderr, result.stderr
        records.append({"name": name, "base": str(BASE), "base_sha256": EXPECTED,
                        "source": str(path), "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                        "executable": str(exe), "exe_sha256": hashlib.sha256(exe.read_bytes()).hexdigest(),
                        "real_runJob_and_billing_unchanged": True,
                        "second_pass_fast_path": "Unique image bytes <= machine capacity proves zero second pull",
                        "ordinary_delay": "exact" if name == "hybrid" else "original membership heuristic",
                        "windows_process_cpu_clock": True, "official_submission_sent": False})
    (ROOT / "research/v11_pull_manifest.json").write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf8")
    print(json.dumps([{k: r[k] for k in ["name", "source_sha256", "exe_sha256"]} for r in records]))


if __name__ == "__main__":
    main()
