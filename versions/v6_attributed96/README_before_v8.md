# 星环算力平台调度：96分版本

**本账号最高自动分：96 / 100**，2026-11-15，[提交543902](https://acm.sztu.edu.cn:40081/examsys/contest/status?cid=2231#solution_id=543902)。最新已登录核验累计使用5次、剩余5次。

当前默认代码基于 [Shuang-su 公开的96分解法](https://github.com/Shuang-su/SZTU-2026-data-structure-final-homework/tree/a35a23f3a8a3c623ff9c62af15e680143264de5e)，固定commit为 `a35a23f3a8a3c623ff9c62af15e680143264de5e`。可读源码和提交文件均保留上游来源说明。本项目实际修复后继数组越界和指令预算，未用变量混淆掩饰来源，不承诺查重结果。

最新本地候选V8已冻结于 `versions/v8_fine/submit.cpp`（17,821字节）。在V7上测试17个单轴邻域和2个组合，最终仅改TH0 5→4、SL 1→1.25。两组独立新场景合计80例，相对V7总利润+0.40%（47升33降），相对正式96策略+1.58%（56升24降）；相对96的最差单例−9.76%。同一生产程序100次运行、182,706次对账全对、零非法指令，本机最大CPU0.4375秒。五项结构试验均未合入，完整成功与失败数据见 `research/v8_experiment.md`。V8尚未正式提交，正式96分默认文件保持原样。

前一候选V7仍保存在 `versions/v7_tuned/submit.cpp`（17,823字节）。有限调参与末tick清理后，两组独立新场景合计64例总利润提高1.06%，40例升、24例降，最差下降8.24%；最终程序88次运行、158,272次对账全对，零非法指令。V7也未正式提交；报告见 `research/v7_experiment.md`。各本地利润增幅不能换算成正式加分。

V7研究还发现本机MinGW的clock()计墙钟，会将评测机/管道等待算进调度保险。新候选和比较基线统一用Windows进程CPU时钟，非Windows保留原clock语义；此前墙钟实验完整保留，不能把本机计时修正直接视为正式提分。证据见 `research/v7_clock_semantics.md`。

| 正式版本 | 分数 | 提交编号 |
| --- | ---: | ---: |
| 早期入架/估价改进 | 84 | 543386 |
| 卡常＋偏激进 | 85 | 543440 |
| 卡常＋偏保守 | 84 | 543441 |
| V4小树＋末作业估价 | 85 | 543899 |
| 署名96分派生修复版 | **96** | **543902** |

早期84/85分路线基于Misuzu0010公开81分程序，保存在 `versions/v1_84/`、`versions/v3_aggressive/` 等目录；旧README/REPORT与85分交付清单已在 `versions/v3_aggressive/` 归档。当前代码改用了上述Shuang-su路线，没有叠加V4离线风险树。

## 默认文件

| 文件 | 用途 |
| --- | --- |
| `submit.cpp` | 与正式96分回执完全相同，16,926字节，ASCII/LF，保留来源注释。 |
| `main.cpp` | 对应可读源码，32,618字节。 |
| `build/main.exe`、`build/submit.exe` | 对应本机已验证程序。 |
| `versions/v6_attributed96/` | 固定源码、提交文件、来源、修改和验证清单。 |
| `results/final_manifest.json` | 当前默认源码、程序和评测机的大小与哈希。 |
| `research/official_v6_attributed96.json`、`.md` | 本账号96分脱敏回执。 |

学校当前编程题源码限制为64,000 UTF-8字节。打包仅安全移除注释和空白，逐token核对，再保留上游署名注释；不重命名标识符。以已冻结的 `submit.cpp` 为正式记录对应文件。

## 实质修复

1. 在读取/写入后继预测临时数组之前检查8行容量，修复第9个有效后继可越界的问题。
2. 统计每tick全部RUN/KILL，遵守20,000条上限，ANS/END不计入。
3. 同tick预热RUN/KILL/RUN先预留完整3条预算，避免只发半套。
4. 超预算的止损KILL排到下一tick，并在CPU时间保险前处理；已DONE/FAIL的作业不再发KILL。

保留上游同tick镜像预热、五情景收益估计、租户时长统计、候选机架排序、忙机器预约及止损。真实运行费、首次仓库费和重复网络费仍按协议核算。对账只使用初始化和已收到事件，不读取未来、真实隐藏时长或私有评测数据。

## 验证与复现

冻结的提交程序运行了54个本地场景（16训练、4压力、32额外确认、2原生样例），97,075次对账全对、零非法指令；本机最大CPU为0.4375秒。训练large两例超日志保守范围，原记录保留，范围内汇总排除。本地利润不等于正式分数。

定向测试直接调用真实调度函数，覆盖0至1000后继、预算19997/19998/19999/20000、跨tick止损以及DONE/FAIL过期。修复版与checked数组副本均通过；恢复原晚检查的负对照准确捕获第9分支越界。MinGW缺libubsan，未宣称UBSan通过。

```powershell
g++ -std=c++17 -O2 -Wall -Wextra submit.cpp -o build/submit.exe
python tools/bench.py --exe build/submit.exe --cases cases/stress --out results/my_stress --workers 1
python tools/run_attributed96_regressions.py
```

`bench.py` 直接连接原始本地评测机 `tpj_win.exe`，保存完整报告、CPU/内存、对账、非法指令及输入/程序/评测机哈希，不执行网页提交。`ok`不代表已经验证正式1秒时限。原生样例直接用各自的 `turn_00.in`，应分别指定输出目录。

详细记录：`research/v6_attributed96_review.md`、`results/v6_attributed96_comparison/`、`results/v6_attributed96_focused/`。此前独立迁移到85分路线的预热候选在 `candidates/v5_same_tick_warm.cpp`，它未正式提交，也不是当前96分源码。

页面显示本次500ms/16300kB；时间为平台兼容字段。`res_show=false`，剩余4组的状态和利润目标不可见，不能认定它们都因q>1失败。没有第三次新增提交或结束考试。
