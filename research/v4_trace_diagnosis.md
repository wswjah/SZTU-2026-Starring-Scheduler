# V4 工作流级诊断与数据字段

2026-11-14。基于当前正式 85 分源码，诊断程序为 `candidates/v4_trace.cpp`。它只在正常调度之外记录旁路状态，并在最后一条协议回复后向 stderr 导出 CSV；任何事后结果均未参与决策。根目录源码未改，未访问学校或提交。

## 数据与一致性

- 完整 train16：26,420 条流程，19,616 条至少执行过一次 RUN，6,804 条未开工。
- `results/v4_trace/first_admissions.csv`：只保留已首跑流程，供训练首跑时风险校准。
- `results/v4_trace/all_flows.csv`：全部流程，保留未开工样本但不能将其视为“本来无法完成”的负标签。
- `results/v4_trace/<case>/flows.csv`：各世界单独数据。
- `results/v4_trace/diagnosis.json`、`trace_manifest.json`：聚合与指纹。
- 16 例均零对账错、零非法；完整 judge 报告与 `results/v3_final_aggressive/summary.json` 中对应 train 记录逐例相同。逐流程成本与收益求和精确等于 judge 总成本与收益；各流程 `cost = run + pull + net`、`run = prep_run + compute_run`。
- train16 包含原有两个 large 边界压力例，日志量超过保守的 3,000,000 字符；本数据作为训练诊断使用，不冒充 16 个均在题面范围的正式验证。

## 主要洞见

16 例合计花费 45,987,118、收益 98,503,314。其中已开工未完成的流程花费 **7,259,594**、收益为零；已完成却净亏的流程总净亏 **666,406**。最主要的负贡献来自未完成投入，而不是完成后成本略高于收益。

| 世界 | 未完成已开工流程数 | 这类沉没费用 | 已完成净亏 |
| --- | ---: | ---: | ---: |
| standard_00 | 176 | 385,618 | 9,130 |
| heavy_00 | 392 | 1,009,512 | 90,469 |
| slow_00 | 194 | 315,541 | 39,761 |
| small_00 | 89 | 186,462 | 11,644 |
| fast_00 | 135 | 259,301 | 10,875 |

不能把这些沉没费用都归因于故障。上述世界的未完成流程中，没有任何作业 FAIL 中断的流程分别有 86、249、145、56、68 个，花费分别为 149,935、662,715、250,500、103,267、121,618。也不能把这些量直接当成可全部回收的利润上界：拒绝这些任务会改变资源、缓存与后续调度，必须闭环重跑检验。

首跑预测也有明显不确定性：例如 standard_00 中 176 个未完成已开工流程，有 129 个首跑时预测可在 deadline 前完成；heavy_00 对应为 275/392，slow_00 为 128/194。相反，已完成流程的实际工期/首跑计划工期中位数约 0.81～0.92。只用完成样本校准时长，会丢掉最困难的未完成尾部，不能据这些中位数简单降低所有时长。

自动改架确实频繁：standard_00 为 422/982 个已开工流程，heavy_00 为 738/1674，slow_00 为 253/556。未完成组改架比例更高，但流程规模、故障、持续时间等同时影响改架机会，相关性不能视为因果。主代理已闭环检验强锚定并观察到退步，因此本统计不支持直接固定机架。

在线机器 CPU 核时利用率在上述世界约为 35.0%、55.0%、15.0%、25.7%、61.7%。这是容量占用口径，不是“这些空闲 CPU 全都可以盈利地利用”的证明：配额、单机内存、机架定位、依赖和收益门槛都会限制可用任务。`ready_tick_avg` 也含依赖已满足但未必具备配额/收益条件的就绪项。

## 可作为首跑时模型输入的字段

除下表后见结果外，以下量均在首条 RUN 真正修改缓存、资源和账单之前记录。

| 字段 | 精确定义 |
| --- | --- |
| `case`, `id`, `tenant` | 数据联结键；随机世界编号/流程编号/租户原始编号不具备跨世界稳定含义，不宜直接当模型特征。 |
| `arrival`, `deadline`, `grace`, `value`, `job_count`, `root_jobs` | 到达 tick、截止、宽限、名义价值、作业数、无前驱作业数。均在到达时已知。 |
| `first_start` | 首条实际 RUN 的 tick，之后没有更新。 |
| `first_cost` | 首跑 `place_job` 头部校验当前计划、必要时重算后得到的 `flow.remaining_cost`；85 分版本为 `1.1 * flow.plan_cost`。包含整个未完成流程的预估费用，不是仅首个作业费用。 |
| `first_plan_cost` | 同一时点未经 1.1 安全系数放大的 `flow.plan_cost`。 |
| `first_time` | 同一时点的 `flow.remaining_time`；`place_job` 已将其设为当前 `flow.plan_duration`。不是该流程最终真实工期，也不含首跑后未来排队事实。 |
| `first_plan_duration` | 同一时点的 `flow.plan_duration`，与这里的 `first_time` 应相同。 |
| `first_factor` | 首跑时该租户当前已学到的 `duration_factor`。 |
| `first_estimated_work` | 首跑时 `flow.estimated_work`，即未完成作业输入估时 × 核数之和，尚未乘租户时长倍率。 |
| `first_path_quota` | 首跑前路径最小总配额 `quota_limits[tenant]`。 |
| `first_headroom` | 首跑前实时调用 `remaining_quota(tenant)` 的结果，包含本 tick 此前其他 RUN 已占用的配额。 |
| `first_rack` | 首跑前工作流的 preferred rack。 |
| `first_actual_rack` | 首条 RUN 最终选择机器所在 rack；可能因输入就近执行与 preferred rack 不同。 |
| `first_rack_cores` | 首跑 preferred rack 当前在线机器的总 CPU 核数；不是空闲核数。preferred rack 无效时为 -1。 |
| `first_rack_workload` | 首跑前该 preferred rack 的当前 `rack_workload`，未加本流程本次入场的剩余核时。 |
| `first_prepare` | 首条 RUN 选中机器的精确 `best_prepare_time`，即真实输入传输准备和镜像准备的最大值；在发 RUN 前已可计算。它不等于整个流程的预测准备时间。 |
| `first_immediate` | 首条 RUN 的精确 `best_fee`（本次输入传输费＋仓库拉取费），在启动时立即收取。 |
| `first_job_cores`, `first_job_estimated_duration` | 首个选中作业的 CPU 需求与输入估计时长，不是事后真实时长。 |
| `first_deadline_slack` | 分析脚本派生的 `deadline - first_start - first_time`；未开工为缺失。 |

现有数据不含首跑时租户/全场样本数，没有为这两列重复运行完整世界。浮点首跑量当前由 C++ 默认 6 位有效数字导出，适合初步校准但不是原 double 的逐位备份。`first_immediate` 等整数费用用 128 位整数转换输出，无浮点截断。

## 仅可作为标签/诊断的后见字段

| 字段 | 定义 |
| --- | --- |
| `finish` | 最后一个作业完成 tick；未完成为 -1。 |
| `runs` | RUN 尝试总数，重启会重复计数。 |
| `failed_jobs`, `killed_jobs` | 分别被 FAIL、KILL 中断的运行尝试次数；不是去重作业数。 |
| `done_jobs`, `end_running` | 最终完成的去重作业数、结束仍在运行的作业数。 |
| `end_ready` | 最终状态为待运行且依赖已满足的作业数，含过期后已被移出 ready 表的作业，不表示最终还能合法盈利地启动。 |
| `earned` | 真实完成时间按题面折扣、整除得到的收益；未完成为零。 |
| `cost` | 独立仿射账单 `offset + rate*(T+1)`，包含全部尝试的费用。 |
| `net`, `pull` | 所有 RUN 实际发生的输入传输费、仓库拉取费。 |
| `run`, `prep_run`, `compute_run` | 全部尝试运行费，以及其中实际占用在准备期、计算期的费用。 |
| `interrupted_run`, `interrupted_fees` | 被 FAIL/KILL 的尝试所花运行费、该尝试启动即付费用；已完成尝试不计入。 |
| `auto_changes` | 已开工后 choose_rack 提交的 preferred rack 变化总数。 |
| `auto_valid_changes` | 其中从一个有效 preferred rack 变到另一个不同有效 rack 的次数；不含成功救急 reroute。 |
| `auto_to_none` | 其中改为无有效 preferred rack 的次数。 |
| `reroutes` | try_reroute 实际成功启动作业的救急换架次数，失败后回滚的尝试不计。 |
| `rack_runs_N` | 最终所有 RUN 尝试落在各 rack 的次数。 |
| `profit`, `category` | 分析脚本派生的最终净收益与四类结果，不得作为当时输入。 |

`first_admissions.csv` 的未完成标签表示“在当前 85 分策略这条实际轨迹下没有完成”，不等价于该流程不可完成，也不提供某个未执行动作的反事实收益。被中断或最终未完成的作业没有完整真实时长标签。
