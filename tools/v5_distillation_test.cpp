#include <bits/stdc++.h>
using namespace std;
static double v4_admission_score(const float* x) {
    static const short f[]={2,2,2,-2,-2,3,-2,-2,3,2,-2,-2,14,-2,-2};
    static const short l[]={1,2,3,-1,-1,6,-1,-1,9,10,-1,-1,13,-1,-1};
    static const short r[]={8,5,4,-1,-1,7,-1,-1,12,11,-1,-1,14,-1,-1};
    static const double t[]={0.33023485541343689,0.22496424615383148,0.16021289676427841,-2,-2,0.78763905167579651,-2,-2,0.55881783366203308,0.45336927473545074,-2,-2,0.69224998354911804,-2,-2};
    static const double v[]={0.37696678030875896,0.56331108281914388,0.70758281140481605,0.80834336987645528,0.64265967280050762,0.46538224531725186,0.50065769080874045,0.19926263025978433,0.21001572236913654,0.32272984114506637,0.40696005515182676,0.18093876387106061,0.14161803894154326,0.19386421785769534,0.016951855815637764};
    int n=0;
    while(f[n]>=0)n=x[f[n]]<=t[n]?l[n]:r[n];
    return v[n];
}
static bool distilled(float cost_ratio,float duration_ratio,float window_fraction) {
    return !(cost_ratio <= 0.33023485541343689) &&
                !(duration_ratio <= 0.55881783366203308) &&
                !(window_fraction <= 0.69224998354911804);
}
static int leaf_for(const float* x) {
    static const short f[]={2,2,2,-2,-2,3,-2,-2,3,2,-2,-2,14,-2,-2};
    static const short l[]={1,2,3,-1,-1,6,-1,-1,9,10,-1,-1,13,-1,-1};
    static const short r[]={8,5,4,-1,-1,7,-1,-1,12,11,-1,-1,14,-1,-1};
    static const double t[]={0.33023485541343689,0.22496424615383148,0.16021289676427841,-2,-2,0.78763905167579651,-2,-2,0.55881783366203308,0.45336927473545074,-2,-2,0.69224998354911804,-2,-2};
    int n=0;while(f[n]>=0)n=x[f[n]]<=t[n]?l[n]:r[n];return n;
}
int main() {
    array<vector<float>,3> values;
    for(auto& v:values) v={-numeric_limits<float>::infinity(),-10.f,-1.f,-0.f,0.f,1.f,10.f,
        numeric_limits<float>::infinity(),numeric_limits<float>::quiet_NaN(),numeric_limits<float>::signaling_NaN()};
    {float x=float(0.33023485541343689);
        values[0].push_back(x);
        for(int i=0;i<4;++i)values[0].push_back(x=nextafterf(x,-numeric_limits<float>::infinity()));
        x=float(0.33023485541343689);
        for(int i=0;i<4;++i)values[0].push_back(x=nextafterf(x,numeric_limits<float>::infinity()));}
    {float x=float(0.22496424615383148);
        values[0].push_back(x);
        for(int i=0;i<4;++i)values[0].push_back(x=nextafterf(x,-numeric_limits<float>::infinity()));
        x=float(0.22496424615383148);
        for(int i=0;i<4;++i)values[0].push_back(x=nextafterf(x,numeric_limits<float>::infinity()));}
    {float x=float(0.16021289676427841);
        values[0].push_back(x);
        for(int i=0;i<4;++i)values[0].push_back(x=nextafterf(x,-numeric_limits<float>::infinity()));
        x=float(0.16021289676427841);
        for(int i=0;i<4;++i)values[0].push_back(x=nextafterf(x,numeric_limits<float>::infinity()));}
    {float x=float(0.45336927473545074);
        values[0].push_back(x);
        for(int i=0;i<4;++i)values[0].push_back(x=nextafterf(x,-numeric_limits<float>::infinity()));
        x=float(0.45336927473545074);
        for(int i=0;i<4;++i)values[0].push_back(x=nextafterf(x,numeric_limits<float>::infinity()));}
    {float x=float(0.78763905167579651);
        values[1].push_back(x);
        for(int i=0;i<4;++i)values[1].push_back(x=nextafterf(x,-numeric_limits<float>::infinity()));
        x=float(0.78763905167579651);
        for(int i=0;i<4;++i)values[1].push_back(x=nextafterf(x,numeric_limits<float>::infinity()));}
    {float x=float(0.55881783366203308);
        values[1].push_back(x);
        for(int i=0;i<4;++i)values[1].push_back(x=nextafterf(x,-numeric_limits<float>::infinity()));
        x=float(0.55881783366203308);
        for(int i=0;i<4;++i)values[1].push_back(x=nextafterf(x,numeric_limits<float>::infinity()));}
    {float x=float(0.69224998354911804);
        values[2].push_back(x);
        for(int i=0;i<4;++i)values[2].push_back(x=nextafterf(x,-numeric_limits<float>::infinity()));
        x=float(0.69224998354911804);
        for(int i=0;i<4;++i)values[2].push_back(x=nextafterf(x,numeric_limits<float>::infinity()));}
    uint64_t checks=0;array<bool,15> visited{};
    auto check=[&](float a,float b,float c){
        float x[15]{};x[2]=a;x[3]=b;x[14]=c;
        bool reference=v4_admission_score(x)<.05,actual=distilled(a,b,c);
        if(reference!=actual){cerr<<"Mismatch: "<<a<<' '<<b<<' '<<c<<'\n';exit(1);}
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
    if(!visited[3]){cerr<<"Unvisited leaf 3\n";return 2;}++leaves;
    if(!visited[4]){cerr<<"Unvisited leaf 4\n";return 2;}++leaves;
    if(!visited[6]){cerr<<"Unvisited leaf 6\n";return 2;}++leaves;
    if(!visited[7]){cerr<<"Unvisited leaf 7\n";return 2;}++leaves;
    if(!visited[10]){cerr<<"Unvisited leaf 10\n";return 2;}++leaves;
    if(!visited[11]){cerr<<"Unvisited leaf 11\n";return 2;}++leaves;
    if(!visited[13]){cerr<<"Unvisited leaf 13\n";return 2;}++leaves;
    if(!visited[14]){cerr<<"Unvisited leaf 14\n";return 2;}++leaves;
    cout<<"{\"checks\":"<<checks<<",\"boundary_combinations\":"<<boundary
        <<",\"visited_leaves\":"<<leaves<<",\"all_equal\":true,\"includes_nan_and_infinity\":true}\n";
}
