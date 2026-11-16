"""Summarize the one actual-placement order rollout without selecting on fresh data."""
from pathlib import Path
import hashlib
import json
import re
from compare import compare,markdown
from v12_order_make import make

ROOT=Path(__file__).resolve().parent.parent
source=ROOT/"candidates/v12_order.cpp"
assert source.read_text(encoding="utf8")==make((ROOT/"versions/v10_input_fix/main.cpp").read_text(encoding="utf8"))
manifest=json.loads((ROOT/"research/v12_order_manifest.json").read_text(encoding="utf8"))
assert hashlib.sha256(source.read_bytes()).hexdigest()==manifest["source_sha256"]
assert hashlib.sha256((ROOT/"build/v12_order.exe").read_bytes()).hexdigest()==manifest["exe_sha256"]
comparison=compare(ROOT/"results/v10_input_verification/train/fixed",ROOT/"results/v12_order_train")
(ROOT/"results/v12_order_train/comparison.json").write_text(json.dumps(comparison,ensure_ascii=False,indent=2),encoding="utf8")
(ROOT/"results/v12_order_train/comparison.md").write_text(markdown(comparison),encoding="utf8")
rows=json.loads((ROOT/"results/v12_order_train/summary.json").read_text(encoding="utf8"))
assert len(rows)==16 and all(r["ok"]for r in rows)
diagnostics=[]
for row in rows:
    text=(Path(row["run_dir"])/"solver_stderr.txt").read_text(encoding="utf8")
    match=re.search(r"V12_ORDER searches=(\d+) swaps=(\d+) trials=(\d+) machine_copies=(\d+)",text)
    assert match,row["case"]
    diagnostics.append({"case":row["case"],**dict(zip(["searches","swaps","trials","machine_copies"],map(int,match.groups())))})
totals={key:sum(r[key]for r in diagnostics)for key in ["searches","swaps","trials","machine_copies"]}
test=json.loads((ROOT/"results/v12_order_tests/summary.json").read_text(encoding="utf8"))
assert test["all_passed"] and test["source_sha256"]==manifest["source_sha256"]
valid=comparison["valid_range_summary"]
worst=min((r for r in comparison["rows"]if not r["baseline_range_violations"]and r["profit_ratio"]is not None),key=lambda r:r["profit_ratio"])
record={"manifest":manifest,"training":valid,"boundary":comparison["boundary_pressure_summary"],
        "health":{"runs":16,"all_ok":True,"audit_total":sum(r["audit_total"]for r in rows),"audit_errors":0,"illegal_commands":0,
                  "max_cpu_seconds":max(r["solver_cpu_seconds"]for r in rows),"max_peak_memory_bytes":max(r["solver_peak_memory_bytes"]for r in rows)},
        "diagnostics":diagnostics,"diagnostic_totals":totals,"transaction_tests":test,"worst_valid":worst,
        "decision":"Reject on train-only regression; no fresh evaluation or additional parameter variants",
        "official_submission_sent":False,"fresh_data_accessed":False}
(ROOT/"research/v12_order_results.json").write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding="utf8")
manifest["training"]={"result":"research/v12_order_results.json","valid_profit_change_pct":valid["total_profit_increase_pct"],
                      "improved":valid["improved"],"regressed":valid["regressed"],"all_ok":True,"fresh_evaluated":False}
(ROOT/"research/v12_order_manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf8")
report=f"""# V12：真实tryPlace的双顺序事务rollout

2026-11-16。底座为固定8MiB修复版本`versions/v10_input_fix/main.cpp`。本轮只有一个结构候选，没有额外选参、没有查看V12新验证或正式提交。

## 结果与决定

训练16例全部正常，{record['health']['audit_total']:,}次对账全对、0非法指令。范围内14例利润{valid['baseline_total_profit']:,}→{valid['candidate_total_profit']:,}（{valid['total_profit_increase_pct']:+.4f}%），{valid['improved']}升{valid['regressed']}降，中位利润比{valid['median_profit_ratio']:.6f}。最差{worst['case']}为{100*(worst['profit_ratio']-1):.2f}%。两个原large日志边界例均改善，仍保留并排除于14例范围内；不能用全16近乎持平来掩盖主要场景退步。

实际搜索{totals['searches']:,}对、选择交换顺序{totals['swaps']:,}次，执行私有trial {totals['trials']:,}次、仅复制首次触及的机器状态{totals['machine_copies']:,}份。策略确实触发。当前不建议进入新场景、组合或正式提交。

本机最大CPU{record['health']['max_cpu_seconds']:.6f}秒、峰值内存{record['health']['max_peak_memory_bytes']:,}字节，是本次健康记录，不与历史基线时间的小差值对比宣称提速。

## 单一候选的规则

仅当某流程当前恰有两个ready作业、left在2..8、流程总作业不超过128、两者都没有仍有效的预约/重试缓存，且各自按当前机器、输入可达性和祖先配额可立即执行时，才考虑额外搜索。总作业128限制约束当前流程预测数组快照的开销。

分别从同一原始状态调用真实tryPlace(A)、tryPlace(B)，和真实tryPlace(B)、tryPlace(A)。比较实际进入运行状态的作业数，数量相同再比较原五情景预期收入减本trial真实即时启动费与剩余预计费用。即时费来自当前租户tenFix增量；同tick首RUN/KILL没有elapsed CPU，故不会把未来运行费混入即时费。完全相同时保留原顺序。

原schedule的CPU保险公式不改；额外搜索要求late<−0.03且used<0.65，并在每个候选pair重新读取进程CPU预算。搜索不预测未来事件、不合成DONE、不改原RUN/KILL、忙机预约、缓存拉取或命令预算路径。最后仅以真实tryPlace执行选定顺序。

## 事务怎样恢复状态

runJob与occupy入口只有在trial激活时才记录首次touch。每trial只保存实际选中的机器/机架缓存、machJobs、free/freedAt、virtual资源和timeline；两次tryPlace最多选择两台机器，不复制全部360台缓存。

保存两作业的scalar区、当前Flow、当前流程jobEnd/Tail/Theta、K<=200租户的used与账单数组、EMA/runFee/命令数/outbuf原长度。Job原始代码有未初始化但尚不读取的scalar字段，因此不做typed复制：只按字符复制至pre向量之前的scalar对象表示，pre/suc向量从未被tryPlace或预测修改；Flow为trivially-copyable类型，完整原始表示按memcpy还原。测试包含未使用scalar哨兵字节，确保不会凭空初始化或泄漏这些字段。

trial只往outbuf追加，不触及stdout；回滚截断至原长度。内存容量可能变化，逻辑内容恢复，不把vector/string capacity当调度状态。新增诊断计数和已消耗CPU不回滚。

原tryPlace的registry iq/iv改为显式全局数组，回滚恢复缓存内容/版本后清空全部iv，使下一次报价重新核验。否则一次假设性cache ver可与另一次不同真实内容形成ABA。q的旧整数值可留存，因为清零iv会强制重算，不允许它验证假设性memo。

## 事务与真实价格的定向验证

实际候选通过4,270项检查，包括200组随机多机器/缓存/剩余预算fixture的正逆共400次完整状态复原；检查缓存次序/成员/版本、作业scalar、账单、配额、真实/虚拟资源、timeline、预测数组、EMA、命令数与输出内容。

有一例两作业同镜像，A输入网络费高、B无输入费：原顺序实际启动费170，交换顺序110，两者都启动2作业且各4条命令。rollout准确得到60差额，最终输出仅包含省费分支，真实账单110；所有假设指令均已撤销。另验证0..7个剩余命令槽、原子预热、busy机器预约、live reservation/配额/CPU/规模gate、同分保留原序。

两个负对照均准确失败：去掉iv清零会触发假设memo残留检查；去掉feeAvg恢复会触发首trial状态泄漏检查。这证明事务测试能够发现关键漏回滚，而不是只检查输出长度。

## 为什么未采用

真实执行两顺序消除了V11独立报价的个体资源不兼容问题，但只看当前两作业启动数与当前流程预测，仍不是全平台的未来利润优化。交换后会改变其它流程后续可用机器、镜像缓存、队列和学习EMA；局部省费或多启动一个任务不保证总利润增加。当前真实闭环训练已经出现回退，因此不通过继续试参数掩盖这一结论。

复现：`tools/v12_order_make.py`、`v12_order_tests.cpp`、`v12_order_test.py`、`v12_order_report.py`。源码`candidates/v12_order.cpp`，SHA256 `{manifest['source_sha256']}`；所有测试与训练记录在`results/v12_order_tests/`、`results/v12_order_train/`及本目录manifest/results JSON。根目录与已冻结版本未改。
"""
(ROOT/"research/v12_order_review.md").write_text(report,encoding="utf8")
print(json.dumps({"valid_profit_change_pct":valid["total_profit_increase_pct"],"up":valid["improved"],"down":valid["regressed"],"totals":totals,"all_ok":True}))
