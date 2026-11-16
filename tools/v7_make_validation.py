"""Freeze new seeds and distribution shifts before V7 candidate selection."""
from pathlib import Path
import hashlib
import json
from make_cases import BASE, PROFILES

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "cases/v7_validation"
assert not OUT.exists(), "Preserve the existing frozen validation set"
OUT.mkdir(parents=True)
manifest = []


def write(name, cfg, category):
    data = "".join(f"{k} {v}\n" for k, v in cfg.items()).encode("ascii")
    path = OUT / f"{name}.in"
    path.write_bytes(data)
    manifest.append({"file": path.name, "parameters": cfg,
                     "sha256": hashlib.sha256(data).hexdigest(), "category": category,
                     "purpose": "frozen before V7 selection; evaluate only frozen finalists"})


for i, (profile, changes) in enumerate(PROFILES.items()):
    for j in range(3):
        cfg = BASE | changes | {"seed": 151120261 + i * 29137 + j * 71059}
        if profile == "large":
            cfg.update(load=.65, log_rate=.08)
        write(f"new_{profile}_{j:02}", cfg, "new_seed")

shifts = {
    "very_fast": dict(bias_lo=.25, bias_hi=.65, sigma=.2, straggler_p=.01, load=1.1),
    "very_slow": dict(bias_lo=1.8, bias_hi=3.2, sigma=.45, straggler_p=.14, load=.55),
    "no_failures": dict(fail_frac=0, blackswan=0, link_events=100),
    "uncertain": dict(sigma=.8, straggler_p=.2, load=.7),
    "high_failures": dict(fail_frac=.4, precursor_frac=.65, falsealarm_frac=.2, load=.7),
    "sparse": dict(load=.2, fail_frac=.1),
    "dense": dict(load=1.5),
    "changing": dict(quota_events=220, link_events=450, audit_rate=5, load=.75),
}
for i, (profile, changes) in enumerate(shifts.items()):
    cfg = BASE | {"log_rate": .10} | changes | {"seed": 151180261 + 91093 * i}
    write(f"shift_{profile}", cfg, "distribution_shift")
(OUT / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf8")
print("Frozen 24 new-seed worlds and 8 distribution-shift worlds")
