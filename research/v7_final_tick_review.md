# V7：最后tick清理

基线为冻结96分源码经 `tools/v7_portable_clock.adapt` 适配后的进程CPU时间版本。没有改根目录默认文件、没有新调参或更广终局启发式、没有访问学校或提交。

只添加一个分支：在 `schedule` 的 `drainDeferredKills` 之后、CPU保险之前，若 `now==T`，按20,000指令预算对仍运行的作业发出 `killNow`，然后直接返回，不再启动新作业。

DONE事件已在本tick调度前处理。题面真实运行时长至少1，已知T之后无法产生工作流收入；T时新启动的作业来不及完成。停止余下作业可省最后一个tick的运行费。若运行作业多于剩余命令预算，严格只停止预算容许的部分，不产生非法KILL或半套预热。与其它终局估价变化相比，这一分支不猜未来工期。

## 实际对照

对照数据为 `results/v7_cpu_screen/baseline`，候选运行完整train16。逐例输入和评测机哈希由compare校验。

- 16/16 `earned` 精确相同；16/16利润提高、费用下降。
- 所有拉取费pull和网络费net精确相同，全部成本减少都等于run费减少。
- 全16节省6,937，利润70,679,876→70,686,813（约+0.0098%）。
- 按保守日志范围排除large两个边界例后，14例节省6,238，利润54,438,029→54,444,267（约+0.0115%）。
- 全16对账正确、零非法指令；观测最大CPU0.453125秒，不作为同期提速结论。

完整逐case的earned/cost/run/pull/net核验在 `results/v7_final_tick_train/dominance.json`。有CPU自适应的不同二进制理论上仍可能在T之前走出不同轨迹；本次16例已实际确认收入相同，不能把这个经验结果扩张成所有不同编译环境都必然严格支配。

## 边界回归

`tools/test_v7_final_tick.cpp` 直接调用未改候选的schedule：T时停止所有在跑作业、禁止新RUN；预算只剩1条或已满仍遵守上限；已DONE的延后请求会过期，另一个真实运行作业只被终止一次；账单、配额、运行费率精确对账。全部通过，记录见 `results/v7_final_tick_train/focused_test.json`。测试将main重命名后include，编译器提示被重命名的入口无显式return；该入口未调用，生产源码独立编译没有此提示。

候选为 `candidates/v7_final_tick.cpp`，可复现生成工具 `tools/make_v7_final_tick.py`，程序 `build/v7_final_tick.exe`。完整指纹见 `research/v7_final_tick_manifest.json`。结果小但规则明确，可考虑与更强候选合并，不建议单独花一次正式提交。

后续可以研究“剩余DAG最少运行步数已超过T剩余时间”的提前停止，但本轮没有混入该启发式。
