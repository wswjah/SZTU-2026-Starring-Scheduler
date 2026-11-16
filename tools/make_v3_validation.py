"""Frozen new seeds for evaluating aggressive/conservative candidates."""
from pathlib import Path
import hashlib
import json
from make_cases import BASE, PROFILES

root = Path(__file__).resolve().parent.parent
out = root / 'cases/v3_validation'
out.mkdir(parents=True, exist_ok=True)
manifest = []
names = list(PROFILES) + ['standard', 'heavy', 'unstable', 'slow']
for index, profile in enumerate(names):
    cfg = BASE | PROFILES[profile] | {'seed': 202611130 + 7927 * index}
    if profile == 'large':
        cfg.update(load=0.85, log_rate=0.12)
    name = f'{index:02}_{profile}.in'
    data = ''.join(f'{k} {v}\n' for k, v in cfg.items()).encode('ascii')
    (out / name).write_bytes(data)
    manifest.append({'file': name, 'parameters': cfg,
                     'sha256': hashlib.sha256(data).hexdigest(),
                     'purpose': 'new-seed validation; not used for tuning'})
(out / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
print(f'Created {len(manifest)} new-seed validation inputs')
