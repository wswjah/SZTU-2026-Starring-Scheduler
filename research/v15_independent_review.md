# V15 32→128训练扩展独立审查

2026-11-16。本审查只读计划、输入、既有训练/导出源码和训练工件，重算数组、权重、标准化、预算及已有C++数值输出；没有重训、执行C++或交互评测、修改候选、读取V15留出/确认利润或提交。

结论：**未发现阻断实现问题。** 新输入隔离、128世界合并、固定epoch/step控制、折内规范化、导出与原门控集成均通过下述有限检查。更多训练数据或更低条件预测误差本身不保证闭环利润、正式分数或AC。

## 输入隔离与训练分布

独立读取旧32、新96、新holdout40、confirmation40的参数文件和冻结manifest，逐文件SHA及manifest SHA均匹配。配置用排序键及Decimal规范化数值计算语义hash，包含seed；空白、键顺序或浮点写法不同不会逃过重复检查。

新96+新40+40共176个seed及完整语义cfg hash均唯一，并与cases下636个历史参数配置无重叠。合并的128训练世界与新80评估世界按seed和语义cfg hash完全分离，没有将旧验证集提升为训练集。这里只读取输入参数，没有读取新评估利润。

新96除seed外，逐profile精确等于旧V13训练32：8个原profile各新增12个种子，旧每profile4个，合并后每profile16个。该实验增加同一名义分布的独立世界数，不是扩展到新的训练profile分布。

证据：`research/v15_input_independent_audit.json`；工具 `tools/v15_independent_input_audit.py`。

## 128世界数据、标签与权重

- 全流程194,313；实际入场164,406＝旧41,151＋新123,255。
- admitted CSV SHA256：`8522b19c49f114cc32827e33a72fbfc3bf1de1214c0021615da18b1dfc06a30b`。
- arrays NPZ SHA256：`0e9f9c1fcf4116221ee357d42fb7e6565a41b72fcee30c6b65039a6305315979`。

旧/新世界分别用 `v13/`、`v15/` 前缀，128个键与预期输入集合完全相同；world_names、worlds、group_to_case和groups逐项一致，未把不同目录同名fast_00等合并为一个世界。

从合并CSV独立重建全部x(float32)、两个y、groups和weights，与NPZ逐项精确相等。旧32的all/admitted CSV去掉前缀后，与原V13数据逐行数值相同。训练仅使用seen且实际runs>0的入场流程；其余29,907条零入场流程不作为失败标签，实际费用和收益均为零。

权重统一按全部128世界构造 `N/128/count[group]`，每世界总权重相等、全局均值1。旧32总体权重精确为1/4，新96为3/4；不是把旧/新两块各占一半而使旧世界过重。

本审查还按128个世界将CSV的earned/cost/run/pull/net/profit重新求和，与各自99分baseline完整报告逐项精确一致；逐流程finish对应的整数迟到收益也全部重算相等。不可开始流程没有伪造反事实失败标签，已开始未完成者保留真实零收益及全部尝试费用。

dataset采集代理另已逐份核对不变trace与baseline的完整报告等价、真实RUN/预热/重试/release及T+1尾费账本；新96两套共192次实际运行、335,032次对账全对，late/guard计数为零。本独立审查复用该观测证据，并自行重聚合CSV到baseline，没有重复192次交互。

证据：`research/v15_dataset_independent_audit.json`、采集代理的 `research/v15_dataset.json`；工具 `tools/v15_independent_dataset_audit.py`。

## 训练计划及预算控制

四个模型与原门控在fit前固定，全部进入相同的新80世界，不按本轮训练利润另筛门槛或结构：

| 模型 | 模型设置 | 原门控 | 最终fit预算 |
| --- | --- | --- | --- |
| A128_120 | 18→16→2，seed141116 | 原A的25%收入混合 | 120epoch／19,320 updates |
| B128_120 | 18→16→8→2，seed141117 | 原B strict | 120epoch／19,320 updates |
| tree128 | depth3／minleaf500／seed131116 | 原strict | 固定一次树拟合 |
| A128_steps | 与A相同 | 原A的25%收入混合 | 每fit精确4,920 updates |

训练仍为float64、raw线性输出世界加权MSE、Adam lr.003/wd1e-4/batch1024、固定seed和单CPU线程；标签保持原范围，输入按折内mean/std及1e-6下限规范化并clip[-8,8]，只在评估/推理clip输出。没有早停、best epoch、额外seed或结果后阈值搜索。

128全训练164,406行，每epoch161批。A/B固定120epoch的最终更新为19,320、样本呈现19,728,720次，独立计数一致。A128_steps精确4,920次更新，即30个完整epoch加第31个epoch的90批，样本呈现5,024,340次。每个新折也固定4,920，折内norm及计数均逐折核对。

旧A32最终120×ceil(41,151/1024)＝4,920 updates，样本呈现4,938,120次。故A128_steps**仅对齐旧最终fit的Adam更新次数**，没有对齐旧折预算、epoch数、样本呈现数、规范化或梯度数据分布。固定120epoch在更多数据上同时增加更新数，因此不能将两者差异全部归因于数据量；step对照用于帮助辨别这一耦合，而不是完全消除所有训练差异。

## 折分、规范化与预测工件

逐模型检查4折完整世界不相交、128世界各折外一次。独立从每折训练行重算weighted mean/std、常数预测，与保存工件逐项精确一致；最后部署fit才使用全部128训练世界。OOF、训练折常数及旧v13/新增v15两个族的MSE均从保存数组重算，与记录精确相同。

三份MLP的全部164,406条最终Torch预测，用独立NumPy前向复算，最大误差依次为A128_120 5.00e-16、B128_120 5.55e-16、A128_steps 4.44e-16。所有C++ mean/std及各层权重/bias字面量与模型JSON逐项精确相等，维度和行序维持原[输出][输入]导出约定；隐藏ReLU、末层线性及两个输出clip范围未改。

tree128的全部最终预测与JSON树精确一致，C++节点/阈值/叶值字面量精确一致；15节点、8叶，每叶实际样本数均≥500，各叶均覆盖128世界。新树仅使用forecast_net_per_value，不据此将它解释为因果动作价值或通用完工概率。

## C++数值输出与原门控集成

对作者已执行的数值查询，独立重建同一输入并读取保存的C++输出，没有再次编译/执行：A128_120与A128_steps各1,743条、B128_120 1,744条，C++/NumPy误差均小于9e-16；tree128 1,189条、8叶及阈值邻域均精确。另有逐标量bias-first行序复算作为归约顺序核对。

四份实际候选全文逐项等于：对应原V13门控源码只替换predictor和诊断前缀。A两版仍为原25%混合，B/tree仍为原strict；原18维首RUN前helper、!started限制、配额/预约/等待/批次预算次序、8MiB/scanner、原始字节预约回滚和真实费用实现均保留。没有新增运行中模型止损或typed读取未初始化旧res字段。

数值harness的四公式比较仍有已明确的边界：blend使用float32 x2/x4比率重组，不是直接调用运行时的raw-double forecast.Allow。实际源码核对证明raw forecast原式未改；公式查询相等不能夸大成每个真实阈值边界的完备验证。该限定不是已发现的候选错误。

证据：`research/v15_model_independent_audit.json`，对应工具 `tools/v15_independent_model_audit.py`；作者C++数值记录 `research/v15_numeric.json`、`results/v15_numeric/`。四源、模型、数据和计划的完整哈希均保存在上述JSON及 `research/v15_models.json`。

本审查0次新fit、0次C++执行、0次新交互；未读取本轮新80世界的利润。这里只能确认实验隔离与实现证据，主任务负责闭环收益比较、压力/生产验证及任何后续正式提交授权。

## 主80选择之后的额外40输入核对

主任务在主80结果已见后选择扩训B继续确认，先记录v15_postconfirmation_plan.json并固定baseline、旧A32、旧B32、扩训B128四源，再增加独立40新种子。独立检查这40个manifest/文件SHA、seed2021116287+i×104729及仅换seed的32原profile+8shift布局均吻合；40个seed和含seed语义cfg hash内部唯一，并与812个历史参数输入及train128完全无重叠。四个当前版本manifest与计划快照的规范化hash相同，可读源/提交源/实际exe也全部匹配冻结hash。新证据见research/v15_postconfirmation_input_review.json。这属于选择后的额外独立确认，不能说成最初80计划的一部分；原128数据审查结论不变。本段未读取额外40的任何结果或利润，没有新训练、交互或源文件修改。
