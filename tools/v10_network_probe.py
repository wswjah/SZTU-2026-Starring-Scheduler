"""Exercise actual full protocol ROUTE/HEAD/ALARM against independent oracles."""
from pathlib import Path
import hashlib
import heapq
import json
import random
import subprocess
from v10_fix_input import huffman_codes

ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/"results/v10_network_probe"


def one(seed):
    rng=random.Random(seed)
    T,D,N,R,M,K,W,E=600,5,600,30,30,200,60,1000
    racks=[(r//6,(r//6)*120+r%6) for r in range(R)]
    edges=[(i,i+1,rng.randint(1,20)) for i in range(N-1)]
    while len(edges)<E:
        u,v=rng.sample(range(N),2);edges.append((u,v,rng.randint(1,20)))
    adj=[[] for _ in range(N)]
    for e,(u,v,w) in enumerate(edges):adj[u].append((v,w,e));adj[v].append((u,w,e))
    up=[True]*E;dcdown=[False]*D
    order=[0]+rng.sample(list(range(1,K)),K-1)
    parent=[-1]*K
    for pos in range(1,K):parent[order[pos]]=rng.choice(order[:pos])
    quota=[rng.randint(0,100) for _ in range(K)];undo=[]
    patterns={"a":3,"aa":5,"abab":7,"b":2}
    freq=[1,1,2,3,5,8,13,21,34];codes=huffman_codes(freq)
    alarm=[[0]*M for _ in range(T+1)]
    lines=[f"{T} {D} {N} {R} {M} {K} 1 1 {len(patterns)} {W} {E}","1 1 1 1 1","1 1 1 1 1"]
    lines += [f"{dc} {node} 1" for dc,node in racks]
    lines += [f"{x} 1 1 1" for x in range(M)]
    lines += [f"{u} {v} {w}" for u,v,w in edges]
    lines += [f"{parent[i]} {quota[i]}" for i in range(K)]
    lines += ["1","1 0"," ".join(map(str,freq))]
    lines += [f"{p} {weight}" for p,weight in patterns.items()]
    expected=[];events_total=0

    def distance(a,b):
        start,end=racks[a][1],racks[b][1]
        if dcdown[start//120] or dcdown[end//120]:return -1
        q=[(0,start)];dist={start:0}
        while q:
            score,u=heapq.heappop(q)
            if score!=dist[u]:continue
            if u==end:return score
            for v,w,e in adj[u]:
                if not up[e] or dcdown[v//120]:continue
                value=score+w
                if value<dist.get(v,10**18):dist[v]=value;heapq.heappush(q,(value,v))
        return -1

    for tick in range(1,T+1):
        events=[]
        for _ in range(rng.randrange(1,7)):
            e=rng.randrange(E);up[e]=not up[e];events.append(("LUP" if up[e] else "LDOWN")+f" {e}")
        if tick%17==0:
            dc=rng.randrange(D);dcdown[dc]=not dcdown[dc]
            if dcdown[dc]:
                events += [f"FAIL {x}" for x in range(M) if racks[x][0]==dc]
                events.append(f"DCDOWN {dc}")
            else:
                events += [f"UP {x}" for x in range(M) if racks[x][0]==dc]
                events.append(f"DCUP {dc}")
        for _ in range(rng.randrange(3)):
            if undo and rng.randrange(3)==0:
                count=rng.randint(1,min(3,len(undo)));events.append(f"UNDO {count}")
                for _ in range(count):node,old=undo.pop();quota[node]=old
            else:
                node=rng.randrange(K);value=rng.randrange(101);undo.append((node,quota[node]));quota[node]=value
                events.append(f"QUOTA {node} {value}")
        for _ in range(rng.randrange(3)):
            x=rng.randrange(M)
            if dcdown[racks[x][0]]:continue
            text="".join(rng.choice("aab_") for _ in range(rng.randint(12,45)))
            bits="".join(codes[8 if c=="_" else ord(c)-97] for c in text)
            encoded="".join(format(int((bits+"000")[i:i+4],2),"x") for i in range(0,len(bits),4))
            events.append(f"LOG {x} {len(bits)} {encoded}")
            alarm[tick][x]=sum(weight*sum(text.startswith(p,i) for i in range(len(text))) for p,weight in patterns.items())+alarm[tick][x]
        queries=[];answers=[]
        for i in range(3):
            a,b=rng.randrange(R),rng.randrange(R)
            if i==0 and tick%4==0:b=a
            queries.append(f"ROUTE {a} {b}");answers.append(distance(a,b))
        node=rng.randrange(K);head=10**18
        for_ancestor=node
        while for_ancestor>=0:head=min(head,quota[for_ancestor]);for_ancestor=parent[for_ancestor]
        queries.append(f"HEAD {node}");answers.append(head)
        x=rng.randrange(M);queries.append(f"ALARM {x}");answers.append(sum(alarm[t][x] for t in range(max(1,tick-W+1),tick+1)))
        lines.append(f"TICK {tick} {len(events)} {len(queries)}");lines.extend(events);lines.extend(queries)
        expected += ["ANS "+" ".join(map(str,answers)),"END"];events_total+=len(events)
    data=("\n".join(lines)+"\n").encode("ascii")
    run=subprocess.run([str(ROOT/"build/v8_fine.exe")],input=data,capture_output=True,cwd=ROOT,timeout=20)
    actual=run.stdout.decode("ascii").replace("\r\n","\n").splitlines()
    assert run.returncode==0 and actual==expected,(seed,run.returncode,next(((i,a,b)for i,(a,b)in enumerate(zip(actual,expected))if a!=b),None))
    (OUT/f"seed_{seed}.in").write_bytes(data)
    return {"seed":seed,"ticks":T,"queries":T*5,"events":events_total,"all_answers_exact":True,"initialization":{"D":D,"N":N,"R":R,"M":M,"K":K,"E":E,"W":W},"protocol_sha256":hashlib.sha256(data).hexdigest()}


if __name__=="__main__":
    OUT.mkdir(parents=True,exist_ok=True)
    results=[one(seed) for seed in [103991,104021]]
    (OUT/"summary.json").write_text(json.dumps(results,indent=2),encoding="utf8")
    print(json.dumps(results))
