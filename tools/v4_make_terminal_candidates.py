"""Two fixed corrections for an actually ready last remaining job."""
from pathlib import Path
import hashlib
import json

def sub(s,old,new,count=1):
    assert s.count(old)==count,(old,s.count(old),count)
    return s.replace(old,new)

def main():
    source=Path('main.cpp').read_text(encoding='utf-8')
    baseline=hashlib.sha256(Path('main.cpp').read_bytes()).hexdigest()
    assert baseline=='21ab5033ed9052e37b691c8f632029b181fe824f9f612cea9364e21bd8ab985c',baseline
    a=source.index('    bool place_job(int job_index) {')
    b=source.index('    void schedule() {',a)
    section=source[a:b]
    section=sub(section,'        auto& flow = workflows[job.workflow_index];','''        auto& flow = workflows[job.workflow_index];
        bool terminal_ready=flow.finished_jobs+1==flow.jobs_end-flow.jobs_begin &&
                            job.status==0 && job.unfinished_predecessors==0;''')
    section=sub(section,'        double tail = estimate_tail(job, duration_factor),\n               later = max(0., flow.remaining_cost - job.planned_cost);','''        double tail = terminal_ready ? 0. : estimate_tail(job, duration_factor),
               later = terminal_ready ? 0. : max(0., flow.remaining_cost - job.planned_cost);''')
    section=sub(section,'            double span = max(flow.remaining_time, prepare_time + duration + tail + .5*forward_delay);','''            double span = terminal_ready ? prepare_time+duration :
                          max(flow.remaining_time, prepare_time + duration + tail + .5*forward_delay);''')
    section=sub(section,'                max(.77 * flow.remaining_time, prepare_time + max(1., .72 * duration) + .77 * tail + .5*forward_delay);','''                terminal_ready ? prepare_time+max(1.,.72*duration) :
                max(.77 * flow.remaining_time, prepare_time + max(1., .72 * duration) + .77 * tail + .5*forward_delay);''')
    place=source[:a]+section+source[b:]
    rescue='''            if(profit<=0 && flow.has_started &&
               flow.finished_jobs+1==flow.jobs_end-flow.jobs_begin) {
                for(int last=flow.jobs_begin;last<flow.jobs_end;++last) {
                    const auto& terminal=jobs[last];
                    if(terminal.status!=0 || terminal.unfinished_predecessors!=0) continue;
                    double duration=max(1.,terminal.estimated_duration*duration_factor);
                    double income=.72*reward_at(flow,current_tick+duration)+
                                  .28*reward_at(flow,current_tick+max(1.,.72*duration));
                    double minimum_run_cost=(double)terminal.required_cores*min_cpu_price*duration;
                    double upper_profit=income-minimum_run_cost;
                    if(upper_profit>0) {
                        profit=.15*upper_profit;
                        flow.remaining_time=duration;
                        flow.remaining_cost=minimum_run_cost;
                    }
                    break;
                }
            }
'''
    full=sub(place,'            if (profit <= 0)\n                continue;',rescue+'            if (profit <= 0)\n                continue;')
    manifest={}
    for name,text in [('place',place),('rescue',full)]:
        text='// V4 actual last-job valuation: '+name+'; no protocol or accounting changes.\n'+text
        path=Path('candidates')/f'v4_terminal_{name}.cpp'
        path.write_text(text,encoding='utf-8',newline='\n')
        manifest[name]={'source':str(path),'source_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'baseline_sha256':baseline}
    Path('candidates/v4_terminal_manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print('Created two fixed last-job valuation candidates')

if __name__=='__main__':
    main()
