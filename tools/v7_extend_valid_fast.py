"""Retain an oversized validation world and add a separate in-range fast world."""
from pathlib import Path
import hashlib
import json
from make_cases import BASE

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "cases/v7_validation"
manifest_path = OUT / "manifest.json"
manifest = json.loads(manifest_path.read_text(encoding="utf8"))
assert not any(x["file"] == "shift_very_fast_valid.in" for x in manifest)
for item in manifest:
    if item["file"] == "shift_very_fast.in":
        item["observed_scope_violation"] = "baseline generated 68455 jobs > 60000; retain as boundary pressure"
cfg = BASE | {"log_rate": .10, "bias_lo": .25, "bias_hi": .65, "sigma": .2,
              "straggler_p": .01, "load": .7, "seed": 191281401}
data = "".join(f"{k} {v}\n" for k, v in cfg.items()).encode("ascii")
path = OUT / "shift_very_fast_valid.in"
path.write_bytes(data)
manifest.append({"file": path.name, "parameters": cfg, "sha256": hashlib.sha256(data).hexdigest(),
                 "category": "distribution_shift", "purpose": "additional fast world within job limit; freeze before evaluating candidates"})
manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf8")
print("Oversized world preserved; added one separately frozen fast world")
