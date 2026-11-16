"""Fixed admission-risk alternatives to the untouched official 84-point source."""
from pathlib import Path
import hashlib
import json

VARIANTS = {
    'aggressive_mild': dict(safety=1.10, margin=1.20, long_cost=.75, mix=.72, started=1.12, new=1.05),
    'aggressive_medium': dict(safety=1.05, margin=1.15, long_cost=.75, mix=.65, started=1.15, new=1.08),
    'aggressive_strong': dict(safety=1.00, margin=1.10, long_cost=.80, mix=.60, started=1.18, new=1.10),
    'conservative_mild': dict(safety=1.30, margin=1.30, long_cost=.68, mix=.78, started=1.12, new=1.02),
    'conservative_medium': dict(safety=1.35, margin=1.35, long_cost=.65, mix=.80, started=1.10, new=1.00),
    'conservative_strong': dict(safety=1.50, margin=1.50, long_cost=.60, mix=.90, started=1.05, new=.98),
}

def main():
    baseline_path=Path('versions/v1_84/main.cpp')
    source=baseline_path.read_text(encoding='utf-8')
    source_hash=hashlib.sha256(baseline_path.read_bytes()).hexdigest()
    assert source_hash=='89812abdcecbb3d65fada3d2dfdc11461489ea1c5ca5c126bf00a83651bc275b'
    manifest={}
    for name, c in VARIANTS.items():
        changes={
            'flow.remaining_cost = 1.2 * flow.plan_cost;': f'flow.remaining_cost = {c["safety"]} * flow.plan_cost;',
            'current_tick + 1.25 * flow.remaining_time':f'current_tick + {c["margin"]} * flow.remaining_time',
            'flow.remaining_cost > .7 * flow.value':f'flow.remaining_cost > {c["long_cost"]} * flow.value',
            '.72 * reward_at(':f'{c["mix"]} * reward_at(',
            '.28 * reward_at(':f'{1-c["mix"]:.12g} * reward_at(',
            'income * 1.03':f'income * {c["new"]}',
            'income * (flow.has_started ? 1.12 : 1.03)':f'income * (flow.has_started ? {c["started"]} : {c["new"]})',
        }
        output=source
        for old,new in changes.items():
            assert old in output, (name,old)
            output=output.replace(old,new)
        output='// V3 admission experiment: '+name+'; no protocol/accounting changes.\n'+output
        target=Path('candidates')/f'v3_policy_{name}.cpp'
        target.write_text(output,encoding='utf-8',newline='\n')
        manifest[name]=dict(configuration=c,source=str(target),source_sha256=hashlib.sha256(target.read_bytes()).hexdigest(),baseline_sha256=source_hash)
    Path('candidates/v3_policy_manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print('Created',len(manifest),'fixed variants')

if __name__=='__main__':
    main()
