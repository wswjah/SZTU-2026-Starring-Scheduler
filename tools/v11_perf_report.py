"""Summarize actual-current profiling and two rejected performance candidates."""
from pathlib import Path
import json
import re

ROOT=Path(__file__).resolve().parent.parent
result=json.loads((ROOT/"research/v11_perf_results.json").read_text(encoding="utf8"))
baseline={}
for split in ["train","stress"]:
    rows=json.loads((ROOT/f"results/v10_input_verification/{split}/fixed/summary.json").read_text(encoding="utf8"))
    baseline.update({r["case"]:r for r in rows})
profile_rows=json.loads((ROOT/"results/v11_perf_profile/summary.json").read_text(encoding="utf8"))
profile=[]
for row in profile_rows:
    assert row["ok"] and row["report"]==baseline[row["case"]]["report"]
    text=(Path(row["run_dir"])/"solver_stderr.txt").read_text(encoding="utf8")
    counters={}
    for name,calls,samples,nanos,estimate in re.findall(r"V11_PROFILE (\w+) calls=(\d+) samples=(\d+) sample_ns=(\d+) estimate_ns=(\d+)",text):
        counters[name]={"calls":int(calls),"samples":int(samples),"sample_ns":int(nanos),"estimate_ns":int(estimate)}
    calls,hits,layers=map(int,re.search(r"V11_QUOTES calls=(\d+) version_hits=(\d+) layers=(\d+)",text).groups())
    profile.append({"case":row["case"],"all_full_reports_equal":True,"counters":counters,"quote_calls":calls,"version_hits":hits,"version_hit_ratio":hits/calls,"quote_layer_visits":layers})
result["current_profile"]=profile
result["decision"]="Reject both membership memo and generic O3 pragma: exact reports preserved, no measured pressure CPU benefit; no combination tested."
(ROOT/"research/v11_perf_results.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf8")
lines=["# V11：当前99分派生底座的性能试验", "", "2026-11-15。底座固定为versions/v10_input_fix/main.cpp，保留8MiB日志缓冲区修复；没有更改默认/冻结文件或进行正式提交。", "",
       "## 结论", "", "两项候选都保持现有调度完整结果，却没有得到压力CPU收益，均不建议合入，也没有继续叠加组合。", "",
       "| 程序 | 3轮×4压力累计CPU | 相对基线 |", "| --- | ---: | ---: |"]
for name in ["base","memo","o3"]:
    lines.append(f"| {name} | {result['total_cpu'][name]:.6f}s | {100*(result['relative_total_cpu'][name]-1):+.2f}% |")
lines += ["", "4个压力世界、每配置3次、同一世界内轮换执行顺序，bench每次workers1，程序与评测机不并发复跑同一对。其它主任务可在同时运行，WindowsCPU计量也有约15.625ms粒度，因此不把一次短场景差值当稳定提速；在当前配对样本中，两候选均缺乏正收益证据。", "",
          "| 压力场景 | 基线CPU中位数 | memo | O3 |", "| --- | ---: | ---: | ---: |"]
for case,values in result["case_median_cpu"].items():
    lines.append(f"| {case} | {values['base']:.6f} | {values['memo']:.6f} | {values['o3']:.6f} |")
lines += ["", "## 当前代码的热点", "", "单独从本次固定底座生成计数/采样版，未复用针对旧81分代码的profiler。抽检fast_00、large_01及max_topology，完整judge报告逐字与未加诊断的底座相同。", "",
          "| 场景 | tryPlace调用 | transferCost调用 | 成员估价次数 | 可复用版本比例 |", "| --- | ---: | ---: | ---: | ---: |"]
for r in profile:
    lines.append(f"| {r['case']} | {r['counters']['tryPlace']['calls']:,} | {r['counters']['transferCost']['calls']:,} | {r['quote_calls']:,} | {100*r['version_hit_ratio']:.2f}% |")
lines += ["", "schedule与tryPlace是主要调度开销来源，flowEstimate、网络转移估价、忙机等待、解码和真实LRU也分别计数。对很短函数的采样计时本身占比不小，而且是嵌套包含时间，不能把这些estimate_ns简单相加或当精确耗时百分比。这里的profile仅用于选实验方向，最终依据未加计时的真实候选程序配对测量。", "",
          "## 两项具体修改", "", "membership memo仅替换原按成员集合累加qreg/qrack的循环，按image×machine保存报价并以机器/机架内容版本作废。保留Cache.q、真实LRU、收费、镜像层次序和所有估价数值。FAIL清空机器缓存时补ver递增，否则未来memo会错误复用。缓存命中移动LRU次序不会改变这一近似成员报价，因此不必递增内容版本。约1MiB额外memo访问和版本比较没有在当前场景抵消原短层列表的成本。", "",
          "这个memo不能替代另一条分支的精确LRU预览：精确预览依赖访问次序，必须另用次序版本；本实现明确只用于原成员近似报价，已与精确拉取代理沟通。", "",
          "另一候选仅添加通用#pragma GCC optimize(\"O3\")，不启用fast-math，不指定CPU指令集。对当前小循环/分支的更多优化并未带来可测压力收益。不能把本机结论外推为所有编译器和平台上O3都更慢；当前交付继续保留原编译优化设置。", "",
          "## 验证记录", "", "两候选各train16共32次实跑，完整judge报告逐字一致，0对账错/0非法。36次压力配对全部完整报告一致且合法，3次诊断也一致；本子任务共71次实际运行。没有出现需要关闭TS才能复现的输出漂移，因此未额外执行TS0控制。源码、可执行文件与逐例结果均保留。", "",
          "工具：tools/v11_perf_profile.py、tools/v11_perf_candidates.py、tools/v11_perf_measure.py、tools/v11_perf_report.py。结果：research/v11_perf_profile_manifest.json、v11_perf_candidates.json、v11_perf_results.json以及results/v11_perf_*。没有以失败候选消耗正式机会。", ""]
(ROOT/"research/v11_perf_review.md").write_text("\n".join(lines),encoding="utf8")
print(json.dumps({"profile_reports_equal":True,"actual_runs":71,"decision":"reject both performance candidates"}))
