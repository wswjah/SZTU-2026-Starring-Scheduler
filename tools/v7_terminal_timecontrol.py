"""Disable only CPU-driven insurance to separate policy from timing effects."""
from pathlib import Path
import hashlib
import json
import subprocess
from bench import run_case

ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'results/v7_terminal_timecontrol'
OUT.mkdir(exist_ok=True)
inputs={'base':ROOT/'versions/v6_attributed96/main.cpp',
        'rescue':ROOT/'candidates/v7_terminal_rescue.cpp',
        'conditioned':ROOT/'candidates/v7_terminal_conditioned.cpp'}
rows=[]
for label,path in inputs.items():
    source=path.read_text(encoding='utf8')
    assert source.count('PRM(TS, 1);')==1
    source=source.replace('PRM(TS, 1);','PRM(TS, 0);')
    control=OUT/f'{label}_ts0.cpp';control.write_text(source,encoding='utf8')
    exe=ROOT/f'build/v7_terminal_{label}_ts0.exe'
    subprocess.run(['g++','-std=c++17','-O2',str(control),'-o',str(exe)],check=True,cwd=ROOT)
    group=[]
    for case in ['standard_00','heavy_00','fast_00']:
        r=run_case(exe,ROOT/f'cases/train/{case}.in',OUT/label)
        r['variant']=label
        group.append(r);rows.append(r)
    (OUT/label/'summary.json').write_text(json.dumps(group,indent=2),encoding='utf8')
(OUT/'summary.json').write_text(json.dumps(rows,indent=2),encoding='utf8')
for r in rows: print(r['variant'],r['case'],r['profit'],r['ok'])
for label in ['rescue','conditioned']:
    a={r['case']:r for r in rows if r['variant']=='base'}
    b={r['case']:r for r in rows if r['variant']==label}
    print('report_equivalence',label,{case:a[case]['report']==b[case]['report'] for case in a})
