"""Create an output-preserving counting/sampling build of frozen main.cpp."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
code = (ROOT/'main.cpp').read_text(encoding='utf8')

instrument = r'''
struct profile_measurement { unsigned long long calls = 0, nanos = 0, samples = 0; };
static profile_measurement profile_preview, profile_plan, profile_schedule;
static unsigned long long profile_copies = 0, profile_memo_hits = 0;
struct profile_sample {
    profile_measurement& value;
    bool sample;
    std::chrono::steady_clock::time_point start;
    profile_sample(profile_measurement& entry, unsigned mask = 63) : value(entry), sample((entry.calls++ & mask) == 0) {
        if (sample) start = std::chrono::steady_clock::now();
    }
    ~profile_sample() {
        if (sample) {
            value.nanos += std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::steady_clock::now()-start).count();
            ++value.samples;
        }
    }
};
'''
code = code.replace('struct network_state {', instrument+'\nstruct network_state {',1)
code = code.replace('layer_cache machine_copy = machine_cache, rack_copy = rack_cache;',
                    '++profile_copies;\n            layer_cache machine_copy = machine_cache, rack_copy = rack_cache;',1)
code = code.replace('vector<image_hint> image_hints;',
                    'vector<unsigned long long> profile_seen;\n    array<unsigned long long,30> profile_versions{};\n    vector<image_hint> image_hints;',1)
code = code.replace('image_hints.resize(rack_count * image_count);',
                    'image_hints.resize(rack_count * image_count);\n        profile_seen.resize(machine_count * image_count);',1)
code = code.replace('machine.cache.clear();',
                    'machine.cache.clear();\n            ++profile_versions[machine.rack_id];',1)
code = code.replace('pull_image_layers(machine.cache, racks[machine.rack_id].cache, image.layers);',
                    'pull_image_layers(machine.cache, racks[machine.rack_id].cache, image.layers);\n        ++profile_versions[machine.rack_id];',1)
code = code.replace('''    pull_amounts preview_job_image(int machine_id, job_state& job) {
        auto& machine = machines[machine_id];''', '''    pull_amounts preview_job_image(int machine_id, job_state& job) {
        profile_sample measurement(profile_preview);
        auto& machine = machines[machine_id];
        auto& seen = profile_seen[machine_id * image_count + job.image_id];
        unsigned long long version = profile_versions[machine.rack_id] + 1;
        profile_memo_hits += seen == version;
        seen = version;''',1)
code = code.replace('''                      int machine = -1) {
        if (machine < 0)''','''                      int machine = -1) {
        profile_sample measurement(profile_plan);
        if (machine < 0)''',1)
code = code.replace('''    void schedule() {
        online_machines.clear();''', '''    void schedule() {
        profile_sample measurement(profile_schedule, 0);
        online_machines.clear();''',1)
code = code.replace('solver.run();', r'''solver.run();
    auto dump = [](const char* name, profile_measurement& value) {
        std::cerr << "PROFILE," << name << ",calls=" << value.calls << ",samples=" << value.samples
                  << ",estimated_ns=" << (value.samples ? value.nanos * value.calls / value.samples : 0) << '\n';
    };
    dump("preview",profile_preview); dump("plan",profile_plan); dump("schedule",profile_schedule);
    std::cerr << "PROFILE,copies=" << profile_copies << ",memo_hits=" << profile_memo_hits << '\n';''',1)
destination=ROOT/'candidates/v2_profile.cpp'
destination.write_text(code,encoding='utf8')
print(destination)
