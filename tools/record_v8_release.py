"""Promote the exact officially submitted V8 artifacts after confirmed99."""
from pathlib import Path
import hashlib
import json
import shutil

ROOT = Path(__file__).resolve().parent.parent
VERSION = ROOT / "versions/v8_fine"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    receipt = json.loads((ROOT / "research/official_v8_fine.json").read_text(encoding="utf8"))
    status = receipt["final_status"]
    account = receipt["postflight_meta"]["by_qid"]["488"]
    assert status["exam_score"] == account["best_score"] == 99
    assert receipt["submission_posts_sent"] == 1 and account["used"] == 6 and account["remain"] == 4
    version = json.loads((VERSION / "manifest.json").read_text(encoding="utf8"))
    assert sha(VERSION / "submit.cpp") == receipt["source_sha256"] == version["packed_sha256"]
    assert sha(VERSION / "main.cpp") == version["source_sha256"]
    executable = Path(version["executable"])
    assert sha(executable) == version["exe_sha256"]
    assert version["validation"]["primary_runs"] == 100 and version["validation"]["audit_errors"] == 0
    current_path = ROOT / "results/final_manifest.json"
    current = json.loads(current_path.read_text(encoding="utf8"))
    if current["official_score"] < 99:
        assert current["official_score"] == 96
        archive = ROOT / "versions/v6_attributed96"
        for filename in ["main.cpp", "submit.cpp"]:
            assert sha(ROOT / filename) == current["artifacts"][filename]["sha256"]
            assert (ROOT / filename).read_bytes() == (archive / filename).read_bytes()
        for filename, target in [("README.md", "README_before_v8.md"), ("REPORT.md", "REPORT_before_v8.md"),
                                 ("results/final_manifest.json", "final_manifest_before_v8.json")]:
            assert not (archive / target).exists(), "Never overwrite a previous release archive"
            shutil.copy2(ROOT / filename, archive / target)
    for source, target in [(VERSION / "main.cpp", ROOT / "main.cpp"),
                           (VERSION / "submit.cpp", ROOT / "submit.cpp"),
                           (executable, ROOT / "build/main.exe"), (executable, ROOT / "build/submit.exe")]:
        shutil.copy2(source, target)
    names = ["main.cpp", "submit.cpp", "build/main.exe", "build/submit.exe", "tpj_win.exe"]
    release = {
        "date": "2026-11-15", "candidate": "v8_fine", "official_score": 99,
        "official_submission_id": 544054, "official_submission_url": receipt["submission_url"],
        "official_submissions_total": 6, "remaining_submissions": 4,
        "previous_96_manifest": "versions/v6_attributed96/final_manifest_before_v8.json",
        "upstream_repository": "https://github.com/Shuang-su/SZTU-2026-data-structure-final-homework",
        "upstream_commit": "a35a23f3a8a3c623ff9c62af15e680143264de5e",
        "attribution_preserved": True,
        "artifacts": {name: {"bytes": (ROOT / name).stat().st_size, "sha256": sha(ROOT / name)} for name in names},
        "results": "research/v8_experiment_manifest.json", "official_receipt": "research/official_v8_fine.json",
        "frozen_experiment": "versions/v8_fine/manifest.json", "best_source_matches_official_receipt": True,
        "remaining_case_cause": "Unknown: official per-case feedback is not published",
    }
    current_path.write_text(json.dumps(release, ensure_ascii=False, indent=2), encoding="utf8")
    readme = """# 星环算力平台调度：99分版本

**本账号最高自动分99/100**，2026-11-15，[正式提交544054](https://acm.sztu.edu.cn:40081/examsys/contest/status?cid=2231#solution_id=544054)。正常登录核验已用6次、剩余4次。本次用户授权的一次提交已用完。

根目录main.cpp、submit.cpp及build默认程序现在与正式99分冻结版本一致。提交文件17,821字节，SHA256 `bafff023f3cc6c19ca3259bd4ce81123b9a58cd4c118cd9a6d9c1e19b162c706`。源码开头保留上游来源说明；这也是已经提交的确切内容。

## 当前实现

底座来自Shuang-su公开源码，固定commit `a35a23f3a8a3c623ff9c62af15e680143264de5e`。保留同tick预热、五情景收益预测、在线租户时长学习、忙机器预约与止损；本地修复后继数组越界、20,000指令预算、原子预热与延后终止。

后续加入末tick清理与Windows进程CPU计时适配，并调整SB=2、RK=16、KILLK=1.1、ADM=0.05、TH0=4、SL=1.25。非Windows保留原clock表达式。参数通过本地训练筛选，最终冻结后80个新场景相对96策略总利润+1.58%，56升24降，最差−9.76%。实际提交后正式96→99，不能把每项修改分别归因为新增3分。

同一生产程序100次运行、182,706次对账全对、零非法指令；训练两个large为日志边界世界，完整结果保留。最大本机CPU0.4375秒，不等同于正式最慢用时。官方页面496ms/16324kB为兼容字段，res_show=false，最后1组失分原因未知。

## 文件

| 文件 | 用途 |
| --- | --- |
| main.cpp / submit.cpp | 当前正式99分可读及提交源码 |
| versions/v8_fine/ | 冻结99分源码与验证、正式记录清单 |
| results/final_manifest.json | 当前默认文件大小与SHA256 |
| research/official_v8_fine.json / .md | 脱敏正式回执 |
| research/v8_experiment.md | 19组参数与5项结构试验，含全部失败方向 |
| versions/v6_attributed96/ | 原96分源码及本次推广前文档和清单 |
| research/v9_alarm_*.json / .md | 独立的告警风险研究，未进入正式99分代码 |

## 正式记录

| 版本 | 分数 | 提交编号 |
| --- | ---: | ---: |
| 早期改进 | 84 | 543386 |
| 卡常与偏激进 | 85 | 543440 |
| 偏保守 | 84 | 543441 |
| V4风险树与末作业估价 | 85 | 543899 |
| 署名96分派生修复 | 96 | 543902 |
| V8有限调参与末tick清理 | **99** | **544054** |

早期84/85路线基于Misuzu0010公开81分程序，各版本、源码与实验均保留。99分没有叠加V4风险树，也没有加入V9告警模型。

本地评测用tools/bench.py直接连接原始tpj_win.exe，记录完整账目、错误、指令、CPU及哈希；本地生成世界不提供官方利润目标。学校提交源码限制64,000 UTF-8字节；当前打包只移除空白和非提交注释，逐token校验，不改标识符。
"""
    (ROOT / "README.md").write_text(readme, encoding="utf8")
    report = ROOT / "REPORT.md"
    old_report = report.read_text(encoding="utf8")
    marker = "<!-- v8 official99 release -->"
    if marker not in old_report:
        intro = """# 验证记录

<!-- v8 official99 release -->
2026-11-15正式更新：V8提交544054为**99分**，最高96→99，正常核验已用6次、剩余4次。本轮只发送一次代码POST。根目录源码与默认程序已推广为这份99分文件，17,821字节；来源注释为正式已提交内容的一部分。回执见research/official_v8_fine.json/.md。

100次实际生产程序运行、182,706次对账全对、零非法；80个新场景相对96策略总利润+1.58%。详情隐藏，最后1组的状态、利润与目标不可见；不能判断失分原因。告警风险研究在独立候选中进行，尚未进入正式代码。

## 以下为提交前及早期历史记录

下文中的默认文件、授权与剩余次数描述是各记录当时的历史状态；当前以results/final_manifest.json为准。

"""
        report.write_text(intro+old_report.split("\n", 1)[1], encoding="utf8")
    experiment = ROOT / "research/v8_experiment.md"
    text = experiment.read_text(encoding="utf8")
    marker = "<!-- officially99 -->"
    if marker not in text:
        text += "\n## 正式后验结果\n\n<!-- officially99 -->\n用户随后明确授权正式提交一次：544054得99分，最高96→99，已用6次、剩4次。提交文件SHA与本报告冻结候选完全相同，只有一次代码POST。根目录已推广为99分文件；以上未提交/默认96的表述为试验结束时历史状态。正式回执见official_v8_fine.json/.md，最后1组详情不公开。\n"
        experiment.write_text(text, encoding="utf8")
    print(json.dumps({"official_score": 99, "submission_id": 544054, "remaining": 4,
                      "exact_submitted_source_promoted": sha(ROOT / "submit.cpp") == receipt["source_sha256"]}))


if __name__ == "__main__":
    main()
