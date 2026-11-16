# 本地利润对比

本地生成场景的利润差异不等于 OJ 分数变化。

比较 66 例；提升 42 例、下降 24 例、持平 0 例。

日志保守按 3 MB = 3,000,000 个解码字符核验，同时标出超过 3 MiB = 3,145,728 的情况。边界压力例保留在全部结果中，另从范围内汇总排除。

已核验范围内共 64 例：利润 280,773,392 → 283,748,772（+1.06%），等权平均利润比 1.0315，中位比 1.0057；提升 40、下降 24、持平 0。

以下表格为全部结果（含边界压力例）；完整静态边数等信息缺失时不声称已核验该字段。

| 指标 | 基线 | 候选 |
| --- | ---: | ---: |
| 总利润 | 329,319,889 | 333,297,419 |
| 总利润增幅 | — | +1.21% |
| 各例等权平均利润比 | 1 | 1.0312 |
| 各例利润比中位数 | 1 | 1.0083 |
| 对账错误 | 0 | 0 |
| 非法指令 | 0 | 0 |
| 最大本机 CPU 秒数 | 0.4688 | 0.5625 |
| 最大峰值内存 MiB | 32.36 | 32.45 |

基线利润非正的用例不计算利润比，仍计入总利润：validation/shift_very_slow

基线存在边界或范围外压力数据（保留在全部统计，从范围内汇总排除）：

- validation/shift_very_fast: jobs=68455 > 60000
- validation/shift_very_fast_valid: jobs=64198 > 60000

候选存在边界或范围外压力数据（保留在全部统计，从范围内汇总排除）：

- validation/shift_very_fast: jobs=68455 > 60000
- validation/shift_very_fast_valid: jobs=64198 > 60000

| 用例 | 基线利润 | 候选利润 | 利润变化 | 候选 CPU 秒 |
| --- | ---: | ---: | ---: | ---: |
| confirmation/fast_00 | 14,141,236 | 14,417,844 | +1.96% | 0.4062 |
| confirmation/fast_01 | 9,955,379 | 9,986,165 | +0.31% | 0.2031 |
| confirmation/fast_02 | 10,174,732 | 10,295,882 | +1.19% | 0.3125 |
| confirmation/fast_03 | 11,945,749 | 12,177,887 | +1.94% | 0.2969 |
| confirmation/heavy_00 | 3,409,136 | 3,369,409 | -1.17% | 0.2188 |
| confirmation/heavy_01 | 5,634,700 | 5,915,238 | +4.98% | 0.2188 |
| confirmation/heavy_02 | 4,658,696 | 4,826,019 | +3.59% | 0.1406 |
| confirmation/heavy_03 | 5,087,748 | 5,134,387 | +0.92% | 0.2188 |
| confirmation/large_00 | 8,374,011 | 8,266,405 | -1.28% | 0.2812 |
| confirmation/large_01 | 5,853,744 | 5,712,599 | -2.41% | 0.2188 |
| confirmation/large_02 | 7,350,042 | 7,355,926 | +0.08% | 0.2656 |
| confirmation/large_03 | 5,356,058 | 5,529,732 | +3.24% | 0.2656 |
| confirmation/light_00 | 4,098,174 | 3,933,628 | -4.02% | 0.1250 |
| confirmation/light_01 | 2,167,137 | 2,158,075 | -0.42% | 0.1094 |
| confirmation/light_02 | 4,191,279 | 4,173,336 | -0.43% | 0.1250 |
| confirmation/light_03 | 2,065,139 | 1,965,997 | -4.80% | 0.0938 |
| confirmation/slow_00 | 293,956 | 392,361 | +33.48% | 0.0625 |
| confirmation/slow_01 | 351,291 | 392,872 | +11.84% | 0.0938 |
| confirmation/slow_02 | 758,418 | 860,312 | +13.44% | 0.0938 |
| confirmation/slow_03 | 321,919 | 497,825 | +54.64% | 0.0938 |
| confirmation/small_00 | 1,041,091 | 955,303 | -8.24% | 0.0156 |
| confirmation/small_01 | 723,670 | 780,732 | +7.89% | 0.0156 |
| confirmation/small_02 | 1,711,553 | 1,648,736 | -3.67% | 0.0469 |
| confirmation/small_03 | 1,338,415 | 1,337,243 | -0.09% | 0.0781 |
| confirmation/standard_00 | 1,889,703 | 1,909,744 | +1.06% | 0.1406 |
| confirmation/standard_01 | 4,223,562 | 4,344,473 | +2.86% | 0.1562 |
| confirmation/standard_02 | 5,107,023 | 5,198,949 | +1.80% | 0.1562 |
| confirmation/standard_03 | 3,404,722 | 3,332,297 | -2.13% | 0.1875 |
| confirmation/unstable_00 | 2,666,855 | 2,668,643 | +0.07% | 0.1250 |
| confirmation/unstable_01 | 4,103,177 | 4,137,146 | +0.83% | 0.1875 |
| confirmation/unstable_02 | 1,326,359 | 1,483,740 | +11.87% | 0.1406 |
| confirmation/unstable_03 | 2,036,639 | 2,043,573 | +0.34% | 0.1250 |
| validation/new_fast_00 | 10,380,005 | 10,340,839 | -0.38% | 0.1719 |
| validation/new_fast_01 | 13,910,654 | 14,380,678 | +3.38% | 0.3438 |
| validation/new_fast_02 | 15,580,795 | 15,643,640 | +0.40% | 0.3438 |
| validation/new_heavy_00 | 1,116,731 | 1,361,857 | +21.95% | 0.0938 |
| validation/new_heavy_01 | 2,746,620 | 2,913,358 | +6.07% | 0.1250 |
| validation/new_heavy_02 | 2,179,615 | 2,271,181 | +4.20% | 0.1406 |
| validation/new_large_00 | 7,886,721 | 7,956,528 | +0.89% | 0.2031 |
| validation/new_large_01 | 10,301,698 | 10,108,749 | -1.87% | 0.2500 |
| validation/new_large_02 | 10,176,427 | 10,192,128 | +0.15% | 0.2969 |
| validation/new_light_00 | 2,464,603 | 2,350,507 | -4.63% | 0.0781 |
| validation/new_light_01 | 3,645,470 | 3,604,713 | -1.12% | 0.1250 |
| validation/new_light_02 | 2,074,445 | 2,060,027 | -0.70% | 0.0625 |
| validation/new_slow_00 | 522,021 | 561,630 | +7.59% | 0.0938 |
| validation/new_slow_01 | 909,172 | 989,583 | +8.84% | 0.1094 |
| validation/new_slow_02 | 795,765 | 778,491 | -2.17% | 0.0781 |
| validation/new_small_00 | 1,218,847 | 1,236,025 | +1.41% | 0.0312 |
| validation/new_small_01 | 824,762 | 781,936 | -5.19% | 0.0469 |
| validation/new_small_02 | 1,252,282 | 1,374,446 | +9.76% | 0.0469 |
| validation/new_standard_00 | 3,015,152 | 3,011,304 | -0.13% | 0.0938 |
| validation/new_standard_01 | 8,004,674 | 8,075,569 | +0.89% | 0.1719 |
| validation/new_standard_02 | 3,923,852 | 3,775,576 | -3.78% | 0.1406 |
| validation/new_unstable_00 | 2,787,002 | 2,774,939 | -0.43% | 0.1094 |
| validation/new_unstable_01 | 3,169,709 | 3,149,713 | -0.63% | 0.1406 |
| validation/new_unstable_02 | 4,353,606 | 4,399,742 | +1.06% | 0.1406 |
| validation/shift_changing | 2,247,416 | 2,238,712 | -0.39% | 0.1250 |
| validation/shift_dense | 5,622,484 | 6,110,393 | +8.68% | 0.2188 |
| validation/shift_high_failures | 1,629,240 | 1,794,359 | +10.13% | 0.0469 |
| validation/shift_no_failures | 5,789,723 | 5,822,984 | +0.57% | 0.1094 |
| validation/shift_sparse | 1,781,464 | 1,717,531 | -3.59% | 0.0625 |
| validation/shift_uncertain | 568,193 | 612,616 | +7.82% | 0.0781 |
| validation/shift_very_fast | 23,911,841 | 24,468,137 | +2.33% | 0.5625 |
| validation/shift_very_fast_light | 14,134,621 | 14,158,052 | +0.17% | 0.1406 |
| validation/shift_very_fast_valid | 24,634,656 | 25,080,510 | +1.81% | 0.4219 |
| validation/shift_very_slow | -1,690 | -1,512 | 未定义 | 0.0312 |
