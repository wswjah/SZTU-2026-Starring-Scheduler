#define main scheduler_program_main
#include "../candidates/v3_perf_queue.cpp"
#undef main
int main() {
    mt19937_64 rng(0x834729bdULL);
    for(int trial=0;trial<200000;++trial) {
        int n=(trial%5==0?400:1+rng()%48);
        for(int i=0;i<400;++i) layer_cache::layer_sizes[i]=rng()%700;
        layer_cache m,r;
        m.capacity=(trial%13==0?0:rng()%5000);
        r.capacity=(trial%17==0?0:rng()%7000);
        for(int i=0,k=rng()%160;i<k;++i) m.touch_layer(rng()%n);
        for(int i=0,k=rng()%160;i<k;++i) r.touch_layer(rng()%n);
        vector<int> layers;
        for(int i=0,k=(trial%31==0?1000:rng()%90);i<k;++i) layers.push_back(rng()%n);
        auto mm=m,rr=r;
        auto expected=pull_image_layers(mm,rr,layers);
        auto m0=m,r0=r;
        auto actual=preview_image_pull(m,r,layers);
        if(actual.registry_bytes!=expected.registry_bytes || actual.rack_bytes!=expected.rack_bytes ||
           m.used_bytes!=m0.used_bytes || r.used_bytes!=r0.used_bytes ||
           m.previous_layer!=m0.previous_layer || m.next_layer!=m0.next_layer ||
           r.previous_layer!=r0.previous_layer || r.next_layer!=r0.next_layer) {
            cerr<<"Mismatch at "<<trial<<"\n"; return 1;
        }
    }
    cout<<"200000 randomized cache previews exactly match full LRU simulation; source caches unchanged.\n";
}
