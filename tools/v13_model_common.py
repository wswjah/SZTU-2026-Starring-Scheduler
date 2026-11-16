"""Predeclared V13 model features and first-admission policies."""
from pathlib import Path
import json

ROOT=Path(__file__).resolve().parent.parent
BASE=ROOT/"versions/v12_scan_input_fix/main.cpp"
FEATURES=["jobs","root_fraction","forecast_cost_per_value","forecast_time_per_window","forecast_revenue_per_value",
          "forecast_net_per_value","work_per_quota_window","headroom_fraction","window_fraction","elapsed_fraction",
          "tenant_duration_factor","deadline_slack_fraction","first_cores_per_quota","selected_prep_fraction",
          "first_transfer_fee_per_value","first_duration_fraction","forecast_age_fraction","selected_prewarm"]
POLICIES={
    "veto_light":{"type":"net_veto","net_threshold":.02,"forecast_net_threshold":.25,"min_jobs":3},
    "veto_strict":{"type":"net_veto","net_threshold":.08,"forecast_net_threshold":.40,"min_jobs":3},
    "rev_blend25":{"type":"revenue_blend","model_weight":.25},
    "rev_blend50":{"type":"revenue_blend","model_weight":.50},
}
DECLARATIONS=r'''
struct V13ModelForecast {double rem=0,work=0,cost=0,rev=0;int tick=0,roots=0;};
vector<V13ModelForecast> v13ModelForecasts;
'''
FEATURE_CPP=r'''
void v13ModelFeatures(int ji,int machine,double preparation,bool warm,float* x) {
    const Job& j=jobs[ji];const Flow& w=flows[j.wf];const V13ModelForecast& p=v13ModelForecasts[j.wf];
    int grace=max(5,(w.dl-w.arrive)/3);
    double window=max(1.,double(min(T,w.dl+grace-1)-now)),value=max(1.,double(w.v));
    ll quota=LLONG_MAX,headroom=LLONG_MAX;
    for(int a=w.tenant;a>=0;a=tenPar[a])quota=min(quota,tenQuota[a]),headroom=min(headroom,tenQuota[a]-tenUsed[a]);
    double capacity=max(1.,double(quota));ll time,fee,away;
    transferCost(jobs[ji],machRack[machine],time,fee,away);
    x[0]=float(w.n);x[1]=float(double(p.roots)/max(1,w.n));
    x[2]=float(p.cost/value);x[3]=float(p.rem/window);x[4]=float(p.rev/value);x[5]=float((p.rev-p.cost)/value);
    x[6]=float(p.work/(capacity*window));x[7]=float(headroom/capacity);x[8]=float(window/T);x[9]=float(double(now)/T);
    x[10]=float(tenFactor(w.tenant));x[11]=float((w.dl-now)/window);x[12]=float(j.c/capacity);
    x[13]=float(preparation/window);x[14]=float(fee/value);x[15]=float(j.e*tenFactor(w.tenant)/window);
    x[16]=float(double(now-p.tick)/T);x[17]=warm?1.f:0.f;
}
'''


def once(source,old,new):
    assert source.count(old)==1,old[:100]
    return source.replace(old,new)


def base_instrumentation(source):
    source=once(source,"int freedAt[360];","int freedAt[360];\n"+DECLARATIONS)
    source=once(source,"void tryPlace(int ji) {",FEATURE_CPP+"\nvoid tryPlace(int ji) {")
    source=once(source,"""            w.dirty = 0, w.key = 1;""","""            auto& v13forecast=v13ModelForecasts[wi];
            v13forecast.rem=rem;v13forecast.work=work;v13forecast.cost=cost;v13forecast.rev=rev;v13forecast.tick=now;
            w.dirty = 0, w.key = 1;""")
    source=once(source,"""                flows.push_back(w);""","""                flows.push_back(w);
                V13ModelForecast v13forecast;
                F(i,w.n)v13forecast.roots+=jobs[w.first+i].pre.empty();
                v13ModelForecasts.push_back(v13forecast);""")
    return source


def declare_plan():
    path=ROOT/"research/v13_model_plan.json"
    record={"features":FEATURES,"policies":POLICIES,"max_depth":3,"min_samples_leaf":500,"folds":4,
            "targets":["earned/value","clip((earned-actual_cost)/value,-2,1)"],
            "training":"cases/v13_train32 only","inference":"Before first actual complete RUN batch,selectedmachine/budget already feasible,never modifies started workflows",
            "forecast":"Cached only where original schedule truly updates rem/work/cost/rev;no extra flowEstimate",
            "labels":"Actual admitted baseline-policy conditional outcomes,not causal or counterfactual;never-started excluded",
            "official_submission_sent":False}
    if path.exists():
        assert json.loads(path.read_text(encoding="utf8"))==record,"Do not change the predeclared policy plan"
    else:
        path.write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding="utf8")

