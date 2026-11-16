# 星环算力平台调度：本地优化与提交

本项目基于 [Misuzu0010 公开的 81 分版本](https://github.com/Misuzu0010/SZTU-2026-data-structure-final-homework)，保留原始参考代码后进行改进。当前代码只使用初始化信息和已经收到的事件，不读取未来事件、真实时长或隐藏评测数据。

**本账号最近确认的最高自动分：85 / 100 分**，2026-11-14，[提交记录 543440](https://acm.sztu.edu.cn:40081/examsys/contest/status?cid=2231#solution_id=543440)。根目录源码已更新为这份胜出的激进版。原84分版保存在 `versions/v1_84/`，本轮两版分别保存在 `versions/v3_aggressive/`、`versions/v3_conservative/`。截至该次核验累计使用3次，剩余7次。

2026-11-15 更新：用户已授权 V4 再提交一次，但学校入口转入新的统一认证网关，认证站 HTTPS 连接持续失败，尚未发送代码、未产生新编号或得分。本次没有消耗提交机会；上述85分、已用3次/剩余7次是11月14日最后一次登录核验值，当前无法重新查询。待提交文件仍为 `versions/v4_risk_terminal/submit.cpp`（57,073字节），授权保留，记录见 `research/official_v4_risk_terminal_attempt.md`。

已按固定 commit 审阅 [Shuang-su 的96分仓库](https://github.com/Shuang-su/SZTU-2026-data-structure-final-homework/tree/a35a23f3a8a3c623ff9c62af15e680143264de5e)，快照在 `reference/shuang96/`，未提交对方代码。原样运行其预热/不预热版，各52个本项目场景均零对账错误、零非法指令；在额外32例中，分别比V4总利润高41.98%和20.49%。这些是本地利润，不是本账号正式得分。主要差异、边界和可复现结果见 `research/shuang96_strategy_review.md`、`research/shuang96_local_comparison.md`。

规则迁移的独立候选为 `candidates/v5_same_tick_warm.cpp`：在本项目85分底座上，仅对符合费用与缓存条件的已选机器执行同tick预热，不改变原规划、选机或加入V4模型。范围内训练14例总利润提高11.92%，压力4例提高16.08%，额外32例提高14.72%且32/32提升；54个不同场景（含2样例和2边界训练），另重复冒烟检查standard_00一次，合计55次运行均零对账错误、零非法指令。候选尚未正式提交，根目录85分与已授权的V4文件均未改动。证据见 `research/same_tick_warm_audit.md` 和 `results/v5_same_tick_warm_confirmation/comparison.json`。

| 正式版本 | 分数 | 提交编号 |
| --- | ---: | ---: |
| 原版 | 84 | 543386 |
| 卡常＋偏激进 | **85** | 543440 |
| 卡常＋偏保守 | 84 | 543441 |

## 使用哪个文件

| 文件 | 用途 |
| --- | --- |
| `submit.cpp` | 最高85分对应的单文件 C++17 源码，55,042 字节，ASCII、LF 换行。 |
| `main.cpp` | 对应的可阅读源码，保留原来的中文说明和新增策略。 |
| `build/submit.exe` | 本机 Windows 调试程序。 |
| `REPORT.md` | 利润对比、性能、局限和正式评测记录。 |
| `reference/` | 同学公开的原始源码、题面和 README。 |
| `research/site_problem.md` | 2026-11-13 登录核验的官方题面，不含登录凭据。 |
| `results/final_manifest.json` | 最终源码、程序和评测机的大小、哈希及结果目录。 |

学校当前编程题页面检查的是 **64,000 个 UTF-8 字节**。`main.cpp` 含中文注释，不能直接作为限长提交文件；使用 `submit.cpp`。打包只去掉注释和安全的空白，不重命名标识符，并重新核对全部 C++ token。

## 改进内容

1. 整条工作流仍选择一个主要机架，但单个作业还可以选择外部输入、已完成前驱输出所在的机架，减少大数据搬运。
2. 选择这些机架时，同时估计输出回到主要机架的后续传输费与准备时间，避免只省当前作业而拖慢后继。真实账单仍只累计实际发生的费用。
3. 为剩余费用增加估计余量，并提高排队优先级中的工期权重。原84分版余量为20%，当前85分激进版为10%；本轮保守对照为35%。
4. 后续传输估价按机架计算一次，供该架的所有候选机器复用；补齐输入结束的处理。
5. 镜像拉取预览采用惰性队列，避免复制完整LRU；最短路使用索引堆。这两项保持原策略的计算结果。同期串行两轮压力总CPU耗时下降约14.17%，两个大场景约10.38%，详细原始计时见 `research/v3_performance_review.md`。

跨机架输入、运行费、两级 LRU、配额撤销、动态路由、告警、SLACK 的对账规则沿用并核验原有实现。没有采用读取样例未来数据、固定种子识别或隐藏信息推断。

## 编译与运行

在项目目录使用 MinGW g++ 或兼容的 GNU C++17 编译器：

```powershell
g++ -std=c++17 -O2 -Wall -Wextra submit.cpp -o build/submit.exe
python tools/bench.py --exe build/submit.exe --cases cases/stress --out results/my_stress --workers 1
```

`bench.py` 通过双向管道连接选手程序与原始 `tpj_win.exe`。利润、对账错误、非法指令、CPU、峰值内存、完整错误输出和输入/程序/评测机 SHA-256 会写入结果目录。它不执行网页提交。`ok` 表示本地协议和对账通过，时间是否超过 1 秒另列，不能仅凭 `ok` 宣称正式通过。

两个原生样例分别运行，避免相同文件名覆盖结果：

```powershell
python tools/bench.py --exe build/submit.exe --cases sample_00/turn_00.in --out results/my_samples/sample_00
python tools/bench.py --exe build/submit.exe --cases sample_01/turn_00.in --out results/my_samples/sample_01
```

也可打开原来的 `csg_tpj_debug_player_windows_amd64.exe`，选择 `main.cpp`。`config.json` 已指向可阅读源码，并设置 1 秒、256 MB。官方工具的本机统计仍不能替代 OJ 结果。

## 复现与继续优化

```powershell
python tools/make_cases.py
python tools/make_cases.py --out cases/holdout --seeds 2 --seed-base 91827364
python tools/make_stress_cases.py
python tools/pack_submission.py --self-test
python tools/compare.py results/baseline_holdout results/final_holdout --json results/check.json --md results/check.md
```

`cases/train` 用于调参，`cases/holdout` 在候选冻结后验证，`cases/stress` 是四个范围内大规模压力场景。生成器有时会产生超范围数据：原输入与结果全部保留，但日志超过保守的 3,000,000 字符或作业超过 60,000 的场景，在正式范围内统计中排除，单列为边界压力。不要把本地利润增幅换算成 OJ 加分。

源码修改后，重新打包、编译、对比；已有结果只证明其记录的源码和程序版本。实验候选在 `candidates/`，比较记录在 `results/` 和 `artifacts/`；最终交付文件是根目录的 `main.cpp`、`submit.cpp`。
