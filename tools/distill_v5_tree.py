"""Mechanically reduce the frozen admission tree to its exact veto predicate.

Right branches use !(float_value <= double_threshold), retaining NaN behavior.
No source file is overwritten and the frozen tree and V4 source are checked.
"""
from pathlib import Path
import argparse
import hashlib
import json
import re

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--metadata',default='research/v4_admission_tree.json')
p.add_argument('--source',default='versions/v4_risk_terminal/main.cpp')
p.add_argument('--output',default='candidates/v5_distilled.cpp')
args=p.parse_args()
meta=json.loads(Path(args.metadata).read_text(encoding='utf8'))
tree=meta['tree'];source=Path(args.source).read_text(encoding='utf8')
if Path(args.source).resolve()==Path(args.output).resolve():p.error('Source must be preserved')
start=source.index('static double v4_admission_score(')
end=source.index('\nstruct network_state',start)
original=source[start:end].strip()
for cpp,key in [('f','feature'),('l','left'),('r','right'),('t','threshold'),('v','value')]:
    match=re.search(r'static const (?:short|double) '+cpp+r'\[\]=\{([^}]+)\};',original)
    assert match,cpp
    assert [float(x) for x in match.group(1).split(',')]==[float(x) for x in tree[key]],key

paths=[]
def visit(node,path):
    feature=tree['feature'][node]
    if feature<0:
        paths.append(dict(leaf=node,score=tree['value'][node],reject=tree['value'][node]<.05,path=path))
        return
    step=dict(node=node,feature=feature,name=meta['features'][feature],threshold=tree['threshold'][node])
    visit(tree['left'][node],path+[step|{'take_left':True}])
    visit(tree['right'][node],path+[step|{'take_left':False}])
visit(0,[])
rejected=[x for x in paths if x['reject']]
assert len(rejected)==1
path=rejected[0]['path']
assert [x['feature'] for x in path]==[2,3,14]
names={2:'cost_ratio',3:'duration_ratio',14:'window_fraction'}
def condition(step):
    comparison=f"{names[step['feature']]} <= {format(step['threshold'],'.17g')}"
    return '('+comparison+')' if step['take_left'] else '!('+comparison+')'
predicate=' &&\n                '.join(condition(x) for x in path)
replacement='// Exact .05 admission veto distilled from the frozen tree; all right branches retain NaN semantics.\n'
source=source[:start]+replacement+source[end:]
old='''            float x[15]{};
            // The frozen tree uses only these three pre-admission features.
            x[2]=float(flow.plan_cost/max<i64>(1,flow.value));
            x[3]=float(flow.plan_duration/horizon);
            x[14]=float(horizon/total_ticks);
            if(v4_admission_score(x)<0.05)return 0;'''
new='''            const float cost_ratio=float(flow.plan_cost/max<i64>(1,flow.value));
            const float duration_ratio=float(flow.plan_duration/horizon);
            const float window_fraction=float(horizon/total_ticks);
            if('''+predicate+''')return 0;'''
assert source.count(old)==1
source=source.replace(old,new,1)
assert 'v4_admission_score' not in source
Path(args.output).write_text(source,encoding='utf8',newline='\n')
manifest=dict(source=args.source,source_sha256=hashlib.sha256(Path(args.source).read_bytes()).hexdigest(),
              metadata=args.metadata,metadata_sha256=hashlib.sha256(Path(args.metadata).read_bytes()).hexdigest(),
              output=args.output,output_sha256=hashlib.sha256(Path(args.output).read_bytes()).hexdigest(),
              score_cutoff=.05,rejection_leaf=rejected[0],all_leaf_paths=paths,
              predicate=predicate,float32_conversion_retained=True,nan_right_branch_semantics_retained=True)
Path('results/v5_distillation').mkdir(parents=True,exist_ok=True)
Path('results/v5_distillation/manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf8')

# Reuse the deployed tree implementation verbatim as the test oracle.
test='''#include <bits/stdc++.h>
using namespace std;
'''+original+'''
static bool distilled(float cost_ratio,float duration_ratio,float window_fraction) {
    return '''+predicate+''';
}
static int leaf_for(const float* x) {
    static const short f[]={'''+','.join(map(str,tree['feature']))+'''};
    static const short l[]={'''+','.join(map(str,tree['left']))+'''};
    static const short r[]={'''+','.join(map(str,tree['right']))+'''};
    static const double t[]={'''+','.join(format(x,'.17g') for x in tree['threshold'])+'''};
    int n=0;while(f[n]>=0)n=x[f[n]]<=t[n]?l[n]:r[n];return n;
}
int main() {
    array<vector<float>,3> values;
    for(auto& v:values) v={-numeric_limits<float>::infinity(),-10.f,-1.f,-0.f,0.f,1.f,10.f,
        numeric_limits<float>::infinity(),numeric_limits<float>::quiet_NaN(),numeric_limits<float>::signaling_NaN()};
'''
for pos,feature in enumerate([2,3,14]):
    for step in [dict(threshold=t) for f,t in zip(tree['feature'],tree['threshold']) if f==feature]:
        test+='''    {float x=float('''+format(step['threshold'],'.17g')+''');
        values['''+str(pos)+'''].push_back(x);
        for(int i=0;i<4;++i)values['''+str(pos)+'''].push_back(x=nextafterf(x,-numeric_limits<float>::infinity()));
        x=float('''+format(step['threshold'],'.17g')+''');
        for(int i=0;i<4;++i)values['''+str(pos)+'''].push_back(x=nextafterf(x,numeric_limits<float>::infinity()));}
'''
test+='''    uint64_t checks=0;array<bool,15> visited{};
    auto check=[&](float a,float b,float c){
        float x[15]{};x[2]=a;x[3]=b;x[14]=c;
        bool reference=v4_admission_score(x)<.05,actual=distilled(a,b,c);
        if(reference!=actual){cerr<<"Mismatch: "<<a<<' '<<b<<' '<<c<<'\\n';exit(1);}
        visited[leaf_for(x)]=true;++checks;
    };
    for(float a:values[0])for(float b:values[1])for(float c:values[2])check(a,b,c);
    uint64_t boundary=checks;
    mt19937_64 rng(0x579bcdefULL);
    auto random_float=[&](){uint32_t bits=uint32_t(rng());float value;memcpy(&value,&bits,4);return value;};
    for(int i=0;i<2000000;++i) check(random_float(),random_float(),random_float());
    for(int i=0;i<1000000;++i) {
        double a=double(int64_t(rng()))/double(1ULL<<60);
        double b=double(int64_t(rng()))/double(1ULL<<60);
        double c=double(int64_t(rng()))/double(1ULL<<60);
        check(float(a),float(b),float(c));
    }
    int leaves=0;
'''
for leaf in [x['leaf'] for x in paths]:test+=f'    if(!visited[{leaf}]){{cerr<<"Unvisited leaf {leaf}\\n";return 2;}}++leaves;\n'
test+='''    cout<<"{\\"checks\\":"<<checks<<",\\"boundary_combinations\\":"<<boundary
        <<",\\"visited_leaves\\":"<<leaves<<",\\"all_equal\\":true,\\"includes_nan_and_infinity\\":true}\\n";
}
'''
Path('tools/v5_distillation_test.cpp').write_text(test,encoding='utf8',newline='\n')
print(json.dumps(dict(rejection_leaf=rejected[0]['leaf'],predicate=predicate,generated_source=args.output),ensure_ascii=False))
