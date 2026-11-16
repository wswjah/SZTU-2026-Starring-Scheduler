"""Audit postselection input40/frozenprogram identities only;neverread results."""
from pathlib import Path
from decimal import Decimal
import hashlib
import json
from v15_independent_input_audit import config,digest,sha

ROOT=Path(__file__).resolve().parent.parent


def object_sha(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode("utf8")).hexdigest()


def main():
    plan_path=ROOT/"research/v15_postconfirmation_plan.json"
    plan=json.loads(plan_path.read_text(encoding="utf8"))
    assert set(plan["fixed_candidates"])=={"v12_scan_input_fix","v14_mlp_A","v14_mlp_B","v15_B128_120"}
    directory=ROOT/"cases/v15_postconfirmation";manifest_path=directory/"manifest.json"
    manifest=json.loads(manifest_path.read_text(encoding="utf8"));assert len(manifest)==40
    template={row["file"]:row for row in json.loads((ROOT/"cases/v15_holdout/manifest.json").read_text(encoding="utf8"))}
    rows=[]
    for index,entry in enumerate(manifest):
        path=directory/entry["file"];cfg=config(path);assert cfg is not None and sha(path)==entry["sha256"]
        assert int(Decimal(cfg["seed"]))==2021116287+index*104729
        canonical_declared={key:config_value for key,config_value in config(path).items()}
        assert canonical_declared=={key:str(Decimal(str(value)).normalize())for key,value in entry["parameters"].items()}
        old_cfg=config(ROOT/"cases/v15_holdout"/entry["file"])
        assert {k:v for k,v in cfg.items()if k!="seed"}=={k:v for k,v in old_cfg.items()if k!="seed"}
        assert entry["category"]==template[entry["file"]]["category"]
        rows.append({"file":str(path),"seed":cfg["seed"],"raw_sha256":sha(path),"semantic_cfg_sha256":digest(cfg)})
    assert len({r["seed"]for r in rows})==len({r["semantic_cfg_sha256"]for r in rows})==40
    history=[]
    for path in sorted((ROOT/"cases").rglob("*.in")):
        if directory in path.parents:continue
        cfg=config(path)
        if cfg is not None:history.append({"seed":cfg["seed"],"hash":digest(cfg)})
    historical_seeds={r["seed"]for r in history};historical_hashes={r["hash"]for r in history}
    assert not{r["seed"]for r in rows}&historical_seeds
    assert not{r["semantic_cfg_sha256"]for r in rows}&historical_hashes
    train=[]
    for subdir in ["v13_train32","v15_train96"]:
        for path in (ROOT/f"cases/{subdir}").glob("*.in"):train.append(config(path))
    assert len(train)==128
    assert not{r["seed"]for r in rows}&{r["seed"]for r in train}
    assert not{r["semantic_cfg_sha256"]for r in rows}&{digest(r)for r in train}
    programs=[]
    for name,snapshot in plan["fixed_candidates"].items():
        version_path=Path(snapshot["packed_source"]).parent/"manifest.json"
        version=json.loads(version_path.read_text(encoding="utf8"))
        assert object_sha(version)==object_sha(snapshot),(name,"current version manifest drifted from planned snapshot")
        source=Path(snapshot["source"]);packed=Path(snapshot["packed_source"]);exe=Path(snapshot["executable"])
        assert sha(source)==snapshot["source_sha256"]and sha(packed)==snapshot["packed_sha256"]and sha(exe)==snapshot["exe_sha256"]
        assert packed.stat().st_size==snapshot["packed_bytes"]
        programs.append({"name":name,"manifest":str(version_path),"manifest_file_sha256":sha(version_path),
                         "manifest_semantic_sha256":object_sha(snapshot),"manifest_exact_to_plan_snapshot":True,
                         "source_sha256":snapshot["source_sha256"],"packed_sha256":snapshot["packed_sha256"],
                         "exe_sha256":snapshot["exe_sha256"],"all_actual_files_match_frozen_hashes":True})
    result={"date":"2026-11-16","plan_sha256":sha(plan_path),"manifest_sha256":sha(manifest_path),
            "new_cases":40,"historical_parameter_inputs_checked":len(history),"train_worlds_checked":128,
            "all_input_files_match_manifest_sha":True,"all_seeds_follow_predeclared_formula":True,
            "all40_seeds_and_semantic_cfg_hashes_unique":True,"no_seed_or_cfg_repeated_in_any_historical_input":True,
            "no_train128_seed_or_cfg_overlap":True,"same_predeclared32profile_plus8shift_configs_seedonly_change":True,
            "fixed_programs":programs,"inputs":rows,
            "design":"Postselection confirmation: expandedB chosen after primary80,then40newseeds evaluated with fixedbaseline/oldA32/oldB32/B128;notpartoftheoriginal80 preregistration",
            "new40_results_or_profits_read":False,"new_fit_runs":0,"new_interactive_runs":0,"source_or_frozen_files_modified":False,
            "original128_audit_conclusions_changed":False}
    out=ROOT/"research/v15_postconfirmation_input_review.json"
    assert not out.exists();out.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf8")
    report_path=ROOT/"research/v15_independent_review.md";text=report_path.read_text(encoding="utf8")
    marker="## 主80选择之后的额外40输入核对"
    assert marker not in text
    text+="\n"+marker+"\n\n"
    text+=(f"主任务在主80结果已见后选择扩训B继续确认，先记录v15_postconfirmation_plan.json并固定baseline、旧A32、旧B32、扩训B128四源，再增加独立40新种子。独立检查这40个manifest/文件SHA、seed2021116287+i×104729及仅换seed的32原profile+8shift布局均吻合；40个seed和含seed语义cfg hash内部唯一，并与{len(history)}个历史参数输入及train128完全无重叠。四个当前版本manifest与计划快照的规范化hash相同，可读源/提交源/实际exe也全部匹配冻结hash。新证据见research/v15_postconfirmation_input_review.json。这属于选择后的额外独立确认，不能说成最初80计划的一部分；原128数据审查结论不变。本段未读取额外40的任何结果或利润，没有新训练、交互或源文件修改。\n")
    report_path.write_text(text,encoding="utf8")
    print(json.dumps({"new_cases":40,"historical_inputs":len(history),"seeds_and_cfg_disjoint":True,
                      "frozen_programs_verified":len(programs),"new40_profits_read":False}))


if __name__=="__main__":main()
