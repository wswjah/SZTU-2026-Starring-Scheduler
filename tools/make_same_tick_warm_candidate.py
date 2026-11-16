"""Isolate same-tick image warming on the fixed 85-point source.

This candidate keeps the existing selection and admission decisions. Only after
one machine has already been selected does it optionally emit RUN/KILL/RUN.
The extra network fee must be no larger than the saved preparation CPU fee.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
source = ROOT / "versions/v3_aggressive/main.cpp"
output = ROOT / "candidates/v5_same_tick_warm.cpp"
code = source.read_text(encoding="utf8")
marker = "    void run() {\n        initialize();"
assert code.count(marker) == 1
code = code.replace(marker, "    long long warm_count=0, warm_saved_ticks=0;\n"
                    "    i128 warm_extra_network=0, warm_saved_cpu=0;\n\n" + marker)
marker = """        auto& machine = machines[best_machine];
        pull_image_layers(machine.cache, racks[machine.rack_id].cache, image.layers);
        ++environment_version;"""
replacement = """        auto& machine = machines[best_machine];
        const auto& best_route = route[machine.rack_id];
        i128 saved_cpu = (i128)(best_prepare_time-best_route.transfer_time) *
                         job.required_cores * cpu_prices[racks[machine.rack_id].datacenter_id];
        // Sufficient, conservative conditions: the complete image stays on this
        // machine; no event occurs inside this command batch; repeated input
        // transfer costs no more than the preparation CPU fee it removes.
        bool warm = image.total_bytes<=machine.cache.capacity &&
                    best_prepare_time>best_route.transfer_time &&
                    best_route.transfer_fee<=saved_cpu &&
                    commands_sent<=command_limit-3;
        pull_image_layers(machine.cache, racks[machine.rack_id].cache, image.layers);
        if (warm) {
            // The first RUN's immediate bill is permanent. Its rate and quota
            // changes cancel at this same tick, and it changes no DAG state.
            update_account(job,best_machine,1,best_fee);
            update_account(job,best_machine,-1);
            emit_command("RUN ",job.job_id,best_machine);
            emit_command("KILL ",job.job_id);
            ++warm_count;
            warm_saved_ticks+=best_prepare_time-best_route.transfer_time;
            warm_extra_network+=best_route.transfer_fee;
            warm_saved_cpu+=saved_cpu;
            best_prepare_time=best_route.transfer_time;
            best_fee=best_route.transfer_fee;
            // Repeat the actual second RUN's LRU touches. All image layers fit,
            // so these are machine-cache hits and cause no registry/rack pulls.
            auto second=pull_image_layers(machine.cache,racks[machine.rack_id].cache,image.layers);
            assert(second.registry_bytes==0 && second.rack_bytes==0);
        }
        ++environment_version;"""
assert code.count(marker) == 1
code = code.replace(marker, replacement)
marker = """            io.flush();
        }
    }
};"""
replacement = """            io.flush();
        }
        cerr << "WARM count=" << warm_count << " saved_preparation=" << warm_saved_ticks
             << " extra_network=" << (long long)warm_extra_network
             << " saved_cpu=" << (long long)warm_saved_cpu << '\\n';
    }
};"""
assert code.count(marker) == 1
code = code.replace(marker, replacement)
output.write_text(code, encoding="utf8", newline="\n")
print(output)
