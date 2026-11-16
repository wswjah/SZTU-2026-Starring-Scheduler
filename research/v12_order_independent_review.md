# V12 双顺序事务 rollout 独立只读复核

2026-11-16。只读检查候选、生成器及其可达调用；没有修改候选、生成新策略、编译或运行 benchmark。

- 候选：`candidates/v12_order.cpp`，40,265字节，SHA256 `d2910cf5f57822db01a71b5d54cfadfc2c557dcc45f51ea203d22ebb7e5a1878`。
- 生成器：`tools/v12_order_make.py`，SHA256 `b22c20f5104124cfadba257bd018ea2cf4ef16d40626448732647795d19debec`。
- 底座：`versions/v10_input_fix/main.cpp`。在内存中调用生成器的纯文本 `make` 转换，与当前候选全文相同；没有执行生成器主入口或写回候选。

结论：**在当前 `v12OrderPair → v12OrderEvaluate → tryPlace/flowEstimate` 调用范围内，未发现可复现的公共状态回滚遗漏或试跑命令泄漏。** 该结论限于下述代码和前提，不是运行测试、所有合法输入正确性或时限证明。

## 修改入口与首次触摸

`runJob` 第289行在修改任何状态之前调用 `v12OrderTouchMachine(x)`；`occupy` 第422行也在修改虚拟资源和时间线之前调用同一钩子。

`touch` 第473行先去重机器，保存该机器的真实/虚拟空闲资源、`freedAt`、完整机器缓存、运行作业列表和释放时间线，再按机架去重保存完整架缓存。两作业都落在同一机器时保留第一次修改前的唯一快照；两台机器共享一个架时，架快照同样早于第一台机器的拉取/命中LRU修改。缓存和vector保存是深拷贝，没有把原容器的指针当独立快照。

`release/killNow` 本身没有触摸钩子，但当前 trial 中唯一可达的 KILL 是 `tryPlace` 的同tick预热路径：先 `runJob(ji,bx)`，再 `killNow(ji)`。该机器已在第一次 RUN 前完成保存。试跑不调用 `stopOrDefer`、`drainDeferredKills`、事件处理、网络重算或其他机器的释放，因此当前路径下这不是漏钩子。若以后在 trial 内新增直接释放其他运行作业，必须重新审查这一前提。

## 快照和恢复覆盖

| 被试跑修改的状态 | 保存/恢复范围 | 复核结果 |
| --- | --- | --- |
| 两个目标Job的 `state/mach/t0/prep/ready/res*` 等标量 | `savedJobs` 保存 `offsetof(Job,pre)` 前缀，第462、490行原字节复制 | 当前Job定义的全部标量都位于 `pre` 前，没有覆盖vector对象 |
| `pre/suc` | 无需快照 | 当前试跑只读，不增加/删除依赖，也不增删 `jobs` |
| 当前Flow的 `started/dirty` 等字段 | 保存/恢复整个Flow，第463、491行 | 两个Job在Pair入口检查均属于同一wi，release修改的也是该Flow |
| 租户真实账本及已用配额 | `tenUsed/tenFix/tenRate/tenRateStart` 的前K项，第464、492行 | RUN与同tickKILL的各祖先配额及本租户收费均覆盖；`tenQuota` 和撤销栈本次不变 |
| 机器与架缓存、LRU、sum/in/ver | 每个触摸对象的完整Cache，第476、479、487、489行 | 内容、顺序、容量上限和版本均回退 |
| 实际空闲资源、运行列表、freedAt | 机器journal，第485—487行 | 覆盖RUN、同tickKILL和随后真实RUN |
| 虚拟资源及timeline | `occupy` 前触摸，第486—487行 | 覆盖真实启动和只创建预约的两条路径 |
| `jobEnd/jobTail/jobTheta` | 当前Flow完整 `[first,first+n)`，第466—468、494行 | 包含 `flowEstimate` 向已完成前驱的tail回写；依赖限于题目规定的同工作流DAG |
| `overhead/ovWait/feeAvg/runFee` | 标量保存/恢复，第458、495行 | 第一次/第二次预热费用及在线EMA不会留在另一分支 |
| 命令计数和待输出字符串 | 第458、496行 | 恢复旧commandsUsed并截回原outbuf长度，保留进入trial前已写好的ANS和真实命令 |
| `v12OrderActive` | 构造后置this；rollback先置空，第470、483行 | 非嵌套RAII事务，析构自动回退；`restored`避免二次恢复 |

`Job` 静态断言要求standard-layout，`Flow`静态断言要求trivially-copyable（第460—461行）。在当前定义中，`Job::pre` 前只有int/double字段及布局填充；通过unsigned-char存储与memcpy复制对象表示，不会复制、覆盖或析构 `pre/suc` 的vector控制块。没有把字节数组强转成未对齐的Job/Flow对象。该做法依赖当前字段布局；若以后将可变标量加到vector之后，前缀快照不再自动覆盖它。

## 静态报价缓存与scratch

原 `tryPlace` 的 `iq/iv` 已全部替换为可统一失效的 `v12OrderIq/v12OrderIv`，没有残留另一套局部静态版本表。回滚恢复缓存版本后，第498行将全部 `v12OrderIv` 清零。按现有非负缓存版本约定，下一次报价必然重新计算，因此假想拉取状态的Iq数值不会因版本回退发生ABA误命中；不必恢复Iq本身。

`tryPlace` 的 `tts/tfs/rfee/cand/qr/qz/qm/qf/nq` 是随后使用前会重新构建的scratch；不可达架不会进入候选列表，其旧槽不会被消费。`flowEstimate` 的 `st/du` 当前工作流每个槽位先清零，再按拓扑序使用。它们没有持久账本或合法性状态需要恢复。

`v12OrderTrials/Searches/Swaps/Copies` 计数故意跨试跑累加，且只在最终END之后写stderr，不参与调度或对账，未恢复不构成公共状态泄漏。

## 预约、配额与预热边界

`v12OrderReservationLive` 第642行与原 `tryPlace` 第513行的预约判定相同，包括 `resM<0` 的暂缓预约。任一目标仍有有效预约时直接回退普通调度，不先试跑修改其预约。

`v12OrderIndividual` 同时检查当前真实空闲CPU/内存、机器上线、静态容量、租户到根的配额以及输入可达性。`transferCost` 尽管接收非const引用，当前实现只读Job，const_cast没有写入目标。入口检查只证明两个任务分别可立即运行；它不替代组合约束。实际每次 `tryPlace` 仍先重新检查当时配额，并通过virtual资源/timeline判断机器等待，因第一个任务占用而使第二个失败或预约是合法试跑结果。

命令预算仍由原 `tryPlace/runJob/killNow` 维护：普通RUN占1条，预热先检查完整3条余额，然后RUN→KILL→RUN；不会因为评估两个顺序而绕过20,000条限制。预算不足时产生的Job预约字段、scratch和零次启动结果仍被快照覆盖。试跑前两个目标均要求state=0，故 `result.started` 不会把原有运行任务误算为本次启动。

`deferredKills` 未快照，但当前试跑不调用排队止损接口；入口外原schedule已完成延后KILL清理和Flow止损，不会在事务期间并发执行这些步骤。

## 输出与CPU门控的有限性

试跑的RUN/KILL只追加到 `outbuf`，没有调用真实stdout写入。真实 `fwrite/fflush` 在main第954—955行、整个schedule返回后执行；trial析构已在评分函数返回前恢复输出长度。最后诊断在第958行写stderr，位于最终END之后。

额外门控在schedule和每个Pair入口检查 `late<−0.03 && used<0.65`，之后一对任务的两个分支评估和最终提交作为一个工作单元完成。当前代码没有承诺在每次tryPlace内部再次中止，因此它是限制试跑机会的启发式预算，不是硬时限保证。这里未跑性能验证。

快照回滚还原的是容器内容，不保证还原vector/string的原capacity、分配地址、分配器状态或真实消耗的CPU。深拷贝后move回去可能缩小原有vector容量；outbuf.resize会保留试跑扩出的capacity；全部Iv失效也会增加后续重算。这些不应误报成对账/协议状态错误，但会改变后续运行成本，进而触发CPU保险并影响实际动作。即使最终选择原顺序，仍不能只凭值状态复原推断整条轨迹与未试跑程序完全一致。

本次没有已确认的可复现bug需要修复；应由作者和主任务的事务边界测试、关闭rollout对照及正式生产程序验证继续承担动态证据。默认99分代码、冻结文件和提交状态均未在本复核中修改。
