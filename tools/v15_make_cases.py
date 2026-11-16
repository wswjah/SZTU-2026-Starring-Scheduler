"""Freeze96 additional training worlds and80 new validation worlds up front."""
from pathlib import Path
import hashlib
import json
from v13_make_cases import write_set

ROOT = Path(__file__).resolve().parent.parent


def main():
    old_train = json.loads((ROOT / "cases/v13_train32/manifest.json").read_text(encoding="utf8"))
    profiles = {}
    for row in old_train:
        profile = row["file"].rsplit("_", 1)[0]
        profiles.setdefault(profile, dict(row["parameters"]))
    assert len(profiles) == 8
    entries = []
    for i, (profile, parameters) in enumerate(profiles.items()):
        for j in range(12):
            config = dict(parameters)
            config["seed"] = 1721116287+i*30011+j*111119
            entries.append((f"{profile}_{j:02}.in", config, "additional_training_same_profile"))
    write_set("v15_train96", entries)
    template = json.loads((ROOT / "cases/v14_holdout/manifest.json").read_text(encoding="utf8"))
    for split, seed in [("holdout", 1821116287), ("confirmation", 1921116287)]:
        entries = []
        for i, row in enumerate(template):
            config = dict(row["parameters"])
            config["seed"] = seed+i*104729
            entries.append((row["file"], config, row["category"]))
        write_set("v15_"+split, entries)
    reference_names = ["v12_scan_input_fix", "v13_model_fast", "v14_mlp_A", "v14_mlp_B"]
    references = {}
    for name in reference_names:
        version = json.loads((ROOT / f"versions/{name}/manifest.json").read_text(encoding="utf8"))
        references[name] = {k: version[k] for k in ["packed_source", "packed_sha256", "executable", "exe_sha256"]}
    manifests = {name: hashlib.sha256((ROOT / f"cases/{name}/manifest.json").read_bytes()).hexdigest()
                 for name in ["v13_train32", "v15_train96", "v15_holdout", "v15_confirmation"]}
    plan = {"date": "2026-11-16", "training": "OldV13train32+new96=128 worlds;no validation promotion to training",
        "additional_training": "Same8 profiles,12 new seeds each; nominal profile mix held fixed",
        "validation": "New40+40 frozen before fitting/outcomes; all fixed old and refit policies tested unchanged",
        "references": references, "case_manifests_sha256": manifests,
        "refits": {
            "A128_120": "18-16-2,seed141116,120epochs,originalA25% revenue blend gate",
            "B128_120": "18-16-8-2,seed141117,120epochs,originalBstrict gate",
            "tree128": "Depth3/minleaf500,seed131116,originalstrict gate",
            "A128_steps": "SameA,exact4920updates for each fit; matches oldfullA32 update count,originalA25% gate;CV budget not same as oldfold fits"},
        "fixed_hyperparameters": "V14 float64/train-only world-weighted normalization,18float32 inputs,Adam lr.003/wd1e-4/batch1024,raw loss,eval clip unchanged",
        "selection": "No new threshold search or train-profit shortlist;all4 refits evaluated on same new80 regardless train results",
        "interpretation": "120epochs on more rows also means more optimizer steps;fixed-update A control helps separate this effect. More rows alone cannot guarantee higher profits.",
        "controls": "8MiB/scanner/99parameters/CPUguard/20k/rawscalar rollback retained;official99 defaults unchanged",
        "official_submission_sent": False}
    path = ROOT / "research/v15_plan.json"
    assert not path.exists()
    path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf8")
    print("Frozen96 new training and80 new validation worlds;planned32-to128 expansion and four fixed refits")


if __name__ == "__main__":
    main()
