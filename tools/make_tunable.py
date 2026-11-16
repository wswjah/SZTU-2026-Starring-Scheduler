"""Create a parameterized research executable from the unmodified reference."""
from pathlib import Path
import argparse

p=argparse.ArgumentParser()
p.add_argument('--source',default='reference/StarRing_readable.cpp')
p.add_argument('--out',default='candidates/tunable.cpp')
args=p.parse_args()
source = Path(args.source).read_text(encoding='utf-8')
insert = '''
static double parameter(const char* key, double fallback) {
    const char* p = getenv(key);
    return p ? atof(p) : fallback;
}
static const double duration_scale=parameter("SR_DURATION",1.0);
static const double tenant_prior=parameter("SR_PRIOR",4.0);
static const double progress_base=parameter("SR_PROGRESS",1.8);
static const double work_price=parameter("SR_WORK",0.8);
static const double time_price=parameter("SR_TIME",3.0);
static const double rack_wait=parameter("SR_RACK_WAIT",0.25);
static const double risk_scale=parameter("SR_RISK",1.0);
static const double ratio_clip=parameter("SR_CLIP",4.0);
static const double estimate_weight=parameter("SR_EST_WEIGHT",0.0);
static const double prior_mean=parameter("SR_MEAN",1.2);
static const double running_floor=parameter("SR_RUNNING_FLOOR",0.25);
static const double long_margin=parameter("SR_LONG_MARGIN",1.25);
static const double plan_age=parameter("SR_PLAN_AGE",1.0);
static const double unstarted_plan_age=parameter("SR_UNSTARTED_AGE",1.0);
static const double cost_safety=parameter("SR_COST_SAFETY",1.0);
static const double reward_mix=parameter("SR_REWARD_MIX",0.72);
static const double optimism=parameter("SR_OPTIMISM",0.77);
'''
source = source.replace('using namespace std;', 'using namespace std;\n'+insert)
replacements = {
    '.25, 4.);': '.25, ratio_clip);\n            double sample_weight = pow((double)job.estimated_duration,estimate_weight);\n            ratio *= sample_weight;',
    '++tenant.sample_count;': 'tenant.sample_weight += sample_weight;',
    '++duration_sample_count;': 'duration_sample_weight += sample_weight;',
    'int parent_id = -1, sample_count;': 'double sample_weight = 0; int parent_id = -1, sample_count;',
    'double duration_ratio_sum; // 全场真实时长倍率样本和': 'double duration_ratio_sum, duration_sample_weight = 0; // Global sample weight',
    '(duration_ratio_sum + 9.6) / (duration_sample_count + 8.)': '(duration_ratio_sum + 8.*prior_mean) / (duration_sample_weight + 8.)',
    '(tenant.duration_ratio_sum + 4 * global) / (tenant.sample_count + 4.)': 'duration_scale * (tenant.duration_ratio_sum + tenant_prior * global) / (tenant.sample_weight + tenant_prior)',
    '.25 * duration});': 'running_floor * duration});',
    '.25 * max(0., rack_workload[rack_id] - own)': 'rack_wait * max(0., rack_workload[rack_id] - own)',
    '+ risk(machine) +': '+ risk_scale * risk(machine) +',
    '1.8 + 1.2 * flow.finished_jobs /': 'progress_base + 1.2 * flow.finished_jobs /',
    '(18. + .8 * work + 3. * flow.remaining_time)': '(18. + work_price * work + time_price * flow.remaining_time)',
    'current_tick + 1.25 * flow.remaining_time': 'current_tick + long_margin * flow.remaining_time',
    'flow.plan_duration - (current_tick - flow.plan_tick)': 'flow.plan_duration - (flow.has_started ? plan_age : unstarted_plan_age) * (current_tick - flow.plan_tick)',
    'flow.remaining_cost = flow.plan_cost;': 'flow.remaining_cost = cost_safety*flow.plan_cost;',
    '.72 * reward_at(flow, current_tick + elapsed_time) +\n               .28 * reward_at(flow, current_tick + max(1., .77 * elapsed_time))': 'reward_mix * reward_at(flow, current_tick + elapsed_time) +\n               (1.-reward_mix) * reward_at(flow, current_tick + max(1., optimism * elapsed_time))',
}
for old,new in replacements.items():
    assert old in source, old
    source=source.replace(old,new)
Path(args.out).write_text(source,encoding='utf-8',newline='\n')
print('Wrote '+args.out)
