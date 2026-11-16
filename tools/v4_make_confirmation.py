"""Additional frozen worlds to check risk-model generalization."""
from pathlib import Path
import hashlib
import json
from make_cases import BASE,PROFILES

root=Path(__file__).resolve().parent.parent
out=root/'cases/v4_confirmation'
out.mkdir(parents=True,exist_ok=True)
manifest=[]
for i,(name,changes) in enumerate(PROFILES.items()):
    for j in range(4):
        cfg=BASE|changes|{'seed':310920265+17093*i+19391*j}
        if name=='large':cfg.update(load=.75,log_rate=.12)
        path=out/f'{name}_{j:02}.in'
        data=''.join(f'{k} {v}\n' for k,v in cfg.items()).encode('ascii')
        path.write_bytes(data)
        manifest.append({'file':path.name,'parameters':cfg,'sha256':hashlib.sha256(data).hexdigest(),
                         'purpose':'confirm frozen V4 model; no model fitting or tuning on these outcomes'})
(out/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
print('Created 32 new confirmation worlds.')
