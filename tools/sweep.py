"""Compare declared parameter variants on practice cases with the official TPJ."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import statistics
from bench import run_case

VARIANTS = {
    'default': {},
    'duration_080': {'SR_DURATION': .8},
    'duration_090': {'SR_DURATION': .9},
    'duration_110': {'SR_DURATION': 1.1},
    'duration_120': {'SR_DURATION': 1.2},
    'prior_1': {'SR_PRIOR': 1},
    'prior_10': {'SR_PRIOR': 10},
    'clip_2': {'SR_CLIP': 2},
    'clip_3': {'SR_CLIP': 3},
    'weighted_05': {'SR_EST_WEIGHT': .5},
    'weighted_1': {'SR_EST_WEIGHT': 1},
    'progress_1': {'SR_PROGRESS': 1},
    'progress_3': {'SR_PROGRESS': 3},
    'work_04': {'SR_WORK': .4},
    'work_16': {'SR_WORK': 1.6},
    'time_0': {'SR_TIME': 0},
    'time_10': {'SR_TIME': 10},
    'rack_wait_0': {'SR_RACK_WAIT': 0},
    'rack_wait_1': {'SR_RACK_WAIT': 1},
    'risk_0': {'SR_RISK': 0},
    'risk_3': {'SR_RISK': 3},
    'risk_10': {'SR_RISK': 10},
    'running_05': {'SR_RUNNING_FLOOR': .5},
    'long_margin_1': {'SR_LONG_MARGIN': 1},
    'long_margin_15': {'SR_LONG_MARGIN': 1.5},
}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--exe',default='build/tunable.exe')
    p.add_argument('--cases',default='cases/train')
    p.add_argument('--glob',default='*_00.in')
    p.add_argument('--out',default='results/sweep')
    p.add_argument('--workers',type=int,default=2)
    p.add_argument('--variants',nargs='*')
    p.add_argument('--spec',help='JSON mapping variant names to environments')
    args=p.parse_args()
    variants=json.loads(Path(args.spec).read_text()) if args.spec else VARIANTS
    if args.variants:
        variants={k:variants[k] for k in args.variants}
    cases=sorted(Path(args.cases).glob(args.glob))
    output=Path(args.out)
    output.mkdir(parents=True,exist_ok=True)
    (output/'variants.json').write_text(json.dumps(variants,indent=2))
    summaries={}
    for name,env in variants.items():
        def run(case):
            target=output/name/case.stem/'result.json'
            if target.exists():
                result=json.loads(target.read_text(encoding='utf-8'))
                if result.get('ok'): return result
            return run_case(args.exe,case,output/name,env=env)
        with ThreadPoolExecutor(args.workers) as pool:
            results=list(pool.map(run,cases))
        (output/name/'summary.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
        record={'name':name,'env':env,'ok':all(r['ok'] for r in results),
                'profit':sum(r.get('profit',0) for r in results),
                'max_cpu':max(r.get('solver_cpu_seconds',0) for r in results),
                'profits':{r['case']:r.get('profit',0) for r in results}}
        if 'default' in summaries:
            base=summaries['default']['profits']
            ratios=[record['profits'][k]/v for k,v in base.items() if v>0]
            record.update(mean_ratio=statistics.mean(ratios),median_ratio=statistics.median(ratios),
                          wins=sum(record['profits'][k]>v for k,v in base.items()),
                          min_ratio=min(ratios))
        summaries[name]=record
        (output/'comparison.json').write_text(json.dumps(summaries,indent=2),encoding='utf-8')
        print(json.dumps({k:v for k,v in record.items() if k!='profits'}),flush=True)

if __name__=='__main__':
    main()
