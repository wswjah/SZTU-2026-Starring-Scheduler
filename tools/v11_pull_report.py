"""Consolidate the bounded exact-image-quote experiment without promotion."""
from pathlib import Path
import hashlib
import json

ROOT=Path(__file__).resolve().parent.parent


def main():
    result=json.loads((ROOT/"research/v11_pull_results.json").read_text(encoding="utf8"))
    assert result["actual_runs"]==41
    assert all(e["all_health"]["all_runs_ok"] and e["all_health"]["all_audits_correct"] and e["all_health"]["all_commands_legal"] for e in result["experiments"])
    assert hashlib.sha256((ROOT/"versions/v10_input_fix/main.cpp").read_bytes()).hexdigest()=="b0854a70f54ccb47d287a48be37e447eb100147ca3f2e556c20c20498f705ae6"
    assert hashlib.sha256((ROOT/"main.cpp").read_bytes()).hexdigest()=="b39a299e1983d1837393cdce80fce6ffbdaa209df170a7d865069df011514e3d"
    assert hashlib.sha256((ROOT/"submit.cpp").read_bytes()).hexdigest()=="bafff023f3cc6c19ca3259bd4ce81123b9a58cd4c118cd9a6d9c1e19b162c706"
    lines=["# V11：在公平CPU计时下重试逐层精确镜像估价", "",
           "日期：2026-11-15。底座为99分调度参数及已保留的8MiB输入修复：versions/v10_input_fix/main.cpp。此分支未访问学校、未提交、未改默认或冻结版本，也未读取V11新验证数据。", "",
           "## 两版在看结果前固定", "",
           "A hybrid：保留原静态membership快速路径；当重复层、镜像超机器容量或插入可能造成机器/机架淘汰时，用真实Cache局部副本按层顺序模拟首次RUN，并精确估计第二次RUN剩余拉取。普通启动和预热均按对应registry/rack字节计算实际ceil准备时间与直接费用。", "",
           "B fee_only：首次直接registry费及预热的第二次RUN残余仍精确，但普通冷启动准备时间保留原membership估计，分离直接费用修正与更保守时间预测的作用。真实runJob、账本、quota、缓存和命令预算实现全部原样。", "",
           "唯一镜像层总字节能放进机器容量时，一次完整按层处理后所有镜像层都已驻留，第二次RUN必无镜像拉取，因此可直接返回零。超容量情况仍做第二次精确模拟。此快捷分支不改变报价结果。", "",
           "## 结果", "",
           "| 版本 | 范围内14例总利润 | 升/降 | 中位利润比 | 等权变化 | 最差变化 | 两个边界large总利润 | 本次最大CPU |", "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for e in result["experiments"]:
        v=e["valid_range"]
        lines.append(f"| {e['name']} | {v['total_profit_increase_pct']:+.4f}% | {v['improved']}/{v['regressed']} | {v['median_profit_ratio']:.6f} | {v['equal_weight_increase_pct']:+.4f}% | {100*(e['worst_ratio']-1):.2f}% | {e['boundary']['total_profit_increase_pct']:+.4f}% | {e['all_health']['max_cpu_seconds']:.6f}s |")
    lines += ["", "训练large00/01原有日志量超过保守3,000,000字符，完整保留为边界压力，不纳入14例范围内利润。精确局部报价并未带来更好的闭环总利润；两版均不建议合并或进入新验证。不能将少数世界收益或边界总收益单独当作整体改进。", "",
              "## 报价与保险计数", "", "| 版本 | 候选机器报价 | 需精确预览 | 首次pull计数不一致 | 第二次RUN残余 | late tick | 保险跳tick |", "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for e in result["experiments"]:
        d=e["diagnostics"]["totals"]
        lines.append(f"| {e['name']} | {d['previews']:,} | {d['exact']:,} | {d['first_mismatch']:,} | {d['warm_residual']:,} | {d['late_samples']} | {d['guard_returns']} |")
    lines += ["", "hybrid的12次late全部发生在边界large_01，未跳调度tick，但可能取消部分周期重估；14个范围内世界未出现late。fee_only全16例都未出现late。报价次数是候选尝试数，不是独立作业或独立失误数。当前生成世界第二次RUN残余全部为0，不证明正式输入永不超容量。", "",
              "## TS0控制与预览验证", "",
              "分别将相同基线和两候选TS设为0，在standard00、heavy00、fast00共跑9次。基线TS0与原TS1、两候选各自TS0与各自TS1的完整judge报告，三例全部逐字一致。hybrid在这三例利润都退步；fee_only除fast00略升外另外两例退步。加上范围内没有late，当前负收益不能简单归咎于旧Windows墙钟混杂。", "",
              "真实v11PreviewImage函数直接include入独立测试：5个定向场景（未touch层先被淘汰、超容量第二次rack残余、超容量第二次registry残余、重复层、零容量/零字节）和20,000个随机两次RUN预览，均与独立list LRU oracle相同；源缓存的顺序、membership、容量、字节和version均不变。",
              f"两版train32次及TS0控制9次，共41次实际TPJ运行、{result['audit_total']:,}次对账全对、0非法指令；测试程序另计。候选生产编译无警告；测试入口重命名原main会产生原隐式返回警告，非生产缺陷。", "",
              "本机CPU记录来自本次粗筛，可能与其它独立任务并行；未为负收益候选追加严格配对压力计时，不把它们当正式1秒保证或精确慢多少。", "",
              "## 可复现文件", "",
              "- tools/v11_pull_make.py：两版生成，输入源SHA有固定检查；candidates/v11_pull/{hybrid,fee_only}.cpp保留。",
              "- tools/v11_pull_tests.cpp、tools/v11_pull_screen.py：预览oracle、train与TS0控制。",
              "- research/v11_pull_manifest.json、v11_pull_results.json：全源码/程序哈希、逐世界计数与汇总。",
              "- results/v11_pull/：完整TPJ报告、所有失败世界与TS0控制，不覆盖旧V7实验。", "",
              "结论：本分支完成有界两版重试，拒绝合并。原99分默认程序及8MiB修复候选未改变。", ""]
    (ROOT/"research/v11_pull_review.md").write_text("\n".join(lines),encoding="utf8")
    print("V11 pull report recorded;2 variants rejected,41 runs all correct;default/frozen sources unchanged")


if __name__=="__main__":main()
