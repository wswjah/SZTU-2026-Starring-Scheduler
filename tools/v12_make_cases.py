"""Fixed new seeds for the final bounded routing and pair-order experiments."""
from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parent.parent
template = json.loads((ROOT / "cases/v11_holdout/manifest.json").read_text(encoding="utf8"))
for split, seed_base, stride in [("holdout", 921116183, 104729), ("confirmation", 1021116183, 104723)]:
    directory = ROOT / f"cases/v12_{split}"
    assert not directory.exists(), "Do not replace predeclared inputs"
    directory.mkdir(parents=True)
    records = []
    for index, item in enumerate(template):
        config = dict(item["parameters"])
        config["seed"] = seed_base+index*stride
        raw = "".join(f"{k} {v}\n" for k, v in config.items()).encode("ascii")
        path = directory / item["file"]
        path.write_bytes(raw)
        records.append({"file": path.name, "parameters": config, "category": item["category"],
                        "sha256": hashlib.sha256(raw).hexdigest(),
                        "purpose": f"V12 {split}: no parameter selection using these outcomes"})
    (directory / "manifest.json").write_text(json.dumps(records, indent=2), encoding="utf8")
plan = {"date": "2026-11-16", "base": "versions/v10_input_fix/main.cpp", "official_best": 99,
        "new_submissions_authorized": False,
        "exploration": "12 predeclared coarse routing/lookahead single axes and1 two-ready-job transactional order rollout",
        "train": "train16:14checked range+2old log boundaries",
        "development": "Old V8development80; V11new80 may be reused only if explicitly relabeled development",
        "finalists": "At most2 train/development-selected candidates, frozen before V12holdout; no fitting from holdout/confirmation",
        "fresh": "40holdout+40confirmation predeclared before any V12 results",
        "constraints": "Retain8MiB buffer,20k commands,CPU insurance,original99 header; default99 untouched"}
(ROOT / "research/v12_plan.json").write_text(json.dumps(plan, indent=2), encoding="utf8")
print("Prepared80 V12 new worlds and recorded bounded plan")
