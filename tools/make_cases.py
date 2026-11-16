"""Generate reproducible public TPJ practice inputs; never official hidden tests."""
import argparse
import json
from pathlib import Path

BASE = dict(seed=20261105, T=500, D=4, nodes_per_dc=90,
            racks_per_dc=5, mach_per_rack_lo=6, mach_per_rack_hi=12,
            NT=120, NL=300, NI=80, p_noise=8000, p_signal=45, W=40,
            load=0.9, sigma=0.35, bias_lo=0.7, bias_hi=1.8,
            fail_frac=0.15, precursor_frac=0.65, falsealarm_frac=0.1,
            blackswan=1, link_events=200, quota_events=70,
            log_rate=0.18, straggler_p=0.08, audit_rate=3.5)
PROFILES = {
    'standard': {},
    'light': dict(load=0.45, fail_frac=0.08, straggler_p=0.03),
    'heavy': dict(load=1.35, sigma=0.45, straggler_p=0.12),
    'unstable': dict(fail_frac=0.3, precursor_frac=0.85, falsealarm_frac=0.15,
                     link_events=350, quota_events=120),
    'slow': dict(bias_lo=1.2, bias_hi=2.5, sigma=0.5, straggler_p=0.16),
    'fast': dict(bias_lo=0.45, bias_hi=1.0, sigma=0.2, straggler_p=0.03),
    'small': dict(T=400, D=2, nodes_per_dc=70, racks_per_dc=4,
                  mach_per_rack_lo=6, mach_per_rack_hi=10, NT=60, NI=60,
                  NL=200, load=1.05, p_noise=4000, p_signal=30),
    'large': dict(T=600, D=5, nodes_per_dc=100, racks_per_dc=6,
                  mach_per_rack_lo=9, mach_per_rack_hi=12, NT=200, NL=400,
                  NI=120, p_noise=10000, p_signal=60, load=1.1, W=60),
}

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out', default='cases/train')
    p.add_argument('--seeds', type=int, default=2, help='Seeds per profile')
    p.add_argument('--seed-base', type=int, default=735102)
    args = p.parse_args()
    directory = Path(args.out)
    directory.mkdir(parents=True, exist_ok=True)
    manifest = []
    for i, (name, overrides) in enumerate(PROFILES.items()):
        for j in range(args.seeds):
            cfg = BASE | overrides | {'seed': args.seed_base + 10007*i + 31337*j}
            target = directory / f'{name}_{j:02}.in'
            target.write_text(''.join(f'{k} {v}\n' for k,v in cfg.items()), encoding='ascii')
            manifest.append(dict(file=target.name, profile=name, parameters=cfg))
    (directory/'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print(f'Created {len(manifest)} practice inputs in {directory}')

if __name__ == '__main__':
    main()
