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

int main() {
 double c0=double(clock())/CLOCKS_PER_SEC, p0=V7_SCHEDULER_USED(1);
 auto w0=std::chrono::steady_clock::now();
 std::this_thread::sleep_for(std::chrono::milliseconds(300));
 double c1=double(clock())/CLOCKS_PER_SEC, p1=V7_SCHEDULER_USED(1);
 auto w1=std::chrono::steady_clock::now();
 volatile unsigned long long burn=0;
 double target=p1+.15;
 while(V7_SCHEDULER_USED(1)<target) for(int i=0;i<10000;++i) burn+=i;
 double c2=double(clock())/CLOCKS_PER_SEC, p2=V7_SCHEDULER_USED(1);
 auto w2=std::chrono::steady_clock::now();
 std::cout<<"sleep_old_clock="<<c1-c0<<" sleep_portable_cpu="<<p1-p0<<" sleep_wall="<<std::chrono::duration<double>(w1-w0).count()
          <<" burn_old_clock="<<c2-c1<<" burn_portable_cpu="<<p2-p1<<" burn_wall="<<std::chrono::duration<double>(w2-w1).count()<<"\n";
}
