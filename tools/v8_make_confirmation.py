"""Confirm the already-frozen V8 finalist without further parameter fitting."""
from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "cases/v8_confirmation"
assert not OUT.exists(), "Never replace existing confirmation inputs"
assert (ROOT / "versions/v8_fine/manifest.json").is_file()
OUT.mkdir(parents=True)
old = json.loads((ROOT / "cases/v8_holdout/manifest.json").read_text(encoding="utf8"))
records = []
for index, entry in enumerate(old):
    cfg = dict(entry["parameters"])
    cfg["seed"] = 491115921 + index * 97117
    raw = "".join(f"{k} {v}\n" for k, v in cfg.items()).encode("ascii")
    path = OUT / entry["file"]
    path.write_bytes(raw)
    records.append({"file": path.name, "parameters": cfg, "category": entry["category"],
                    "sha256": hashlib.sha256(raw).hexdigest(),
                    "purpose": "Independent confirmation of frozen v8_fine, no fitting"})
(OUT / "manifest.json").write_text(json.dumps(records, indent=2), encoding="utf8")
print("Froze 40 confirmation worlds for the unchanged V8 candidate")
