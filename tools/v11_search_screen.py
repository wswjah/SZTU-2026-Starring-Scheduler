"""Three predeclared, more expensive placement searches on frozen input-fixed99."""
from pathlib import Path
import hashlib
import json
import re
import subprocess
import sys
from compare import compare, markdown

ROOT = Path(__file__).resolve().parent.parent
BASE = ROOT / "versions/v10_input_fix/main.cpp"
BASE_SHA = "b0854a70f54ccb47d287a48be37e447eb100147ca3f2e556c20c20498f705ae6"
BASELINE = ROOT / "results/v10_input_verification/train/fixed"
OUT = ROOT / "results/v11_search"
CONFIGS = {
    "full_racks": {"RK": 30},
    "warm_rank": {"RK": 16, "machine_aware_rack_fee": True},
    "full_wide": {"RK": 30, "lookahead_successors": 16, "lookahead_inputs": 12},
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf8")


def once(source, old, new):
    assert source.count(old) == 1, old
    return source.replace(old, new)


def make(name, config):
    assert sha(BASE) == BASE_SHA
    source = BASE.read_text(encoding="utf8")
    source, count = re.subn(r"PRM\(RK,\s*[^)]+\)", f"PRM(RK, {config['RK']})", source)
    assert count == 1
    if config.get("machine_aware_rack_fee"):
        old = """            // registry fee of the layers the rack cache does not hold (a machine may still hold them)
            static ll iq[120][30];
            static int iv[120][30];
            ll& q = iq[j.img][r];
            if (iv[j.img][r] != rackCache[r].ver + 1) {
                iv[j.img][r] = rackCache[r].ver + 1, q = 0;
                for (int l : imageLayers[j.img])
                    if (!rackCache[r].in[l]) q += layerSize[l];
            }
            rfee[r] = RF * q * Ureg;"""
        new = """            // Rank with the cheapest capable online machine's static registry miss fee.
            // Cache membership only; final candidate pricing/execution remains unchanged.
            static ll machineMissing[120][360];
            static int rackVersion[120][360], machineVersion[120][360];
            ll q = LLONG_MAX;
            for (int x : rackMachs[r]) {
                if (!machUp[x] || machCpu[x] < j.c || machMem[x] < j.m) continue;
                ll& missing = machineMissing[j.img][x];
                if (rackVersion[j.img][x] != rackCache[r].ver + 1 ||
                    machineVersion[j.img][x] != machCache[x].ver + 1) {
                    rackVersion[j.img][x] = rackCache[r].ver + 1;
                    machineVersion[j.img][x] = machCache[x].ver + 1;
                    missing = 0;
                    for (int l : imageLayers[j.img])
                        if (!machCache[x].in[l] && !rackCache[r].in[l]) missing += layerSize[l];
                }
                q = min(q,missing);
            }
            if (q == LLONG_MAX) continue;
            rfee[r] = RF * q * Ureg;"""
        source = once(source, old, new)
        # The original machine version was unused by pricing and did not change
        # on FAIL; invalidate the newly introduced membership memo explicitly.
        source = once(source, """                c.q.clear(), c.sum = 0;
                memset(c.in, 0, 400);""", """                c.q.clear(), c.sum = 0;
                ++c.ver;
                memset(c.in, 0, 400);""")
    if "lookahead_successors" in config:
        successors, inputs = config["lookahead_successors"], config["lookahead_inputs"]
        source = once(source, "static int qr[8][5], nq[8];", f"static int qr[{successors}][{inputs}], nq[{successors}];")
        source = once(source, "static ll qz[8][5];", f"static ll qz[{successors}][{inputs}];")
        source = once(source, "static double qm[8][5], qf[8][5];", f"static double qm[{successors}][{inputs}], qf[{successors}][{inputs}];")
        source = once(source, "int ns = 0, sj[8];", f"int ns = 0, sj[{successors}];")
        source = once(source, "if (ns >= 8) break;  // Check before any access to qr/ns scratch rows.",
                      f"if (ns >= {successors}) break;  // Check before any access to qr/ns scratch rows.")
        source = once(source, "if (p != ji && k < 5 && (jobs[p].state || GU > 0))", f"if (p != ji && k < {inputs} && (jobs[p].state || GU > 0))")
    assert source.split("#include", 1)[0] == BASE.read_text(encoding="utf8").split("#include", 1)[0]
    assert "tok[1 << 23]" in source and "COMMAND_LIMIT = 20000" in source
    path = ROOT / "candidates/v11_search" / f"{name}.cpp"
    assert not path.exists(), "Preserve experiment sources"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(source.encode("utf8"))
    exe = ROOT / "build" / f"v11_search_{name}.exe"
    compiled = subprocess.run(["g++", "-std=c++17", "-O2", "-Wall", "-Wextra", str(path), "-o", str(exe)],
                              cwd=ROOT, capture_output=True, text=True)
    assert compiled.returncode == 0 and not compiled.stderr.strip(), compiled.stderr
    return {"name": name, "config": config, "source": str(path), "source_sha256": sha(path),
            "executable": str(exe), "exe_sha256": sha(exe), "base_sha256": BASE_SHA,
            "header_unchanged": True, "buffer_8m_preserved": True, "official_submission_sent": False}


def evaluate(config):
    dest = OUT / config["name"]
    tested = subprocess.run([sys.executable, "tools/bench.py", "--exe", config["executable"], "--cases", "cases/train",
                             "--out", str(dest), "--workers", "1"], cwd=ROOT, capture_output=True, text=True, encoding="utf8")
    assert tested.returncode == 0, tested.stdout + tested.stderr
    value = compare(BASELINE, dest)
    dump(dest / "comparison.json", value)
    (dest / "comparison.md").write_text(markdown(value), encoding="utf8")
    rows = [r for r in value["rows"] if not r["baseline_range_violations"] and not r["candidate_range_violations"]]
    worst = min((r for r in rows if r["profit_ratio"] is not None), key=lambda r: r["profit_ratio"])
    record = {**config, "result_dir": str(dest), "valid_range": value["valid_range_summary"],
              "boundary": value["boundary_pressure_summary"], "all_health": value["candidate_health"], "worst": worst}
    dump(dest / "manifest.json", record)
    v = record["valid_range"]
    print(json.dumps({"name": config["name"], "pct": v["total_profit_increase_pct"],
                      "equal_pct": v["equal_weight_increase_pct"], "median": v["median_profit_ratio"],
                      "up": v["improved"], "down": v["regressed"], "equal": v["unchanged"],
                      "worst": worst["profit_ratio"], "max_cpu": record["all_health"]["max_cpu_seconds"]}), flush=True)
    return record


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf8")
    assert not (ROOT / "research/v11_search_plan.json").exists()
    dump(ROOT / "research/v11_search_plan.json", {"base": str(BASE), "base_sha256": BASE_SHA,
         "configs": CONFIGS, "training": "cases/train16,14 checked-range +2 large log boundary worlds",
         "budget": "Exactly3 variants, no duration/priority tuning, root owns validation",
         "note": "Process CPU insurance is preserved; CPU<1s does not prove degradation never occurs.",
         "official_submission_sent": False})
    configs = [make(name, config) for name, config in CONFIGS.items()]
    dump(ROOT / "research/v11_search_manifest.json", configs)
    records = []
    for config in configs:
        records.append(evaluate(config))
        dump(OUT / "summary.json", records)
        dump(ROOT / "research/v11_search_results.json", records)


if __name__ == "__main__":
    main()
