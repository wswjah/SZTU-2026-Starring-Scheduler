"""Fixed, independent boundary scenarios; check actual generated counts after runs."""
import hashlib
import json
from pathlib import Path
from make_cases import BASE

ROOT = Path(__file__).resolve().parent.parent
COMMON = dict(T=600,D=5,nodes_per_dc=120,racks_per_dc=6,
              mach_per_rack_lo=12,mach_per_rack_hi=12,NT=200,NL=400,NI=120,
              p_noise=10000,p_signal=60,W=60,load=0.85)
PROFILES = {
    'max_topology': dict(seed=914071,log_rate=0.12,audit_rate=5.4),
    'logs_audits': dict(seed=914193,load=0.62,log_rate=0.15,audit_rate=5.6),
    'failures': dict(seed=914327,load=0.85,fail_frac=0.35,precursor_frac=0.8,
                    falsealarm_frac=0.2,link_events=450,quota_events=150,
                    straggler_p=0.18,log_rate=0.13,audit_rate=5.1),
    'overload': dict(seed=914459,load=1.08,log_rate=0.1,audit_rate=4.5),
    'slow_costly': dict(seed=914591,load=0.85,bias_lo=1.3,bias_hi=2.5,
                       sigma=0.5,straggler_p=0.2,log_rate=0.12,audit_rate=5.3),
}

def main():
    directory = ROOT/'cases/stress'
    directory.mkdir(parents=True,exist_ok=True)
    outside = ROOT/'cases/stress_out_of_scope'
    outside.mkdir(parents=True,exist_ok=True)
    manifest=[]
    outside_manifest=[]
    for name,extra in PROFILES.items():
        cfg=BASE|COMMON|extra
        data=''.join(f'{k} {v}\n' for k,v in cfg.items()).encode('ascii')
        destination = outside if name == 'overload' else directory
        target=destination/(name+'.in')
        target.write_bytes(data)
        target_manifest = outside_manifest if name == 'overload' else manifest
        target_manifest.append(dict(file=target.name,parameters=cfg,
                             sha256=hashlib.sha256(data).hexdigest(),
                             intended_scope=('preserved over-limit probe (66156 jobs)' if name == 'overload'
                                             else 'near maximum; actual counts require verification'),
                             maximum_jobs=60000,maximum_audits=3500,
                             maximum_logchars=3_000_000,
                             binary_log_limit_reference=3*1024*1024))
    (directory/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf8')
    (outside/'manifest.json').write_text(json.dumps(outside_manifest,indent=2),encoding='utf8')
    print('Generated',len(manifest),'in-range stress cases and',len(outside_manifest),'preserved over-limit probe')

if __name__=='__main__':
    main()
