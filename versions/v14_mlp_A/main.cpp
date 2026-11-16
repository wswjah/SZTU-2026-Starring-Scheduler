// Build:  g++ -std=c++11 -O2 sol.cpp            (add -DDBG for diagnostics on stderr)
// Submit: python3 minify.py sol.cpp submit.cpp --names   (same program, < 16384 bytes)
//
// Overview
//  * Audit: every state the questions ask about is maintained incrementally - tenant bills
//    (fixed part + rate * time), quota head-room along the tenant tree with an undo stack,
//    rack-to-rack shortest paths (recomputed only for the source racks a link event can affect),
//    LRU layer caches of machines and racks, alarm scores (Huffman decoding + Aho-Corasick),
//    and the slack of a job in the DAG of its workflow.
//  * Duration model: real / estimated duration is learned per tenant from finished jobs and from
//    running jobs that are already overdue, shrunk towards the pooled ratio.
//  * Workflow value: remaining critical path (durations, preparation, queueing) and remaining cost
//    are estimated; the expected revenue is averaged over five finish-time scenarios. A flow is
//    started only if that beats its remaining cost, and a started flow is killed once it no longer
//    does. Flows are served in order of expected profit per core-tick (started flows first,
//    flows with little slack first).
//  * Placement: for a ready job the racks are ranked by transfer fee + delay + run cost, plus a
//    one-step look-ahead (what the successors will pay to gather their inputs); on the best racks
//    every machine is priced including image pulls and the wait for a busy machine (a per-machine
//    timeline of expected releases, so that a job may reserve a machine instead of taking a bad one).
//  * A CPU-time insurance degrades the scheduler gradually if the judge machine is slow.
#include <bits/stdc++.h>
#include <unistd.h>

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

using namespace std;
typedef long long ll;
#define F(i, n) for (int i = 0; i < (int)(n); i++)

// ---------------- fast input ----------------
char inbuf[1 << 16], tok[1 << 23];
int inpos, inlen;
int getch() {
    if (inpos == inlen) {
        inlen = read(0, inbuf, sizeof inbuf);
        inpos = 0;
        if (inlen <= 0) return -1;
    }
    return inbuf[inpos++];
}
int readTok() {
    int c = getch(), n = 0;
    while (c == ' ' || c == '\n' || c == '\r') c = getch();
    while (c > ' ') tok[n++] = c, c = getch();
    tok[n] = 0;
    return n;
}
ll readInt() {
    int c=getch();
    while(c>=0&&c<=' ') c=getch();
    bool negative=c=='-';
    if(c=='-'||c=='+') c=getch();
    ll value=0;
    if(negative) {
        while(unsigned(c-'0')<10) value=value*10-(c-'0'),c=getch();
    } else {
        while(unsigned(c-'0')<10) value=value*10+(c-'0'),c=getch();
    }
    return value;
}

// ---------------- world state ----------------
int T, D, N, R, M, K, L, I, P, W, E, now;
ll Breg, Brack, Bnet, Ureg, Unet, price[8];

struct Cache {
    vector<int> q;  // LRU order, front = least recently used
    ll cap, sum;
    int ver;  // bumped whenever the contents change
    char in[400];
};
Cache rackCache[30], machCache[360];
int rackDc[30], rackNode[30];
int machRack[360], machCpu[360], machMem[360], freeCpu[360], freeMem[360], machUp[360];
vector<int> machJobs[360];
ll alarmAt[360][602];

int edgeU[1000], edgeV[1000], edgeW[1000], edgeUp[1000], dcDown[8], netDirty = 1;
vector<int> adj[600];
ll rackDist[30][30];

int tenPar[200], tenOrder[200];
ll tenQuota[200], tenUsed[200], tenFix[200], tenRate[200], tenRateStart[200];
double tenDur[602], tenEst[602];
vector<pair<int, ll>> undoStack;

int layerSize[400];
vector<int> imageLayers[120];
int huffChild[20][2], huffRoot;
vector<array<int, 8>> acGo;
vector<ll> acVal;

struct Job {
    int id, wf, c, m, e, img, s, zin, zout, state, mach, t0, prep, outRack, need, ready;
    int resM, resAt, resT;  // cached reservation: machine, tick it was computed, tick it expires
    double resEnd, xt, xf;  // xt / xf: time / fee to bring the external input to the flow's home rack
    vector<int> pre, suc;
};
struct Flow {
    int id, tenant, dl, arrive, first, n, left, dead, endT, started, home, dirty, adm;
    double key;
    ll v;
};
vector<Job> jobs;
vector<Flow> flows;
unordered_map<int, int> jobIndex;
string outbuf;
constexpr int COMMAND_LIMIT = 20000;
int commandsUsed;
vector<int> deferredKills;
size_t deferredHead;
ll runFee;
int freedAt[360];

struct V13ModelForecast {double rem=0,work=0,cost=0,rev=0;int tick=0,roots=0;};
vector<V13ModelForecast> v13ModelForecasts;


// ---------------- caches ----------------
bool cacheHit(Cache& c, int l) {
    if (!c.in[l]) return 0;
    c.q.erase(find(c.q.begin(), c.q.end(), l));
    c.q.push_back(l);
    return 1;
}
void cachePut(Cache& c, int l) {
    c.q.push_back(l);
    c.in[l] = 1, c.ver++;
    c.sum += layerSize[l];
    while (c.sum > c.cap) {
        int o = c.q[0];
        c.sum -= layerSize[o];
        c.in[o] = 0;
        c.q.erase(c.q.begin());
    }
}

// ---------------- network ----------------
// nodeDist[a][v]: distance from rack a's node to node v. A link event only invalidates the rows
// (source racks) whose distances it can change.
ll nodeDist[30][600];
char rowDirty[30];
void recomputeNet() {
    static int q[1024];
    static char in[600];
    int per = N / D;
    F(a, R) if (rowDirty[a]) {
        ll* d = nodeDist[a];
        F(i, N) d[i] = 1e18;
        int s = rackNode[a], h = 0, t = 0;
        if (!dcDown[s / per]) d[s] = 0, q[t++] = s;
        while (h != t) {  // queue-based Bellman-Ford; the graph is small and sparse
            int u = q[h++ & 1023];
            in[u] = 0;
            for (int e : adj[u]) {
                int v = edgeU[e] ^ edgeV[e] ^ u;
                if (edgeUp[e] && !dcDown[v / per] && d[u] + edgeW[e] < d[v]) {
                    d[v] = d[u] + edgeW[e];
                    if (!in[v]) in[v] = 1, q[t++ & 1023] = v;
                }
            }
        }
        F(b, R) rackDist[a][b] = d[rackNode[b]] > 9e17 ? -1 : d[rackNode[b]];
        rowDirty[a] = 0;
    }
    netDirty = 0;
}

// ---------------- tunables ----------------
#define PRM(n, d) const double n = d
PRM(TH0, 4);      // base value of one tick of delay, per core
PRM(MG, 1);       // lateness uncertainty margin as a fraction of remaining path
PRM(DEADK, 0.6);  // optimism factor before declaring a flow dead
PRM(SB, 2);       // priority boost of already started flows
PRM(PEN, 1);      // look-ahead penalty for leaving the predecessors' rack
PRM(RESV, 30);    // longest wait (ticks) worth a reservation
PRM(OVK, 1);      // weight of the learned per-job overhead
PRM(SP, 0.4);     // spread of the finish-time scenarios
PRM(KILLK, 1.1);    // kill a started flow when expected revenue < KILLK * remaining cost
PRM(ADM, 0.05);      // required profit margin (fraction of cost) to start a flow
PRM(THR, 6);      // waiting flows are re-evaluated every THR ticks
PRM(OD, 0.25);    // an overdue job is expected to need OD * (its run time so far) more ticks

PRM(WK, 0);       // weight of the learned queueing delay per job
PRM(WCAP, 12);    // cap on one observation of queueing delay
PRM(RT0, 3);      // ticks before a job without a usable machine is examined again
PRM(RT1, 4);      // longest life of a cached reservation
PRM(RTK, 0.5);    // cached reservation lives RTK * (expected wait)
PRM(BB, 0.03);    // growth of the remaining-time estimate with the number of unfinished jobs
PRM(SL, 1.25);       // priority discount for flows with plenty of slack
PRM(RK, 16);      // number of candidate racks examined per job
PRM(LAK, 1);      // weight of the one-step look-ahead in rack selection
PRM(GU, 1);       // 1: guess the rack of unplaced predecessors in the look-ahead
PRM(TS, 1);
PRM(F0, 1.5);     // prior real/estimated duration ratio
PRM(W0, 100);     // weight of that prior (in estimated ticks)
PRM(W1, 30);      // weight of the pooled ratio in a tenant's ratio
PRM(PW, 1);       // 1: warm the caches with RUN + KILL in the same tick before the real RUN
PRM(HS, 1);       // 1: the end of the horizon is applied to each finish-time scenario separately
PRM(HZ, 30);      // tolerance (ticks) of that test
PRM(RF, 1);       // weight of the registry fee when racks are ranked

// ---------------- job lifecycle ----------------
// real/estimated duration ratio of a tenant. Evidence: finished jobs, plus running jobs that are
// already overdue (their run time so far is a lower bound). A tenant's ratio is shrunk towards the
// pooled ratio, which itself starts from a pessimistic prior.
double allDur, allEst, allRunD, allRunE, tenRunD[602], tenRunE[602], tenF[602];
double tenFactor(int o) { return tenF[o]; }
void updateFactors() {
    double pool = (allDur + allRunD + W0 * F0) / (allEst + allRunE + W0);
    F(o, K) tenF[o] = (tenDur[o] + tenRunD[o] + W1 * pool) / (tenEst[o] + tenRunE[o] + W1);
}

// release resources of a running job at current tick
void release(int ji) {
    Job& j = jobs[ji];
    int x = j.mach, o = flows[j.wf].tenant;
    ll cp = j.c * price[rackDc[machRack[x]]];
    freeCpu[x] += j.c;
    freeMem[x] += j.m;
    freedAt[x] = now;
    flows[j.wf].dirty = 1;
    machJobs[x].erase(find(machJobs[x].begin(), machJobs[x].end(), ji));
    tenFix[o] += cp * (now - j.t0);
    tenRate[o] -= cp;
    tenRateStart[o] -= cp * j.t0;
    for (int a = o; a >= 0; a = tenPar[a]) tenUsed[a] -= j.c;
    j.state = 0;
    j.ready = now, j.resT = 0;
}

// Stop requests beyond the current command budget survive to the next tick.
// Events may finish or interrupt a queued job before then; those requests expire.
void killNow(int ji) {
    assert(commandsUsed < COMMAND_LIMIT);
    outbuf += "KILL " + to_string(jobs[ji].id) + "\n";
    ++commandsUsed;
    release(ji);
}
void stopOrDefer(int ji) {
    if (jobs[ji].state != 1) return;
    if (commandsUsed < COMMAND_LIMIT) killNow(ji);
    else deferredKills.push_back(ji);
}
void drainDeferredKills() {
    while (deferredHead < deferredKills.size() && commandsUsed < COMMAND_LIMIT) {
        int ji = deferredKills[deferredHead++];
        if (jobs[ji].state == 1) killNow(ji);
    }
    if (deferredHead == deferredKills.size()) deferredKills.clear(), deferredHead = 0;
}

ll dst(int a, int b) { return a == b ? 0 : rackDist[a][b] < 0 ? 99 : rackDist[a][b]; }

// transfer time / fee of job j when placed on rack r; false if some input is unreachable.
// away = largest distance to a predecessor's output rack (0 when the job stays with its predecessors)
bool transferCost(Job& j, int r, ll& tt, ll& tf, ll& away) {
    tt = tf = away = 0;
    int k = j.pre.size();
    for (int i = j.s < 0 ? 0 : -1; i < k; i++) {
        int s = i < 0 ? j.s : jobs[j.pre[i]].outRack;
        ll z = i < 0 ? j.zin : jobs[j.pre[i]].zout;
        if (s == r) continue;
        ll d = rackDist[r][s];
        if (d < 0) return 0;
        tt = max(tt, d + (z + Bnet - 1) / Bnet);
        tf += z * d * Unet;
        if (i >= 0) away = max(away, d);
    }
    return 1;
}

void runJob(int ji, int x) {
    assert(commandsUsed < COMMAND_LIMIT);
    ++commandsUsed;
    Job& j = jobs[ji];
    int r = machRack[x], o = flows[j.wf].tenant;
    ll tt, tf, aw, qreg = 0, qrack = 0;
    transferCost(j, r, tt, tf, aw);
    for (int l : imageLayers[j.img]) {
        if (cacheHit(machCache[x], l)) continue;
        if (cacheHit(rackCache[r], l))
            qrack += layerSize[l];
        else
            qreg += layerSize[l], cachePut(rackCache[r], l);
        cachePut(machCache[x], l);
    }
    ll cp = j.c * price[rackDc[r]];
    j.prep = max(tt, (qreg + Breg - 1) / Breg + (qrack + Brack - 1) / Brack);
    j.state = 1;
    j.mach = x;
    j.t0 = now;
    freeCpu[x] -= j.c;
    freeMem[x] -= j.m;
    machJobs[x].push_back(ji);
    tenFix[o] += runFee = tf + qreg * Ureg;
    tenRate[o] += cp;
    tenRateStart[o] += cp * now;
    for (int a = o; a >= 0; a = tenPar[a]) tenUsed[a] += j.c;
    outbuf += "RUN " + to_string(j.id) + " " + to_string(x) + "\n";
}

// ---------------- reconciliation helpers ----------------
ll slackOf(int ji) {
    Flow& w = flows[jobs[ji].wf];
    static ll es[1 << 16], tl[1 << 16];
    ll cp = 0;
    F(i, w.n) {
        Job& j = jobs[w.first + i];
        es[i] = 0;
        tl[i] = 0;
        if (j.state > 1) continue;
        for (int p : j.pre)
            if (jobs[p].state < 2) es[i] = max(es[i], es[p - w.first] + jobs[p].e);
        cp = max(cp, es[i] + j.e);
    }
    for (int i = w.n - 1; i >= 0; i--) {
        Job& j = jobs[w.first + i];
        if (j.state > 1) continue;
        tl[i] += j.e;
        for (int p : j.pre) tl[p - w.first] = max(tl[p - w.first], tl[i]);
    }
    return cp - es[ji - w.first] - tl[ji - w.first];
}

// ---------------- scheduling ----------------
double jobEnd[1 << 17], jobTheta[1 << 17], jobTail[1 << 17], overhead = 3, ovWait = 1, feeAvg = 50;
vector<pair<double, ll>> timeline[360];  // (expected release tick, cores << 32 | memory) incl. reservations
int virtCpu[360], virtMem[360];
vector<int> rackMachs[30];

double revenueAt(Flow& w, double f) {
    ll g = max(5, (w.dl - w.arrive) / 3);
    if (f <= w.dl) return w.v;
    if (f >= w.dl + g) return 0;
    return w.v * (w.dl + g - f) / g;
}

// estimated remaining critical path (ticks), remaining work (core-ticks) and remaining cost of a
// workflow; also fills per-job urgency (jobTheta) and tail length (jobTail)
void flowEstimate(Flow& w, double& rem, double& work, double& cost) {
    static double st[1 << 16], du[1 << 16];
    double f = tenFactor(w.tenant);
    ll pr = price[rackDc[w.home]];
    rem = work = cost = 0;
    F(i, w.n) {
        Job& j = jobs[w.first + i];
        st[i] = du[i] = 0;
        if (j.state > 1) continue;
        for (int p : j.pre) st[i] = max(st[i], st[p - w.first] + du[p - w.first]);
        du[i] = j.state ? jobEnd[w.first + i] - now : j.e * f + OVK * overhead + j.xt;
        work += j.c * du[i];
        if (!j.state) du[i] += WK * ovWait;
        cost += j.state ? j.c * du[i] * price[rackDc[machRack[j.mach]]] : j.c * du[i] * pr + feeAvg + j.xf;
        rem = max(rem, st[i] + du[i]);
        jobTail[w.first + i] = 0;
    }
    ll g = max(5, (w.dl - w.arrive) / 3);
    for (int i = w.n - 1; i >= 0; i--) {
        int ji = w.first + i;
        Job& j = jobs[ji];
        if (j.state > 1) continue;
        jobTail[ji] += du[i];
        for (int p : j.pre) jobTail[p] = max(jobTail[p], jobTail[ji]);
        double path = st[i] + jobTail[ji], x = (now + path - w.dl) / (MG * path + 1) + 1;
        jobTheta[ji] = TH0 * j.c + w.v * 1.0 / g * min(1.0, max(0.0, x));
    }
}

// home rack of a workflow: the rack where running everything is cheapest (external inputs have
// to be brought there); also fills the per-job transfer time / fee towards it
void chooseHome(Flow& w) {
    double best = 1e18;
    F(h, R) {
        double tot = 0;
        F(i, w.n) {
            Job& j = jobs[w.first + i];
            ll cp = j.c * price[rackDc[h]], d = j.s < 0 || j.s == h ? 0 : rackDist[h][j.s];
            tot += cp * j.e;
            if (d < 0) tot += 1e9;
            if (d > 0) tot += j.zin * d * Unet + (d + (j.zin + Bnet - 1) / Bnet) * (cp + TH0 * j.c);
        }
        if (tot < best) best = tot, w.home = h;
    }
    F(i, w.n) {
        Job& j = jobs[w.first + i];
        ll d = j.s < 0 || j.s == w.home ? 0 : rackDist[w.home][j.s];
        if (d < 0) d = 60;
        j.xt = d ? d + (j.zin + Bnet - 1) / Bnet : 0, j.xf = j.zin * d * Unet;
    }
}

// expected ticks until machine x has room for (c, m)
double waitFor(int x, int c, int m, double lim) {
    int fc = virtCpu[x], fm = virtMem[x];
    if (fc >= c && fm >= m) return 0;
    for (auto& q : timeline[x]) {
        if (q.first - now > lim) break;  // too late to be the best choice
        fc += q.second >> 32, fm += int(q.second);
        if (fc >= c && fm >= m) return q.first - now;
    }
    return 1e9;
}

void occupy(int x, int ji, double end) {
    virtCpu[x] -= jobs[ji].c, virtMem[x] -= jobs[ji].m;
    pair<double, ll> v(end, ll(jobs[ji].c) << 32 | jobs[ji].m);
    timeline[x].insert(lower_bound(timeline[x].begin(), timeline[x].end(), v), v);
}


void v13ModelFeatures(int ji,int machine,double preparation,bool warm,float* x) {
    const Job& j=jobs[ji];const Flow& w=flows[j.wf];const V13ModelForecast& p=v13ModelForecasts[j.wf];
    int grace=max(5,(w.dl-w.arrive)/3);
    double window=max(1.,double(min(T,w.dl+grace-1)-now)),value=max(1.,double(w.v));
    ll quota=LLONG_MAX,headroom=LLONG_MAX;
    for(int a=w.tenant;a>=0;a=tenPar[a])quota=min(quota,tenQuota[a]),headroom=min(headroom,tenQuota[a]-tenUsed[a]);
    double capacity=max(1.,double(quota));ll time,fee,away;
    transferCost(jobs[ji],machRack[machine],time,fee,away);
    x[0]=float(w.n);x[1]=float(double(p.roots)/max(1,w.n));
    x[2]=float(p.cost/value);x[3]=float(p.rem/window);x[4]=float(p.rev/value);x[5]=float((p.rev-p.cost)/value);
    x[6]=float(p.work/(capacity*window));x[7]=float(headroom/capacity);x[8]=float(window/T);x[9]=float(double(now)/T);
    x[10]=float(tenFactor(w.tenant));x[11]=float((w.dl-now)/window);x[12]=float(j.c/capacity);
    x[13]=float(preparation/window);x[14]=float(fee/value);x[15]=float(j.e*tenFactor(w.tenant)/window);
    x[16]=float(double(now-p.tick)/T);x[17]=warm?1.f:0.f;
}

static void v13ModelPredict(const float* x,double* prediction) {
    static const double mean[18]={12.814873008712269,0.24757155098575145,0.32923126812762316,0.51190106215445641,0.85862047250838569,0.52938920223875907,0.017026197823316585,0.77549073408229963,0.45062288326328509,0.32336865710111912,1.3383808955708398,0.81023119794142873,0.01933338933283087,0.0086641039168437774,0.0034686463731950345,0.10227543027101449,0.0007967073808567885,0.81944144941096975};
    static const double scale[18]={15.76918528718965,0.27280308847425827,0.17028750616237592,0.21259278290539044,0.1627715596315425,0.27633824382744504,0.017709908820591713,0.25020542302828219,0.27766675759923426,0.2385812636373785,0.43740612476878871,0.14131903143521737,0.017762067148155231,0.031911328339495698,0.01514456510688109,0.10767596886696774,0.0021790592180097211,0.38465199908257186};
    double a0[18];F(i,18)a0[i]=min(8.,max(-8.,(double(x[i])-mean[i])/scale[i]));
    static const double w0[16][18]={0.022379694115961912,-0.21702774478913561,-0.052564409792675119,0.036959111926669522,-0.0055780463230126389,0.062911871576846037,-0.037989053773640841,0.11486492582343041,0.31365297960284322,0.34057979468493488,-0.092782484303580604,-0.0077434015028919525,0.016235131262309785,-0.014039663488086631,0.040006637919866847,0.14327159564028821,0.022852140674514732,0.034678259621035344,0.0023486366192064802,-0.031632732741410423,-0.084626281558308508,-0.12035075838268114,0.060303946520775517,-0.11216779911615965,0.045396748369390567,-0.050627250340241021,0.025980394931447583,-0.049153443621496443,0.06724112875471322,0.11201028987465597,-0.035676347287718992,0.052906575319786091,-0.013581687408657703,0.0163125340514346,0.0055356630037841767,0.44788625341095073,0.086524603247025919,0.32743235136776166,-0.10921144774021893,0.14383522342592989,0.23354075160346777,0.076831591982569933,-0.20329247961884508,-0.087479385616660923,0.25092246020677161,0.011527983467635727,0.04553888018159203,-0.078661822112633603,-0.076808883283251236,0.252147685792875,-0.032837445054421384,-0.026901408716041388,0.11757017659911477,-0.090461838983430895,0.10249946066151371,-0.045400377093961816,-0.067342862921915755,-0.1822910931015303,0.073363620173812275,-0.03624853999703774,0.063296605722258009,0.048726944855177444,0.24158262646764747,-0.093351920205743275,-0.088676202248807998,-0.057625212845443828,-0.0094908216795887533,-0.031122979862467003,-0.051131921712962457,-0.0099531447377133927,0.025533475140784179,-0.43580313438905216,-0.14316639222137117,-0.060185268455360333,0.066738149173445074,-0.23918178504082216,-0.0033715060893888312,0.042654610917792157,-0.021537149672921727,0.019505424418478284,-0.22339646901475863,0.14239915177566306,-0.039547389341789259,0.098552676975225656,0.017125476637044584,0.0061676952385942806,-0.014706538752833049,-0.11826997399518628,-0.07670013639549797,0.013182068661867549,0.16392819436950687,-0.032928682335506464,-0.11509414456399766,-0.15378975551915397,0.11206795466600056,-0.047169064990963003,0.0075030608287503173,0.11955336569058839,-0.093675760184832618,-0.11281879408256396,-0.24377548206980418,-0.024914101882654978,-0.032185629264871438,-0.066775807043705768,-0.11111167961715877,0.0051127105291671453,0.24984166362154678,0.17388305983454802,0.054832026535463464,0.061235665412951459,0.031657018907629293,0.085270639686226363,0.05072679544538343,-0.095572738290355605,0.044471729378400313,0.025905473600806458,-0.087934267693152532,-0.068248473112278801,-0.068505310023297586,-0.1168785175717868,0.070895352905937348,-0.12745790094745535,-0.13619041530574497,-0.053890308857222971,-0.045480963836616296,0.13672081681878936,0.16951392582694341,-0.21046649160002454,0.091022006340590114,0.5607147779683187,-0.018678776604927443,-0.072220094318573819,-0.00032785636603654972,-0.01160573255808791,0.086338569579717625,-0.05294633752687105,0.085471495218241905,-0.32669665016837979,0.024961126573298648,0.20288337590235678,-0.0014971012660803698,-0.013627728696265575,0.033194862321831407,0.11352575964886394,0.045438834340188514,-0.1575180499969305,-0.027116834784218263,0.26495455019132208,0.049971912322815219,-0.095715369840382092,0.044091895360756105,0.023180388664416969,0.1193823338222766,-0.15314626143513693,-0.26655115948318842,0.2726047543873118,-0.043281916198556876,0.011342760283840733,0.14313887434320269,-0.018335300832927462,-0.052351653029620977,0.11857402554626101,0.14195673700695391,-0.0381255376743719,0.27152651652829407,0.037972881250892966,-0.010481967514186031,-0.026060790314122197,0.17547918938606924,0.011210952849413714,0.071304485188090377,-0.22853431866301749,0.15121888208901096,0.066422912839809278,-0.14284016197466023,-0.17136696426227732,0.061287724827772158,0.026340583857526561,0.05980917590742376,-0.059448219954412337,0.056261241093657363,-0.017419361043466156,-0.016896835221786147,-0.36666199256775506,-0.041640302050241502,-0.0044651140515274725,0.011206921334672552,-0.01932442130526249,-0.24154868900865306,0.21176034381194872,-0.040740268583565206,-0.04460255886645189,-0.15337020398926499,-0.12008607099377427,-0.041750343747901084,0.17775908051605549,0.14598518947780476,-0.17308819300552319,-0.026161859957876652,0.039475907120791985,0.24127898765751601,0.084485351342163492,0.051708132555645943,-0.059433456130959857,-0.017978054121540816,-0.064120978672310591,0.018853835191132071,0.010416825744229471,0.0042937278921079793,0.046721628556987457,3.7684689392601233e-05,0.057046920643212179,0.012521633508253971,0.022579681187403174,0.035963095836907939,-0.12040610119841456,-0.04356644193839785,-0.079303541538781011,-0.31015986301590137,-0.13078864152981312,-0.0090755230213116819,0.056886125499191774,-0.021724824287099976,-0.1309984563510041,-0.19507066569095724,0.088604860545505773,-0.099349798783557611,0.18851672776134476,0.045923680795768008,-0.068379152071971219,-0.045613494512580628,0.07127132519600908,0.0053757816753491729,-0.11322738357803072,-0.060147638144481812,-0.057113153278114094,0.013427031378811571,-0.08486357042100362,0.088521597152408441,-0.10664398251576285,-0.17949934681628621,0.0058609918994171374,-0.069351943672589095,0.13159422546876234,-0.039011997853761166,-0.089382469804573664,-0.11770052746140582,-0.066325936720847842,-0.015489719547391683,0.30734181940690702,0.080986211555986329,-0.033433706771426062,0.022612698280748862,0.08968329522329184,0.33348686071414196,0.041039186911275047,-0.096706729803422709,-0.20377028147490428,-0.02461070644230608,-0.097430242288555013,0.069665997158594811,0.014745168459578791,0.014405955979439096,0.088202260822513021,0.028804483154062456,0.047558657859313611,-0.059242497475255701,0.031600994692840507,0.03968308337629152,-0.045554412966058631,0.056787212234349009,0.054146313248345644,-0.033517005731560495,-0.17422301816383501,0.076529867689653905,0.17465201630562938,0.070287137382201645,-0.065340088489229495,-0.013112710147890816,0.093315195405702517,-0.38870181105465451,0.46292152356533339,-0.0095629909332396422,0.086722251524603167,-0.054433313447304704,0.032611578861082367,0.18031132670649405,0.065631716688769423};
    static const double b0[16]={-0.048877764124663221,0.39455835408296935,0.080540886793982233,0.1544107267137273,0.58351803361082166,0.46148270587129064,0.23431202878776922,-0.53510779312076484,0.24417051644986978,-0.45174747218617345,-0.22283670521469334,0.54897361606353756,0.53646838548219822,0.11060523674422845,-0.62803950266526454,0.036735577267426323};
    double a1[16];
    F(o,16){double value=b0[o];F(i,18)value+=w0[o][i]*a0[i];a1[o]=max(0.,value);}
    static const double w1[2][16]={0.11726374775858607,0.22786028332734351,0.11835361824799806,0.16507481027309581,0.26065409711622112,0.15655900863118671,0.13013214670485129,-0.27098451902802423,0.14023569832635488,-0.23637355677296823,-0.15171589656318385,0.1746269913508017,0.17402150051834478,0.10692164680646191,-0.29498881439888586,-0.15630377494691156,0.086776124748254121,0.012823107917668376,0.14298933453598958,0.078202707390186824,0.1780659952590562,0.14911996466469787,-0.028462452961229033,-0.16748884702968964,0.12674344470327659,-0.082156721523184914,-0.13893330556106392,-0.16620869949399292,0.2885007734227214,0.077291626319857573,-0.012475667109283956,-0.14211555114643298};
    static const double b1[2]={0.17625389545412309,0.17999940855869953};
    double a2[2];
    F(o,2){double value=b1[o];F(i,16)value+=w1[o][i]*a1[i];a2[o]=value;}
    prediction[0]=min(1.,max(0.,a2[0]));prediction[1]=min(1.,max(-2.,a2[1]));
}


ll v13ModelAttempts,v13ModelRejects,v13ModelLate,v13ModelGuardReturns;
#ifdef V13_MODEL_DISABLED
volatile double v13ModelDisabledSink;
#endif
static bool v13ModelAllow(int ji,int machine,double prep,bool warm) {
    ++v13ModelAttempts;
    float x[18];v13ModelFeatures(ji,machine,prep,warm,x);
    double prediction[2];v13ModelPredict(x,prediction);
    const auto& forecast=v13ModelForecasts[jobs[ji].wf];
    (void)forecast;
#ifdef V13_MODEL_DISABLED
    v13ModelDisabledSink=prediction[0]+prediction[1]+x[0];
    return true;
#else
    bool allow=((1-0.25)*forecast.rev+0.25*prediction[0]*flows[jobs[ji].wf].v>forecast.cost*(1+ADM));
    v13ModelRejects+=!allow;
    return allow;
#endif
}

void tryPlace(int ji) {
    Job& j = jobs[ji];
    Flow& w = flows[j.wf];
    array<unsigned char,offsetof(Job,pre)> v13BeforeJob;
    if(!w.started)memcpy(v13BeforeJob.data(),&j,v13BeforeJob.size());
    for (int a = w.tenant; a >= 0; a = tenPar[a])
        if (tenUsed[a] + j.c > tenQuota[a]) {
            return;
        }
    if (j.resT > now && (j.resM < 0 || (machUp[j.resM] && freedAt[j.resM] < j.resAt))) {
        if (j.resM >= 0) occupy(j.resM, ji, j.resEnd);
        return;
    }
    double est = max(1.0, j.e * tenFactor(w.tenant)), best = 1e18, th = jobTheta[ji], bw = 0, bs = 0;
    int bx = -1, bwarm = 0;
    static ll tts[30], tfs[30];
    static double rfee[30];
    static vector<pair<double, int>> cand;
    cand.clear();
    F(r, R) {
        ll aw;
        if (transferCost(j, r, tts[r], tfs[r], aw)) {
            // registry fee of the layers the rack cache does not hold (a machine may still hold them)
            static ll iq[120][30];
            static int iv[120][30];
            ll& q = iq[j.img][r];
            if (iv[j.img][r] != rackCache[r].ver + 1) {
                iv[j.img][r] = rackCache[r].ver + 1, q = 0;
                for (int l : imageLayers[j.img])
                    if (!rackCache[r].in[l]) q += layerSize[l];
            }
            rfee[r] = RF * q * Ureg;
            // keep the RK cheapest racks, sorted
            pair<double, int> v = {rfee[r] + tfs[r] + th * (tts[r] + PEN * aw * !j.suc.empty()) + j.c * price[rackDc[r]] * (tts[r] + est), r};
            int k = cand.size();
            if (k < RK) cand.push_back(v);
            else if (v.first < cand[--k].first) ;
            else continue;
            for (; k && v.first < cand[k - 1].first; k--) cand[k] = cand[k - 1];
            cand[k] = v;
        }
    }
    if (LAK > 0) {
        // look one step ahead: every successor will have to gather this job's output and its other
        // inputs (external input, outputs of predecessors that are already placed) on one rack
        static int qr[8][5], nq[8];
        static ll qz[8][5];
        static double qm[8][5], qf[8][5];
        int ns = 0, sj[8];
        for (int si : j.suc) {
            if (ns >= 8) break;  // Check before any access to qr/ns scratch rows.
            Job& s = jobs[si];
            int k = 0;
            if (s.s >= 0) qr[ns][k] = s.s, qz[ns][k++] = s.zin;
            for (int p : s.pre)
                if (p != ji && k < 5 && (jobs[p].state || GU > 0)) {
                    Job* q = &jobs[p];
                    // an unplaced predecessor is guessed to run where its own inputs are
                    for (int it = 0; it < 3 && !q->state && q->s < 0 && q->pre.size(); it++) q = &jobs[q->pre[0]];
                    qr[ns][k] = q->state > 1 ? q->outRack : q->state ? machRack[q->mach] : q->s < 0 ? w.home : q->s, qz[ns][k++] = jobs[p].zout;
                }
            if (!k) continue;
            F(a, k) {
                qm[ns][a] = qf[ns][a] = 0;
                F(b, k) {
                    ll d = dst(qr[ns][a], qr[ns][b]);
                    if (d) qm[ns][a] = max(qm[ns][a], double(d + (qz[ns][b] + Bnet - 1) / Bnet)), qf[ns][a] += qz[ns][b] * d;
                }
            }
            nq[ns] = k, sj[ns++] = si;
        }
        if (ns) {
            for (auto& cr : cand) {
                int r = cr.second;
                F(i, ns) {
                    double sth = jobTheta[sj[i]] + jobs[sj[i]].c * price[rackDc[r]], stayT = 0, stayF = 0;
                    F(a, nq[i]) {
                        ll d = dst(r, qr[i][a]);
                        if (d) stayT = max(stayT, double(d + (qz[i][a] + Bnet - 1) / Bnet)), stayF += qz[i][a] * d;
                    }
                    double la = sth * stayT + Unet * stayF;
                    F(a, nq[i]) {
                        ll d = dst(r, qr[i][a]);
                        la = min(la, sth * max(d ? double(d + (j.zout + Bnet - 1) / Bnet) : 0, qm[i][a]) + Unet * (j.zout * d + qf[i][a]));
                    }
                    cr.first += LAK * la;
                }
            }
            sort(cand.begin(), cand.end());
        }
    }
    for (auto& cr : cand) {
        int r = cr.second;
        cr.first -= rfee[r];
        if (cr.first >= best) continue;
        for (int x : rackMachs[r]) {
            if (!machUp[x] || machCpu[x] < j.c || machMem[x] < j.m) continue;
            double wt = waitFor(x, j.c, j.m, (best - cr.first) / (th + 1e-9));
            if (cr.first + th * wt >= best) continue;
            ll qreg = 0, qrack = 0;
            for (int l : imageLayers[j.img])
                if (!machCache[x].in[l]) (rackCache[r].in[l] ? qrack : qreg) += layerSize[l];
            ll s = max(tts[r], (qreg + Breg - 1) / Breg + (qrack + Brack - 1) / Brack);
            double cost = cr.first + qreg * Ureg + (j.c * price[rackDc[r]] + th) * (s - tts[r]) + th * wt;
            // A RUN puts the layers into the caches at once and a KILL in the same tick costs no run
            // fee, so RUN + KILL + RUN skips the pull time; the transfer fee is then paid twice.
            double warm = cr.first + qreg * Ureg + tfs[r] + th * wt;
            int wm = PW > 0 && warm < cost;
            if (wm) cost = warm, s = tts[r];
            if (cost < best) best = cost, bx = x, bw = wt, bs = s, bwarm = wm;
        }
    }
    j.resAt = now, j.resM = -1, j.resT = now + RT0;
    if (bx < 0 || bw > RESV) return;
    if (bw > 0) {
        j.resM = bx, j.resEnd = now + bw + bs + est, j.resT = now + min(RT1, bw * RTK);
        occupy(bx, ji, now + bw + bs + est);
        return;
    }
    // RUN/KILL/RUN is one atomic decision: never emit a partial prewarm batch.
    if (commandsUsed + (bwarm ? 3 : 1) > COMMAND_LIMIT) return;
    if(!w.started&&!v13ModelAllow(ji,bx,bs,bwarm)) {
        memcpy(reinterpret_cast<unsigned char*>(&j),v13BeforeJob.data(),v13BeforeJob.size());
        return;
    }
    int rdy = j.ready;
    ll fee0 = 0;
    if (bwarm && !bw) {
        runJob(ji, bx);
        fee0 = runFee;
        killNow(ji);
        j.ready = rdy;
    }
    runJob(ji, bx);
    runFee += fee0;
    w.started = w.dirty = 1;
    overhead = overhead * .98 + .02 * max(0.0, j.prep - j.xt);
    ovWait = ovWait * .98 + .02 * min(WCAP, double(now - j.ready));
    feeAvg = feeAvg * .98 + .02 * (runFee - j.xf);
    jobEnd[ji] = now + j.prep + est;
    occupy(bx, ji, jobEnd[ji]);
}

void schedule() {
    drainDeferredKills();
    // No future completion event can create revenue after the known final tick.
    if (now == T) {
        F(x,M) {
            while (!machJobs[x].empty() && commandsUsed < COMMAND_LIMIT)
                killNow(machJobs[x].back());
            if (commandsUsed == COMMAND_LIMIT) break;
        }
        return;
    }
    // CPU-time insurance (limit: 1 s per test). `late` > 0 means we are behind a linear budget
    // that ends at 0.7 s: first the periodic re-evaluation of flows is dropped, then scheduling
    // runs only every 2nd, 4th, ... 32nd tick; close to the limit only the audit is answered.
    double used = V7_SCHEDULER_USED(TS), late = used - .08 - .62 * now / T;
    v13ModelLate+=late>=0;
    if (used > .93 || (late > 0 && now % (1 << min(5, int(late / .04))))) {++v13ModelGuardReturns;return;}
    updateFactors();
    allRunD = allRunE = 0;
    F(i, K) tenRunD[i] = tenRunE[i] = 0;
    F(x, M) {
        virtCpu[x] = freeCpu[x], virtMem[x] = freeMem[x];
        timeline[x].clear();
        for (int q : machJobs[x]) {
            double el = max(0, now - jobs[q].t0 - jobs[q].prep);
            int o = flows[jobs[q].wf].tenant;
            if (el > jobs[q].e * tenF[o]) allRunD += el, tenRunD[o] += el, allRunE += jobs[q].e, tenRunE[o] += jobs[q].e;
            timeline[x].push_back({jobEnd[q] = max(now + 1 + OD * el, jobEnd[q]), ll(jobs[q].c) << 32 | jobs[q].m});
        }
        sort(timeline[x].begin(), timeline[x].end());
    }
    updateFactors();
    vector<pair<double, int>> order;
    F(wi, flows.size()) {
        Flow& w = flows[wi];
        if (w.dead || !w.left) continue;
        if (w.dirty || (late < 0 && (now + wi) % int(THR) == 0)) {
            double rem, work, cost, rev = 0;
            flowEstimate(w, rem, work, cost);
            static const double sc[5] = {-1, -.5, 0, 1, 2};
            rem *= 1 + BB * log(w.left);  // the longest of many noisy paths is longer than the path of the means
            F(k, 5) {
                double f = now + rem * (1 + SP * sc[k]);
                if (f <= T + HZ || !HS) rev += revenueAt(w, f) / 5;  // nothing is earned after the last tick
            }
            if (!HS && now + rem > T) rev = 0;
            auto& v13forecast=v13ModelForecasts[wi];
            v13forecast.rem=rem;v13forecast.work=work;v13forecast.cost=cost;v13forecast.rev=rev;v13forecast.tick=now;
            w.dirty = 0, w.key = 1;
            if (rev > cost * (w.started ? KILLK : 1 + ADM)) {
                w.key = -(rev - cost) / (work + 1) * (w.started ? SB : 1) / (1 + SL * max(0.0, (w.dl - now - rem) / rem));
            } else if (w.started) {
                w.dead = 1;
                F(i, w.n) if (jobs[w.first + i].state == 1) {
                    stopOrDefer(w.first + i);
                }
            } else if (revenueAt(w, now + rem * DEADK) <= 0)
                w.dead = 1;
        }
        if (w.key < 0 && !w.dead) order.push_back({w.key, wi});
    }
    sort(order.begin(), order.end());
    for (auto& o : order) {
        Flow& w = flows[o.second];
        static vector<pair<double, int>> ready;
        ready.clear();
        F(i, w.n) {
            Job& j = jobs[w.first + i];
            if (j.state == 0 && j.need == 0) ready.push_back({-jobTail[w.first + i], w.first + i});
        }
        sort(ready.begin(), ready.end());
        for (auto& q : ready) tryPlace(q.second);
    }
}

int main() {
    T = readInt(), D = readInt(), N = readInt(), R = readInt(), M = readInt(), K = readInt();
    L = readInt(), I = readInt(), P = readInt(), W = readInt(), E = readInt();
    Breg = readInt(), Brack = readInt(), Bnet = readInt(), Ureg = readInt(), Unet = readInt();
    F(i, D) price[i] = readInt();
    F(i, R) rackDc[i] = readInt(), rackNode[i] = readInt(), rackCache[i].cap = readInt();
    F(i, M) {
        machRack[i] = readInt(), freeCpu[i] = machCpu[i] = readInt(), freeMem[i] = machMem[i] = readInt();
        machCache[i].cap = readInt(), machUp[i] = 1;
        rackMachs[machRack[i]].push_back(i);
    }
    F(i, E) {
        edgeU[i] = readInt(), edgeV[i] = readInt(), edgeW[i] = readInt(), edgeUp[i] = 1;
        adj[edgeU[i]].push_back(i), adj[edgeV[i]].push_back(i);
    }
    F(i, K) tenPar[i] = readInt(), tenQuota[i] = readInt();
    {  // order tenants so that parents come first
        int cnt = 0;
        vector<char> seen(K);
        while (cnt < K) F(i, K) if (!seen[i] && (tenPar[i] < 0 || seen[tenPar[i]])) seen[i] = 1, tenOrder[cnt++] = i;
    }
    F(i, L) layerSize[i] = readInt();
    F(i, I) {
        int k = readInt();
        while (k--) imageLayers[i].push_back(readInt());
    }
    {  // huffman tree
        ll wt[20];
        char alive[20] = {};
        F(i, 9) wt[i] = readInt(), alive[i] = 1;
        for (int id = 9; id < 17; id++) {
            int pick[2];
            F(k, 2) {
                int b = -1;
                F(i, id) if (alive[i] && (b < 0 || wt[i] < wt[b])) b = i;
                alive[b] = 0, pick[k] = b;
                huffChild[id][k] = b;
            }
            wt[id] = wt[pick[0]] + wt[pick[1]], alive[id] = 1;
        }
        huffRoot = 16;
    }
    {  // aho-corasick
        acGo.push_back(array<int, 8>());
        acVal.push_back(0);
        F(i, P) {
            int n = readTok(), u = 0;
            F(k, n) {
                int c = tok[k] - 'a';
                if (!acGo[u][c]) acGo[u][c] = acGo.size(), acGo.push_back(array<int, 8>()), acVal.push_back(0);
                u = acGo[u][c];
            }
            acVal[u] += readInt();
        }
        vector<int> fail(acGo.size()), que;
        F(c, 8) if (acGo[0][c]) que.push_back(acGo[0][c]);
        F(qi, que.size()) {
            int u = que[qi];
            acVal[u] += acVal[fail[u]];
            F(c, 8) {
                int v = acGo[u][c];
                if (v)
                    fail[v] = acGo[fail[u]][c], que.push_back(v);
                else
                    acGo[u][c] = acGo[fail[u]][c];
            }
        }
    }
    F(a, R) rowDirty[a] = 1;
    for (;;) {
        if (!readTok()) break;  // "TICK"
        now = readInt();
        int ne = readInt(), nq = readInt();
        while (ne--) {
            readTok();
            string ev = tok;
            if (ev == "DONE") {
                int ji = jobIndex[readInt()];
                Job& j = jobs[ji];
                Flow& w = flows[j.wf];
                int o = w.tenant;
                tenDur[o] += now - j.t0 - j.prep, tenEst[o] += j.e, allDur += now - j.t0 - j.prep, allEst += j.e;
                release(ji);
                j.state = 2;
                j.outRack = machRack[j.mach];
                for (int s : j.suc) jobs[s].need--, jobs[s].ready = now;
                w.left--;
                if (!w.left) w.endT = now;
            } else if (ev == "FAIL") {
                int x = readInt();
                while (machJobs[x].size()) release(machJobs[x][0]);
                machUp[x] = 0;
                Cache& c = machCache[x];
                c.q.clear(), c.sum = 0;
                memset(c.in, 0, 400);
            } else if (ev == "UP") {
                int x = readInt();
                machUp[x] = 1;
            }
            else if (ev == "DCDOWN" || ev == "DCUP") {
                dcDown[readInt()] = ev.size() > 4, netDirty = 1;
                F(a, R) rowDirty[a] = 1;
            } else if (ev == "LDOWN" || ev == "LUP") {
                int e = readInt(), u = edgeU[e], v = edgeV[e];
                edgeUp[e] = ev.size() < 4, netDirty = 1;
                F(a, R) {
                    ll x = nodeDist[a][u], y = nodeDist[a][v];
                    // going up: matters if it is a shortcut; going down: matters if it was tight
                    if (edgeUp[e] ? x + edgeW[e] < y || y + edgeW[e] < x : x + edgeW[e] == y || y + edgeW[e] == x) rowDirty[a] = 1;
                }
            }
            else if (ev == "QUOTA") {
                int t = readInt();
                undoStack.push_back({t, tenQuota[t]});
                tenQuota[t] = readInt();
            } else if (ev == "UNDO") {
                int k = readInt();
                while (k--) tenQuota[undoStack.back().first] = undoStack.back().second, undoStack.pop_back();
            } else if (ev == "LOG") {
                int x = readInt(), b = readInt(), u = huffRoot, st = 0;
                readTok();
                ll sc = 0;
                F(i, b) {
                    int h = tok[i / 4], bit = ((h <= '9' ? h - '0' : (h | 32) - 'a' + 10) >> (3 - i % 4)) & 1;
                    u = huffChild[u][bit];
                    if (u < 9) {
                        st = u < 8 ? acGo[st][u] : 0;
                        sc += acVal[st];
                        u = huffRoot;
                    }
                }
                alarmAt[x][now] += sc;
            } else {  // WF
                Flow w;
                w.id = readInt(), w.tenant = readInt(), w.v = readInt(), w.dl = readInt(), w.n = w.left = readInt();
                w.arrive = now, w.first = jobs.size(), w.dead = w.started = w.adm = 0, w.dirty = 1, w.key = 1;
                F(i, w.n) {
                    Job j;
                    j.id = readInt(), j.c = readInt(), j.m = readInt(), j.e = readInt(), j.img = readInt();
                    j.s = readInt(), j.zin = readInt(), j.zout = readInt(), j.need = readInt();
                    j.state = 0, j.wf = flows.size(), j.ready = now, j.resT = 0;
                    F(k, j.need) {
                        int p = jobIndex[readInt()];
                        j.pre.push_back(p);
                        jobs[p].suc.push_back(jobs.size());
                    }
                    jobIndex[j.id] = jobs.size();
                    jobs.push_back(j);
                }
                if (netDirty) recomputeNet();
                chooseHome(w);
                flows.push_back(w);
                V13ModelForecast v13forecast;
                F(i,w.n)v13forecast.roots+=jobs[w.first+i].pre.empty();
                v13ModelForecasts.push_back(v13forecast);
            }
        }
        if (netDirty) recomputeNet();
        outbuf = "ANS";
        while (nq--) {
            readTok();
            char q = tok[0], q2 = tok[1];
            int a = readInt();
            ll ans = 0;
            if (q == 'B') {
                static ll sub[200];
                F(i, K) sub[i] = tenFix[i] + tenRate[i] * now - tenRateStart[i];
                for (int i = K - 1; i > 0; i--) sub[tenPar[tenOrder[i]]] += sub[tenOrder[i]];
                ans = sub[a];
            } else if (q == 'H') {
                ans = 1e18;
                for (; a >= 0; a = tenPar[a]) ans = min(ans, tenQuota[a] - tenUsed[a]);
            } else if (q == 'R' && q2 == 'O')
                ans = rackDist[a][readInt()];
            else if (q == 'A') {
                for (int t = max(1, now - W + 1); t <= now; t++) ans += alarmAt[a][t];
            } else if (q == 'S')
                ans = slackOf(jobIndex[a]);
            else
                ans = (q == 'C' ? machCache[a] : rackCache[a]).sum;
            outbuf += " " + to_string(ans);
        }
        outbuf += "\n";
        commandsUsed = 0;
        schedule();
        outbuf += "END\n";
        fwrite(outbuf.data(), 1, outbuf.size(), stdout);
        fflush(stdout);
        if (now == T) break;
    }
    fprintf(stderr,"V14_MLP_POLICY attempts=%lld rejects=%lld late=%lld guard_returns=%lld\n",v13ModelAttempts,v13ModelRejects,v13ModelLate,v13ModelGuardReturns);
}
