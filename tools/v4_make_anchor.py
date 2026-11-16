"""Test stronger workflow rack commitment without changing protocol/accounting."""
from pathlib import Path
import hashlib
import json

root=Path(__file__).resolve().parent.parent
original=(root/'main.cpp').read_bytes()
assert hashlib.sha256(original).hexdigest()=='21ab5033ed9052e37b691c8f632029b181fe824f9f612cea9364e21bd8ab985c'
source=original.decode('utf-8')
anchor='''            return;
        i128 bytes[30]{};
'''
assert source.count(anchor)==1
manifest={}
for role,condition in [
    ('committed','true'),
    ('inflight','any_of(jobs.begin()+flow.jobs_begin,jobs.begin()+flow.jobs_end,[](const job_state& j){return j.status==1;})'),
]:
    replacement='''            return;
        // Preserve the anchor while it remains feasible; emergency rerouting is unchanged.
        if (flow.has_started && flow.preferred_rack>=0 && CONDITION &&
            plan_on_rack(flow,flow.preferred_rack)) {
            flow.plan_tick=current_tick;
            flow.planned_finished_jobs=flow.finished_jobs;
            flow.detailed_plan_tick=current_tick;
            flow.detailed_plan_environment=environment_version;
            return;
        }
        i128 bytes[30]{};
'''.replace('CONDITION',condition)
    target=root/'candidates'/f'v4_anchor_{role}.cpp'
    target.write_text(source.replace(anchor,replacement),encoding='utf-8',newline='\n')
    manifest[role]={'source':str(target),'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),
                    'hypothesis':'reduce needless anchor migration after work has started'}
(root/'research/v4_anchor_manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
print('Created two anchor-commitment variants; official 85-point source untouched.')
