"""Verify all twelve recorded single-axis sources without more benchmarks."""
from pathlib import Path
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parent.parent
records = json.loads((ROOT / "research/v12_routing_results.json").read_text(encoding="utf8"))
plan = json.loads((ROOT / "research/v12_routing_plan.json").read_text(encoding="utf8"))
assert len(records) == len(plan["configs"]) == 12
base_path = Path(plan["base"])
assert hashlib.sha256(base_path.read_bytes()).hexdigest() == plan["base_sha256"]
base = base_path.read_text(encoding="utf8")
checks = []
for record in records:
    assert record["parameters"] == plan["configs"][record["name"]]
    assert len(record["parameters"]) == 1
    key, value = next(iter(record["parameters"].items()))
    expected, count = re.subn(rf"PRM\({key},\s*[^)]+\)", f"PRM({key}, {value})", base)
    assert count == 1
    source_path, exe_path = Path(record["source"]), Path(record["executable"])
    source = source_path.read_text(encoding="utf8")
    assert source == expected
    assert hashlib.sha256(source_path.read_bytes()).hexdigest() == record["source_sha256"]
    assert hashlib.sha256(exe_path.read_bytes()).hexdigest() == record["exe_sha256"]
    rows = json.loads((Path(record["result_dir"]) / "summary.json").read_text(encoding="utf8"))
    assert len(rows) == 16 and all(Path(r["input"]).parent.name == "train" for r in rows)
    assert all(r["ok"] for r in rows)
    checks.append({"name": record["name"], "parameter": key, "value": value,
                   "whole_source_equals_base_with_only_this_constant_replaced": True,
                   "source_sha256_matches": True, "exe_sha256_matches": True,
                   "all_16_inputs_from_train": True})
health_path = ROOT / "research/v12_routing_health.json"
health = json.loads(health_path.read_text(encoding="utf8"))
health.update({"source_integrity": checks, "single_axis_source_checks_all_pass": True,
               "all_twelve_valid_range_total_profit_negative": all(r["valid_range"]["total_profit_increase_pct"] < 0 for r in records),
               "extra_config_or_combination_added": False,
               "followup_selected_by_parent": ["pen_0875", "pen_0"],
               "followup_status": "Parent owns old-development evaluation; this subtask did not read it or any V12 held-out outcomes"})
health_path.write_text(json.dumps(health, ensure_ascii=False, indent=2), encoding="utf8")
report_path = ROOT / "research/v12_routing_review.md"
text = report_path.read_text(encoding="utf8")
marker = "## 训练筛选结论与源码核对"
assert marker not in text
text += "\n" + marker + "\n\n"
text += "12项范围内训练总利润全部下降，未发现已证实更好的替代参数。尤其LAK=0的14例全部退步，总利润−6.467%，本轮数据支持保留既有前瞻；GU=0也有12降2升，不支持直接关闭未知前驱位置猜测。\n\n"
text += "PEN=0.875总利润−0.460%，但等权平均+0.415%、中位比1.00156、最差−2.94%，7升6降1平；PEN=0总利润−0.589%，等权+0.452%、中位比1.00028、最差−5.22%，7升7降。主任务仅选择这两项进入旧开发集，以检查收益分布；这些正均值/中位数不能抵消训练总利润下降，也不是新验证收益。\n\n"
text += "已逐份重建基线只替换声明的单个PRM常量后应得到的完整文本，并与12份候选全文核对相同；来源与二进制哈希均匹配记录，所有192次输入均来自train16。核对没有产生额外benchmark、配置或组合，详情见v12_routing_health.json。\n"
report_path.write_text(text, encoding="utf8")
print(json.dumps({"single_axis_sources_verified": len(checks), "runs": health["runs"],
                  "audit_total": health["audit_total"], "all_negative_training_totals": health["all_twelve_valid_range_total_profit_negative"],
                  "extra_variants": False}))
