#define main v11_scan_original_main
#include "../candidates/v11_scan.cpp"
#undef main

int main() {
    std::cout<<readInt()<<'\n';
    for(int i=0;i<11;++i)std::cout<<readInt()<<'\n';
    readTok();std::cout<<tok<<'\n';
    std::cout<<readInt()<<'\n';
    readTok();std::cout<<tok<<'\n';
    std::cout<<readInt()<<'\n';
    std::cout<<readInt()<<'\n';
    std::cout<<readInt()<<'\n';
    std::cout<<readInt()<<'\n';
}
