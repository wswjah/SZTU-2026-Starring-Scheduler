"""Validate the two-feature implementation without selecting a new model policy."""
from pathlib import Path
import argparse
import hashlib
import json
import subprocess
import sys
from compare import compare
from v11_freeze import freeze

ROOT = Path(__file__).resolve().parent.parent
NAME = "v13_model_fast"
OUT = ROOT / "results/v13_production_check"


def load(path):
    return json.loads((ROOT / path).read_text(encoding="utf8"))


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf8")


def freezing():
    record = freeze(NAME, ROOT / "candidates/v13_model/production.cpp",
        "Policy-equivalent production implementation of frozen strict: compute only x5/x10, remove diagnostics and unused forecast fields; no refitting or threshold changes",
        "Already observed V13 worlds used only for implementation equivalence, not new policy validation")
    record.update(policy_reference="versions/v13_model_strict/manifest.json",
        policy_validation="research/v13_experiment_manifest.json",
        policy_changed=False, training_changed=False)
    dump(ROOT / f"versions/{NAME}/manifest.json", record)


def auxiliary(name):
    directory = ROOT / f"results/v13_aux_{name}"
    assert not directory.exists()
    version = load(f"versions/{name}/manifest.json")
    process = subprocess.run([sys.executable, "tools/bench.py", "--exe", version["executable"],
        "--cases", "cases/stress", "sample_00/turn_00.in", "sample_01/turn_00.in",
        "--out", str(directory), "--workers", "1"], cwd=ROOT, capture_output=True,
        encoding="utf8", text=True)
    assert process.returncode == 0, process.stdout+process.stderr
    rows = load(str(directory / "summary.json"))
    assert len(rows) == 6 and all(r["ok"] for r in rows)
    print(json.dumps({"name": name, "auxiliary6_healthy": True}), flush=True)


def verify():
    OUT.mkdir(parents=True, exist_ok=True)
    version = load(f"versions/{NAME}/manifest.json")
    assert hashlib.sha256(Path(version["packed_source"]).read_bytes()).hexdigest() == version["packed_sha256"]
    assert hashlib.sha256(Path(version["executable"]).read_bytes()).hexdigest() == version["exe_sha256"]
    equalities, production_runs, reference_aux = [], [], []
    for split in ["holdout", "confirmation"]:
        old = load(f"results/v13_{split}_v13_model_strict/summary.json")
        new = load(f"results/v13_{split}_{NAME}/summary.json")
        mapping = {r["case"]: r for r in old}
        assert len(old) == len(new) == 40
        for row in new:
            a = mapping[row["case"]]
            equalities.append({"case": split+"/"+row["case"],
                "input_equal": a["input_sha256"] == row["input_sha256"],
                "full_report_equal": a["report"] == row["report"]})
        production_runs += new
    for name in ["v13_model_strict", NAME]:
        rows = load(f"results/v13_aux_{name}/summary.json")
        rows = [dict(r, case=Path(r["input"]).parent.name+"/"+r["case"]) for r in rows]
        directory = OUT / (name+"_aux6")
        dump(directory / "summary.json", rows)
        if name == NAME:
            production_runs += rows
        else:
            reference_aux = rows
    old_aux = {r["case"]: r for r in reference_aux}
    for row in production_runs[-6:]:
        a = old_aux[row["case"]]
        equalities.append({"case": "aux/"+row["case"],
            "input_equal": row["input_sha256"] == a["input_sha256"],
            "full_report_equal": row["report"] == a["report"]})
    assert len(equalities) == 86 and all(r["input_equal"] and r["full_report_equal"] for r in equalities)
    assert len(production_runs) == 86 and all(r["ok"] and r["audit_errors"] == 0 and r["incidents"] == 0 for r in production_runs)
    assert {r["exe_sha256"] for r in production_runs} == {version["exe_sha256"]}
    # A long Huffman token is a separate direct protocol test, not an extra TPJ world.
    data = (ROOT / "results/v10_fix_input/large_huffman_protocol.in").read_bytes()
    expected = "".join(f"ANS {3000000 if t <= 20 else 0}\nEND\n" for t in range(1,401)).encode("ascii")
    ran = subprocess.run([version["executable"]], input=data, capture_output=True, cwd=ROOT, timeout=20)
    assert ran.returncode == 0 and not ran.stderr and ran.stdout.replace(b"\r\n", b"\n") == expected
    policy = load("research/v13_experiment_manifest.json")["comparisons"]["v13_model_strict"]
    health = {"main_runs": 86, "audit_total": sum(r["audit_total"] for r in production_runs),
        "audit_errors": 0, "illegal_commands": 0,
        "max_cpu_seconds": max(r["solver_cpu_seconds"] for r in production_runs),
        "max_peak_memory_bytes": max(r["solver_peak_memory_bytes"] for r in production_runs),
        "all86_full_reports_equal_to_full_strict": True,
        "large_protocol400_exact": True,
        "scope": "Observed V13 worlds80 for implementation equivalence + maximum-scale pressure4 + original native samples2; native samples have historical short-T initialization",
        "fresh80_policy_profit_increase_pct": policy["fresh80"]["total_profit_increase_pct"],
        "fresh80_policy_worst_ratio": policy["worst"]["profit_ratio"]}
    version["validation"] = health
    version["local_selection_status"] = "Preferred experimental profit candidate; +0.4813% on80 fresh policy tests,52 up28 down,worst-6.06%; official score unknown"
    dump(ROOT / f"versions/{NAME}/manifest.json", version)
    dump(OUT / "equivalence.json", equalities)
    dump(OUT / "summary.json", {"name": NAME, "health": health, "policy": policy,
        "extra_reference_aux_runs": len(reference_aux), "policy_changed": False,
        "performance_claim": "No isolated speedup percentage established; unused work removed and full reports compared",
        "original_defaults_unchanged": True, "official_submission_sent": False})
    print(json.dumps({"version": NAME, "health": health}))


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf8")
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["freeze", "aux", "verify"])
    parser.add_argument("--name", choices=[NAME, "v13_model_strict", "v12_scan_input_fix", "v14_mlp_A", "v14_mlp_B"])
    args = parser.parse_args()
    if args.mode == "freeze":
        freezing()
    elif args.mode == "aux":
        assert args.name
        auxiliary(args.name)
    else:
        verify()
