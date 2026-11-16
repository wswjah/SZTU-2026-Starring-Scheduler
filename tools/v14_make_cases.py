"""Freeze untouched neural-policy validation worlds before any neural fitting."""
from pathlib import Path
import json
from v13_make_cases import write_set

ROOT = Path(__file__).resolve().parent.parent


def main():
    template = json.loads((ROOT / "cases/v13_holdout/manifest.json").read_text(encoding="utf8"))
    for split, seed in [("holdout", 1521116287), ("confirmation", 1621116287)]:
        entries = []
        for i, row in enumerate(template):
            config = dict(row["parameters"])
            config["seed"] = seed+i*104729
            entries.append((row["file"], config, row["category"]))
        write_set("v14_"+split, entries)
    print("Frozen V14 fresh40+confirmation40 for neural policies; training remains V13train32")


if __name__ == "__main__":
    main()
