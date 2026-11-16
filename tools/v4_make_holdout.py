"""New worlds frozen after training; never used to fit the risk model."""
from pathlib import Path
import hashlib
import json
from make_cases import BASE,PROFILES

root=Path(__file__).resolve().parent.parent
directory=root/'cases/v4_holdout'
directory.mkdir(exist_ok=True,parents=True)
manifest=[]
for i,(profile,overrides) in enumerate(PROFILES.items()):
    for j in range(2):
        cfg=BASE|overrides|{'seed':78411255+19013*i+37813*j}
        if profile=='large':cfg.update(load=.75,log_rate=.12)
        name=f'{profile}_{j:02}.in'
        data=''.join(f'{k} {v}\n' for k,v in cfg.items()).encode('ascii')
        (directory/name).write_bytes(data)
        manifest.append({'file':name,'parameters':cfg,'sha256':hashlib.sha256(data).hexdigest(),
                         'purpose':'new-world V4 validation, not used to train the admission model'})
(directory/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
print('Frozen 16 unseen V4 worlds; all original datasets untouched.')
