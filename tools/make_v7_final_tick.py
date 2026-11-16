"""Known-horizon last-tick cleanup on the portable process-CPU adapter."""
from pathlib import Path
import hashlib
import json
from v7_portable_clock import adapt

ROOT=Path(__file__).resolve().parent.parent
CLEANUP='''
    // DONE has already been consumed. Nothing newly run or still unfinished
    // at the last tick can produce revenue after this known horizon.
    if (now == T) {
        F(x,M) {
            while (!machJobs[x].empty() && commandsUsed < COMMAND_LIMIT)
                killNow(machJobs[x].back());
            if (commandsUsed == COMMAND_LIMIT) break;
        }
        return;
    }'''


def apply(source):
    source=adapt(source)
    if CLEANUP in source:
        return source
    anchor='''void schedule() {
    drainDeferredKills();'''
    assert source.count(anchor)==1
    return source.replace(anchor,anchor+CLEANUP)


def main():
    import argparse
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input',type=Path,default=ROOT/'versions/v6_attributed96/main.cpp')
    p.add_argument('--output',type=Path,default=ROOT/'candidates/v7_final_tick.cpp')
    p.add_argument('--manifest',type=Path,default=ROOT/'research/v7_final_tick_manifest.json')
    args=p.parse_args()
    source=apply(args.input.read_text(encoding='utf8'))
    args.output.write_text(source,encoding='utf8',newline='\n')
    args.manifest.write_text(json.dumps({
        'base':str(args.input),'base_sha256':hashlib.sha256(args.input.read_bytes()).hexdigest(),
        'source':str(args.output),'source_sha256':hashlib.sha256(args.output.read_bytes()).hexdigest(),
        'portable_clock_adapter':True,'changes':['only now==T cleanup before CPU insurance'],
        'official_submission_sent':False},indent=2),encoding='utf8')
    print(str(args.output))


if __name__=='__main__':
    main()
