"""Deadline-window admission externalities; two fixed structural alternatives."""
from pathlib import Path
import hashlib
import json

def sub(source,old,new,count=1):
    assert source.count(old)==count,(old,source.count(old),count)
    return source.replace(old,new)

METHODS=r'''
    void admission_rebuild(vector<admission_entry>& row, size_t first=0) {
        double w=0,v=0,rw=0,rv=0;
        if(first) {
            const auto& p=row[first-1];
            w=p.sum_work; v=p.sum_value; rw=p.sum_rate_work; rv=p.sum_rate_value;
        }
        for(size_t i=first;i<row.size();++i) {
            auto& e=row[i];
            double h=max(1,e.deadline-current_tick);
            w+=e.work; v+=e.value; rw+=e.work/h; rv+=e.value/h;
            e.sum_work=w; e.sum_value=v; e.sum_rate_work=rw; e.sum_rate_value=rv;
        }
    }

    void admission_insert(int scope,const admission_entry& entry,bool rebuilding) {
        auto& row=admission_rows[scope];
        if(rebuilding) { row.push_back(entry); return; }
        auto p=upper_bound(row.begin(),row.end(),entry.deadline,
                           [](int d,const admission_entry& e){return d<e.deadline;});
        size_t i=p-row.begin();
        row.insert(p,entry);
        admission_rebuild(row,i);
    }

    void admission_register(workflow_state& flow,bool rebuilding) {
        if(flow.estimated_work<=0 || current_tick>=flow.last_profitable_tick) return;
        double done=flow.schedule_tick==current_tick ? flow.estimated_work_done : 0.;
        double w=max(0.,estimate_remaining_work(flow)-done);
        double h=max(1.,flow.plan_duration-max(0,current_tick-flow.plan_tick));
        double value=max(0.,estimate_reward(flow,h)-1.1*flow.plan_cost);
        if(w<=0 || value<=0) return;
        admission_entry entry{flow.last_profitable_tick,w,value};
        for(int a:tenants[flow.tenant_id].ancestor_path)
            admission_insert(a,entry,rebuilding);
        if(flow.preferred_rack>=0)
            admission_insert(tenant_count+flow.preferred_rack,entry,rebuilding);
    }

    void admission_build(i64 online_cores) {
        admission_online_cores=online_cores;
        for(auto& row:admission_rows) row.clear();
        for(auto& flow:workflows) if(flow.has_started)
            admission_register(flow,true);
        for(auto& row:admission_rows) {
            stable_sort(row.begin(),row.end(),[](const admission_entry& a,const admission_entry& b) {
                return a.deadline<b.deadline;
            });
            admission_rebuild(row);
        }
    }

    double admission_scope_cost(int scope,int deadline,double own,double capacity) {
        const auto& row=admission_rows[scope];
        if(row.empty() || capacity<=0) return 0.;
        auto p=upper_bound(row.begin(),row.end(),deadline,
                           [](int d,const admission_entry& e){return d<e.deadline;});
        double used=0,value=0,rw=0,rv=0;
        if(p!=row.begin()) {
            const auto& e=*(p-1);
            used=e.sum_work; value=e.sum_value;
            rw=e.sum_rate_work; rv=e.sum_rate_value;
        }
        double horizon=max(1,deadline-current_tick);
        INCLUDE_LATER
        if(used<=0 || value<=0) return 0.;
        double spare=max(0.,capacity*horizon-used);
        double displaced=min(used,max(0.,own-spare));
        return displaced*value/used;
    }

    double admission_externality(workflow_state& flow) {
        if(flow.has_started || current_tick>=flow.last_profitable_tick) return 0.;
        double own=max(0.,estimate_remaining_work(flow));
        double charge=0.;
        for(int a:tenants[flow.tenant_id].ancestor_path) {
            double capacity=min((double)tenants[a].quota,admission_online_cores);
            charge=max(charge,admission_scope_cost(a,flow.last_profitable_tick,own,capacity));
        }
        if(flow.preferred_rack>=0)
            charge=max(charge,admission_scope_cost(tenant_count+flow.preferred_rack,
                       flow.last_profitable_tick,own,(double)rack_online_cores[flow.preferred_rack]));
        return charge;
    }
'''

def main():
    source=Path('main.cpp').read_text(encoding='utf-8')
    baseline=hashlib.sha256(Path('main.cpp').read_bytes()).hexdigest()
    assert baseline=='21ab5033ed9052e37b691c8f632029b181fe824f9f612cea9364e21bd8ab985c',baseline
    source=sub(source,'struct scheduler {\n','''struct admission_entry {
    int deadline;
    double work,value;
    double sum_work=0,sum_value=0,sum_rate_work=0,sum_rate_value=0;
};

struct scheduler {
    vector<vector<admission_entry>> admission_rows;
    double admission_online_cores=0;
''')
    source=sub(source,'        tenant_workload.resize(tenant_count);','        tenant_workload.resize(tenant_count);\n        admission_rows.resize(tenant_count+rack_count);')
    source=sub(source,'        for (int workflow_index : active_workflows) {','        admission_build(online_cores);\n        for (int workflow_index : active_workflows) {')
    inner='            flow.remaining_cost = 1.1 * flow.plan_cost; // Allow for uncertain future startup costs.'
    assert source.count(inner)==2
    start=source.index('    bool place_job(int job_index) {')
    end=source.index('    void schedule() {',start)
    section=source[start:end]
    section=sub(section,inner+'\n','')
    marker='        double duration_factor = tenants[flow.tenant_id].duration_factor,\n               duration = max(1., job.estimated_duration * duration_factor);'
    section=sub(section,marker,'        flow.remaining_cost = 1.1*flow.plan_cost + admission_externality(flow);\n'+marker)
    section=sub(section,'        flow.has_started = 1;','        if(!flow.has_started) admission_register(flow,false);\n        flow.has_started = 1;')
    source=source[:start]+section+source[end:]
    source=sub(source,inner,'            double admission_charge=admission_externality(flow);\n            flow.remaining_cost = 1.1*flow.plan_cost + admission_charge;')
    source=sub(source,'                                                min_cpu_price));','                                                min_cpu_price)-admission_charge);')
    variants={
        'edf':'// Only commitments whose hard profit window expires within this window.',
        'reservation':'''const auto& total=row.back();
        used+=horizon*max(0.,total.sum_rate_work-rw);
        value+=horizon*max(0.,total.sum_rate_value-rv);'''
    }
    manifest={}
    for name,later in variants.items():
        methods=METHODS.replace('INCLUDE_LATER',later)
        output=sub(source,'    void touch_workflow(workflow_state& flow, int workflow_index) {',methods+'\n    void touch_workflow(workflow_state& flow, int workflow_index) {')
        output='// V4 committed-flow protection: '+name+'; admission shadow cost only.\n'+output
        target=Path('candidates')/f'v4_commitment_{name}.cpp'
        target.write_text(output,encoding='utf-8',newline='\n')
        manifest[name]={'source':str(target),'source_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'baseline_sha256':baseline,'description':later}
    Path('candidates/v4_commitment_manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print('Created exactly two deadline-budget candidates')

if __name__=='__main__':
    main()
