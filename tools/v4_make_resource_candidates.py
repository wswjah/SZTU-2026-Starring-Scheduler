"""Two structural priority variants accounting for CPU and memory occupancy."""
from pathlib import Path
import hashlib
import json

def replace(source, old, new, count=1):
    assert source.count(old)==count,(old,source.count(old),count)
    return source.replace(old,new)

def main():
    original=Path('main.cpp').read_text(encoding='utf-8')
    baseline_hash=hashlib.sha256(Path('main.cpp').read_bytes()).hexdigest()
    assert baseline_hash.startswith('21ab'),baseline_hash
    shared=replace(original,
        'struct workflow_state {\n',
        'struct workflow_state {\n    double estimated_memory_work=0, estimated_memory_work_done=0, unfinished_memory=0;\n')
    shared=replace(shared,
        '    array<int, 30> representative_machine;',
        '    array<double,30> resource_memory_capacity{}, resource_free_memory{}, resource_free_cores{};\n    array<int, 30> representative_machine;')
    shared=replace(shared,
        '            flow.estimated_work += (double)job.required_cores * job.estimated_duration;',
        '            flow.estimated_work += (double)job.required_cores * job.estimated_duration;\n            flow.estimated_memory_work += (double)job.required_memory * job.estimated_duration;\n            flow.unfinished_memory += (double)job.required_memory;')
    shared=replace(shared,
        '        flow.estimated_work -= (double)job.required_cores * job.estimated_duration;',
        '        flow.estimated_work -= (double)job.required_cores * job.estimated_duration;\n        flow.estimated_memory_work -= (double)job.required_memory * job.estimated_duration;\n        flow.unfinished_memory -= (double)job.required_memory;')
    shared=replace(shared,
        '        flow.frontier_tail = flow.estimated_work_done = 0;',
        '        flow.frontier_tail = flow.estimated_work_done = 0;\n        flow.estimated_memory_work_done = 0;')
    shared=replace(shared,
        '        rack_online_cores.fill(0);',
        '        rack_online_cores.fill(0);\n        resource_memory_capacity.fill(0);\n        resource_free_memory.fill(0);\n        resource_free_cores.fill(0);')
    shared=replace(shared,
        '                flow.estimated_work_done += job.required_cores * max(0., duration + 1 - left);',
        '                flow.estimated_work_done += job.required_cores * max(0., duration + 1 - left);\n                flow.estimated_memory_work_done += job.required_memory * max(0., duration + 1 - left);')
    shared=replace(shared,
        '            free_cores += machine.free_cores;',
        '            free_cores += machine.free_cores;\n            resource_memory_capacity[rack] += (double)machine.total_memory;\n            resource_free_memory[rack] += (double)machine.free_memory;\n            resource_free_cores[rack] += (double)machine.free_cores;')
    stats='''
#ifdef V4_RESOURCE_STATS
            ++resource_checks;
            resource_affected += resource_work > work*1.001;
#endif
'''
    shared=replace(shared,'struct scheduler {\n','struct scheduler {\n#ifdef V4_RESOURCE_STATS\n    long long resource_checks=0, resource_affected=0;\n#endif\n')
    shared=replace(shared,'            io.flush();\n        }\n    }','''            io.flush();
        }
#ifdef V4_RESOURCE_STATS
        fprintf(stderr,"RESOURCE checks=%lld affected=%lld\\n",resource_checks,resource_affected);
#endif
    }''')
    common='''            double memory_work=max(0.,flow.estimated_memory_work*duration_factor+
                                      flow.unfinished_memory-flow.estimated_memory_work_done);
            double resource_work=work;
            int resource_rack=flow.preferred_rack;
            if(resource_rack>=0) {
                double cpu_capacity=max(1.,min((double)quota_limits[flow.tenant_id],
                                              (double)rack_online_cores[resource_rack]));
                double memory_capacity=max(1.,resource_memory_capacity[resource_rack]);
                RATIO
                resource_work=max(work,memory_work*cpu_per_memory);
            }
'''
    variants={
        'dominant':'double cpu_per_memory=cpu_capacity/memory_capacity;',
        'pressure':'''double cpu_available=max(0.,min((double)quota_headroom[flow.tenant_id],
                                                   resource_free_cores[resource_rack]));
                double cpu_per_memory=(cpu_capacity+cpu_available)/
                                      (memory_capacity+resource_free_memory[resource_rack]);'''
    }
    manifest={}
    for name,ratio in variants.items():
        source=replace(shared,'            double slack = max(0., flow.deadline - current_tick - flow.remaining_time),',common.replace('RATIO',ratio)+stats+'            double slack = max(0., flow.deadline - current_tick - flow.remaining_time),')
        source=replace(source,'profit * urgent * progress / (18. + .8 * work + 6. * flow.remaining_time);','profit * urgent * progress / (18. + .8 * resource_work + 6. * flow.remaining_time);')
        source='// V4 resource priority: '+name+'; no billing or feasibility changes.\n'+source
        target=Path('candidates')/f'v4_resource_{name}.cpp'
        target.write_text(source,encoding='utf-8',newline='\n')
        manifest[name]={'source':str(target),'source_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'baseline_source_sha256':baseline_hash,'description':ratio}
    Path('candidates/v4_resource_manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print('Created exactly two resource-priority variants from',baseline_hash)

if __name__=='__main__':
    main()
