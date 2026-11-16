#include <bits/stdc++.h>
#include <unistd.h>
using namespace std;typedef long long ll;
#define F(i,n) for(int i=0;i<(int)(n);i++)
char inbuf[1<<16],tok[1<<22];int inpos,inlen;int getch(){if(inpos==inlen){inlen=read(0,inbuf,sizeof inbuf);inpos=0;if(inlen<=0)return-1;}return inbuf[inpos++];
}int readTok(){int c=getch(),n=0;while(c==' '||c=='\n'||c=='\r')c=getch();while(c>' ')tok[n++]=c,c=getch();tok[n]=0;return n;}ll readInt(){readTok();return atoll(tok);
}int T,D,N,R,M,K,L,I,P,W,E,now;ll Breg,Brack,Bnet,Ureg,Unet,price[8];struct Cache{vector<int>q;ll cap,sum;int ver;char in[400];};Cache rackCache[30],machCache[360];
int rackDc[30],rackNode[30];int machRack[360],machCpu[360],machMem[360],freeCpu[360],freeMem[360],machUp[360];vector<int>machJobs[360];ll alarmAt[360][602];
int edgeU[1000],edgeV[1000],edgeW[1000],edgeUp[1000],dcDown[8],netDirty=1;vector<int>adj[600];ll rackDist[30][30];int tenPar[200],tenOrder[200];ll tenQuota[200],tenUsed[200],tenFix[200],tenRate[200],tenRateStart[200];
double tenDur[602],tenEst[602];vector<pair<int,ll>>undoStack;int layerSize[400];vector<int>imageLayers[120];int huffChild[20][2],huffRoot;vector<array<int,8>>acGo;
vector<ll>acVal;struct Job{int id,wf,c,m,e,img,s,zin,zout,state,mach,t0,prep,outRack,need,ready;int resM,resAt,resT;double resEnd,xt,xf;vector<int>pre,suc;
};struct Flow{int id,tenant,dl,arrive,first,n,left,dead,endT,started,home,dirty,adm;double key;ll v;};vector<Job>jobs;vector<Flow>flows;unordered_map<int,int>jobIndex;
string outbuf;ll runFee;int freedAt[360];bool cacheHit(Cache&c,int l){if(!c.in[l])return 0;c.q.erase(find(c.q.begin(),c.q.end(),l));c.q.push_back(l);return 1;
}void cachePut(Cache&c,int l){c.q.push_back(l);c.in[l]=1,c.ver++;c.sum+=layerSize[l];while(c.sum>c.cap){int o=c.q[0];c.sum-=layerSize[o];c.in[o]=0;c.q.erase(c.q.begin());
}}ll nodeDist[30][600];char rowDirty[30];void recomputeNet(){static int q[1024];static char in[600];int per=N/D;F(a,R)if(rowDirty[a]){ll*d=nodeDist[a];
F(i,N)d[i]=1e18;int s=rackNode[a],h=0,t=0;if(!dcDown[s/per])d[s]=0,q[t++]=s;while(h!=t){int u=q[h++&1023];in[u]=0;for(int e:adj[u]){int v=edgeU[e]^edgeV[e]^u;
if(edgeUp[e]&&!dcDown[v/per]&&d[u]+edgeW[e]<d[v]){d[v]=d[u]+edgeW[e];if(!in[v])in[v]=1,q[t++&1023]=v;}}}F(b,R)rackDist[a][b]=d[rackNode[b]]>9e17?-1:d[rackNode[b]];
rowDirty[a]=0;}netDirty=0;}double allDur,allEst,allRunD,allRunE,tenRunD[602],tenRunE[602],tenF[602];double tenFactor(int o){return tenF[o];}void updateFactors(){
double pool=(allDur+allRunD+100.*1.5)/(allEst+allRunE+100.);F(o,K)tenF[o]=(tenDur[o]+tenRunD[o]+30.*pool)/(tenEst[o]+tenRunE[o]+30.);}void release(int ji){
Job&j=jobs[ji];int x=j.mach,o=flows[j.wf].tenant;ll cp=j.c*price[rackDc[machRack[x]]];freeCpu[x]+=j.c;freeMem[x]+=j.m;freedAt[x]=now;flows[j.wf].dirty=1;
machJobs[x].erase(find(machJobs[x].begin(),machJobs[x].end(),ji));tenFix[o]+=cp*(now-j.t0);tenRate[o]-=cp;tenRateStart[o]-=cp*j.t0;for(int a=o;a>=0;a=tenPar[a])tenUsed[a]-=j.c;
j.state=0;j.ready=now,j.resT=0;}ll dst(int a,int b){return a==b?0:rackDist[a][b]<0?99:rackDist[a][b];}bool transferCost(Job&j,int r,ll&tt,ll&tf,ll&away){
tt=tf=away=0;int k=j.pre.size();for(int i=j.s<0?0:-1;i<k;i++){int s=i<0?j.s:jobs[j.pre[i]].outRack;ll z=i<0?j.zin:jobs[j.pre[i]].zout;if(s==r)continue;
ll d=rackDist[r][s];if(d<0)return 0;tt=max(tt,d+(z+Bnet-1)/Bnet);tf+=z*d*Unet;if(i>=0)away=max(away,d);}return 1;}void runJob(int ji,int x){Job&j=jobs[ji];
int r=machRack[x],o=flows[j.wf].tenant;ll tt,tf,aw,qreg=0,qrack=0;transferCost(j,r,tt,tf,aw);for(int l:imageLayers[j.img]){if(cacheHit(machCache[x],l))continue;
if(cacheHit(rackCache[r],l))qrack+=layerSize[l];else qreg+=layerSize[l],cachePut(rackCache[r],l);cachePut(machCache[x],l);}ll cp=j.c*price[rackDc[r]];j.prep=max(tt,(qreg+Breg-1)/Breg+(qrack+Brack-1)/Brack);
j.state=1;j.mach=x;j.t0=now;freeCpu[x]-=j.c;freeMem[x]-=j.m;machJobs[x].push_back(ji);tenFix[o]+=runFee=tf+qreg*Ureg;tenRate[o]+=cp;tenRateStart[o]+=cp*now;
for(int a=o;a>=0;a=tenPar[a])tenUsed[a]+=j.c;outbuf+="RUN "+to_string(j.id)+" "+to_string(x)+"\n";}ll slackOf(int ji){Flow&w=flows[jobs[ji].wf];static ll es[1<<16],tl[1<<16];
ll cp=0;F(i,w.n){Job&j=jobs[w.first+i];es[i]=0;tl[i]=0;if(j.state>1)continue;for(int p:j.pre)if(jobs[p].state<2)es[i]=max(es[i],es[p-w.first]+jobs[p].e);
cp=max(cp,es[i]+j.e);}for(int i=w.n-1;i>=0;i--){Job&j=jobs[w.first+i];if(j.state>1)continue;tl[i]+=j.e;for(int p:j.pre)tl[p-w.first]=max(tl[p-w.first],tl[i]);
}return cp-es[ji-w.first]-tl[ji-w.first];}double jobEnd[1<<17],jobTheta[1<<17],jobTail[1<<17],overhead=3,ovWait=1,feeAvg=50;vector<pair<double,ll>>timeline[360];
int virtCpu[360],virtMem[360];vector<int>rackMachs[30];double revenueAt(Flow&w,double f){ll g=max(5,(w.dl-w.arrive)/3);if(f<=w.dl)return w.v;if(f>=w.dl+g)return 0;
return w.v*(w.dl+g-f)/g;}void flowEstimate(Flow&w,double&rem,double&work,double&cost){static double st[1<<16],du[1<<16];double f=tenFactor(w.tenant);ll pr=price[rackDc[w.home]];
rem=work=cost=0;F(i,w.n){Job&j=jobs[w.first+i];st[i]=du[i]=0;if(j.state>1)continue;for(int p:j.pre)st[i]=max(st[i],st[p-w.first]+du[p-w.first]);du[i]=j.state?jobEnd[w.first+i]-now:j.e*f+1.*overhead+j.xt;
work+=j.c*du[i];if(!j.state)du[i]+=0.*ovWait;cost+=j.state?j.c*du[i]*price[rackDc[machRack[j.mach]]]:j.c*du[i]*pr+feeAvg+j.xf;rem=max(rem,st[i]+du[i]);
jobTail[w.first+i]=0;}ll g=max(5,(w.dl-w.arrive)/3);for(int i=w.n-1;i>=0;i--){int ji=w.first+i;Job&j=jobs[ji];if(j.state>1)continue;jobTail[ji]+=du[i];
for(int p:j.pre)jobTail[p]=max(jobTail[p],jobTail[ji]);double path=st[i]+jobTail[ji],x=(now+path-w.dl)/(1.*path+1)+1;jobTheta[ji]=5.*j.c+w.v*1.0/g*min(1.0,max(0.0,x));
}}void chooseHome(Flow&w){double best=1e18;F(h,R){double tot=0;F(i,w.n){Job&j=jobs[w.first+i];ll cp=j.c*price[rackDc[h]],d=j.s<0||j.s==h?0:rackDist[h][j.s];
tot+=cp*j.e;if(d<0)tot+=1e9;if(d>0)tot+=j.zin*d*Unet+(d+(j.zin+Bnet-1)/Bnet)*(cp+5.*j.c);}if(tot<best)best=tot,w.home=h;}F(i,w.n){Job&j=jobs[w.first+i];
ll d=j.s<0||j.s==w.home?0:rackDist[w.home][j.s];if(d<0)d=60;j.xt=d?d+(j.zin+Bnet-1)/Bnet:0,j.xf=j.zin*d*Unet;}}double waitFor(int x,int c,int m,double lim){
int fc=virtCpu[x],fm=virtMem[x];if(fc>=c&&fm>=m)return 0;for(auto&q:timeline[x]){if(q.first-now>lim)break;fc+=q.second>>32,fm+=int(q.second);if(fc>=c&&fm>=m)return q.first-now;
}return 1e9;}void occupy(int x,int ji,double end){virtCpu[x]-=jobs[ji].c,virtMem[x]-=jobs[ji].m;pair<double,ll>v(end,ll(jobs[ji].c)<<32|jobs[ji].m);timeline[x].insert(lower_bound(timeline[x].begin(),timeline[x].end(),v),v);
}void tryPlace(int ji){Job&j=jobs[ji];Flow&w=flows[j.wf];for(int a=w.tenant;a>=0;a=tenPar[a])if(tenUsed[a]+j.c>tenQuota[a]){return;}if(j.resT>now&&(j.resM<0||(machUp[j.resM]&&freedAt[j.resM]<j.resAt))){
if(j.resM>=0)occupy(j.resM,ji,j.resEnd);return;}double est=max(1.0,j.e*tenFactor(w.tenant)),best=1e18,th=jobTheta[ji],bw=0,bs=0;int bx=-1,bwarm=0;static ll tts[30],tfs[30];
static double rfee[30];static vector<pair<double,int>>cand;cand.clear();F(r,R){ll aw;if(transferCost(j,r,tts[r],tfs[r],aw)){static ll iq[120][30];static int iv[120][30];
ll&q=iq[j.img][r];if(iv[j.img][r]!=rackCache[r].ver+1){iv[j.img][r]=rackCache[r].ver+1,q=0;for(int l:imageLayers[j.img])if(!rackCache[r].in[l])q+=layerSize[l];
}rfee[r]=1.*q*Ureg;pair<double,int>v={rfee[r]+tfs[r]+th*(tts[r]+1.*aw*!j.suc.empty())+j.c*price[rackDc[r]]*(tts[r]+est),r};int k=cand.size();if(k<12.)cand.push_back(v);
else if(v.first<cand[--k].first);else continue;for(;k&&v.first<cand[k-1].first;k--)cand[k]=cand[k-1];cand[k]=v;}}if(1.>0){static int qr[8][5],nq[8];static ll qz[8][5];
static double qm[8][5],qf[8][5];int ns=0,sj[8];for(int si:j.suc){Job&s=jobs[si];int k=0;if(s.s>=0)qr[ns][k]=s.s,qz[ns][k++]=s.zin;for(int p:s.pre)if(p!=ji&&k<5&&(jobs[p].state||1.>0)){
Job*q=&jobs[p];for(int it=0;it<3&&!q->state&&q->s<0&&q->pre.size();it++)q=&jobs[q->pre[0]];qr[ns][k]=q->state>1?q->outRack:q->state?machRack[q->mach]:q->s<0?w.home:q->s,qz[ns][k++]=jobs[p].zout;
}if(!k||ns>7)continue;F(a,k){qm[ns][a]=qf[ns][a]=0;F(b,k){ll d=dst(qr[ns][a],qr[ns][b]);if(d)qm[ns][a]=max(qm[ns][a],double(d+(qz[ns][b]+Bnet-1)/Bnet)),qf[ns][a]+=qz[ns][b]*d;
}}nq[ns]=k,sj[ns++]=si;}if(ns){for(auto&cr:cand){int r=cr.second;F(i,ns){double sth=jobTheta[sj[i]]+jobs[sj[i]].c*price[rackDc[r]],stayT=0,stayF=0;F(a,nq[i]){
ll d=dst(r,qr[i][a]);if(d)stayT=max(stayT,double(d+(qz[i][a]+Bnet-1)/Bnet)),stayF+=qz[i][a]*d;}double la=sth*stayT+Unet*stayF;F(a,nq[i]){ll d=dst(r,qr[i][a]);
la=min(la,sth*max(d?double(d+(j.zout+Bnet-1)/Bnet):0,qm[i][a])+Unet*(j.zout*d+qf[i][a]));}cr.first+=1.*la;}}sort(cand.begin(),cand.end());}}for(auto&cr:cand){
int r=cr.second;cr.first-=rfee[r];if(cr.first>=best)continue;for(int x:rackMachs[r]){if(!machUp[x]||machCpu[x]<j.c||machMem[x]<j.m)continue;double wt=waitFor(x,j.c,j.m,(best-cr.first)/(th+1e-9));
if(cr.first+th*wt>=best)continue;ll qreg=0,qrack=0;for(int l:imageLayers[j.img])if(!machCache[x].in[l])(rackCache[r].in[l]?qrack:qreg)+=layerSize[l];ll s=max(tts[r],(qreg+Breg-1)/Breg+(qrack+Brack-1)/Brack);
double cost=cr.first+qreg*Ureg+(j.c*price[rackDc[r]]+th)*(s-tts[r])+th*wt;double warm=cr.first+qreg*Ureg+tfs[r]+th*wt;int wm=1.>0&&warm<cost;if(wm)cost=warm,s=tts[r];
if(cost<best)best=cost,bx=x,bw=wt,bs=s,bwarm=wm;}}j.resAt=now,j.resM=-1,j.resT=now+3.;if(bx<0||bw>30.)return;if(bw>0){j.resM=bx,j.resEnd=now+bw+bs+est,j.resT=now+min(4.,bw*.5);
occupy(bx,ji,now+bw+bs+est);return;}int rdy=j.ready;ll fee0=0;if(bwarm&&!bw){runJob(ji,bx);fee0=runFee;outbuf+="KILL "+to_string(j.id)+"\n";release(ji);
j.ready=rdy;}runJob(ji,bx);runFee+=fee0;w.started=w.dirty=1;overhead=overhead*.98+.02*max(0.0,j.prep-j.xt);ovWait=ovWait*.98+.02*min(12.,double(now-j.ready));
feeAvg=feeAvg*.98+.02*(runFee-j.xf);jobEnd[ji]=now+j.prep+est;occupy(bx,ji,jobEnd[ji]);}void schedule(){double used=clock()*1./CLOCKS_PER_SEC,late=used-.08-.62*now/T;
if(used>.93||(late>0&&now%(1<<min(5,int(late/.04)))))return;updateFactors();allRunD=allRunE=0;F(i,K)tenRunD[i]=tenRunE[i]=0;F(x,M){virtCpu[x]=freeCpu[x],virtMem[x]=freeMem[x];
timeline[x].clear();for(int q:machJobs[x]){double el=max(0,now-jobs[q].t0-jobs[q].prep);int o=flows[jobs[q].wf].tenant;if(el>jobs[q].e*tenF[o])allRunD+=el,tenRunD[o]+=el,allRunE+=jobs[q].e,tenRunE[o]+=jobs[q].e;
timeline[x].push_back({jobEnd[q]=max(now+1+.25*el,jobEnd[q]),ll(jobs[q].c)<<32|jobs[q].m});}sort(timeline[x].begin(),timeline[x].end());}updateFactors();
vector<pair<double,int>>order;F(wi,flows.size()){Flow&w=flows[wi];if(w.dead||!w.left)continue;if(w.dirty||(late<0&&(now+wi)%int(6.)==0)){double rem,work,cost,rev=0;
flowEstimate(w,rem,work,cost);static const double sc[5]={-1,-.5,0,1,2};rem*=1+.03*log(w.left);F(k,5){double f=now+rem*(1+.4*sc[k]);if(f<=T+30.||!1.)rev+=revenueAt(w,f)/5;
}if(!1.&&now+rem>T)rev=0;w.dirty=0,w.key=1;if(rev>cost*(w.started?1.:1+0.)){w.key=-(rev-cost)/(work+1)*(w.started?3.:1)/(1+1.*max(0.0,(w.dl-now-rem)/rem));
}else if(w.started){w.dead=1;F(i,w.n)if(jobs[w.first+i].state==1){outbuf+="KILL "+to_string(jobs[w.first+i].id)+"\n";release(w.first+i);}}else if(revenueAt(w,now+rem*.6)<=0)w.dead=1;
}if(w.key<0&&!w.dead)order.push_back({w.key,wi});}sort(order.begin(),order.end());for(auto&o:order){Flow&w=flows[o.second];static vector<pair<double,int>>ready;
ready.clear();F(i,w.n){Job&j=jobs[w.first+i];if(j.state==0&&j.need==0)ready.push_back({-jobTail[w.first+i],w.first+i});}sort(ready.begin(),ready.end());
for(auto&q:ready)tryPlace(q.second);}}int main(){T=readInt(),D=readInt(),N=readInt(),R=readInt(),M=readInt(),K=readInt();L=readInt(),I=readInt(),P=readInt(),W=readInt(),E=readInt();
Breg=readInt(),Brack=readInt(),Bnet=readInt(),Ureg=readInt(),Unet=readInt();F(i,D)price[i]=readInt();F(i,R)rackDc[i]=readInt(),rackNode[i]=readInt(),rackCache[i].cap=readInt();
F(i,M){machRack[i]=readInt(),freeCpu[i]=machCpu[i]=readInt(),freeMem[i]=machMem[i]=readInt();machCache[i].cap=readInt(),machUp[i]=1;rackMachs[machRack[i]].push_back(i);
}F(i,E){edgeU[i]=readInt(),edgeV[i]=readInt(),edgeW[i]=readInt(),edgeUp[i]=1;adj[edgeU[i]].push_back(i),adj[edgeV[i]].push_back(i);}F(i,K)tenPar[i]=readInt(),tenQuota[i]=readInt();
{int cnt=0;vector<char>seen(K);while(cnt<K)F(i,K)if(!seen[i]&&(tenPar[i]<0||seen[tenPar[i]]))seen[i]=1,tenOrder[cnt++]=i;}F(i,L)layerSize[i]=readInt();
F(i,I){int k=readInt();while(k--)imageLayers[i].push_back(readInt());}{ll wt[20];char alive[20]={};F(i,9)wt[i]=readInt(),alive[i]=1;for(int id=9;id<17;
id++){int pick[2];F(k,2){int b=-1;F(i,id)if(alive[i]&&(b<0||wt[i]<wt[b]))b=i;alive[b]=0,pick[k]=b;huffChild[id][k]=b;}wt[id]=wt[pick[0]]+wt[pick[1]],alive[id]=1;
}huffRoot=16;}{acGo.push_back(array<int,8>());acVal.push_back(0);F(i,P){int n=readTok(),u=0;F(k,n){int c=tok[k]-'a';if(!acGo[u][c])acGo[u][c]=acGo.size(),acGo.push_back(array<int,8>()),acVal.push_back(0);
u=acGo[u][c];}acVal[u]+=readInt();}vector<int>fail(acGo.size()),que;F(c,8)if(acGo[0][c])que.push_back(acGo[0][c]);F(qi,que.size()){int u=que[qi];acVal[u]+=acVal[fail[u]];
F(c,8){int v=acGo[u][c];if(v)fail[v]=acGo[fail[u]][c],que.push_back(v);else acGo[u][c]=acGo[fail[u]][c];}}}F(a,R)rowDirty[a]=1;for(;;){if(!readTok())break;
now=readInt();int ne=readInt(),nq=readInt();while(ne--){readTok();string ev=tok;if(ev=="DONE"){int ji=jobIndex[readInt()];Job&j=jobs[ji];Flow&w=flows[j.wf];
int o=w.tenant;tenDur[o]+=now-j.t0-j.prep,tenEst[o]+=j.e,allDur+=now-j.t0-j.prep,allEst+=j.e;release(ji);j.state=2;j.outRack=machRack[j.mach];for(int s:j.suc)jobs[s].need--,jobs[s].ready=now;
w.left--;if(!w.left)w.endT=now;}else if(ev=="FAIL"){int x=readInt();while(machJobs[x].size())release(machJobs[x][0]);machUp[x]=0;Cache&c=machCache[x];c.q.clear(),c.sum=0;
memset(c.in,0,400);}else if(ev=="UP"){int x=readInt();machUp[x]=1;}else if(ev=="DCDOWN"||ev=="DCUP"){dcDown[readInt()]=ev.size()>4,netDirty=1;F(a,R)rowDirty[a]=1;
}else if(ev=="LDOWN"||ev=="LUP"){int e=readInt(),u=edgeU[e],v=edgeV[e];edgeUp[e]=ev.size()<4,netDirty=1;F(a,R){ll x=nodeDist[a][u],y=nodeDist[a][v];if(edgeUp[e]?x+edgeW[e]<y||y+edgeW[e]<x:x+edgeW[e]==y||y+edgeW[e]==x)rowDirty[a]=1;
}}else if(ev=="QUOTA"){int t=readInt();undoStack.push_back({t,tenQuota[t]});tenQuota[t]=readInt();}else if(ev=="UNDO"){int k=readInt();while(k--)tenQuota[undoStack.back().first]=undoStack.back().second,undoStack.pop_back();
}else if(ev=="LOG"){int x=readInt(),b=readInt(),u=huffRoot,st=0;readTok();ll sc=0;F(i,b){int h=tok[i/4],bit=((h<='9'?h-'0':(h|32)-'a'+10)>>(3-i%4))&1;u=huffChild[u][bit];
if(u<9){st=u<8?acGo[st][u]:0;sc+=acVal[st];u=huffRoot;}}alarmAt[x][now]+=sc;}else{Flow w;w.id=readInt(),w.tenant=readInt(),w.v=readInt(),w.dl=readInt(),w.n=w.left=readInt();
w.arrive=now,w.first=jobs.size(),w.dead=w.started=w.adm=0,w.dirty=1,w.key=1;F(i,w.n){Job j;j.id=readInt(),j.c=readInt(),j.m=readInt(),j.e=readInt(),j.img=readInt();
j.s=readInt(),j.zin=readInt(),j.zout=readInt(),j.need=readInt();j.state=0,j.wf=flows.size(),j.ready=now,j.resT=0;F(k,j.need){int p=jobIndex[readInt()];
j.pre.push_back(p);jobs[p].suc.push_back(jobs.size());}jobIndex[j.id]=jobs.size();jobs.push_back(j);}if(netDirty)recomputeNet();chooseHome(w);flows.push_back(w);
}}if(netDirty)recomputeNet();outbuf="ANS";while(nq--){readTok();char q=tok[0],q2=tok[1];int a=readInt();ll ans=0;if(q=='B'){static ll sub[200];F(i,K)sub[i]=tenFix[i]+tenRate[i]*now-tenRateStart[i];
for(int i=K-1;i>0;i--)sub[tenPar[tenOrder[i]]]+=sub[tenOrder[i]];ans=sub[a];}else if(q=='H'){ans=1e18;for(;a>=0;a=tenPar[a])ans=min(ans,tenQuota[a]-tenUsed[a]);
}else if(q=='R'&&q2=='O')ans=rackDist[a][readInt()];else if(q=='A'){for(int t=max(1,now-W+1);t<=now;t++)ans+=alarmAt[a][t];}else if(q=='S')ans=slackOf(jobIndex[a]);
else ans=(q=='C'?machCache[a]:rackCache[a]).sum;outbuf+=" "+to_string(ans);}outbuf+="\n";schedule();outbuf+="END\n";fwrite(outbuf.data(),1,outbuf.size(),stdout);
fflush(stdout);if(now==T)break;}}
