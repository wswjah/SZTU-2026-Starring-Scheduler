"""Add an experimental online-only stop-loss to the public scheduler."""
from pathlib import Path
s=Path('candidates/tunable.cpp').read_text(encoding='utf-8')
s=s.replace('static const double duration_scale=', 'static const double stop_ratio=parameter("SR_STOP",1e20);\nstatic const double stop_min_age=parameter("SR_STOP_AGE",0);\nstatic const double duration_scale=')
s=s.replace('int tenant_id, jobs_begin, jobs_end, deadline, grace_period, last_profitable_tick,',
            'int first_start_tick=-1;\n    int tenant_id, jobs_begin, jobs_end, deadline, grace_period, last_profitable_tick,')
s=s.replace('flow.has_started = 1;', 'flow.has_started = 1;\n        if(flow.first_start_tick<0) flow.first_start_tick=current_tick;')
anchor='            double profit = estimate_reward(flow, flow.remaining_time) - flow.remaining_cost;'
insert='''
            if (flow.has_started && stop_ratio < 1e10 && flow.preferred_rack >= 0 &&
                current_tick - flow.first_start_tick >= stop_min_age &&
                plan_on_rack(flow,flow.preferred_rack)) {
                double income=estimate_reward(flow,flow.plan_duration);
                if(flow.plan_cost>income*stop_ratio) {
                    for(int j=flow.jobs_begin;j<flow.jobs_end && commands_sent<command_limit;++j)
                        if(jobs[j].status==1) {
                            emit_command("KILL ",jobs[j].job_id);
                            release_job(j,0);
                            ++environment_version;
                        }
                    flow.last_profitable_tick=0;
                    flow.priority=0;
                    continue;
                }
            }
'''
assert anchor in s
s=s.replace(anchor,insert+anchor)
Path('candidates/stop.cpp').write_text(s,encoding='utf-8',newline='\n')
print('Wrote candidates/stop.cpp')
