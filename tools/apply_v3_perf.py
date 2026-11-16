"""Copy the two validated, strategy-independent V3 performance primitives.

The input is never overwritten. Typical use:
python tools/apply_v3_perf.py --input candidates/policy.cpp --output candidates/policy_fast.cpp
"""
import argparse
from pathlib import Path

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--input', required=True)
p.add_argument('--output', required=True)
args = p.parse_args()
source_path, output_path = Path(args.input), Path(args.output)
if source_path.resolve() == output_path.resolve():
    p.error('Input and output must differ')
source = source_path.read_text(encoding='utf-8')
template = (Path(__file__).resolve().parent.parent/'candidates/v3_perf_combo.cpp').read_text(encoding='utf-8')
if 'struct preview_lru_queue' in source:
    p.error('Input already has the queue implementation')

begin, end = source.index('struct network_state {'), source.index('\nstruct layer_cache {')
t_begin, t_end = template.index('struct network_state {'), template.index('\nstruct layer_cache {')
source = source[:begin] + template[t_begin:t_end] + source[end:]
begin, end = source.index('inline pull_amounts preview_image_pull('), source.index('\nstruct log_tracker')
t_begin, t_end = template.index('// Exact preview through a lazy queue'), template.index('\nstruct log_tracker')
source = source[:begin] + template[t_begin:t_end] + source[end:]
output_path.parent.mkdir(parents=True, exist_ok=True)
output_path.write_text(source, encoding='utf-8', newline='\n')
print(f'Wrote {output_path}; source preserved')
