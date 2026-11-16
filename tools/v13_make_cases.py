"""Freeze broad new training and two untouched V13 test sets up front."""
from pathlib import Path
import hashlib
import json
from make_cases import BASE, PROFILES

ROOT = Path(__file__).resolve().parent.parent


def write_set(name, entries):
    directory = ROOT / "cases" / name
    assert not directory.exists(), "Never replace an experiment's inputs"
    directory.mkdir(parents=True)
    manifest = []
    for filename, config, category in entries:
        raw = "".join(f"{k} {v}\n" for k, v in config.items()).encode("ascii")
        (directory / filename).write_bytes(raw)
        manifest.append({"file": filename, "parameters": config, "category": category,
                         "sha256": hashlib.sha256(raw).hexdigest()})
    (directory / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf8")


def main():
    entries = []
    for i, (profile, changes) in enumerate(PROFILES.items()):
        for j in range(4):
            config = BASE | changes | {"seed": 1121116287+i*30011+j*111119}
            if profile == "large":
                config.update(load=.65, log_rate=.08)
            if profile == "fast":
                config.update(load=.75)
            entries.append((f"{profile}_{j:02}.in", config, "new_training_seed"))
    write_set("v13_train32", entries)
    template = json.loads((ROOT / "cases/v12_holdout/manifest.json").read_text(encoding="utf8"))
    for split, seed in [("holdout", 1221116287), ("confirmation", 1321116287)]:
        entries = []
        for i, row in enumerate(template):
            config = dict(row["parameters"])
            config["seed"] = seed+i*104729
            entries.append((row["file"], config, row["category"]))
        write_set("v13_"+split, entries)
    print("Prepared32 new training worlds and40+40 untouched V13 worlds")


if __name__ == "__main__":
    main()
