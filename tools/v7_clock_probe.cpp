#include <ctime>
#include <chrono>
#include <thread>
#include <iostream>
#include <windows.h>
static double cpu(){FILETIME c,e,k,u;GetProcessTimes(GetCurrentProcess(),&c,&e,&k,&u);ULARGE_INTEGER a,b;a.LowPart=k.dwLowDateTime;a.HighPart=k.dwHighDateTime;b.LowPart=u.dwLowDateTime;b.HighPart=u.dwHighDateTime;return double(a.QuadPart+b.QuadPart)/1e7;}
int main(){auto a=std::chrono::steady_clock::now();auto c=clock();auto p=cpu();std::this_thread::sleep_for(std::chrono::milliseconds(300));auto d=clock();auto q=cpu();auto b=std::chrono::steady_clock::now();std::cout<<"CLOCKS_PER_SEC="<<CLOCKS_PER_SEC<<" sleep_clock_seconds="<<double(d-c)/CLOCKS_PER_SEC<<" wall_seconds="<<std::chrono::duration<double>(b-a).count()<<" cpu_seconds="<<q-p<<"\n";}
