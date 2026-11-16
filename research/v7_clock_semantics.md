# V7 本机clock语义诊断

2026-11-15。此诊断不修改96分源码或任何正式候选，不进行学校登录或提交。

## 结论

本机MinGW链接的 `clock()` 计算进程开始以来的墙钟时间，包含休眠和交互等待，并非 `tools/bench.py` 用GetProcessTimes测量的进程CPU时间。故“solver_cpu_seconds < 0.4”不能推出原调度的时间保险没有触发；本地TPJ、管道等待和并行负载均可能改变该保险，从而改变动作、最终利润。

微软主文档明确写clock返回进程elapsed wall-clock time：[Time Management](https://learn.microsoft.com/en-us/cpp/c-runtime-library/time-management?view=msvc-170)、[clock](https://learn.microsoft.com/en-us/cpp/c-runtime-library/reference/clock?view=msvc-170)。这里不据此推断学校评测机的具体操作系统。

## 直接实验

源码 `tools/v7_clock_probe.cpp`，程序 `build/v7_clock_probe.exe`。在同一线程只sleep300ms，分别读取C clock、steady_clock，以及GetProcessTimes进程user+kernel CPU。

```text
CLOCKS_PER_SEC=1000
sleep_clock_seconds=0.314
wall_seconds=0.314659
cpu_seconds=0
```

`objdump -p build/v7_clock_probe.exe` 显示导入 `KERNEL32.dll` 和 `msvcrt.dll`，确认所用C运行时。

第一次未加GetProcessTimes的独立探针也为clock0.304秒、wall0.30399秒。两次均支持clock包含sleep。

## 对现有结果的影响

96分代码原调度中 `used=clock()*TS/CLOCKS_PER_SEC`，先按tick线性预算判断late。late>=0就禁止干净workflow的周期重估，late更大时跳部分tick，used>.93完全停止新调度。即使总CPU小，Windows本地运行也可能在这些分支退化。诊断代码和调度策略代码的微小耗时变化，都可能改变轨迹。

此前TS=1的参数/结构候选与基线比较包含本机墙钟反馈的混杂；不能只把利润变化归于参数或新增策略。尤其“逻辑补丁实际触发次数为0但利润改变”的现象，不能作为该补丁有效的证据。

下一步由root统一创建本机CPU计时适配底座：Windows使用GetProcessTimes的kernel+user，非Windows保持原clock；或先用TS=0隔离策略。计时适配应同等用于基线和候选，只用于本地评估一致性，不宣称改变官方策略或直接提分。

按root新指示，原clock诊断副本的全train尚未启动，以免继续积累不可比较结果。保留既有TS=1结果用于历史诊断，不覆盖它们。

## 本机CPU适配及对照

已提供 `tools/v7_portable_clock.py` 的 `adapt(source: str) -> str`。只替换唯一调度计时表达式，并在unistd include之后插入条件实现：

- Windows通过GetProcessTimes读取当前进程kernel+user时间，100ns换算秒；失败明确stderr报错并退出3，不退回墙钟。
- 非Windows宏仍直接计算 `clock() * (scale) / CLOCKS_PER_SEC`，保留原表达式运算顺序，不改变调度阈值。
- 同一适配重复调用幂等；命令行禁止输入与输出路径相同，因此不会改正式冻结文件。

已生成 `candidates/v7_cpu/base.cpp` / `build/v7_cpu_base.exe` 供root统一基线重筛。对应关闭保险的独立控制为 `candidates/v7_cpu/base_ts0.cpp` / `build/v7_cpu_base_ts0.exe`。

第二探针 `tools/v7_portable_clock_probe.cpp` 使用同一条件实现，输出：

```text
sleep_old_clock=0.312 sleep_portable_cpu=0 sleep_wall=0.310904
burn_old_clock=0.152 burn_portable_cpu=0.15625 burn_wall=0.152675
```

说明新计时不包含sleep，实际消耗CPU则增长。Windows进程CPU计账粒度使数值无需与steady墙钟逐微秒相等。

用实际本地TPJ分别运行portable TS=1与原源码TS=0，每个世界均完整报告逐字一致：

| 训练世界 | portable利润 | TS0利润 | 全部对账/指令 |
| --- | ---: | ---: | --- |
| fast_00 | 14,086,150 | 14,086,150 | 正确/合法 |
| standard_00 | 2,628,618 | 2,628,618 | 正确/合法 |
| large_01 | 11,453,598 | 11,453,598 | 正确/合法 |

三世界共6次；large_01仍是原训练日志边界压力例，不因计时对照而改变范围分类。完整报告和哈希保存在 `results/v7_cpu_clock_control/portable/`、`ts0/`，汇总为同目录summary.json。此对照只证明这三例中CPU保险适配未改变TS0轨迹，不能证明任何正式世界永不触发保险。

旧96分TS=1已有large_01利润10,717,953，而CPU适配/TS0为11,453,598。它们是同一原调度规则在不同本机保险语义下的区别，不能算新增算法收益。
