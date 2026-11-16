# V11 直接整数扫描试验

2026-11-15。基于冻结`versions/v10_input_fix/main.cpp`，仅替换readInt；readTok、8MiB文本/十六进制缓冲区、真实账本及调度估价完全不改。没有默认/冻结源码修改或正式提交。

旧readInt先把数字逐字符复制进tok，再调用atoll；新函数直接从getch累积整数。负数直接负向累积，避免先取LL_MIN绝对值的溢出；可选+、负号、零、空白、末尾EOF均处理。实现只保证可表示的合法整数输入，不宣称为超出long long范围或混入非数字的非法字段定义新语义。

## tok副作用逐处审计

初始化数值、镜像层号、赫夫曼频数均无后续tok文本读取。模式串的全部字符已在权重readInt之前遍历完。事件类型先复制到独立string ev，之后调用readInt也不依赖tok；LOG的x/b读完后另由readTok覆盖为hex。对账类型的q/q2先复制到char再读参数，ROUTE的第二个参数之后也不依赖原tok。因此不再把数值文本写入tok不会改变合法交互的后续逻辑。

getch在数字循环中仍消费终止该数值的第一个分隔符，与原readTok一致；后续调用自行跳过空白。新readInt额外接受TAB/VT/FF等空白，readTok本身不变，正式评测产生的数值空白格式保持兼容。

## 已完成验证

实际候选函数通过11组原语测试，覆盖LL_MIN=-9223372036854775808、LL_MAX、32位边界、9位编号、可选+、负零、六种ASCII空白、跨64KiB及128KiB输入缓冲区边界、混合数值/文本/hex，以及连续两次EOF返回0。另重放6,000,000字符hex日志的完整协议，400条ALARM逐条精确，8MiB修复仍有效。

train16全部完整judge报告与底座逐字一致，不只是利润相同；27,953次对账全对、0非法指令。本机最大CPU0.390625秒只是健康记录，不能与不同运行时段的历史值比较得出提速。

在主任务明确暂停其它批量评测的空窗内，4个压力世界各做3次base/scan交错配对，共24次，全部完整judge报告一致，78,960次对账全对、0非法。累计CPU为基线3.125000秒、scanner3.046875秒（−2.50%）；没有出现需要关闭TS才能保持行为的输出漂移。

| 场景 | 基线CPU中位数 | 扫描器CPU中位数 |
| --- | ---: | ---: |
| failures | 0.265625 | 0.250000 |
| logs_audits | 0.281250 | 0.281250 |
| max_topology | 0.328125 | 0.328125 |
| slow_costly | 0.187500 | 0.140625 |

这是小幅正向证据，Windows计量有15.625ms粒度，不应把−2.50%当跨机器确定提速，更不意味着利润会直接增长。当前没有报告或正确性回退，可以作为可合并的低影响性能候选；如合入更复杂策略，仍应以组合后的实际程序核验。没有因该小差异重复扩展测时次数。

## 源码与合并

`tools/v11_scan_make.py`导出`apply(source)`，只替换唯一readInt原定义，并确认8MiB修复存在；可供其它已选策略源合并。没有改变源头署名注释。

候选：`candidates/v11_scan.cpp`，SHA256 `d59972ba208958bca0688f432515e60edee920815596eb32644415d461224828`。程序：`build/v11_scan.exe`，SHA256 `b86de36f1e7ae825ea0b5eed3083f107d80a070b03372e2db4c0239ab14907aa`。

记录：`research/v11_scan_manifest.json`、`v11_scan_results.json`、`results/v11_scan_test/summary.json`、`results/v11_scan_train/`以及`results/v11_scan_paired/`。压力工具为`tools/v11_scan_measure.py --pressure`，已在通知后的空窗执行完毕，主任务已获知窗口结束。
