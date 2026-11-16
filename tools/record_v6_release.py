"""Promote the verified official result and preserve the previous release."""
from pathlib import Path
import hashlib
import json
import shutil

ROOT = Path(__file__).resolve().parent.parent
VERSION = ROOT / "versions/v6_attributed96"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    receipt = json.loads((ROOT / "research/official_v6_attributed96.json").read_text(encoding="utf8"))
    final = receipt["final_status"]
    account = receipt["postflight_meta"]["by_qid"]["488"]
    assert final["exam_score"] == 96 and account["best_score"] == 96
    assert account["used"] == 5 and account["remain"] == 5
    version = json.loads((VERSION / "manifest.json").read_text(encoding="utf8"))
    assert digest(VERSION / "submit.cpp") == receipt["source_sha256"] == version["packed_source"]["sha256"]
    assert digest(VERSION / "main.cpp") == version["source_sha256"]
    exe = ROOT / "build/v6_attributed96.exe"
    assert digest(exe) == version["executable"]["sha256"]
    assert version["validation"]["all_ok"] and version["validation"]["focused_regressions_passed"]

    # Preserve the previous default, without overwriting any earlier archive.
    old_path = ROOT / "results/final_manifest.json"
    old = json.loads(old_path.read_text(encoding="utf8"))
    if old["official_score"] < 96:
        archive = ROOT / "versions/v3_aggressive"
        for filename in ["README.md", "REPORT.md"]:
            target = archive / (filename.replace(".md", "_before_v6.md"))
            if not target.exists():
                shutil.copy2(ROOT / filename, target)
        target = archive / "final_manifest_before_v6.json"
        if not target.exists():
            shutil.copy2(old_path, target)
        for filename in ["main.cpp", "submit.cpp"]:
            assert digest(ROOT / filename) == old["artifacts"][filename]["sha256"]
            assert (ROOT / filename).read_bytes() == (archive / filename).read_bytes()
    for source, target in [(VERSION / "main.cpp", ROOT / "main.cpp"),
                           (VERSION / "submit.cpp", ROOT / "submit.cpp"),
                           (exe, ROOT / "build/main.exe"), (exe, ROOT / "build/submit.exe")]:
        shutil.copy2(source, target)
    version.update(official_submission_sent=True, official_submission_id=543902,
                   official_score=96, official_receipt="research/official_v6_attributed96.json")
    (VERSION / "manifest.json").write_text(json.dumps(version, ensure_ascii=False, indent=2), encoding="utf8")
    names = ["main.cpp", "submit.cpp", "build/main.exe", "build/submit.exe", "tpj_win.exe"]
    release = {
        "date": "2026-11-15", "candidate": "v6_attributed96_bounds_and_command_budget",
        "official_score": 96, "official_submission_id": 543902,
        "official_submission_url": receipt["submission_url"],
        "official_submissions_total": 5, "remaining_submissions": 5,
        "previous_85_manifest": "versions/v3_aggressive/final_manifest_before_v6.json",
        "upstream_repository": version["upstream_repository"], "upstream_commit": version["upstream_commit"],
        "attribution_preserved": True,
        "artifacts": {n: {"bytes": (ROOT / n).stat().st_size, "sha256": digest(ROOT / n)} for n in names},
        "results": "results/v6_attributed96", "focused_regressions": "results/v6_attributed96_focused/summary.json",
        "frozen_experiment": "versions/v6_attributed96/manifest.json", "best_source_matches_official_receipt": True}
    old_path.write_text(json.dumps(release, ensure_ascii=False, indent=2), encoding="utf8")
    readme = """# 星环算力平台调度：96分版本

**本账号最高自动分：96 / 100**，2026-11-15，[提交543902](https://acm.sztu.edu.cn:40081/examsys/contest/status?cid=2231#solution_id=543902)。最新已登录核验累计使用5次、剩余5次。

当前默认代码基于 [Shuang-su 公开的96分解法](https://github.com/Shuang-su/SZTU-2026-data-structure-final-homework/tree/a35a23f3a8a3c623ff9c62af15e680143264de5e)，固定commit为 `a35a23f3a8a3c623ff9c62af15e680143264de5e`。可读源码和提交文件均保留上游来源说明。本项目实际修复后继数组越界和指令预算，未用变量混淆掩饰来源，不承诺查重结果。

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
"""
    (ROOT / "README.md").write_text(readme, encoding="utf8")
    report_path = ROOT / "REPORT.md"
    report = report_path.read_text(encoding="utf8")
    marker = "<!-- v6 official release -->"
    if marker not in report:
        intro = f"""# 验证记录

{marker}
2026-11-15 更新：本账号最高自动分已提高至 **96分**，提交 **543902**。本轮两次为V4 85分（543899）、署名96分派生修复版96分（543902）；累计已用5次、剩余5次，已正常登录核验。

根目录main.cpp/submit.cpp与build默认程序已切到通过验证的V6，提交文件16,926字节。上游为Shuang-su固定commit，来源说明保留；修复后继数组越界、20,000指令预算、预热原子性和延后止损。54次闭环/97,075次对账全对，定向边界及负对照通过。学校页面500ms/16300kB，详情未公开，不能判断余下4组失分原因。

当前清单：results/final_manifest.json；正式回执：research/official_v6_attributed96.json/.md；验证与修改：research/v6_attributed96_review.md。旧85分交付清单和文档已在versions/v3_aggressive归档。

## 早期84/85分路线历史记录

以下保留原记录，其中默认文件与分数是各自日期的历史状态。
"""
        report_path.write_text(intro + report.split("\n", 1)[1], encoding="utf8")
    print(json.dumps({"score": 96, "solution_id": 543902, "remaining": 5,
                      "source_matches_receipt": digest(ROOT / "submit.cpp") == receipt["source_sha256"]}))


if __name__ == "__main__":
    main()
