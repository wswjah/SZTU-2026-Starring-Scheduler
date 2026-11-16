"""Local V7 exact image pricing experiment; official V6 remains untouched."""
from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parent.parent
BASE = ROOT / 'versions/v6_attributed96/main.cpp'

HELPERS = r'''
// Exact simulation only for preview: real caches/bills are left untouched.
struct V7PullAmounts { ll registry = 0, rack = 0; };
ll v7ImageBytes[120];
bool v7RepeatedLayer[120];
long long v7Previews, v7ExactPreviews, v7FirstMismatch, v7WarmResidual;
V7PullAmounts v7PullLayers(Cache& machine, Cache& rack, int image) {
    V7PullAmounts q;
    for (int layer : imageLayers[image]) {
        if (cacheHit(machine, layer)) continue;
        if (cacheHit(rack, layer)) q.rack += layerSize[layer];
        else q.registry += layerSize[layer], cachePut(rack, layer);
        cachePut(machine, layer);
    }
    return q;
}
'''

PRICE = r'''            ll qreg = 0, qrack = 0;
            for (int l : imageLayers[j.img])
                if (!machCache[x].in[l]) (rackCache[r].in[l] ? qrack : qreg) += layerSize[l];
            ++v7Previews;
            ll qreg2 = 0, qrack2 = 0;
            // If no insertion can evict a layer, membership prices are exact.
            // Otherwise preview the two RUNs with real LRU ordering.
            bool exact = v7RepeatedLayer[j.img] ||
                         v7ImageBytes[j.img] > machCache[x].cap ||
                         machCache[x].sum + qreg + qrack > machCache[x].cap ||
                         rackCache[r].sum + qreg > rackCache[r].cap;
            if (exact) {
                ++v7ExactPreviews;
                Cache machine = machCache[x], rack = rackCache[r];
                auto first = v7PullLayers(machine, rack, j.img);
                if (first.registry != qreg || first.rack != qrack) ++v7FirstMismatch;
                qreg = first.registry; qrack = first.rack;
                auto second = v7PullLayers(machine, rack, j.img);
                qreg2 = second.registry; qrack2 = second.rack;
                if (qreg2 || qrack2) ++v7WarmResidual;
            }
            ll s = max(tts[r], (qreg + Breg - 1) / Breg + (qrack + Brack - 1) / Brack);
            double cost = cr.first + qreg * Ureg + (j.c * price[rackDc[r]] + th) * (s - tts[r]) + th * wt;
            ll warmPrep = max(tts[r], (qreg2 + Breg - 1) / Breg + (qrack2 + Brack - 1) / Brack);
            double warm = cr.first + (qreg + qreg2) * Ureg + tfs[r] +
                          (j.c * price[rackDc[r]] + th) * (warmPrep - tts[r]) + th * wt;
            int wm = PW > 0 && warm < cost;
            if (wm) cost = warm, s = warmPrep;
            if (cost < best) best = cost, bx = x, bw = wt, bs = s, bwarm = wm;'''


def main():
    source = BASE.read_text(encoding='utf8')
    source = source.replace('// ---------------- network ----------------', HELPERS + '\n// ---------------- network ----------------', 1)
    start = source.index('            ll qreg = 0, qrack = 0;', source.index('void tryPlace'))
    end_line = '            if (cost < best) best = cost, bx = x, bw = wt, bs = s, bwarm = wm;'
    end = source.index(end_line, start) + len(end_line)
    source = source[:start] + PRICE + source[end:]
    original = '''        int k = readInt();
        while (k--) imageLayers[i].push_back(readInt());'''
    replacement = '''        int k = readInt();
        bool seen[400]{};
        while (k--) {
            int layer = readInt();
            imageLayers[i].push_back(layer);
            if (seen[layer]) v7RepeatedLayer[i] = true;
            else v7ImageBytes[i] += layerSize[layer], seen[layer] = true;
        }'''
    assert source.count(original) == 1
    source = source.replace(original, replacement)
    source = source.replace('        if (now == T) break;', '''        if (now == T) {
            cerr << "V7_PULL previews=" << v7Previews << " exact=" << v7ExactPreviews
                 << " first_mismatch=" << v7FirstMismatch << " warm_residual=" << v7WarmResidual << '\\n';
            break;
        }''', 1)
    out = ROOT / 'candidates/v7_pull_hybrid.cpp'
    data = source.encode('utf8')
    out.write_bytes(data)
    fee_only = source.replace('            ++v7Previews;',
                             '            ++v7Previews;\n            ll naiveQreg = qreg, naiveQrack = qrack;', 1)
    old_time = '            ll s = max(tts[r], (qreg + Breg - 1) / Breg + (qrack + Brack - 1) / Brack);'
    assert fee_only.count(old_time) == 1
    fee_only = fee_only.replace(old_time,
        '            ll s = max(tts[r], (naiveQreg + Breg - 1) / Breg + (naiveQrack + Brack - 1) / Brack);', 1)
    fee_path = ROOT / 'candidates/v7_pull_fee_only.cpp'
    fee_data = fee_only.encode('utf8')
    fee_path.write_bytes(fee_data)
    manifest = {'baseline':str(BASE), 'baseline_sha256':hashlib.sha256(BASE.read_bytes()).hexdigest(),
                'source':str(out), 'source_sha256':hashlib.sha256(data).hexdigest(),
                'change':'LRU-exact first and second pull quote when eviction/duplicate/oversize can matter; otherwise membership fast path',
                'fee_only_ablation':{'source':str(fee_path),'source_sha256':hashlib.sha256(fee_data).hexdigest(),
                                     'change':'Exact immediate registry fees and warm residual; keep original cold-delay heuristic'},
                'real_runJob_and_billing_unchanged':True, 'official_submission_sent':False}
    (ROOT/'research/v7_pull_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(manifest))


if __name__ == '__main__':
    main()
