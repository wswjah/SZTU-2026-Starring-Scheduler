// Focused boundary regressions. The production candidate is included unchanged.
// Build with -fsanitize=bounds -fno-sanitize-recover=all when available.
#include <cstddef>
#include <cstdio>
#include <cstdlib>

#ifdef ATTRIBUTED96_CHECKED_SCRATCH
template<class T, std::size_t N> struct CheckedArray {
    T values[N]{};
    T& operator[](std::size_t i) {
        if (i >= N) {
            std::fprintf(stderr, "checked scratch array out of bounds: %zu >= %zu\n", i, N);
            std::exit(97);
        }
        return values[i];
    }
};
template<class T, std::size_t R, std::size_t C>
using CheckedMatrix = CheckedArray<CheckedArray<T, C>, R>;
#endif

#define main attributed96_solver_main
#ifndef ATTRIBUTED96_SOURCE
#define ATTRIBUTED96_SOURCE "../versions/v6_attributed96/main.cpp"
#endif
#include ATTRIBUTED96_SOURCE
#undef main

static int fixtureVersion = 1000;

static void check(bool ok, const char* message) {
    if (!ok) {
        std::cerr << "FAILED: " << message << '\n';
        std::exit(1);
    }
}

static void fixture(int successors = 0) {
    // Small direct state, without any hidden future information or protocol IO.
    // The same rack makes all input transfer fees/delays zero; a cold image
    // takes ten ticks, so the real tryPlace chooses its prewarm branch.
    jobs.clear(); flows.clear(); outbuf.clear();
    commandsUsed = 0; deferredKills.clear(); deferredHead = 0;
    T = 600; D = N = R = M = K = L = I = 1; now = 10;
    Breg = 1; Brack = 10; Bnet = 1; Ureg = Unet = 1;
    price[0] = 2; layerSize[0] = 10;
    rackDc[0] = machRack[0] = 0;
    rackDist[0][0] = 0;
    tenPar[0] = -1; tenQuota[0] = 1000000;
    tenUsed[0] = tenFix[0] = tenRate[0] = tenRateStart[0] = 0;
    tenF[0] = 1;
    machCpu[0] = machMem[0] = freeCpu[0] = freeMem[0] = 64;
    virtCpu[0] = virtMem[0] = 64;
    machUp[0] = 1; freedAt[0] = 0;
    machJobs[0].clear(); timeline[0].clear(); rackMachs[0] = {0};
    imageLayers[0] = {0};
    rackCache[0] = Cache{}; machCache[0] = Cache{};
    rackCache[0].cap = machCache[0].cap = 100;
    // tryPlace memoizes rack registry estimates by cache version; fixtures
    // use distinct versions rather than silently invalidating its real cache.
    rackCache[0].ver = fixtureVersion += 100;
    machCache[0].ver = fixtureVersion;
    overhead = 3; ovWait = 1; feeAvg = 50;
    Flow flow{};
    flow.id = 900000001; flow.tenant = 0; flow.arrive = 1;
    flow.dl = 500; flow.v = 100000; flow.n = flow.left = successors + 1;
    flow.first = flow.home = 0;
    flows.push_back(flow);
    for (int i = 0; i <= successors; ++i) {
        Job job{};
        job.id = 100000000 + i; job.wf = 0; job.c = job.m = 1;
        job.e = 5; job.img = 0; job.s = i ? 0 : -1;
        job.zin = job.zout = 1; job.ready = 1;
        job.resM = -1;
        if (i) job.pre = {0}, job.need = 1;
        jobs.push_back(job);
        jobTheta[i] = 100;
        jobTail[i] = 5;
        jobEnd[i] = 100;
    }
    for (int i = 1; i <= successors; ++i) jobs[0].suc.push_back(i);
}

static size_t outputLines() {
    return std::count(outbuf.begin(), outbuf.end(), '\n');
}

static void successorBounds() {
    for (int count : {0, 1, 7, 8, 9, 16, 64, 1000}) {
        fixture(count);
        tryPlace(0);
        check(jobs[0].state == 1, "fanout root must start");
        check(commandsUsed == 3 && outputLines() == 3, "fanout prewarm command batch");
        check(jobs[0].prep == 0, "fanout second RUN has a warm image");
        check(tenUsed[0] == 1 && freeCpu[0] == 63, "fanout final resource state");
    }
}

static void atomicBudget() {
    fixture();
    commandsUsed = COMMAND_LIMIT - 2;
    tryPlace(0);
    check(commandsUsed == COMMAND_LIMIT - 2 && outbuf.empty(), "two slots cannot emit partial prewarm");
    check(jobs[0].state == 0 && machJobs[0].empty(), "rejected batch leaves no running job");
    check(tenUsed[0] == 0 && tenFix[0] == 0 && tenRate[0] == 0, "rejected batch leaves no quota or bill");
    check(machCache[0].sum == 0 && rackCache[0].sum == 0, "rejected batch leaves no cache changes");

    fixture();
    commandsUsed = COMMAND_LIMIT - 3;
    tryPlace(0);
    check(commandsUsed == COMMAND_LIMIT && outputLines() == 3, "three slots emit full prewarm");
    const std::string id = std::to_string(jobs[0].id);
    check(outbuf == "RUN " + id + " 0\nKILL " + id + "\nRUN " + id + " 0\n", "prewarm command order");
    check(jobs[0].state == 1 && jobs[0].prep == 0, "prewarm final RUN state");
    check(tenFix[0] == 10 && tenRate[0] == 2 && tenRateStart[0] == 20, "first registry bill persists without first CPU elapsed");
    check(tenUsed[0] == 1 && freeCpu[0] == 63 && freeMem[0] == 63, "prewarm reserves resources only once");

    fixture();
    cachePut(machCache[0], 0);
    commandsUsed = COMMAND_LIMIT - 1;
    tryPlace(0);
    check(commandsUsed == COMMAND_LIMIT && outputLines() == 1, "one slot accepts a normal cache-hit RUN");

    fixture();
    commandsUsed = COMMAND_LIMIT;
    tryPlace(0);
    check(commandsUsed == COMMAND_LIMIT && outbuf.empty() && jobs[0].state == 0, "full budget emits nothing");
}

static void deferredStopLifecycle() {
    fixture(2);
    for (int i = 0; i < 3; ++i) {
        jobs[i].need = 0; jobs[i].pre.clear();
        runJob(i, 0);
    }
    flows[0].dead = 1;
    outbuf.clear();
    commandsUsed = COMMAND_LIMIT;
    for (int i = 0; i < 3; ++i) stopOrDefer(i);
    check(deferredKills.size() == 3 && deferredHead == 0 && outbuf.empty(), "full budget defers all stops");
    check(tenUsed[0] == 3 && machJobs[0].size() == 3, "deferred stops preserve running state");

    // Input events arrive before the next scheduling phase. DONE and FAIL both
    // release resources; only DONE changes the lifecycle state to completed.
    release(1); jobs[1].state = 2;
    release(2); jobs[2].state = 0;
    now = 11;
    commandsUsed = COMMAND_LIMIT - 1;
    drainDeferredKills();
    check(commandsUsed == COMMAND_LIMIT && outputLines() == 1, "deferred drain obeys last command slot");
    check(outbuf == "KILL " + std::to_string(jobs[0].id) + "\n", "only still-running queued job is killed");
    check(deferredHead == 1 && deferredKills.size() == 3, "unprocessed queue survives to a later tick");
    check(jobs[0].state == 0 && jobs[1].state == 2 && jobs[2].state == 0, "DONE and FAIL states remain valid");
    check(tenUsed[0] == 0 && tenRate[0] == 0 && freeCpu[0] == 64 && freeMem[0] == 64, "deferred stop resources reconcile");
    check(tenFix[0] == 12, "queued running fee covers exactly its extra tick");

    ++now;
    commandsUsed = 0; outbuf.clear();
    drainDeferredKills();
    check(commandsUsed == 0 && outbuf.empty(), "expired queued DONE/FAIL requests emit no KILL");
    check(deferredKills.empty() && deferredHead == 0, "drained queue is reset");
}

int main() {
    successorBounds();
    atomicBudget();
    deferredStopLifecycle();
    std::cout << "attributed96 focused regressions passed: fanout(0..1000), atomic budget, deferred DONE/FAIL\n";
    return 0;
}
