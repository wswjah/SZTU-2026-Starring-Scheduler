#define main v13_model_embedded_main
#ifndef V13_MODEL_PRODUCTION_SOURCE
#define V13_MODEL_PRODUCTION_SOURCE "../candidates/v13_model/veto_strict.cpp"
#endif
#include V13_MODEL_PRODUCTION_SOURCE
#undef main

int main() {
    T=600;now=200;D=R=M=1;K=2;N=1;Bnet=5;
    tenPar[0]=-1;tenPar[1]=0;tenQuota[0]=100;tenQuota[1]=50;tenUsed[0]=tenUsed[1]=3;
    machRack[0]=0;rackDist[0][0]=0;
    jobs.assign(1,Job{});jobs[0].wf=0;jobs[0].c=2;jobs[0].e=5;jobs[0].s=-1;
    flows.assign(1,Flow{});flows[0].tenant=1;flows[0].dl=300;flows[0].arrive=1;
    v13ModelForecasts.resize(1);
#ifndef V13_MODEL_PRODUCTION_TRIMMED
    v13ModelForecasts[0].rem=15;v13ModelForecasts[0].work=200;
    v13ModelForecasts[0].tick=197;v13ModelForecasts[0].roots=1;
#endif
    std::cout<<std::setprecision(17);
    int count;std::cin>>count;
    for(int i=0;i<count;++i) {
        int n,warm;long long value;double cost,revenue,factor,prep;
        std::cin>>n>>value>>cost>>revenue>>factor>>prep>>warm;
        flows[0].n=n;flows[0].v=value;v13ModelForecasts[0].cost=cost;v13ModelForecasts[0].rev=revenue;tenF[1]=factor;
        float features[18]{};v13ModelFeatures(0,0,prep,bool(warm),features);
        double prediction[2];v13ModelPredict(features,prediction);
        bool allow=v13ModelAllow(0,0,prep,bool(warm));
        uint32_t netBits,factorBits;memcpy(&netBits,&features[5],4);memcpy(&factorBits,&features[10],4);
        std::cout<<i<<' '<<netBits<<' '<<factorBits<<' '<<features[5]<<' '<<features[10]<<' '<<prediction[0]<<' '<<prediction[1]<<' '<<allow<<'\n';
    }
}
