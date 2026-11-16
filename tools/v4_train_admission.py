"""Fit a small first-admission risk tree and export plain C++ candidates.

Features are available before the first RUN. Outcome columns are labels only.
This learns conditional performance under the old policy, not causal action values.
"""
from pathlib import Path
import csv
import hashlib
import json
import numpy as np
from sklearn.model_selection import GroupKFold
from sklearn.tree import DecisionTreeRegressor

ROOT=Path(__file__).resolve().parent.parent
FEATURES=['jobs','root_fraction','plan_cost_per_value','duration_per_window',
          'deadline_per_window','work_per_quota_window','headroom_fraction',
          'rack_load_per_window','duration_factor','prepare_per_window',
          'immediate_per_value','elapsed_fraction','first_cores_per_quota',
          'first_duration_per_window','window_fraction']

def features(row,total_ticks):
    get=lambda key:float(row[key])
    tick=get('first_start')
    window=max(1.,min(total_ticks,get('deadline')+get('grace')-1)-tick)
    quota=max(1.,get('first_path_quota'))
    cores=max(1.,get('first_rack_cores'))
    value=max(1.,get('value'))
    n=max(1.,get('job_count'))
    return np.asarray([
        n,get('root_jobs')/n,get('first_plan_cost')/value,
        get('first_plan_duration')/window,
        (min(total_ticks,get('deadline'))-tick)/window,
        get('first_estimated_work')/(quota*window),
        get('first_headroom')/quota,
        get('first_rack_workload')/(cores*window),get('first_factor'),
        get('first_prepare')/window,get('first_immediate')/value,
        tick/total_ticks,get('first_job_cores')/quota,
        get('first_job_estimated_duration')*get('first_factor')/window,
        window/total_ticks,
    ],dtype=np.float32)

def make_tree():
    return DecisionTreeRegressor(max_depth=3,min_samples_leaf=300,random_state=417)

def tree_cpp(tree):
    t=tree.tree_
    ints=lambda a:','.join(str(int(x)) for x in a)
    floats=lambda a:','.join(format(float(x),'.17g') for x in a)
    return '''
// Learned first-admission risk; all inference features precede the actual RUN.
static double v4_admission_score(const float* x) {
    static const short f[]={FEATURE};
    static const short l[]={LEFT};
    static const short r[]={RIGHT};
    static const double t[]={THRESHOLD};
    static const double v[]={VALUE};
    int n=0;
    while(f[n]>=0)n=x[f[n]]<=t[n]?l[n]:r[n];
    return v[n];
}
'''.replace('FEATURE',ints(t.feature)).replace('LEFT',ints(t.children_left)).replace('RIGHT',ints(t.children_right)).replace('THRESHOLD',floats(t.threshold)).replace('VALUE',floats(t.value[:,0,0]))

def gate_cpp(threshold):
    return '''
        if (!flow.has_started && !best_investment && flow.preferred_rack>=0) {
            double horizon=max(1.,double(flow.last_profitable_tick-current_tick));
            double quota=max<i64>(1,quota_limits[flow.tenant_id]);
            double cores=max<i64>(1,rack_online_cores[flow.preferred_rack]);
            double value=max<i64>(1,flow.value),count=flow.jobs_end-flow.jobs_begin;
            int roots=0;
            for(int j=flow.jobs_begin;j<flow.jobs_end;++j)
                roots+=jobs[j].predecessors_begin==jobs[j].predecessors_end;
            float x[]={float(count),float(roots/count),float(flow.plan_cost/value),
                float(flow.plan_duration/horizon),
                float((min(total_ticks,flow.deadline)-current_tick)/horizon),
                float(flow.estimated_work/(quota*horizon)),
                float(remaining_quota(flow.tenant_id)/quota),
                float(rack_workload[flow.preferred_rack]/(cores*horizon)),
                float(duration_factor),float(best_prepare_time/horizon),
                float(double(best_fee)/value),float(double(current_tick)/total_ticks),
                float(job.required_cores/quota),
                float(job.estimated_duration*duration_factor/horizon),
                float(horizon/total_ticks)};
#ifdef V4_MODEL_FEATURE_TRACE
            fprintf(stderr,"MLFEATURE,%d",job.workflow_index);
            for(float a:x)fprintf(stderr,",%.9g",double(a));
            fprintf(stderr,"\\n");
#endif
#ifndef V4_MODEL_DISABLED
            if(v4_admission_score(x)<MODEL_THRESHOLD)return 0;
#endif
        }
'''.replace('MODEL_THRESHOLD',str(threshold))

def main():
    data_path=ROOT/'results/v4_trace/first_admissions.csv'
    rows=list(csv.DictReader(data_path.open(encoding='utf-8',newline='')))
    totals={}
    for name in {r['case'] for r in rows}:
        cfg=dict(line.split() for line in (ROOT/'cases/train'/f'{name}.in').read_text().splitlines())
        totals[name]=int(cfg['T'])
    assert all(float(r['first_start'])>=1 for r in rows)
    x=np.stack([features(r,totals[r['case']]) for r in rows])
    assert np.isfinite(x).all()
    y=np.asarray([(float(r['earned'])-float(r['cost']))/max(1.,float(r['value'])) for r in rows])
    y=np.clip(y,-2.,1.)
    groups=np.asarray([r['case'] for r in rows])
    weights=np.sqrt(np.asarray([max(1.,float(r['value'])) for r in rows]))
    for group in set(groups):
        mask=groups==group
        weights[mask]/=weights[mask].sum()
    predictions=np.empty(len(y))
    for train,test in GroupKFold(4).split(x,y,groups):
        model=make_tree().fit(x[train],y[train],sample_weight=weights[train])
        predictions[test]=model.predict(x[test])
    model=make_tree().fit(x,y,sample_weight=weights)
    t=model.tree_
    metadata={'source_sha256':hashlib.sha256((ROOT/'main.cpp').read_bytes()).hexdigest(),
              'data_sha256':hashlib.sha256(data_path.read_bytes()).hexdigest(),
              'rows':len(rows),'worlds':sorted(set(groups)), 'features':FEATURES,
              'label':'clip((earned-cost)/value,-2,1), observed under the official 85-point policy',
              'max_depth':3,'minimum_leaf_rows':300,'world_grouped_cv_folds':4,
              'cv_weighted_mse':float(np.average((predictions-y)**2,weights=weights)),
              'constant_weighted_mse':float(np.average((np.average(y,weights=weights)-y)**2,weights=weights)),
              'cv_predicted_negative_rows':int((predictions<0).sum()),
              'nodes':int(t.node_count),
              'feature_importance':dict(zip(FEATURES,map(float,model.feature_importances_))),
              'selection_bias_warning':'Only baseline-admitted actions are observed; closed-loop evaluation required.',
              'never_started_used_as_negatives':False,
              'tree':{'feature':t.feature.tolist(),'left':t.children_left.tolist(),
                      'right':t.children_right.tolist(),'threshold':t.threshold.tolist(),
                      'value':t.value[:,0,0].tolist()}}
    base=(ROOT/'main.cpp').read_text(encoding='utf-8')
    assert metadata['source_sha256']=='21ab5033ed9052e37b691c8f632029b181fe824f9f612cea9364e21bd8ab985c'
    original='''        if (best_machine < 0)
            return 0;
        auto& machine = machines[best_machine];'''
    assert base.count(original)==1
    for name,threshold in [('clear_loss',-.05),('nonpositive',0.0),('low_margin',.05)]:
        source=base.replace('using namespace std;','using namespace std;\n'+tree_cpp(model))
        source=source.replace(original,'''        if (best_machine < 0)
            return 0;
'''+gate_cpp(threshold)+'''        auto& machine = machines[best_machine];''')
        (ROOT/'candidates'/f'v4_model_{name}.cpp').write_text(source,encoding='utf-8',newline='\n')
    # All fitted leaves are positive: a zero-margin veto is analytically a no-op.
    # The separate ranking candidate caps optimistic new-flow profit estimates.
    used=set(map(int,t.feature[t.feature>=0]))
    assert used<={2,3,14}, used
    source=base.replace('using namespace std;','using namespace std;\n'+tree_cpp(model))
    priority_anchor='''            if (profit <= 0)
                continue;'''
    assert source.count(priority_anchor)==1
    priority='''            if (!flow.has_started) {
                double horizon=max(1.,double(flow.last_profitable_tick-current_tick));
                float x[15]{};
                x[2]=float(flow.plan_cost/max<i64>(1,flow.value));
                x[3]=float(flow.plan_duration/horizon);
                x[14]=float(horizon/total_ticks);
                profit=min(profit,max(0.,v4_admission_score(x)*flow.value));
            }
'''
    source=source.replace(priority_anchor,priority+priority_anchor)
    (ROOT/'candidates/v4_model_priority.cpp').write_text(source,encoding='utf-8',newline='\n')
    metadata['positive_leaf_minimum']=float(t.value[t.feature<0,0,0].min())
    metadata['zero_margin_veto_is_no_op']=bool(metadata['positive_leaf_minimum']>0)
    metadata['nontrivial_candidates']=['low_margin: veto expected profit/value below .05',
        'priority: cap optimistic pre-admission priority by learned expected profit']
    destination=ROOT/'research/v4_admission_tree.json'
    destination.write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:metadata[k] for k in ['rows','nodes','cv_weighted_mse','constant_weighted_mse','cv_predicted_negative_rows','feature_importance']}))

if __name__=='__main__':
    main()
