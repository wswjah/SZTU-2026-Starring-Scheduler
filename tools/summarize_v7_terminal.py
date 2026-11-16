"""Summarize both terminal structures without selecting on held-out worlds."""
from pathlib import Path
import hashlib
import json

ROOT=Path(__file__).resolve().parent.parent
comparisons={}
for phase,suffix in [('initial','train'),('revised','revised_train')]:
    for mode in ['rescue','conditioned']:
        key=f'{phase}_{mode}'
        path=ROOT/f'results/v7_terminal_{mode}_{suffix}/comparison.json'
        result=json.loads(path.read_text(encoding='utf8'))
        comparisons[key]={k:result[k] for k in ['valid_range_summary','boundary_pressure_summary',
                                                'total_profit_increase_pct','improved','regressed','unchanged']}

sources={}
for mode in ['rescue','conditioned']:
    path=ROOT/f'candidates/v7_terminal_{mode}.cpp'
    exe=ROOT/f'build/v7_terminal_{mode}.exe'
    sources[mode]={'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                   'executable':str(exe),'exe_sha256':hashlib.sha256(exe.read_bytes()).hexdigest()}
rows=[]
for mode in ['rescue','conditioned']:
    for phase in ['train','revised_train']:
        rows+=json.loads((ROOT/f'results/v7_terminal_{mode}_{phase}/summary.json').read_text(encoding='utf8'))
rows+=json.loads((ROOT/'results/v7_terminal_diagnosis/summary.json').read_text(encoding='utf8'))
rows+=json.loads((ROOT/'results/v7_terminal_timecontrol/summary.json').read_text(encoding='utf8'))
assert len(rows)==76 and all(r['ok'] for r in rows)
result={'baseline':'versions/v6_attributed96/main.cpp','official_score':96,
        'baseline_sha256':hashlib.sha256((ROOT/'versions/v6_attributed96/main.cpp').read_bytes()).hexdigest(),
        'sources':sources,'comparisons':comparisons,'runs':76,
        'audit_total':sum(r['audit_total'] for r in rows),'audit_errors':sum(r['audit_errors'] for r in rows),
        'illegal_commands':sum(r['incidents'] for r in rows),'all_ok':True,
        'held_out_worlds_read':False,'official_submission_sent':False,
        'timecontrol':'results/v7_terminal_timecontrol/summary.json',
        'diagnosis':'results/v7_terminal_diagnosis/summary.json',
        'recommendation':'Do not promote; weak gains and material regressions; tune with TS=0 controls'}
(ROOT/'research/v7_terminal_results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
text=['# V7：末任务与永久止损结构实验','',
      '基线为本账号正式96分源码，SHA256 `'+result['baseline_sha256']+'`。',
      '仅使用train16，没有读取新验证/留出集，没有登录或提交；根目录默认96分程序未改。','',
      '## 两种结构','',
      'A（rescue）：只在已开工流程剩一个就绪作业、且原粗估价即将将整流永久判死时，',
      '枚举当前可放置机器，以私有LRU副本精确模拟普通启动和同tick预热两次启动，',
      '包括首次/再次仓库费、两次网络费和实际准备时间。按现有五情景预测运行时长，',
      '真实超过T的情景收入为零；仅预计净收益为正时救回，并在实际放置前重新报价。',
      '只复用原runJob/killNow执行，真实账本、prepare、配额、命令预算与实际缓存规则不改。','',
      'B（conditioned）：在A之上，对于只剩一个运行中作业的流程，将既有五种全运行时长情景',
      '按“真实计算时长必须大于已运行计算时长”条件化，重新计算剩余收入和未来CPU费；',
      '五种情景全部被超过时回退原长尾估计。不把KILL/FAIL当完成标签，不读取真实隐藏时长。',
      '五点情景仍是手设启发式，不能声称已校准为真实概率分布。','',
      '每种结构初版曾沿用旧home工期计算优先级中的slack；随后同步更新rem，',
      '使rev/cost/work/rem一致。初轮和修正版结果及初轮源码均保留，不通过挑选初版数字报喜。','',
      '| 版本 | 范围内14例总利润 | 升/降/平 | 全16总利润 |',
      '| --- | ---: | --- | ---: |']
for phase in ['initial','revised']:
    for mode in ['rescue','conditioned']:
        a=comparisons[f'{phase}_{mode}'];v=a['valid_range_summary']
        text.append(f"| {phase} {mode} | {v['total_profit_increase_pct']:+.3f}% | "
                    f"{v['improved']}/{v['regressed']}/{v['unchanged']} | {a['total_profit_increase_pct']:+.3f}% |")
text+=['','训练large两例日志超过保守3,000,000字符范围，作为边界例保留，不计入14例范围内。',
       '最终B最差范围内standard_00约−2.09%，heavy_00约−1.09%；最佳standard_01约+4.65%。',
       '最终A在范围内的变化只涉及fast两组，其中fast00控制证明存在时间保险混杂。','',
       '## 发现CPU保险混杂','',
       '在B的只在结束输出计数的诊断版中：standard00的ready报价涉及16个流程、仅1个流程获正报价、',
       '实际ready救回RUN为0；heavy00与fast00的ready正报价及实际RUN也均0。',
       '运行中条件化在standard00保留3个流程、heavy00保留15个，fast00为0。',
       '这些为三例诊断轨迹的可见门控计数，不推断为全部训练或正式世界的频率。','',
       '将TS从1设为0、其余参数不变，基线/A/B在standard00、heavy00、fast00串行对照：',
       '基线与A三个完整judge报告逐字相同；fast00利润均14,086,150。',
       'B仍改变报告，standard00/ heavy00利润分别为2,573,747 / 4,106,801，',
       '对比TS0基线2,628,618 / 4,152,096均退步。',
       '因此整体CPU低于0.4秒也不能证明阶段性CPU保险从未触发；额外代码/编译布局/阶段开销',
       '会经clock驱动保险改变实际动作。A在TS1下的fast00利润波动不应当成策略改善。','',
       '## 结论与复现','',
       f"本子任务共76次实际运行（64次两轮训练、3次诊断、9次TS0对照），{result['audit_total']}次对账全对、0非法。",
       '观察到的CPU不作为同期提速结论；未进一步用留出集选择该方向，也不建议进入正式提交。',
       'B的总收益较弱且多场景回退，96基线保持不变。调参阶段建议先以TS0做可重复的策略比较，',
       '最终选定候选再还原TS1并独立串行测试时限与正式策略表现。','',
       '生成：`python tools/make_v7_terminal.py`，可用--input/--mode/--prefix移植到另一固定参数源。',
       '诊断：`python tools/v7_terminal_diagnose.py`；时间控制：`python tools/v7_terminal_timecontrol.py`。',
       '最终源码在candidates/v7_terminal_rescue.cpp和v7_terminal_conditioned.cpp；',
       '初版源码在candidates/v7_terminal_initial/，初版结果在results/v7_terminal_*_train，',
       '最终结果在results/v7_terminal_*_revised_train。完整指纹与统计见v7_terminal_results.json。']
(ROOT/'research/v7_terminal_review.md').write_text('\n'.join(text)+'\n',encoding='utf8')
print(json.dumps({'runs':76,'audit_total':result['audit_total'],'all_ok':True,'recommended':False}))
