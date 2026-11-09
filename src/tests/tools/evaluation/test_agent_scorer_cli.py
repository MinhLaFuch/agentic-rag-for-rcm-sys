import json
import sys
from dataclasses import replace

import pandas as pd
import pytest
import yaml

from package.tools.corpus import ItemCorpus
from package.tools.recommenders import ItemKNNRecommender
from package.tools.recommenders.item_knn_data_hash import item_knn_data_hash
from package.tools.recommenders.fit_provenance import fit_provenance
from scripts.evaluation import run_agent_eval as script
from tests.tools.evaluation.test_ranking_streaming import environment


@pytest.mark.parametrize("mode,cached", [("baseline", False), ("hybrid", True)])
def test_cli_records_selected_scorer_cache_and_type1_calls(environment, monkeypatch, mode, cached):
    base, paths, items = environment
    paths = replace(paths, experiments_dir=base/"experiments", log_dir=base/"logs")
    users = {"u0":0,"u1":1,"u2":2}
    meta = pd.DataFrame({"parent_asin":[f"i{i}" for i in range(7)], "domain":["D"]*7,
                         "title":["keyboard"]*7,"first_seen_ts":[1]*7})
    monkeypatch.setattr(script,"get_data_paths",lambda *a:paths)
    monkeypatch.setattr(script,"get_domains",lambda:["D"])
    monkeypatch.setattr(script,"verify_tag_manifest",lambda *a,**k:{"status":"match","manifest_sha256":"fixture","warnings":[]})
    monkeypatch.setattr(script,"build_meta_files",lambda *a:[("D",str(paths.raw_dir/"meta_D.jsonl.gz"))])
    monkeypatch.setattr(script,"load_mappings",lambda *a:(users,items))
    monkeypatch.setattr(script,"build_first_seen_timestamps",lambda *a,**k:{key:1 for key in items})
    monkeypatch.setattr(script,"build_corpus",lambda *a,**k:(ItemCorpus.from_dataframe(meta),meta,1.,{}))
    original_config=script.load_config
    def config(name):
        document=original_config(name)
        if name=="agent/agent_eval":
            document={"agent_eval":{**document["agent_eval"],"k":3}}
        return document
    monkeypatch.setattr(script,"load_config",config)
    def core(_paths, eval_on, neighbors, fit, user2id, item2id):
        if not cached:
            return None
        model=ItemKNNRecommender(neighbors).fit(fit)
        model._fit_data_hash=item_knn_data_hash(fit)
        model._evaluation_artifact_status="validated_train_core_cache"
        model._evaluation_fit_provenance=fit_provenance(fit,user2id=user2id,item2id=item2id,
                                                       eval_on=eval_on,tag="toy",fit_splits=["train_core"])
        return model
    monkeypatch.setattr(script,"build_core_model",core)
    monkeypatch.setattr(sys,"argv",["agent_eval","--agents","baseline,type1","--per-segment","1",
        "--inference-mode","template","--request-scope","realistic","--no-prebuilt",
        "--scorer",mode,"--trajectory-file",mode+".jsonl"])
    script.main()
    result=paths.experiments_dir/"agent_eval"/"exp_001"
    config=yaml.safe_load((result/"config.yaml").read_text(encoding="utf-8"))["config"]
    assert config["knn_cache_used"] is cached
    assert config["scorer"]["mode"] == mode
    assert config["protocol"]["scorer"]==config["scorer"]
    assert config["scorer"]["history_splits"]==["train"]
    rows=[json.loads(s) for s in (result/"trajectories.jsonl").read_text(encoding="utf-8").splitlines()]
    type1=[r for r in rows if r["agent"]=="type1"]
    assert type1
    assert all(r["steps"] and r["tool_calls"] for r in type1)
    if mode=="hybrid":
        train=pd.read_parquet(paths.split_path("train"))
        id2item={v:k for k,v in items.items()}
        for request in (json.loads(s) for s in (result/"requests.jsonl").read_text(encoding="utf-8").splitlines()):
            if request.get("user_idx") is None:
                continue
            seen={id2item[i] for i in train.loc[train.user_idx==request["user_idx"],"item_idx"]}
            for row in rows:
                if row["agent"]=="baseline" and row["request_id"]==request["request_id"]:
                    assert not seen.intersection(row["recommended"])
