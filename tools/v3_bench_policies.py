"""Training-only comparisons for the six fixed V3 risk variants."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
from bench import run_case
from compare import compare, markdown

def main():
    manifest=json.loads(Path('candidates/v3_policy_manifest.json').read_text())
    cases=sorted(Path('cases/train').glob('*.in'))
    summaries={}
    for name,cfg in manifest.items():
        output=Path('results/v3_policy_train')/name
        exe=Path('build')/f'v3_policy_{name}.exe'
        with ThreadPoolExecutor(2) as pool:
            results=list(pool.map(lambda case:run_case(exe,case,output),cases))
        (output/'summary.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
        comparison=compare('results/final_train',output)
        (output/'comparison.json').write_text(json.dumps(comparison,indent=2),encoding='utf-8')
        (output/'comparison.md').write_text(markdown(comparison),encoding='utf-8')
        valid=comparison['valid_range_summary']
        def brief(c):
            keys=['case_count','baseline_total_profit','candidate_total_profit','total_profit_increase_pct','mean_profit_ratio','median_profit_ratio','improved','regressed','unchanged']
            return {k:c[k] for k in keys}
        rows=comparison['rows']
        record=dict(configuration=cfg['configuration'],valid=brief(valid),overall=brief(comparison),boundary=brief(comparison['boundary_pressure_summary']),
                    worst=min(rows,key=lambda r:r['profit_ratio']),ok=all(r['ok'] for r in results),max_cpu=max(r['solver_cpu_seconds'] for r in results))
        summaries[name]=record
        Path('results/v3_policy_train/selection_summary.json').write_text(json.dumps(summaries,indent=2),encoding='utf-8')
        print(json.dumps(dict(name=name,**record)),flush=True)

if __name__=='__main__':
    main()
