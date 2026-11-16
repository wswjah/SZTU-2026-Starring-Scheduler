# V13 strict生产精简：策略完全等价

2026-11-16。原始研究候选`veto_strict.cpp`和模型均未修改。精简副本为`candidates/v13_model/production.cpp`，SHA256 `997d4e112368ca47595585a021c6c9fc7cbbd5e3d09fdc2681afedca43b78983`，36,569字节，O2生产编译无警告。

仅计算实际树使用的两列：`x5=float((cached_rev-cached_cost)/max(1,value))`与`x10=float(tenFactor(tenant))`。保持原float32转换顺序及原schedule预测缓存时点，只保留cost/rev，移除不用的roots/rem/work/tick维护、其它16列特征、额外transferCost/父链遍历、诊断计数与stderr输出。15节点树常量、strict门槛条件、原tryPlace预约scalar字节回滚、8MiB缓冲区、署名头及原CPU保险保留。

非交互测试分别直接包含原strict和生产副本，对2,176个同输入查询比较：两列float32位模式、两预测输出及gate判定的输出全文精确相同。覆盖全部8叶、内部阈值邻近float32、jobs1/2/3/4和forecast margin0.4邻值；允许1,600、拒绝576。Python独立遍历保存的树也逐项精确一致。

本精简子任务没有跑交互或读取新验证集。CPU保险仍依赖实际执行时间，所以最终完整报告等价与时限记录由主任务打包后统一验证，不以原语相等替代端到端验证。

可复现工具：`tools/v13_model_production.py`、`v13_model_production_test.cpp`、`v13_model_production_test.py`；证据：`research/v13_model_production.json`、`v13_model_production_test.json`及`results/v13_model_production_test/`。
