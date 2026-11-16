"""Two bounded terminal-flow experiments from the frozen official 96 source."""
from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parent.parent
BASE = ROOT / 'versions/v6_attributed96/main.cpp'
SHARED = r'''
// Estimate only the final pending job. Deterministic startup is quoted exactly
// on private LRU copies; runtime remains the existing five-scenario forecast.
struct TerminalQuote {
    int machine = -1, warm = 0;
    double revenue = 0, cost = 0, duration = 0, runtime = 0;
};
pair<ll,ll> terminalPull(Cache& mc, Cache& rc, int image) {
    ll reg = 0, rack = 0;
    for (int l : imageLayers[image]) {
        if (cacheHit(mc,l)) continue;
        if (cacheHit(rc,l)) rack += layerSize[l];
        else reg += layerSize[l], cachePut(rc,l);
        cachePut(mc,l);
    }
    return {reg,rack};
}
double terminalRevenue(Flow& w, double prep, double est) {
    static const double scenarios[5] = {-1,-.5,0,1,2};
    double result = 0;
    for (double sc : scenarios) {
        double finish = now + prep + max(1.0,est*(1+SP*sc));
        if (finish <= T) result += revenueAt(w,finish)/5;
    }
    return result;
}
double terminalMeanRuntime(double est) {
    static const double scenarios[5] = {-1,-.5,0,1,2};
    double result = 0;
    for (double sc : scenarios) result += max(1.0,est*(1+SP*sc))/5;
    return result;
}
TerminalQuote terminalQuote(int ji) {
    TerminalQuote result;
    Job& j = jobs[ji];
    Flow& w = flows[j.wf];
    if (j.state || j.need || commandsUsed >= COMMAND_LIMIT) return result;
    for (int a=w.tenant; a>=0; a=tenPar[a])
        if (tenUsed[a]+j.c>tenQuota[a]) return result;
    double est=max(1.0,j.e*tenFactor(w.tenant));
    double mean=terminalMeanRuntime(est), best=0;
    F(r,R) {
        ll tt,tf,aw;
        if (!transferCost(j,r,tt,tf,aw) || tf>=w.v) continue;
        double cp=j.c*price[rackDc[r]];
        if (tf+cp*mean>=w.v) continue;
        for (int x:rackMachs[r]) {
            if (!machUp[x] || freeCpu[x]<j.c || freeMem[x]<j.m ||
                virtCpu[x]<j.c || virtMem[x]<j.m) continue;
            Cache mc=machCache[x],rc=rackCache[r];
            auto first=terminalPull(mc,rc,j.img);
            ll prep=max(tt,(first.first+Breg-1)/Breg+(first.second+Brack-1)/Brack);
            auto consider=[&](int warm,ll preparation,double fee) {
                if (commandsUsed+(warm?3:1)>COMMAND_LIMIT) return;
                double rev=terminalRevenue(w,preparation,est);
                double cost=fee+cp*(preparation+mean);
                if (rev-cost>best) {
                    best=rev-cost;
                    result={x,warm,rev,cost,double(preparation)+mean,est};
                }
            };
            consider(0,prep,double(tf)+double(first.first)*Ureg);
            if (PW>0 && commandsUsed+3<=COMMAND_LIMIT) {
                auto second=terminalPull(mc,rc,j.img);
                ll prep2=max(tt,(second.first+Breg-1)/Breg+(second.second+Brack-1)/Brack);
                consider(1,prep2,2.*tf+(double(first.first)+second.first)*Ureg);
            }
        }
    }
    return result;
}
bool startTerminalChoice(int ji, TerminalQuote q) {
    if (q.machine<0) return false;
    Job& j=jobs[ji]; Flow& w=flows[j.wf];
    if (commandsUsed+(q.warm?3:1)>COMMAND_LIMIT) return false;
    int rdy=j.ready; ll fee0=0;
    if (q.warm) {
        runJob(ji,q.machine); fee0=runFee;
        killNow(ji); j.ready=rdy;
    }
    runJob(ji,q.machine); runFee+=fee0;
    w.started=w.dirty=1;
    overhead=overhead*.98+.02*max(0.0,j.prep-j.xt);
    ovWait=ovWait*.98+.02*min(WCAP,double(now-j.ready));
    feeAvg=feeAvg*.98+.02*(runFee-j.xf);
    jobEnd[ji]=now+j.prep+q.runtime;
    occupy(q.machine,ji,jobEnd[ji]);
    return true;
}
vector<char> terminalRescue;
'''

RUNNING = r'''
// A running terminal job has already survived to its elapsed compute time.
// Retain only runtime scenarios consistent with this visible lower bound.
bool terminalRunningValue(int ji, double& rev, double& cost, double& work) {
    Job& j=jobs[ji]; Flow& w=flows[j.wf];
    if (j.state!=1) return false;
    static const double scenarios[5]={-1,-.5,0,1,2};
    double est=max(1.0,j.e*tenFactor(w.tenant));
    double elapsed=max(0,now-j.t0-j.prep),prep=max(0,j.t0+j.prep-now);
    double count=0,remaining=0;
    rev=0;
    for (double sc:scenarios) {
        double runtime=max(1.0,est*(1+SP*sc));
        if (runtime<=elapsed) continue;
        double left=prep+runtime-elapsed,finish=now+left;
        if (finish<=T) rev+=revenueAt(w,finish);
        remaining+=left; count++;
    }
    if (!count) return false; // Keep the baseline straggler tail out of support.
    rev/=count; remaining/=count;
    work=j.c*remaining;
    cost=work*price[rackDc[machRack[j.mach]]];
    return true;
}
'''


def make(mode,prefix='v7_terminal'):
    source=BASE.read_text(encoding='utf8')
    def replace(old,new):
        nonlocal source
        assert source.count(old)==1,old
        source=source.replace(old,new)
    replace('void tryPlace(int ji) {',SHARED+(RUNNING if mode=='conditioned' else '')+'\nvoid tryPlace(int ji) {')
    replace('    Flow& w = flows[j.wf];\n    for (int a = w.tenant;',
            '''    Flow& w = flows[j.wf];
    if (j.wf<(int)terminalRescue.size() && terminalRescue[j.wf]) {
        startTerminalChoice(ji,terminalQuote(ji));
        return;
    }
    for (int a = w.tenant;''')
    replace('    vector<pair<double, int>> order;','''    vector<pair<double, int>> order;
    terminalRescue.resize(flows.size(),0);''')
    injection='''            if (!(rev>cost*KILLK) && w.started && w.left==1) {
                int last=-1;
                F(i,w.n) if (jobs[w.first+i].state<2) last=w.first+i;
                if (last>=0 && jobs[last].state==0 && !jobs[last].need) {
                    auto quote=terminalQuote(last);
                    if (quote.machine>=0) {
                        rev=quote.revenue; cost=quote.cost;
                        rem=quote.duration;
                        work=jobs[last].c*quote.duration;
                        terminalRescue[wi]=1;
                    }
                }
'''
    if mode=='conditioned':
        injection+='''                else if (last>=0 && jobs[last].state==1) {
                    double nr,nc,nw;
                    if (terminalRunningValue(last,nr,nc,nw)) {
                        rev=nr; cost=nc; work=nw; rem=nw/jobs[last].c;
                    }
                }
'''
    injection+='''            }
'''
    replace('            if (rev > cost * (w.started ? KILLK : 1 + ADM)) {',
            injection+'            if (rev > cost * (w.started ? KILLK : 1 + ADM)) {')
    # Reset only on a full re-estimate; a rescued flow retains its explicit
    # execution gate during the normal six-tick estimate reuse interval.
    replace('            double rem, work, cost, rev = 0;','''            double rem, work, cost, rev = 0;
            terminalRescue[wi]=0;''')
    name=prefix+'_'+mode
    path=ROOT/'candidates'/f'{name}.cpp'
    data=source.encode('utf8');path.write_bytes(data)
    return {'variant':name,'source':str(path),'sha256':hashlib.sha256(data).hexdigest(),
            'base_sha256':hashlib.sha256(BASE.read_bytes()).hexdigest()}


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input',type=Path,default=BASE)
    p.add_argument('--mode',choices=['rescue','conditioned','both'],default='both')
    p.add_argument('--prefix',default='v7_terminal')
    args=p.parse_args()
    BASE=args.input.resolve()
    modes=['rescue','conditioned'] if args.mode=='both' else [args.mode]
    items=[make(mode,args.prefix) for mode in modes]
    (ROOT/'research/v7_terminal_manifest.json').write_text(json.dumps(items,indent=2),encoding='utf8')
    print(json.dumps(items))
