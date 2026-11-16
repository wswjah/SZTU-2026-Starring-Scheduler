"""Build an exact-output memoization candidate without changing frozen main.cpp."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
source=(ROOT/'main.cpp').read_text(encoding='utf8')

def replace_once(old,new):
    global source
    assert source.count(old)==1,(old,source.count(old))
    source=source.replace(old,new,1)

replace_once('struct transfer_estimate {', '''struct exact_pull_preview {
    unsigned cache_epoch = 0;
    pull_amounts amounts{};
};

struct transfer_estimate {''')
replace_once('    vector<image_hint> image_hints;', '''    vector<exact_pull_preview> exact_pull_previews;
    array<unsigned, 30> pull_cache_epochs{};
    vector<image_hint> image_hints;''')
replace_once('        image_hints.resize(rack_count * image_count);', '''        image_hints.resize(rack_count * image_count);
        exact_pull_previews.resize(machine_count * image_count);''')
replace_once('            machine.cache.clear();', '''            machine.cache.clear();
            ++pull_cache_epochs[machine.rack_id];''')
replace_once('''        pull_image_layers(machine.cache, racks[machine.rack_id].cache, image.layers);
        ++environment_version;''', '''        pull_image_layers(machine.cache, racks[machine.rack_id].cache, image.layers);
        ++pull_cache_epochs[machine.rack_id];
        ++environment_version;''')
replace_once('''    pull_amounts preview_job_image(int machine_id, job_state& job) {
        auto& machine = machines[machine_id];
        return preview_image_pull(machine.cache, racks[machine.rack_id].cache,
                                  images[job.image_id].layers);
    }''', '''    pull_amounts preview_job_image(int machine_id, job_state& job) {
        auto& machine = machines[machine_id];
        auto& saved = exact_pull_previews[machine_id * image_count + job.image_id];
        unsigned epoch = pull_cache_epochs[machine.rack_id] + 1;
        if (saved.cache_epoch == epoch)
            return saved.amounts;
        saved.amounts = preview_image_pull(machine.cache, racks[machine.rack_id].cache,
                                          images[job.image_id].layers);
        saved.cache_epoch = epoch;
        return saved.amounts;
    }''')
destination=ROOT/'candidates/v2_fast.cpp'
destination.write_text(source,encoding='utf8')
print(destination)
