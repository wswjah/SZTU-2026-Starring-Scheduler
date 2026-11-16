"""Prepare a further fixed independent seed set before reading V11 holdout."""
from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "cases/v11_confirmation"
assert not OUT.exists()
OUT.mkdir(parents=True)
records = []
for index, entry in enumerate(json.loads((ROOT / "cases/v11_holdout/manifest.json").read_text(encoding="utf8"))):
    cfg = dict(entry["parameters"])
    cfg["seed"] = 811116387+index*92039
    raw = "".join(f"{k} {v}\n" for k, v in cfg.items()).encode("ascii")
    path = OUT / entry["file"]
    path.write_bytes(raw)
    records.append({"file": path.name, "parameters": cfg, "category": entry["category"],
                    "sha256": hashlib.sha256(raw).hexdigest(),
                    "purpose": "Unchanged frozen V11 finalist confirmation; seeds predeclared before reading first40 results"})
(OUT / "manifest.json").write_text(json.dumps(records, indent=2), encoding="utf8")
print("Prepared40 further confirmation worlds; no results used")
