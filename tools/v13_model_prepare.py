"""Reconcile current99 per-flow labels and verify observational noninterference."""
from pathlib import Path
import csv
import hashlib
import io
import json
import re
from v13_model_common import ROOT,FEATURES


def main():
    raw=json.loads((ROOT/"results/v13_model_trace/summary.json").read_text(encoding="utf8"))
    baseline={r["case"]:r for r in json.loads((ROOT/"results/v13_baseline_train32/summary.json").read_text(encoding="utf8"))}
    assert len(raw)==len(baseline)==32
    all_rows=[];records=[]
    for run in raw:
        assert run["ok"]
        assert run["report"]==baseline[run["case"]]["report"],(run["case"],"trace changed complete baseline report")
        path=Path(run["run_dir"])/"solver_stderr.txt"
        lines=path.read_text(encoding="utf8").splitlines()
        metadata=next(line for line in lines if line.startswith("V13_MODEL_META,"))
        meta=dict(part.split("=",1)for part in metadata.split(",")[1:])
        header=next(line.split(",")[1:]for line in lines if line.startswith("V13_MODEL_HEADER,"))
        values=[line.split(",")[1:]for line in lines if line.startswith("V13_MODEL,")]
        assert all(len(row)==len(header)for row in values)
        rows=[{k:float(v)if k.startswith("f")and k[1:].isdigit()else int(v)for k,v in zip(header,row)}for row in values]
        assert len(rows)==int(meta["flows"])
        for row in rows:
            assert bool(row["seen"])==(row["runs"]>0)
            assert row["cost"]==row["run"]+row["pull"]+row["net"]
            assert row["seen"]or(row["cost"]==0 and row["earned"]==0)
        for field in ["earned","cost","run","pull","net"]:
            assert sum(r[field]for r in rows)==run[field],(run["case"],field,sum(r[field]for r in rows),run[field])
        assert sum(r["earned"]-r["cost"]for r in rows)==run["profit"]
        all_rows.extend(dict(case=run["case"],T=int(meta["T"]),**row)for row in rows)
        records.append({"case":run["case"],"flows":len(rows),"admitted":sum(r["seen"]for r in rows),
                        "ledger_exact":True,"full_report_equal":True,"late":int(meta["late"]),"guard_returns":int(meta["guard_returns"]),
                        "trace_sha256":hashlib.sha256(path.read_bytes()).hexdigest()})
    directory=ROOT/"results/v13_model_dataset";directory.mkdir(parents=True,exist_ok=True)
    for label,rows in [("all_flows",all_rows),("admitted",[r for r in all_rows if r["seen"]])]:
        with (directory/f"{label}.csv").open("w",newline="",encoding="utf8")as stream:
            writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    record={"worlds":records,"features":FEATURES,"all_flows":len(all_rows),"admitted":sum(r["seen"]for r in all_rows),
            "trace_runs":32,"all_reports_exact":True,"all_perflow_ledgers_exact":True,"audit_total":sum(r["audit_total"]for r in raw),
            "dataset":"results/v13_model_dataset/admitted.csv","never_started_not_negative_labels":True,
            "source_sha256":hashlib.sha256((ROOT/"candidates/v13_model/trace.cpp").read_bytes()).hexdigest(),"official_submission_sent":False}
    (ROOT/"research/v13_model_dataset.json").write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding="utf8")
    print(json.dumps({k:v for k,v in record.items()if k not in ["worlds","features"]},ensure_ascii=False))


if __name__=="__main__":main()
