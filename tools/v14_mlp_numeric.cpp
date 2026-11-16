#define main v14_mlp_embedded_main
#ifndef V14_MLP_AUDIT_SOURCE
#define V14_MLP_AUDIT_SOURCE "../candidates/v14_mlp/A_veto_strict.cpp"
#endif
#include V14_MLP_AUDIT_SOURCE
#undef main

int main(){
    std::cout<<std::setprecision(17);
    int count;std::cin>>count;
    for(int row=0;row<count;++row){
        float x[18];for(float& value:x)std::cin>>value;
        double p[2];v13ModelPredict(x,p);
        bool light=!(p[1]<.02&&x[5]<.25&&x[0]>=3);
        bool strict=!(p[1]<.08&&x[5]<.4&&x[0]>=3);
        bool blend25=.75*double(x[4])+.25*p[0]>double(x[2])*(1+ADM);
        bool blend50=.5*double(x[4])+.5*p[0]>double(x[2])*(1+ADM);
        std::cout<<row<<' '<<p[0]<<' '<<p[1]<<' '<<light<<' '<<strict<<' '<<blend25<<' '<<blend50<<'\n';
    }
}
