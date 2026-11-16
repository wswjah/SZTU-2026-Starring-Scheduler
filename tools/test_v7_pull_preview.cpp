// Fixed protocol examples for LRU ordering, oversized images, and duplicates.
#define main v7_pull_solver_main
#include "../candidates/v7_pull_hybrid.cpp"
#undef main

static Cache makeCache(ll capacity, initializer_list<int> order = {}) {
    Cache c{};
    c.cap = capacity;
    for (int layer : order) cachePut(c, layer);
    return c;
}

int main() {
    layerSize[0] = layerSize[1] = layerSize[2] = 5;
    imageLayers[0] = {0, 1};
    Cache machine = makeCache(10, {1, 2}), rack = makeCache(100, {0, 1});
    auto first = v7PullLayers(machine, rack, 0);
    assert(first.registry == 0 && first.rack == 10);
    auto second = v7PullLayers(machine, rack, 0);
    assert(second.registry == 0 && second.rack == 0);

    layerSize[0] = layerSize[1] = 7;
    machine = makeCache(7); rack = makeCache(100);
    first = v7PullLayers(machine, rack, 0);
    second = v7PullLayers(machine, rack, 0);
    assert(first.registry == 14 && first.rack == 0);
    assert(second.registry == 0 && second.rack == 14);

    layerSize[0] = layerSize[1] = 4;
    imageLayers[0] = {0, 0, 1};
    machine = makeCache(8); rack = makeCache(100);
    first = v7PullLayers(machine, rack, 0);
    second = v7PullLayers(machine, rack, 0);
    assert(first.registry == 8 && first.rack == 0);
    assert(second.registry == 0 && second.rack == 0);
    cout << "v7 preview fixed LRU/oversize/duplicate examples passed\n";
}
