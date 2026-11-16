"""Summarize the diagnostic-only per-workflow CSV from v4_trace.exe.

All end-of-run labels are hindsight diagnostics, never policy inputs. The first
admission fields contain only values available before the first RUN.
"""
from pathlib import Path
import argparse
import csv
import hashlib
import json
import statistics

FLOATS = {'first_cost','first_plan_cost','first_time','first_factor',
          'first_plan_duration','first_estimated_work','first_rack_workload'}

def group(rows):
    return dict(flows=len(rows), cost=sum(r['cost'] for r in rows),
                earned=sum(r['earned'] for r in rows),
                profit=sum(r['profit'] for r in rows),
                failed_flows=sum(r['failed_jobs']>0 for r in rows),
                failed_jobs=sum(r['failed_jobs'] for r in rows),
                killed_flows=sum(r['killed_jobs']>0 for r in rows),
                auto_changed_flows=sum(r['auto_valid_changes']>0 for r in rows),
                auto_changes=sum(r['auto_valid_changes'] for r in rows),
                late=sum(r['finish']>r['deadline'] for r in rows))

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--trace',default='results/v4_trace')
    p.add_argument('--baseline',default='results/v3_final_aggressive/summary.json')
    args=p.parse_args()
    directory=Path(args.trace)
    base_rows=json.loads(Path(args.baseline).read_text(encoding='utf8'))
    bases={r['case']:r for r in base_rows
           if '\\train\\' in r.get('input','') or '/train/' in r.get('input','')}
    summary=[]
    combined=[]
    for run_dir in sorted(directory.iterdir()):
        if not run_dir.is_dir() or not (run_dir/'solver_stderr.txt').exists():continue
        lines=(run_dir/'solver_stderr.txt').read_text(encoding='utf8').splitlines()
        header=next(x.split(',')[1:] for x in lines if x.startswith('TRACEFLOW_HEADER,'))
        raw=[x.split(',')[1:] for x in lines if x.startswith('TRACEFLOW,')]
        assert all(len(r)==len(header) for r in raw)
        rows=[{k:float(v) if k in FLOATS else int(v) for k,v in zip(header,r)} for r in raw]
        state=next(x.split(',')[1:] for x in lines if x.startswith('TRACESTATE,'))
        report=json.loads((run_dir/'result.json').read_text(encoding='utf8'))
        assert report['report']==bases[run_dir.name]['report'],run_dir.name
        assert sum(r['cost'] for r in rows)==report['cost']
        assert sum(r['earned'] for r in rows)==report['earned']
        assert all(r['run']+r['net']+r['pull']==r['cost'] for r in rows)
        assert all(r['prep_run']+r['compute_run']==r['run'] for r in rows)
        assert sum(r['interrupted_run'] for r in rows)==report['waste']
        assert sum(r['failed_jobs']+r['killed_jobs'] for r in rows)==report['killed']
        for r in rows:
            r['profit']=r['earned']-r['cost']
            r['category']=('never_started' if r['first_start']<0 else
                'unfinished_started' if r['finish']<0 else
                'completed_positive' if r['profit']>0 else 'completed_loss')
            r['first_deadline_slack']=r['deadline']-r['first_start']-r['first_time'] if r['first_start']>=0 else None
        with (run_dir/'flows.csv').open('w',newline='',encoding='utf8') as f:
            w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
        combined.extend(dict(case=run_dir.name,**r) for r in rows)
        started=[r for r in rows if r['first_start']>=0]
        completed=[r for r in started if r['finish']>=0]
        incomplete=[r for r in started if r['finish']<0]
        record=dict(case=run_dir.name, profit=report['profit'],cost=report['cost'],earned=report['earned'],
            exact_baseline_report=True, groups={name:group([r for r in rows if r['category']==name])
                for name in ['never_started','unfinished_started','completed_positive','completed_loss']},
            cpu_utilization=int(state[2])/int(state[1]),ready_tick_avg=int(state[3])/int(state[0]),
            fee_split={k:sum(r[k] for r in rows) for k in ['run','net','pull','prep_run','compute_run','interrupted_run','interrupted_fees']},
            started_count=len(started),started_auto_changed=sum(r['auto_valid_changes']>0 for r in started),
            successful_reroutes=sum(r['reroutes'] for r in rows),
            incomplete_no_failure=group([r for r in incomplete if r['failed_jobs']==0]),
            incomplete_with_failure=group([r for r in incomplete if r['failed_jobs']>0]),
            incomplete_predicted_ontime=group([r for r in incomplete if r['first_deadline_slack']>=0]),
            by_started_job_count={label:group([r for r in started if lo<=r['job_count']<=hi])
                for label,lo,hi in [('1',1,1),('2-4',2,4),('5-12',5,12),('13-40',13,40),('41+',41,100000)]},
            completed_cost_ratio_median=statistics.median([r['cost']/r['first_plan_cost'] for r in completed if r['first_plan_cost']>0]) if completed else None,
            completed_duration_ratio_median=statistics.median([(r['finish']-r['first_start'])/r['first_plan_duration'] for r in completed if r['first_plan_duration']>0]) if completed else None)
        summary.append(record)
        print(json.dumps(dict(case=run_dir.name,profit=record['profit'],unfinished_cost=record['groups']['unfinished_started']['cost'],
            completed_net_loss=-record['groups']['completed_loss']['profit'],cpu_utilization=record['cpu_utilization'],
            auto_changed=record['started_auto_changed'],started=record['started_count'])))
    (directory/'diagnosis.json').write_text(json.dumps(summary,indent=2),encoding='utf8')
    fields=list(dict.fromkeys(k for row in combined for k in row))
    for filename,selected in [('all_flows.csv',combined),
                              ('first_admissions.csv',[r for r in combined if r['first_start']>=0])]:
        with (directory/filename).open('w',newline='',encoding='utf8') as f:
            writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader();writer.writerows(selected)
    manifest=dict(source_sha256=hashlib.sha256(Path('candidates/v4_trace.cpp').read_bytes()).hexdigest(),
                  baseline_source_sha256=hashlib.sha256(Path('main.cpp').read_bytes()).hexdigest(),
                  baseline_reports=args.baseline,trace_directory=args.trace,
                  all_reports_exact=True,all_workflow_costs_and_earned_reconciled=True,
                  cases=[r['case'] for r in summary],flow_rows=len(combined),
                  admitted_rows=sum(r['first_start']>=0 for r in combined),
                  note='Hindsight outcome columns must never be used as decision-time features.')
    (directory/'trace_manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf8')

if __name__=='__main__':main()
