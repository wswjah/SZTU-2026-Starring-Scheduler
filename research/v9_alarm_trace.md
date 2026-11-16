# V9 告警故障观测数据

底座为冻结V8，只采集旁路观测，不改变调度策略、不拟合模型。
事件处理完且schedule前，将本tick在线状态及告警/日志计数留在内存；最后END刷新后才向stderr导出CSV。包含tick0与下线机器，用于完整重建未来FAIL标签；未来事件没有进入在线特征。

训练16例全部正常，27,953次对账正确，0非法指令；共1,511,414行、1,266次FAIL。
完整judge报告逐例与V8生产程序相同：True。前两例standard00/light00先核验，再完成其余14例。
CSV第一行是#V9_TRACE元数据（T/M/W及导出前CPU），第二行为列名。bench统计含导出成本，不能将其当成正式调度耗时。每例日志行数、解码字符数与judge报告逐例相等。

字段：tick,machine,up,dc,cpu,mem,alarm,loglines,decoded_chars,max_line_score,fail,up_event,last_fail_tick。alarm为本tick全部行的告警分和；max_line_score为本tick最大单行告警分；decoded_chars包括分隔符；fail/up_event为本tick已观察的事件。last_fail_tick可由历史事件重建，不包含未来。
机器/场景编号只供联结，不宜当模型数值特征；可由原始磁带计算过去3/8/W tick窗口和距最近FAIL时间。训练时只将当前在线行作为风险起点，并将未来标签窗口被T截断的行删失处理。

文件：results/v9_alarm_trace/<case>/solver_stderr.txt；tapes.json提供哈希和元数据；summary.json提供完整评测报告；equivalence.json提供逐例等价结果。未使用任何新留出集或学校隐藏数据。
