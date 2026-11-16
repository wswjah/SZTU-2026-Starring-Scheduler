"""Check V15 input separation and unchanged training profiles, no result access."""
from pathlib import Path
from decimal import Decimal,InvalidOperation
from collections import Counter,defaultdict
import hashlib
import json

ROOT=Path(__file__).resolve().parent.parent


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def config(path):
    rows=path.read_text(encoding="ascii",errors="strict").splitlines()
    data={}
    for line in rows:
        parts=line.split()
        if not parts:continue
        if len(parts)!=2:return None
        key,value=parts
        try:value=str(Decimal(value).normalize())
        except InvalidOperation:return None
        assert key not in data,(path,key)
        data[key]=value
    return data if "seed"in data else None


def digest(cfg):
    return hashlib.sha256(json.dumps(cfg,sort_keys=True,separators=(",",":")).encode("ascii")).hexdigest()


def main():
    plan=json.loads((ROOT/"research/v15_plan.json").read_text(encoding="utf8"))
    splits={"old32":"v13_train32","new96":"v15_train96","holdout":"v15_holdout","confirmation":"v15_confirmation"}
    entries={};profile_templates={}
    for label,directory in splits.items():
        manifest_path=ROOT/f"cases/{directory}/manifest.json"
        assert sha(manifest_path)==plan["case_manifests_sha256"][directory]
        manifest=json.loads(manifest_path.read_text(encoding="utf8"));rows=[]
        for entry in manifest:
            path=manifest_path.parent/entry["file"];cfg=config(path);assert cfg is not None
            assert sha(path)==entry["sha256"]
            declared={key:str(Decimal(str(value)).normalize())for key,value in entry["parameters"].items()}
            assert cfg==declared
            profile=path.stem.rsplit("_",1)[0]
            without_seed={key:value for key,value in cfg.items()if key!="seed"}
            if label=="old32":
                if profile in profile_templates:assert profile_templates[profile]==without_seed
                profile_templates[profile]=without_seed
            rows.append({"file":str(path),"profile":profile,"seed":cfg["seed"],"semantic_config_sha256":digest(cfg),
                         "without_seed":without_seed,"raw_sha256":entry["sha256"]})
        assert len(rows)=={"old32":32,"new96":96,"holdout":40,"confirmation":40}[label]
        entries[label]=rows
    assert len(profile_templates)==8
    old_counts=Counter(r["profile"]for r in entries["old32"]);new_counts=Counter(r["profile"]for r in entries["new96"])
    assert set(new_counts)==set(old_counts)==set(profile_templates)
    assert set(old_counts.values())=={4}and set(new_counts.values())=={12}
    for row in entries["new96"]:assert row["without_seed"]==profile_templates[row["profile"]]
    excluded={ROOT/f"cases/{name}"for name in ["v15_train96","v15_holdout","v15_confirmation"]}
    historical=[]
    for path in sorted((ROOT/"cases").rglob("*.in")):
        if any(parent in excluded for parent in path.parents):continue
        cfg=config(path)
        if cfg is not None:historical.append({"file":str(path),"seed":cfg["seed"],"semantic_config_sha256":digest(cfg)})
    history_seed=defaultdict(list);history_hash=defaultdict(list)
    for row in historical:
        history_seed[row["seed"]].append(row["file"]);history_hash[row["semantic_config_sha256"]].append(row["file"])
    fresh=entries["new96"]+entries["holdout"]+entries["confirmation"]
    assert len({r["seed"]for r in fresh})==176
    assert len({r["semantic_config_sha256"]for r in fresh})==176
    for row in fresh:
        assert row["seed"]not in history_seed,(row,history_seed[row["seed"]])
        assert row["semantic_config_sha256"]not in history_hash,(row,history_hash[row["semantic_config_sha256"]])
    train=entries["old32"]+entries["new96"];evaluation=entries["holdout"]+entries["confirmation"]
    assert len({r["seed"]for r in train})==128
    assert not{r["seed"]for r in train}&{r["seed"]for r in evaluation}
    assert not{r["semantic_config_sha256"]for r in train}&{r["semantic_config_sha256"]for r in evaluation}
    record={"scope":"Only cases input configs/manifests and frozen plan;no outcomes accessed",
            "case_counts":{key:len(value)for key,value in entries.items()},"historical_configs_checked":len(historical),
            "historical_unique_seeds":len(history_seed),"all176_new_seeds_unique_and_disjoint_from_history":True,
            "all176_new_semantic_cfg_hashes_unique_and_disjoint_from_history":True,
            "all128_training_disjoint_from80_evaluation_by_seed_and_config":True,
            "new96_exact_same8_profiles_excluding_seed":True,"old_profile_counts":dict(old_counts),"new_profile_counts":dict(new_counts),
            "profile_mix_after_merge":"16 worlds per profile,8 profiles=128;new seeds only,not wider training-profile distribution",
            "canonical_config_hash":"Sorted key/value map,Decimal-normalized numbers,seed included;different textualfloat spelling/order does not evade overlap checks",
            "expected_world_keys":["v13/"+Path(r["file"]).stem for r in entries["old32"]]+["v15/"+Path(r["file"]).stem for r in entries["new96"]],
            "frozen_manifest_hashes":plan["case_manifests_sha256"],"fresh_results_read":False}
    out=ROOT/"research/v15_input_independent_audit.json";out.write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding="utf8")
    print(json.dumps({key:record[key]for key in ["case_counts","historical_configs_checked","all176_new_seeds_unique_and_disjoint_from_history","all128_training_disjoint_from80_evaluation_by_seed_and_config","new96_exact_same8_profiles_excluding_seed"]}))


if __name__=="__main__":main()
