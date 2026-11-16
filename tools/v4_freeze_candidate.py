"""Remove diagnostic-only paths and freeze the validated V4 candidate."""
from pathlib import Path
import hashlib
import json

root=Path(__file__).resolve().parent.parent
raw=root/'candidates/v4_model_terminal.cpp'
source=raw.read_text(encoding='utf-8')
model=json.loads((root/'research/v4_admission_tree.json').read_text(encoding='utf-8'))
assert {f for f in model['tree']['feature'] if f>=0}=={2,3,14}
begin=source.index('            double horizon=max(1.,double(flow.last_profitable_tick-current_tick));',source.index('if (!flow.has_started && !best_investment'))
end=source.index('\n        }',begin)
production='''            double horizon=max(1.,double(flow.last_profitable_tick-current_tick));
            float x[15]{};
            // The frozen tree uses only these three pre-admission features.
            x[2]=float(flow.plan_cost/max<i64>(1,flow.value));
            x[3]=float(flow.plan_duration/horizon);
            x[14]=float(horizon/total_ticks);
            if(v4_admission_score(x)<0.05)return 0;'''
source=source[:begin]+production+source[end:]
assert 'V4_MODEL_DISABLED' not in source and 'MLFEATURE' not in source
source='// V4: offline risk calibration plus exact terminal-job candidate pricing.\n'+source
out=root/'versions/v4_risk_terminal'
out.mkdir(exist_ok=True,parents=True)
(out/'main.cpp').write_text(source,encoding='utf-8',newline='\n')
manifest={'date':'2026-11-14','official_baseline_score':85,'official_baseline_id':543440,
          'candidate':'risk_tree_and_terminal_job_estimate','model_nodes':model['nodes'],
          'runtime_features':['plan_cost/value','plan_duration/profitable_window','profitable_window/total_ticks'],
          'training_worlds':model['worlds'],'training_rows':model['rows'],
          'raw_source':str(raw),'raw_source_sha256':hashlib.sha256(raw.read_bytes()).hexdigest(),
          'source':str(out/'main.cpp'),'source_sha256':hashlib.sha256((out/'main.cpp').read_bytes()).hexdigest(),
          'official_submission_authorized':False,'official_submission_sent':False,
          'baseline_files_unchanged':True}
(root/'research/v4_frozen_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
print('Frozen production candidate; no external model file or Python runtime required.')
