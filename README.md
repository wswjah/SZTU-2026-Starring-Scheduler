# 星环算力调度：一次从公开基线到99分的迭代记录

这个仓库记录「星环算力平台调度」的一段完整探索：从公开的81分程序出发，逐步验证到正式99分，也保留没有带来提升的调参、性能优化、故障预测和小模型实验。希望后来的同学既能找到可读代码，也能少走一些已经试过的弯路。

截至2026年11月17日，**最高正式成绩仍为99/100**。V8首次达到99分；最新V16只合入长日志缓冲区修复，正式提交546181仍为99分，现已作为根目录 [main.cpp](main.cpp) 和 [submit.cpp](submit.cpp) 的默认版本。V15扩训神经网络正式为98分，没有采用该模型；本项目尚未取得100分。

整个过程建立在两份公开工作的基础上：早期路线来自 [Misuzu0010的81分程序](https://github.com/Misuzu0010/SZTU-2026-data-structure-final-homework)，后期96→99分路线的主体来自 [Shuang-su的96分程序](https://github.com/Shuang-su/SZTU-2026-data-structure-final-homework)。两位作者的代码与分析是这段探索的基石，来源和派生关系在本文及[致谢](docs/ACKNOWLEDGEMENTS.md)集中记录。

## 从哪里开始

| 想了解什么 | 入口 |
| --- | --- |
| 当前正式99分的代码 | [main.cpp](main.cpp)、[submit.cpp](submit.cpp)、[V16冻结版本](versions/v16_buffer_only/)；[原V8冻结版本](versions/v8_fine/)继续保留 |
| V1—V16做过什么、哪些方向失败了 | [完整实验历程](docs/EXPERIMENT_JOURNEY.md) |
| 仅缓冲区修复的正式验证 | [V16回执](research/official_v16_buffer_only.md)、[实际提交文件本地验证](research/v16_buffer_only_submit_validation.json) |
| 后续输入边界与整数读取修复 | [V10边界复现](research/v10_experiment.md)、[V12输入/扫描修复分支](versions/v12_scan_input_fix/) |
| 首次接纳的小回归树 | [V13模型实验](research/v13_model_experiment.md)、[精简实现](versions/v13_model_fast/) |
| 小神经网络与扩训 | [V14实验](research/v14_experiment.md)、[V15实验](research/v15_experiment.md)、[扩训说明](research/v15_training_report.md) |
| 来源及贡献范围 | [ACKNOWLEDGEMENTS.md](docs/ACKNOWLEDGEMENTS.md) |

版本号表示探索阶段，较新的版本不一定更好。V8正式99分原件保持冻结；V16沿用其全部调度逻辑与参数，仅将token缓冲区从4MiB扩大到8MiB，没有合入神经网络或直接整数扫描。V12输入/扫描分支也保留，但没有单独正式分数。需要研究或继续修改时，请按目标选择对应版本。

## 正式成绩

下面只列实际正式评测结果，和本地利润表分开记录。

| 阶段 | 正式分数 | 提交编号 | 公开回执 |
| --- | ---: | ---: | --- |
| V1：早期改进 | 84 | 543386 | [记录](research/official_submission.md) |
| V3：卡常与偏激进策略 | 85 | 543440 | [记录](research/official_v3_aggressive.md) |
| V3：偏保守策略 | 84 | 543441 | [记录](research/official_v3_conservative.md) |
| V4：首跑风险树与末作业估价 | 85 | 543899 | [记录](research/official_v4_risk_terminal.md) |
| V6：Shuang-su基底的署名派生修复 | 96 | 543902 | [记录](research/official_v6_attributed96.md) |
| V8：有限调参与末tick清理 | **99** | **544054** | [记录](research/official_v8_fine.md) |
| V15：扩训网络B与输入修复 | 98 | 544377 | [记录](research/official_v15_B128_120.md) |
| V16：仅长日志缓冲区修复 | **99** | **546181** | [记录](research/official_v16_buffer_only.md) |

当前V16的**正式提交文件与公开提交文件字节一致**，均为17,538字节，SHA256为`d84158ac1f864dfcc5642eafe400bf482f3cc8e5a8f54775eed36cf1fec49417`。此次正式提交前已经按要求移走开头四行说明，来源继续记录在本文与致谢中。此前V8正式原件为17,821字节，SHA256为`bafff023f3cc6c19ca3259bd4ce81123b9a58cd4c118cd9a6d9c1e19b162c706`，冻结原件未被覆盖。较早版本的公开副本删除了指定头注释，C++ token序列相同，但字节数及SHA可能不同；各版正式原件与发布副本的指纹分列于[发布清单](PUBLICATION_MANIFEST.json)。参考目录的第三方原件保留原样。

V16从实际提交文件重新编译，无编译警告；300万解码字符、600万十六进制字符的长日志构造中，400条答案全部精确。两个原生样例及标准、快速、故障、告警压力共6个场景，10,216次对账全对、零非法指令，完整评测报告与V8逐份一致。直接协议构造与本地TPJ场景分开计数，详见[验证记录](research/v16_buffer_only_submit_validation.json)。V10此前60次TPJ运行、112,146次对账及完整报告等价结果仍保留。

公开副本另经独立重编与复跑：400条长日志答案全对，4个已公开场景10,116次对账全对、零非法指令，完整报告仍与V8相同；[复跑摘要](research/v16_public_archive_validation.json)与上述历史6场景分列。这4例属于已有开发/压力场景，未当作新的独立验证集。

正式平台没有公开逐测试点的利润、目标及失败详情，剩余失分原因仍未知。V16修复了可复现的输入边界问题，但通过数没有增加；不能认定V8与V16仍是同一个测试点失败，也不能据总状态定位原因。**本地总利润增加，不等于正式多通过一个测试点**；正式98分的结果也不能直接归因为网络、输入修复、对账或耗时中的某一项。

## 本地运行

本项目主要在Windows与MinGW环境验证。普通调度程序需要支持C++17的编译器，评测脚本使用Python 3.10及以上；训练模型另需NumPy、scikit-learn和PyTorch。导出的C++调度程序不需要这些训练框架。

请自行从课程提供的材料取得`tpj_win.exe`，放在仓库根目录。**仓库不分发评测机二进制**。它负责生成世界并与调度程序交互，不能用普通的单向输入重定向代替。

在仓库根目录打开PowerShell，例如先运行一个小场景：

```powershell
New-Item -ItemType Directory -Force build | Out-Null
g++ -std=c++17 -O2 main.cpp -o build/main.exe
python tools/bench.py --exe build/main.exe --cases cases/v13_train32/small_00.in --out results/local_smoke --workers 1
```

`tools/bench.py`直接连接调度程序与本地评测机，保存每例报告和`summary.json`，检查退出状态、对账错误与非法指令。它不登录网站，也不提交代码。批量比较时，请让基线和候选使用同一批输入与同一个评测机；性能测量宜单独串行、交错先后顺序，避免把并发和等待时间当成算法变化。

V16另提供适配公开源码的[复核入口](tools/v16_verify_release.py)，可以自行生成长日志协议。只复核400tick长日志、不需要评测机：

```powershell
python tools/v16_verify_release.py --protocol-only
```

使用自备评测机比较V8与V16的完整报告：

```powershell
python tools/v16_verify_release.py --judge tpj_win.exe
```

后一命令默认运行4个公开场景。正式提交前的6场景、10,216次对账记录还包含2个原生样例；原生样例不随仓库发布，如已自行取得可加`--with-samples`。因此默认公开复跑的场景数和对账总数不应与历史6场景记录混用。

`cases/`内的`.in`是本地生成器参数，包含种子，不是官方隐藏测试。原始样例、边界构造和超出题面范围的压力场景应分开解读；历史记录已将发现的超范围场景单列。仓库中的参数与manifest可帮助重建输入，但不能重建官方利润门槛。

## 仓库内容与复现范围

| 目录 | 内容 |
| --- | --- |
| `main.cpp`、`submit.cpp` | 对应正式99分的阅读版与提交版发布副本 |
| `versions/` | 各阶段代码发布副本与冻结记录 |
| `candidates/` | 有效、失败或未晋升的实验候选 |
| `tools/` | 本地评测、生成、打包、训练与检查工具 |
| `research/` | 选取的阶段报告、计划、模型参数与核验记录 |
| `results/` | 利润比较、健康统计等聚合证据 |
| `cases/` | 本地场景参数、种子与manifest |
| `docs/` | 实验历程、致谢和阅读说明 |

公开仓库保留阶段入口、种子、训练与导出代码、模型权重及结果摘要，不上传全部原始机器日志、训练大表和逐次运行目录。部分历史脚本依赖这些未收录材料或原实验路径，所以这里不承诺所有历史步骤一条命令即可完整复跑。可以直接编译冻结C++版本，用自备评测机验证公开参数，并沿报告追踪每项结论的依据。认证、会话和网页提交工具不属于本仓库内容。

## 读实验结果前

题面通过条件同时涉及对账、指令合法性和利润门槛`ceil(q·P*)`。其中`P*`是出题方参考程序在知道未来信息后的利润，题面没有将它定义为全局最优利润。因此`q>1`不能证明该测试点不可能通过，也不能由此推出约90分的理论上限。

对账全对、局部估价更精确、预测误差更低、同批场景总利润更高，分别回答不同问题。我们把正收益、退步、无效优化与正式回落一并留下，希望这份记录能帮助后来的人继续验证、理解和改进。
