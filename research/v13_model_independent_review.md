# V13 小模型独立实现审查

2026-11-16。本审查读取trace、训练、策略和production源码及已有训练工件，并运行获主任务同意的固定状态/数值harness；没有重训、读取留出结果选参、运行交互评测、修改候选或提交。原作者的实验说明保留在v13_model_review.md，本文件独立记录审查证据。

结论：**未发现需要先修改候选的阻断问题。** 首跑时点、标签、世界分组、浮点特征、实际树与四个门控，以及选中strict的运行时精简，均通过下述有限核对；不能据此把条件预测解释为因果最优动作或保证正式加分。

## 绑定对象

- 底座：`versions/v12_scan_input_fix/main.cpp`，SHA256 `d59972ba208958bca0688f432515e60edee920815596eb32644415d461224828`。
- 诊断源：`candidates/v13_model/trace.cpp`，SHA256 `c03d521e97c68e24afb6c1e4d76b19f51f654297dcbd33e51949f8fdcadea211`。
- 完整strict源：`candidates/v13_model/veto_strict.cpp`，SHA256 `560c63b3dbcbe6341b315b1b56ef36f0d41dd902d12216bb5cb12ba3d4d5d55c`。
- 生产精简源：`candidates/v13_model/production.cpp`，SHA256 `997d4e112368ca47595585a021c6c9fc7cbbd5e3d09fdc2681afedca43b78983`。
- 数据CSV：`results/v13_model_dataset/admitted.csv`；摘要、数组和完整树见 `research/v13_model_tree.json`、`results/v13_model_fit/`。

## 数据时点及标签

trace只在原schedule真正调用flowEstimate、乘BB并计算五情景rev之后缓存rem/work/cost/rev/tick，不为特征额外调用会写jobTheta/Tail的flowEstimate。特征在机器已选中、等待为零、完整RUN批次预算满足后，任何预热RUN之前采集。独立seen只置一次，避免w.started在两次预热RUN之间仍为false而覆盖首次快照。

当前窗口按首跑时的 `max(1,min(T,dl+grace-1)-now)` 定义；预测年龄使用当前now减缓存tick；rem已是BB后值，捕获时没有重复放大或混用未来完成时间。selected prep是原报价bs的估计值，不等于实际LRU执行后的真实prep。配额/余量沿真实祖先链计算，输入费只读当前可见输入和路由。ID/seed不在18特征内。

真实标签费用独立累计每次runJob的tf及qreg*Ureg、每次release的cp*(now-t0)，并给最终仍运行作业补到T+1；预热两次RUN、零时长KILL和重试都计入。收益按真实最后DONE和整数迟到折扣计算。作者的32世界对账记录显示逐Flow总和与judge的earned/run/pull/net/cost/profit逐项相等，且诊断完整报告32/32等于底座；本审查复用该核验记录，没有重新采集。

41,151条训练记录全部seen且first_tick>=1，未开始的7,516条流程仅作全账本核验，未当失败负标签。目标是原99分策略条件下earned/value及clip(net/value,-2,1)，不是完工概率，也不是拒绝后的反事实收益。裁剪用于回归，闭环总利润仍使用原始实值。

## 训练工件独立复算

`tools/v13_model_audit_dataset.py` 从既有CSV重新构造全部41,151×18 float32、两个目标、32个世界编号，均与保存数组精确一致。各世界总权重相同，4折训练/测试世界不相交，每个世界恰好折外一次；保存的常数预测逐项等于该折仅训练世界的加权均值，未使用全数据均值。

由保存的OOF/constant数组独立重算MSE，精确等于记录：earned 0.1266446658/0.1717441172，net 0.1135719777/0.1783251577。最终15节点、8叶仅读索引5和10，即forecast_net_per_value与当前tenant_duration_factor。相对常数改善不等于相对现有启发式有同等幅度改善，更不证明利润必升。

证据：`results/v13_model_audit/dataset.json`。没有执行新的fit。

## 实际C++特征及树推理

`tools/v13_model_audit_features.cpp` 直接包含实际trace和tree.inc，不改源码。四个固定状态覆盖forecast_age>0、BB后rem、T与dl+grace窗口截断及clamp到1、非数字排序的父节点链1→3→0、祖先quota/headroom、估计准备期/预热、当前输入传输费。Python从fixture原始状态独立手算18项，再转float32，**72项全部逐位相同**。

helper调用前后额外检查Job标量、Flow、租户账本、预测数组、命令/outbuf和EMA未变。另查询72个已有训练样本及7个内部树节点各3个相邻float32边界，**93条实际C++双输出与Python树和原训练输出全部精确相同**。这里没有声称复原了每个真实首RUN的完整状态。

证据：`results/v13_model_audit/features_tree.json`；对应工具v13_model_audit_features.py/.cpp。

## 门控、预约回滚及预热边界

四个实际policy均只在 `!w.started`、立即放置且完整批次预算足够、任何RUN前调用模型。已有运行流程不进入新流门槛；FAIL后待运行重试仍保留started=true。早于门控的配额不足、活预约和预算不足分支维持原行为。

拒绝使用 `array<unsigned char,offsetof(Job,pre)>` 备份进入tryPlace前的标量对象表示，并memcpy回原Job。未typed读取可能未初始化的resM/resAt/resEnd；pre/suc向量不在复制范围内。首次新流可能带有这些未定义旧预约字节，直接用double/int局部变量读取保存会有问题，本实现已避免。拒绝不留下原quote暂写的resAt/resM/resT，避免额外3tick重试延迟；真实缓存、账本、配额和输出均尚未改动。

`tools/v13_model_audit_gate.cpp` 分别直接包含四份实际policy。固定状态测试通过：低收益新流拒绝的原始字节恢复及零真实副作用、预热仅余2条预算、配额不足、resM<0的活暂缓预约、正常机器预约的原occupy、已开工重试绕过gate且仍执行完整3条预热。另对n门槛、树区域、两种收入混合的等式附近ULP做**376条实际C++布尔决策查询**，与独立Python精确相同。

light全局无动作可直接由叶值证明：最小net预测0.0388084421已经高于拒绝阈值0.02。strict仅拒绝最低叶，该叶x5<=0.0867041163，自动满足额外x5<0.4，且须n>=3；其余叶net>=0.1183538250。因此在相邻叶值间细调net门槛可能不会改变任何动作，不能将这类参数配置重复算成不同有效策略。

作者另提供保留完整helper和树推理、仅关闭gate的2世界完整报告等价控制；light的32世界无拒绝且完整报告32/32相同。两者证据范围不同，没有将2例disabled说成32例disabled。

证据：`results/v13_model_audit/gate.json`。这些均为非交互harness，不重复作者的实际评测。

## Production精简

只读调用生产生成器的纯文本make，与当前production全文一致。tree.inc和strict布尔条件完整保留；cache的cost/rev仍在同一原schedule位置保存。实际树仅使用x5/x10，精简helper的两个float32算式与原18维helper相同，未使用槽位置零；不再计算quota、准备量和预测年龄等未被树/strict消费的值。

真实Job原始字节备份/拒绝恢复、!started范围、预算和预约分支均保留。直接包含实际production复做固定状态测试及同一94条决策查询，使用的两个float32、树预测和strict布尔结果与完整源参考精确一致，源码哈希未变。

证据：`results/v13_model_audit/production.json`，工具v13_model_audit_production.py。该结果证明固定函数/状态用例的等价，不能单凭它证明所有CPU保险轨迹相同：删除未用字段、遍历和诊断会改变分配与耗时。主任务另报告打包生产程序在80新场景、4压力和2样例共86次完整judge报告逐例等于完整strict，400条长日志ANS也精确；本审查没有重复这86次评测。

最终生产提交文件由主任务另行冻结为20,309字节、SHA256 `b7ed699acbe7cd1bfd03fbd68fc35bc1432a52b031df574af620167c63e20a34`。本独立审计未修改默认99分代码、候选、冻结版本、模型阈值或正式提交状态。
