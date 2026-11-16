"""Serial, interleaved timing; retain every raw run and exact judge-report comparison."""
from pathlib import Path
import argparse
import json
import statistics
from bench import run_case


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline',required=True)
    parser.add_argument('--candidate',required=True)
    parser.add_argument('--cases',nargs='+',required=True)
    parser.add_argument('--out',required=True,type=Path)
    parser.add_argument('--rounds',type=int,default=3)
    args=parser.parse_args()
    cases=[]
    for name in args.cases:
        path=Path(name)
        cases.extend(sorted(path.glob('*.in')) if path.is_dir() else [path])
    args.out.mkdir(parents=True,exist_ok=True)
    runs=[]
    for repeat in range(args.rounds):
        order=[('baseline',args.baseline),('candidate',args.candidate)]
        if repeat%2:
            order.reverse()
        for case in cases:
            pair={}
            for label,exe in order:
                row=run_case(exe,case,args.out/f'round_{repeat+1}'/label/case.parent.name)
                row.update(round=repeat+1,variant=label,split=case.parent.name)
                runs.append(row)
                pair[label]=row
                (args.out/'runs.json').write_text(json.dumps(runs,indent=2),encoding='utf8')
            match=pair['baseline']['report']==pair['candidate']['report']
            print(json.dumps(dict(round=repeat+1,case=case.stem,split=case.parent.name,exact_report_match=match,
                baseline_cpu=pair['baseline']['solver_cpu_seconds'],candidate_cpu=pair['candidate']['solver_cpu_seconds'])),flush=True)
            if not match or not all(row['ok'] for row in pair.values()):
                raise RuntimeError('Behavior mismatch or invalid run')
    grouped={}
    for split in sorted({row['split'] for row in runs}):
        selected=[row for row in runs if row['split']==split]
        totals={label:sum(row['solver_cpu_seconds'] for row in selected if row['variant']==label)
                for label in ['baseline','candidate']}
        per_case=[]
        for name in sorted({row['case'] for row in selected}):
            row={'case':name}
            for label in ['baseline','candidate']:
                values=[item['solver_cpu_seconds'] for item in selected if item['case']==name and item['variant']==label]
                row[label+'_all_cpu_seconds']=values
                row[label+'_median_cpu_seconds']=statistics.median(values)
            a,b=row['baseline_median_cpu_seconds'],row['candidate_median_cpu_seconds']
            row['median_reduction_pct']=100*(1-b/a) if a else None
            per_case.append(row)
        grouped[split]=dict(all_cpu_totals=totals,total_cpu_reduction_pct=100*(1-totals['candidate']/totals['baseline']),
                            per_case=per_case)
    summary=dict(rounds=args.rounds,run_count=len(runs),all_reports_exactly_equal=True,splits=grouped,
                 execution='Strictly serial; case-paired runs, variant order alternated per round')
    (args.out/'timing_summary.json').write_text(json.dumps(summary,indent=2),encoding='utf8')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':
    main()
