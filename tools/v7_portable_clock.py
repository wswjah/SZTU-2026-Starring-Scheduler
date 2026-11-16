"""Local timing adapter: Windows process CPU; unchanged clock expression elsewhere.

The frozen submission sources are never edited by this module.
"""
from pathlib import Path
import argparse

MARKER = '// V7_PORTABLE_PROCESS_CPU_CLOCK'
HELPER = r'''
// V7_PORTABLE_PROCESS_CPU_CLOCK
#ifdef _WIN32
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
static inline double v7ProcessCpuSeconds() {
    FILETIME created, exited, kernel, user;
    if (!GetProcessTimes(GetCurrentProcess(), &created, &exited, &kernel, &user)) {
        std::fputs("GetProcessTimes failed while reading scheduling CPU budget\n", stderr);
        std::exit(3);
    }
    ULARGE_INTEGER kernelTicks{}, userTicks{};
    kernelTicks.LowPart = kernel.dwLowDateTime;
    kernelTicks.HighPart = kernel.dwHighDateTime;
    userTicks.LowPart = user.dwLowDateTime;
    userTicks.HighPart = user.dwHighDateTime;
    return double(kernelTicks.QuadPart + userTicks.QuadPart) / 10000000.;
}
#define V7_SCHEDULER_USED(scale) (v7ProcessCpuSeconds() * (scale))
#else
#define V7_SCHEDULER_USED(scale) (clock() * (scale) / CLOCKS_PER_SEC)
#endif
'''


def adapt(source: str) -> str:
    if MARKER in source:
        return source
    original = 'clock() * TS / CLOCKS_PER_SEC'
    if source.count(original) != 1:
        raise ValueError('Expected exactly one existing scheduling clock expression')
    include = '#include <unistd.h>'
    if source.count(include) != 1:
        raise ValueError('Expected exactly one unistd include as the insertion anchor')
    source = source.replace(include, include + '\n' + HELPER, 1)
    return source.replace(original, 'V7_SCHEDULER_USED(TS)', 1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    source, target = Path(args.input), Path(args.output)
    if source.resolve() == target.resolve():
        parser.error('Input and output must differ; frozen sources are not modified')
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(adapt(source.read_text(encoding='utf8')), encoding='utf8', newline='\n')
    print(str(target))


if __name__ == '__main__':
    main()
