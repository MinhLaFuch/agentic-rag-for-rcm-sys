"""Read-only target/fit availability and source/merge loss diagnosis; no fitting."""
import argparse
from collections import Counter,defaultdict
import json
from pathlib import Path
import time

import pandas as pd
import yaml

from package.config import get_data_paths
from package.data.mapping import load_mappings
from package.tools.evaluation import save_experiment,next_experiment_dir
from package.tools.evaluation.retrieval_loss_breakdown import retrieval_loss_breakdown
from package.tools.recommenders.file_hash import file_hash
from package.tools.recommenders.mapping_hash import mapping_hash


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source",type=Path,required=True)
    args=ap.parse_args()
    started=time.perf_counter()
    doc=yaml.safe_load((args.source/"config.yaml").read_text(encoding="utf-8"))
    d=doc["run"]["dataset"]
    if d["eval_on"]!="validation": raise ValueError("validation diagnosis only")
    paths=get_data_paths(d["tag"])
    users,items=load_mappings(paths.mapped_dir)
    if mapping_hash(users)!=d["user_mapping_hash"] or mapping_hash(items)!=d["mapping_hash"]:
        raise ValueError("mapping mismatch")
    train=paths.split_path("train")
    if file_hash(train)!=d["split_files"]["train"]["sha256"]: raise ValueError("train hash mismatch")
    candidate=args.source/"candidate_lists.jsonl"
    before=file_hash(candidate)
    if before!=json.loads((args.source/"artifact_hashes.json").read_text())["candidate_lists.jsonl"]:
        raise ValueError("candidate hash mismatch")
    print("[diagnostic] reading train item column; no ItemKNN fit",flush=True)
    fit_items=set(pd.read_parquet(train,columns=["item_idx"]).item_idx.unique())
    id2item={v:k for k,v in items.items()}
    stats=defaultdict(Counter); seen=set(); queries=Counter()
    expected={u for ids in doc["config"]["sampled_user_ids"].values() for u in ids}
    with candidate.open(encoding="utf-8") as source:
        for line in source:
            r=json.loads(line); u=r["user_idx"]
            if u not in expected or u in seen: raise ValueError("candidate sample mismatch")
            seen.add(u)
            queries[r["segment"]+"_users"]+=1
            queries[r["segment"]+"_with_query"]+=bool(r["semantic_query"]["sent"])
            for group,values in retrieval_loss_breakdown(r,id2item,fit_items).items():
                stats[r["segment"]+":"+group].update(values)
    if seen!=expected or file_hash(candidate)!=before: raise ValueError("incomplete or changed candidates")
    output=save_experiment(next_experiment_dir(paths.experiments_dir/"retrieval_diagnostics"),
        config={"source":str(args.source.resolve()),"candidate_sha256":before,
                "source_config_sha256":file_hash(args.source/"config.yaml"),
                "train_sha256":d["split_files"]["train"]["sha256"],
                "counting":"unique novel target pairs per user; micro counts, not macro recall",
                "metadata_scope":"not measured; absence from fit does not imply missing metadata",
                "loss_scope":"saved top-budget source lists only; cannot diagnose targets below original source limits"},
        metrics={"counts":{k:dict(v) for k,v in stats.items()},"query_availability":dict(queries),
                 "users":len(seen),"fit_catalog_items":len(fit_items)},
        seed=doc["run"]["seed"],dataset_info=d,runtime_seconds=time.perf_counter()-started,
        notes="Read-only artifacts diagnosis. No model fitting, retrieval or production change.")
    print("Saved:",output,flush=True)
    for k,v in stats.items():
        if k.endswith(":overall"): print(k,dict(v),flush=True)


if __name__=="__main__": main()
