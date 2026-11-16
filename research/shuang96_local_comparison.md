# Shuang-su 96分代码：本项目本地对照

日期：2026-11-15。学校正式分数与以下本地利润独立；未提交同学代码。
后续正式记录：原样代码未提交；保留来源且修复边界/预算的V6派生版本提交543902已得96分，见 `official_v6_attributed96.json/.md`。以下表格仍为原样版本的独立本地比较，不能与派生版混用。
固定仓库快照，原样编译 submit.cpp / submit_nowarm.cpp，不调参。
训练中2个日志边界场景保留，但不纳入范围内14例汇总。
同输入与评测机哈希由 compare.py 检查；CPU不是同期配对性能实验。

| 比较（后者相对前者） | 集合 | 范围内例数 | 总利润变化 | 升/降/平 |
| --- | --- | ---: | ---: | --- |
| official85 → shuang_warm | train | 14 | +31.379% | 14/0/0 |
| official85 → shuang_warm | stress | 4 | +38.230% | 4/0/0 |
| official85 → shuang_warm | v4_confirmation | 32 | +43.972% | 32/0/0 |
| v4 → shuang_warm | train | 14 | +28.545% | 14/0/0 |
| v4 → shuang_warm | stress | 4 | +36.661% | 4/0/0 |
| v4 → shuang_warm | v4_confirmation | 32 | +41.978% | 31/1/0 |
| shuang_nowarm → shuang_warm | train | 14 | +15.913% | 13/1/0 |
| shuang_nowarm → shuang_warm | stress | 4 | +19.569% | 4/0/0 |
| shuang_nowarm → shuang_warm | v4_confirmation | 32 | +17.837% | 32/0/0 |
| v4 → shuang_nowarm | train | 14 | +10.898% | 12/2/0 |
| v4 → shuang_nowarm | stress | 4 | +14.295% | 4/0/0 |
| v4 → shuang_nowarm | v4_confirmation | 32 | +20.487% | 28/4/0 |

快照：`a35a23f3a8a3c623ff9c62af15e680143264de5e`。

工作树按本机 Git 设置转成 CRLF；另存原始 Git blob 的字节数和哈希，避免误认代码变更。

每版完整52例（含训练边界2例），全部结果保留于 results/shuang96_submit 与 results/shuang96_nowarm。

详细逐例、范围、错误和时间记录：results/shuang96_comparison/manifest.json。
