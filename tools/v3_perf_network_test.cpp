#define main scheduler_program_main
#include "../candidates/v3_perf_heap.cpp"
#undef main
struct network_state_original {

    int nodes_per_datacenter = 0; // 每个机房的节点数
    vector<int> rack_nodes; // 每个机架接入的网络节点
    vector<i64> edges; // 在线链路存非负时延，离线时按位取反，按输入顺序编号
    vector<vector<pair<int, int>>> adjacency; // 邻接表，每项为邻点和链路编号
    vector<unsigned char> node_online; // 节点是否通电
    array<array<i64, 30>, 30> distance_cache; // 机架间距离，-2 未算，-1 不可达
    vector<i64> distances; // Dijkstra 复用的节点距离表
    vector<pair<i64, int>> distance_heap; // Dijkstra 复用的小根堆
    vector<unsigned char> target_nodes; // 网络节点是否连接至少一个机架

    void initialize(int node_count, int datacenter_count, int rack_count) {
        nodes_per_datacenter = node_count / datacenter_count;
        rack_nodes.resize(rack_count);
        adjacency.resize(node_count);
        node_online.assign(node_count, 1);
        distances.resize(node_count);
        target_nodes.assign(node_count, 0);
        clear_distances();
    }

    void add_link(int from_node, int to_node, i64 latency) {
        int link_id = edges.size();
        edges.push_back(latency);
        adjacency[from_node].emplace_back(to_node, link_id);
        adjacency[to_node].emplace_back(from_node, link_id);
    }

    void clear_distances() {
        for (auto& row : distance_cache)
            row.fill(-2);
    }

    void set_datacenter_online(int datacenter_id, bool is_online) {
        int first_node = datacenter_id * nodes_per_datacenter;
        if (node_online[first_node] != is_online) {
            fill(node_online.begin() + first_node,
                 node_online.begin() + first_node + nodes_per_datacenter, is_online);
            clear_distances();
        }
    }

    void set_link_online(int link_id, bool is_online) {
        if ((edges[link_id] >= 0) != is_online) {
            edges[link_id] = ~edges[link_id];
            clear_distances();
        }
    }

    i64 distance(int from_rack, int to_rack) {
        i64& cached = distance_cache[from_rack][to_rack];
        return cached == -2 ? cached = compute_distances(from_rack, to_rack) : cached;
    }

    i64 compute_distances(int from_rack, int to_rack) {
        int source_node = rack_nodes[from_rack], destination_node = rack_nodes[to_rack];
        if (!node_online[source_node] || !node_online[destination_node])
            return -1;
        if (source_node == destination_node)
            return 0;
        fill(target_nodes.begin(), target_nodes.end(), 0);
        int targets_left = 0;
        for (int node_id : rack_nodes)
            if (!target_nodes[node_id]) {
                target_nodes[node_id] = 1;
                targets_left += node_online[node_id];
            }
        fill(distances.begin(), distances.end(), -1);
        distances[source_node] = 0;
        distance_heap.clear();
        distance_heap.emplace_back(0, source_node);
        while (!distance_heap.empty()) {
            pop_heap(distance_heap.begin(), distance_heap.end());
            auto [distance_so_far, node_id] = distance_heap.back();
            distance_so_far = -distance_so_far;
            distance_heap.pop_back();
            if (distance_so_far != distances[node_id])
                continue;
            if (target_nodes[node_id] && !--targets_left)
                break;
            for (auto [neighbor_id, link_id] : adjacency[node_id])
                if (node_online[neighbor_id] && edges[link_id] >= 0 &&
                    distance_so_far <= numeric_limits<i64>::max() - edges[link_id]) {
                    i64 next_distance = distance_so_far + edges[link_id];
                    if (distances[neighbor_id] < 0 || next_distance < distances[neighbor_id]) {
                        distances[neighbor_id] = next_distance;
                        distance_heap.emplace_back(-next_distance, neighbor_id);
                        push_heap(distance_heap.begin(), distance_heap.end());
                    }
                }
        }
        for (size_t rack_id = 0; rack_id < rack_nodes.size(); ++rack_id)
            distance_cache[rack_id][from_rack] = distance_cache[from_rack][rack_id] =
                distances[rack_nodes[rack_id]];
        return distance_cache[from_rack][to_rack];
    }
};

int main() {
 mt19937_64 rng(0xa2817462ULL);
 for(int trial=0;trial<3000;++trial) {
  int n=2*(4+rng()%27), d=2, r=2+rng()%(min(30,n)-1);
  network_state a; network_state_original b;
  a.initialize(n,d,r); b.initialize(n,d,r);
  for(int i=0;i<r;++i) a.rack_nodes[i]=b.rack_nodes[i]=rng()%n;
  int m=1+rng()%(3*n);
  for(int i=0;i<m;++i) {
   int u=rng()%n,v=rng()%n; i64 w=rng()%15;
   if(trial%17==0) w=(rng()%3==0?LLONG_MAX-rng()%50:rng()%1000);
   a.add_link(u,v,w);b.add_link(u,v,w);
  }
  for(int step=0;step<7;++step) {
   for(int i=0;i<r;++i) for(int j=0;j<r;++j) if(a.distance(i,j)!=b.distance(i,j)) {
    cerr<<"Mismatch "<<trial<<" "<<step<<" "<<i<<" "<<j<<"\n";return 1;
   }
   if(step%3==0) {int dc=rng()%d;bool up=rng()%2; a.set_datacenter_online(dc,up);b.set_datacenter_online(dc,up);}
   else {int e=rng()%m;bool up=rng()%2;a.set_link_online(e,up);b.set_link_online(e,up);}
  }
 }
 cout<<"3000 random dynamic networks (zero and near-overflow weights included): all rack distances identical.\n";
}
