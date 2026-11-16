# V11 ready-frontier分支的独立审计

日期：2026-11-16。审计对象为`tools/v11_frontier_make.py`及两份候选`cost_only.cpp`、`cost_and_time.cpp`；底座为保留8MiB输入修复的`versions/v10_input_fix/main.cpp`。没有网页访问、正式提交或默认/冻结源码修改。

## 发现并修复的一行通用耦合错误

原底座的pending-job cost是在`du += WK*ovWait`之后按du计CPU费。frontier替换旧费用时却扣除`du-WK*ovWait`，因此WK非零时会残留原队列CPU费。当前两候选固定WK=0，原错误在本轮参数下不改变结果，但未来合并WK调参会不一致。

按主任务授权，仅将两份候选及generator中的一行改为：

`double oldCost=j.c*du[i]*price[rackDc[w.home]]+feeAvg+j.xf;`

重编译生产程序无警告。`research/v11_frontier_manifest.json`保留修复前的source/exe哈希，当前source哈希为：cost_only `e61c401f74067945bee0dc411ef6e6701059afdc4d344e6700096fd8cc3b2038`，cost_and_time `fc1fa7f4e95aa836fe3a521befde9dd90fe5695d3c810a18aefd550883e8a768`。之后测试没有再修改这两份源文件。

定向负对照使用私有测试副本将WK设为0.5，并恢复旧oldCost表达式；独立费用oracle准确报告失败。相同WK=0.5测试副本保留修复行时通过，证明测试确实能捕获该残留费用，而不是只在默认WK=0下形式验证。私有副本仅用于原语测试，没有作为新增调参候选或闭环评测分支。

## 实际helper测试

`tools/v11_frontier_audit.cpp`直接包含实际候选源文件，独立枚举机器/输入/镜像成员估价，并在完整`flowEstimate()`调用前后检查真实状态快照。两份实际WK0候选、两份WK0.5控制副本各通过2,022项数值对照，共8,088项；恢复旧行的负对照按预期失败。

覆盖项包括：

- 普通启动/预热现金、一次或两次传输费、预测准备与运行时长，按`cash+theta*prep`选机。
- 叶与祖先的当前headroom由调用方汇总；单作业超过headroom、机器down、物理容量不足、free CPU/内存不足、输入不可达时拒绝报价。
- 首次报价、重复memo命中、机器缓存清空但content ver不变时，FAIL epoch增加可使报价正确作废。
- DAG含DONE前驱、当前ready、运行中及尚未ready作业，含非零工作流起始下标；检查cost、rem、work、tail、theta全部一致。
- 尚未开工流程、left>8不触发修正；真实job字段、缓存次序/成员/容量/版本、账单、配额占用、机器资源、实际运行列表、输出与命令计数不被helper修改。

结果保存在`results/v11_frontier_audit.json`，私有WK控制与负对照副本位于`results/v11_frontier_audit/`。测试入口改名原main造成的隐式返回警告属于harness，实际候选生产编译没有该警告。

## 计价与缓存判定

普通现金估价是首次registry费+一次输入网络费+单位运行费×(prep+估计计算时长)；预热现金是同一首次registry费+两次输入网络费+单位运行费×(输入准备+估计计算时长)。同tick首RUN/KILL不产生运行费，现有规则支持这个费用分解。

预热预测仅在镜像distinct层大小之和不超过机器缓存容量时使用。首次完整镜像访问后这些层可同时驻留，所以紧邻的第二RUN确实不需再拉层；重复层通过seen去重后检验容量是正确的。但首次registry/rack量仍按当前成员集合估计，没有模拟层序访问中的LRU淘汰。因此这是成员近似报价，不能称为真实精确启动费用；该限制已由manifest明确标注。

成员报价memo只依赖machine/rack成员版本及机器FAIL epoch，不依赖LRU次序。cacheHit只调整次序而不改变这类报价，不作废memo合理；cachePut改变成员版本，FAIL虽不改原content ver却增加单独epoch，能覆盖清空机器缓存。没有修改Cache布局、真实cacheHit/cachePut或runJob。

## rem/work/tail一致性

cost_only有意仅替换现金预测，沿用底座时间与工作量；这是预先定义的隔离试验，而不是忘记更新time字段。cost_and_time把已获得报价的ready作业du改为报价持续时间，随后从零重新计算st、rem、work、jobTail与jobTheta。未被替换的待运行作业work仍去掉WK队列项，与底座work口径相同；替换后的即时放置作业使用真实报价prep+estimate，不再叠加旧队列项。DONE作业du/st已由底座置0，不会重新引入完成任务的费用或路径。

选报价时采用原粗估时间产生的jobTheta，再根据选定du重算最终theta，属于一次前向更新，没有迭代求固定点。因此不能声称报价已在最终theta下重新优化过。外层对rem做BB增长、五情景收益估算、优先级和止损仍按原流程进行。

## 个体报价的限制

每个ready作业使用同一份当前free资源、headroom和缓存快照，helper不会为前一个报价预留资源或模拟缓存修改。因此多个报价可能同时指向同一台机器、合计超过配额，或者把本来可共享的一次镜像拉取重复计费。它既不是joint-frontier排程，也不是整个流程必能同时落机的证明；可能低估等待，也可能高估重复拉取费用。

预测helper没有按剩余command budget检验预热3条是否在本tick还能发出。它只提供资源/输入可行的个体费用预测；真正执行仍由未修改的tryPlace检查20,000上限并预留完整预热批次，故不会因此发出非法半批。测试特意保留commandsUsed=19999时调用helper，确认没有发出或扣除指令，但不能把该时刻报价称为“指令预算也满足的即时执行方案”。

## 保留项与结论

8MiB输入缓冲区、来源署名、非Windows clock表达式、真实账单/缓存/配额/命令实现均保留。时间保险条件本身仅增加旁路统计，并在最终END后向stderr输出摘要；额外计算仍可能消耗CPU，应由闭环数据核验，不因总CPU低便推断阶段保险从未触发。

修复oldCost通用耦合后，没有发现第二处确定的实现错误。主任务负责两候选的训练收益及时间保险诊断，本审计不重复bench，也不把原语通过解释为策略能提高利润或正式分数。
