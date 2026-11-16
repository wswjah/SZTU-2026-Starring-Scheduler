"""Freeze two risk directions on the verified, behavior-preserving fast base."""
from pathlib import Path
import hashlib
import json

root = Path(__file__).resolve().parent.parent
base_path = root / 'candidates/v3_perf_combo.cpp'
base_bytes = base_path.read_bytes()
base = base_bytes.decode('utf-8')
anchor = 'flow.remaining_cost = 1.2 * flow.plan_cost;'
assert base.count(anchor) == 2
manifest = {'date': '2026-11-14', 'authorized_new_submissions': 2,
            'base': str(base_path), 'base_sha256': hashlib.sha256(base_bytes).hexdigest(),
            'original_84_submission': 543386, 'variants': {}}
for role, factor in [('aggressive', 1.10), ('conservative', 1.35)]:
    directory = root / 'versions' / ('v3_' + role)
    directory.mkdir(parents=True, exist_ok=True)
    source = (f'// V3 {role}: exact fast computations; admission cost factor {factor}.\n' +
              base.replace(anchor, f'flow.remaining_cost = {factor} * flow.plan_cost;'))
    target = directory / 'main.cpp'
    target.write_text(source, encoding='utf-8', newline='\n')
    manifest['variants'][role] = {'cost_factor': factor, 'source': str(target),
                                  'source_sha256': hashlib.sha256(target.read_bytes()).hexdigest(),
                                  'other_policy_parameters': 'identical to the official 84-point source'}
destination = root / 'research/v3_frozen_manifest.json'
destination.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
print('Frozen aggressive and conservative readable sources; original 84-point files untouched.')
