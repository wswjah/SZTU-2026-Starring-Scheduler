"""Independent seeds after both V7 finalists were frozen; no further fitting."""
from pathlib import Path
import hashlib
import json
from make_cases import BASE, PROFILES

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "cases/v7_confirmation"
assert not OUT.exists(), "Do not regenerate an existing confirmation set"
OUT.mkdir(parents=True)
manifest = []
for i, (profile, changes) in enumerate(PROFILES.items()):
    for j in range(4):
        cfg = BASE | changes | {"seed": 271915144 + 17389 * i + 91009 * j}
        if profile == "large":
            cfg.update(load=.65, log_rate=.08)
        if profile == "fast":
            cfg.update(load=.75)
        raw = "".join(f"{k} {v}\n" for k, v in cfg.items()).encode("ascii")
        path = OUT / f"{profile}_{j:02}.in"
        path.write_bytes(raw)
        manifest.append({"file": path.name, "parameters": cfg, "sha256": hashlib.sha256(raw).hexdigest(),
                         "purpose": "confirm frozen v7_tuned; no parameter fitting on outcomes"})
(OUT / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf8")
print("Frozen 32 independent confirmation worlds")
