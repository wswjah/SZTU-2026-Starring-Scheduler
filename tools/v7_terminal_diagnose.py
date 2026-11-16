"""Read-only end-of-world counters for the terminal policy's visible gates."""
from pathlib import Path
import hashlib
import json
import subprocess
from bench import run_case

ROOT=Path(__file__).resolve().parent.parent
base=ROOT/'candidates/v7_terminal_conditioned.cpp'
source=base.read_text(encoding='utf8')
source=source.replace('struct TerminalQuote {',
'''long long diagReady=0,diagReadyAccept=0,diagReadyRun=0,diagRunning=0,diagRunningAccept=0;
set<int> diagReadyFlows,diagReadyAcceptedFlows,diagReadyRunFlows,diagRunningFlows,diagRunningAcceptedFlows;
struct TerminalQuote {''',1)
source=source.replace('    if (q.machine<0) return false;',
'''    if (q.machine<0) return false;
    ++diagReadyRun; diagReadyRunFlows.insert(jobs[ji].wf);''',1)
source=source.replace('                if (last>=0 && jobs[last].state==0 && !jobs[last].need) {',
'''                if (last>=0 && jobs[last].state==0 && !jobs[last].need) {
                    ++diagReady; diagReadyFlows.insert(wi);''',1)
source=source.replace('                    if (quote.machine>=0) {',
'''                    if (quote.machine>=0) {
                        ++diagReadyAccept; diagReadyAcceptedFlows.insert(wi);''',1)
source=source.replace('                else if (last>=0 && jobs[last].state==1) {',
'''                else if (last>=0 && jobs[last].state==1) {
                    ++diagRunning; diagRunningFlows.insert(wi);''',1)
source=source.replace('                        rev=nr; cost=nc; work=nw; rem=nw/jobs[last].c;',
'''                        rev=nr; cost=nc; work=nw; rem=nw/jobs[last].c;
                        if(nr>nc) {++diagRunningAccept;diagRunningAcceptedFlows.insert(wi);}''',1)
source=source.replace('        if (now == T) break;',
'''        if (now == T) {
            cerr << "TERMINAL ready_queries=" << diagReady << " ready_flows=" << diagReadyFlows.size()
                 << " ready_accept=" << diagReadyAccept << " ready_accept_flows=" << diagReadyAcceptedFlows.size()
                 << " ready_run=" << diagReadyRun << " ready_run_flows=" << diagReadyRunFlows.size()
                 << " running_queries=" << diagRunning << " running_flows=" << diagRunningFlows.size()
                 << " running_accept=" << diagRunningAccept << " running_accept_flows=" << diagRunningAcceptedFlows.size() << '\\n';
            break;
        }''',1)
out=ROOT/'results/v7_terminal_diagnosis'
out.mkdir(exist_ok=True)
path=out/'diagnostic.cpp';path.write_text(source,encoding='utf8')
exe=ROOT/'build/v7_terminal_diagnostic.exe'
subprocess.run(['g++','-std=c++17','-O2',str(path),'-o',str(exe)],check=True,cwd=ROOT)
rows=[]
for case in ['standard_00','heavy_00','fast_00']:
    r=run_case(exe,ROOT/f'cases/train/{case}.in',out)
    r['terminal_counts']=Path(r['run_dir'],'solver_stderr.txt').read_text(encoding='utf8').strip()
    rows.append(r)
(out/'summary.json').write_text(json.dumps(rows,indent=2),encoding='utf8')
(out/'diagnostic_manifest.json').write_text(json.dumps({
    'base_source':str(base),'base_sha256':hashlib.sha256(base.read_bytes()).hexdigest(),
    'diagnostic_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
    'purpose':'end-only counters; not a new policy; CPU insurance can change trajectories',
},indent=2),encoding='utf8')
for r in rows: print(r['case'],r['ok'],r['terminal_counts'])
