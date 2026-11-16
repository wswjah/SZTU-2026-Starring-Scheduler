import json
import pathlib
import shutil
import subprocess
import time
import psutil

root = pathlib.Path(__file__).resolve().parent.parent
(root / 'cases/smoke').mkdir(exist_ok=True)
shutil.copy2(root/'cases/train/standard_00.in', root/'cases/smoke/standard_00.in')
cfg = json.loads((root/'config.json').read_text(encoding='utf8'))
cfg['testdata_dir'] = str(root/'cases/smoke')
(root/'tools/probe_config.json').write_text(json.dumps(cfg, ensure_ascii=False,indent=2),encoding='utf8')
p = subprocess.Popen([str(root/'csg_tpj_debug_player_windows_amd64.exe'),'-noninteractive','-config',str(root/'tools/probe_config.json')],stdout=subprocess.PIPE,stderr=subprocess.PIPE,cwd=root)
seen = set()
t = time.time()
while p.poll() is None and time.time()-t<45:
    for c in psutil.Process(p.pid).children(recursive=True):
        if c.pid not in seen:
            try:
                cmd = c.cmdline()
                if any('tpj' in x or 'solution.exe' in x for x in cmd):
                    print(c.pid,repr(cmd),flush=True)
            except psutil.Error:
                pass
            seen.add(c.pid)
    time.sleep(.005)
o,e=p.communicate(timeout=3)
print(o.decode('utf8','replace'))
print(e.decode('utf8','replace'))
