"""Evaluation-only policy comparison using existing ranker, corpus and checkpoints.

Frozen mode measures policy/fetch only; fresh mode retrieves once per user.
Neither mode changes production policies or selects on test data.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import time
import uuid

import numpy as np
import pandas as pd
import yaml

from package.config import get_data_paths, get_domains, load_config
from package.data.mapping import load_mappings
from package.tools import ItemCFTool, QueryTool, RecoModelTool, SemanticSearchTool
from package.tools.corpus import build_corpus
from package.tools.corpus.apply_metadata_policy import apply_metadata_policy
from package.tools.evaluation import next_experiment_dir, save_experiment
from package.tools.evaluation.policy_chain_compare import policy_chain_compare
from package.tools.evaluation.ranking_run_store import RankingRunStore
from package.tools.evaluation.stage_progress import StageProgress
from package.tools.evaluation.save_experiment import _source_fingerprint, _environment_versions
from package.tools.recommenders.load_item_knn import load_item_knn
from package.tools.recommenders.file_hash import file_hash
from package.tools.recommenders.mapping_hash import mapping_hash
from package.tools.score import BaselineScorer
from package.tools.evaluation.normalize_query_text import normalize_query_text
from package.tools.evaluation.retrieval_loss_breakdown import retrieval_loss_breakdown
from scripts.evaluation.candidate_recall import drop_seen, item_text_tables, round_robin
from scripts.evaluation.analyze_ranking_bottlenecks import _metrics, _score_rows

POLICIES = ("baseline", "popularity_first", "rrf_60")
MERGES = ("union_rr", "union_all")


def _verify(entries):
    for entry in entries:
        p = Path(entry["path"])
        if (file_hash(p) if p.exists() else None) != entry["sha256"]:
            raise ValueError(f"input hash mismatch: {p}")


def _fresh(template, ctx):
    """Only fit history supplies retrieval inputs; template labels are copied later."""
    started = time.perf_counter()
    user = template["user_idx"]
    recent = ctx["recent"].get(user, [])
    seen = set(recent)
    conf = ctx["config"]
    budget = conf["candidate_budget_per_source"]
    ask = min(budget + len(seen), int(load_config("agent/tools")["tools"]["max_candidates"]))
    names = lambda ids: [ctx["id2item"][int(i)] for i in ids]
    source_times = {}
    t = time.perf_counter()
    pop = [int(i) for i in ctx["popular"][:ask]]
    source_times["popularity"] = time.perf_counter()-t
    seeds = names(recent[:conf["retrieval"]["seed_items"]])
    t = time.perf_counter()
    cf = ctx["cf"](items=seeds, top_k=ask) if seeds else None
    source_times["item_cf"] = time.perf_counter()-t
    cf_ids = [ctx["item2id"][x["item_id"]] for x in cf.data["candidates"]
              if x["item_id"] in ctx["item2id"]] if cf and cf.ok else []
    query_items = names(recent[:conf["retrieval"]["query_items"]])
    t = time.perf_counter()
    texts = ctx["text"](query_items)
    raw = " ".join(texts[i][0] for i in query_items if i in texts)
    query = normalize_query_text(raw, conf["protocol"]["query_normalization"])
    source_times["query_construction"] = time.perf_counter()-t
    t = time.perf_counter()
    sem = ctx["semantic"](query=query, limit=ask) if query.strip() else None
    source_times["semantic"] = time.perf_counter()-t
    sem_ids = [ctx["item2id"][x["item_id"]] for x in sem.data["candidates"]
               if x["item_id"] in ctx["item2id"]] if sem and sem.ok else []
    t=time.perf_counter()
    sources = dict(popularity=pop, item_cf=cf_ids, semantic=sem_ids)
    filtered = {s: drop_seen(ids, seen, budget) for s,ids in sources.items()}
    raw_union=list(dict.fromkeys(i for ids in sources.values() for i in ids))
    record = dict(template)
    record.update(sources_raw={s:names(ids) for s,ids in sources.items()},
                  sources_after_seen_filter={s:names(ids) for s,ids in filtered.items()},
                  candidate_sets={"union_rr":names(round_robin(list(filtered.values()),budget)),
                                  "union_all":names(list(dict.fromkeys(i for ids in filtered.values() for i in ids)))},
                  source_failures={"item_cf":cf.error if cf and not cf.ok else None,
                                   "semantic":sem.error if sem and not sem.ok else None},
                  source_latency_seconds=source_times,
                  raw_union=names(raw_union),raw_union_after_seen=names([i for i in raw_union if i not in seen]),
                  seen_filtered_union=names(list(dict.fromkeys(i for ids in filtered.values() for i in ids))),
                  semantic_query={"raw":raw,"sent":query,"normalization":conf["protocol"]["query_normalization"],
                                  "changed":raw!=query,"empty_after_normalization":bool(raw.strip()) and not query.strip()})
    source_times["merge_filter_record"]=time.perf_counter()-t
    record["retrieval_seconds"]=time.perf_counter()-started
    return record


def _summary(store, item2id, seed, bootstrap_samples):
    acceptance=load_config("eval/policy_acceptance")["policy_acceptance"]
    states = {}
    deltas = {}
    cold = {}
    for merge in MERGES:
        aligned = [iter(store.rows(f"{merge}:{p}")) for p in POLICIES]
        for triple in zip(*aligned):
            records = [row for _,row in triple]
            if len({r["user_idx"] for r in records}) != 1:
                raise ValueError("policy user alignment mismatch")
            base = records[0]
            for r in records:
                key = (merge,r["segment"],r["policy"])
                state = states.setdefault(key,dict(requests=0,eligible=0,errors=Counter(),quality=Counter(),rank_quality=Counter(),
                                                   filtering=Counter(),catalog=set(),policy=[],fetch=[],combined=[],chain=[]))
                state["requests"] += 1
                state["filtering"].update(input_candidates=r["input_candidates"],
                                           eligible_candidates=r["eligible_candidates"],
                                           removed=r["eligibility_removed"])
                state["errors"].update(policy=bool(r["policy_error"]),metadata=bool(r["metadata_error"]),
                                        fallback=bool(r["fallback"]),retrieval=any(r["retrieval_errors"].values()))
                state["policy"].append(r["policy_seconds"])
                state["fetch"].append(r["fetch_seconds"])
                state["combined"].append(r["policy_fetch_seconds"])
                if r["retrieval_seconds"] is not None:
                    state["chain"].append(r["retrieval_seconds"]+r["policy_fetch_seconds"])
                targets = set(r["targets_unseen_in_fit"])
                if targets:
                    state["eligible"] += 1
                    for k in (5,10,20):
                        state["quality"].update(_metrics(r["delivered_ids"],targets,item2id,k))
                        state["rank_quality"].update(_metrics(r["ranked_ids"],targets,item2id,k))
                    state["catalog"].update(r["delivered_ids"][:10])
                    if r["policy"] != "baseline":
                        delta = (_metrics(r["delivered_ids"],targets,item2id,10)["ndcg@10"]-
                                 _metrics(base["delivered_ids"],targets,item2id,10)["ndcg@10"])
                        deltas.setdefault(key,[]).append(delta)
                if r["segment"] == "cold":
                    cold[key] = cold.get(key,True) and r["ranked_ids"]==base["ranked_ids"] and r["scores"]==base["scores"]
    rng = np.random.default_rng(seed)
    result = {}
    for (merge,segment,policy),s in states.items():
        def timing(v):
            return {"n":len(v),"mean":float(np.mean(v)),"p95":float(np.percentile(v,95))} if v else None
        n = s["eligible"]
        row = dict(requests=s["requests"],eligible_users=n,
                   metrics={k:v/n for k,v in s["quality"].items()} if n else {},
                   pre_fetch_metrics={k:v/n for k,v in s["rank_quality"].items()} if n else {},
                   catalog_coverage_at10=len(s["catalog"])/len(item2id),unique_top10=len(s["catalog"]),
                   errors={k:int(v) for k,v in s["errors"].items()},policy_latency=timing(s["policy"]),fetch_latency=timing(s["fetch"]),
                   failure_rates={k:v/s["requests"] for k,v in s["errors"].items()},
                   filtering=dict(s["filtering"]),
                   policy_fetch_latency=timing(s["combined"]),fresh_chain_service_latency=timing(s["chain"]),
                   cold_identical=cold.get((merge,segment,policy)))
        if (merge,segment,policy) in deltas:
            values,counts = np.unique(deltas[merge,segment,policy],return_counts=True)
            estimates = rng.multinomial(n,counts/n,size=bootstrap_samples) @ values / n
            alpha=acceptance["family_alpha"]/acceptance["planned_comparisons"]
            row["paired_ndcg10"] = {"mean_delta":float(np.mean(deltas[merge,segment,policy])),
                                    "familywise95_ci":np.percentile(estimates,[100*alpha/2,100*(1-alpha/2)]).tolist(),
                                    "individual_confidence":1-alpha,"resamples":bootstrap_samples}
        result.setdefault(merge,{}).setdefault(segment,{})[policy]=row
    for segments in result.values():
        for segment,policies in segments.items():
            b = policies["baseline"]
            for policy,r in policies.items():
                if policy=="baseline": continue
                if segment=="cold":
                    r["guardrails"]={"identical":r["cold_identical"],
                                     "errors":all(r["errors"].get(k,0)<=b["errors"].get(k,0) for k in ("policy","metadata","fallback","retrieval"))}
                    continue
                bm,rm=b["metrics"],r["metrics"]
                if not bm:
                    r["guardrails"]={"quality":"inconclusive: no eligible users"}; continue
                delta=rm["ndcg@10"]-bm["ndcg@10"]
                checks=dict(ndcg_effect=delta>=max(acceptance["ndcg_absolute_min"],acceptance["ndcg_relative_min"]*bm["ndcg@10"]),
                            paired_lower_positive=r["paired_ndcg10"]["familywise95_ci"][0]>0,
                            recall=rm["recall@10"]>=acceptance["recall_hit_retention_min"]*bm["recall@10"],
                            hit=rm["hit_rate@10"]>=acceptance["recall_hit_retention_min"]*bm["hit_rate@10"],
                            coverage=r["catalog_coverage_at10"]>=acceptance["coverage_retention_min"]*b["catalog_coverage_at10"],
                            policy_fetch_p95=r["policy_fetch_latency"]["p95"]<=acceptance["policy_fetch_p95_ratio_max"]*b["policy_fetch_latency"]["p95"],
                            errors=all(r["errors"].get(k,0)<=b["errors"].get(k,0) for k in ("policy","metadata","fallback","retrieval")))
                checks["fresh_chain_p95"]=(r["fresh_chain_service_latency"]["p95"]<=acceptance["fresh_chain_p95_ratio_max"]*b["fresh_chain_service_latency"]["p95"]
                                           if r["fresh_chain_service_latency"] else None)
                r["guardrails"]=checks
    return result


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source",type=Path,required=True)
    ap.add_argument("--item-knn",type=Path,required=True,help="Validated existing checkpoint model; never refit")
    ap.add_argument("--work-dir",type=Path,required=True)
    ap.add_argument("--resume",action="store_true")
    ap.add_argument("--mode",choices=("frozen","fresh"),default="frozen")
    ap.add_argument("--per-segment",type=int,default=100,help="Prefix of source's fixed sample; 5000 for full exp_009")
    ap.add_argument("--seed",type=int,default=42)
    ap.add_argument("--bootstrap-samples",type=int,default=10000)
    args=ap.parse_args()
    if args.per_segment<1 or args.bootstrap_samples<1000: ap.error("positive sample and >=1000 bootstrap resamples required")
    contract=Path(__file__).resolve().parents[2]/"configs"/"eval"/"policy_acceptance.yaml"
    doc=yaml.safe_load((args.source/"config.yaml").read_text(encoding="utf-8"))
    cfg,dataset=doc["config"],doc["run"]["dataset"]
    if dataset["eval_on"]!="validation": raise ValueError("validation only; no test selection")
    if cfg["scorers"]["baseline_weight"]!=1e-6: raise ValueError("unsupported baseline")
    identity=cfg["checkpoint_identity"]
    entries=list(identity["split_files"].values())+list(identity["metadata_files"].values())
    entries += [{"path":p,"sha256":h} for p,h in identity["mapping_files"].items()]
    entries += identity.get("exclusion_manifests",[])
    for name,digest in json.loads((args.source/"artifact_hashes.json").read_text()).items():
        entries.append({"path":str(args.source/name),"sha256":digest})
    entries += [{"path":str(p.resolve()),"sha256":file_hash(p)} for p in
                (args.source/"config.yaml",args.item_knn,args.item_knn.with_suffix(".meta.json"),contract)]
    print("[provenance] verifying source, splits, mappings, metadata, model and contract",flush=True)
    _verify(entries)
    run_identity=dict(mode=args.mode,seed=args.seed,per_segment=args.per_segment,
                      bootstrap_samples=args.bootstrap_samples,files=entries,
                      code=_source_fingerprint(),environment=_environment_versions())
    paths=get_data_paths(dataset["tag"])
    with RankingRunStore(args.work_dir,run_identity,resume=args.resume) as store:
        published=store.get("publication_destination")
        if published and Path(published).exists():
            published=Path(published)
            for name,h in json.loads((published/"artifact_hashes.json").read_text()).items():
                if file_hash(published/name)!=h: raise ValueError("published artifact changed")
            store.put("final_experiment",str(published.resolve()))
        if store.get("final_experiment"):
            print("Already complete:",store.get("final_experiment")); return
        users,items=load_mappings(paths.mapped_dir)
        if mapping_hash(users)!=dataset["user_mapping_hash"] or mapping_hash(items)!=dataset["mapping_hash"]:
            raise ValueError("mapping assignment mismatch")
        if not all("::" in name for name in items):
            raise ValueError("policy-chain runner currently requires namespaced item mapping")
        fit=pd.read_parquet(paths.split_path("train"),columns=["user_idx","item_idx","timestamp"])
        target=pd.read_parquet(paths.split_path("validation"),columns=["user_idx","item_idx","timestamp"])
        selected={seg:ids[:args.per_segment] for seg,ids in cfg["sampled_user_ids"].items()}
        if any(len(ids)!=args.per_segment for ids in selected.values()): raise ValueError("source cohort too small")
        chosen={u for ids in selected.values() for u in ids}
        target_by_user=target[target.user_idx.isin(chosen)].groupby("user_idx").item_idx.apply(set).to_dict()
        recent=(fit[fit.user_idx.isin(chosen)].sort_values("timestamp").groupby("user_idx").item_idx
                .apply(lambda x:list(x)[::-1]).to_dict())
        knn=load_item_knn(args.item_knn,cfg["retrieval"]["item_knn_neighbors"],fit[["user_idx","item_idx"]],
                          user2id=users,item2id=items,eval_on="validation",tag=dataset["tag"])
        if knn._fit_data_hash!=cfg["retrieval"]["item_knn_fit_data_hash"]: raise ValueError("fit hash differs")
        meta=[(d,str(paths.meta_path(d))) for d in get_domains()]
        corpus,_,coverage=build_corpus(meta,items,float(load_config("agent/agent_eval")["agent_eval"]["min_metadata_coverage"]))
        actual_policy=apply_metadata_policy(corpus,cfg["protocol"]["metadata_policy"]["name"],
                                            as_of_timestamp=int(target.timestamp.min()))
        if actual_policy!=cfg["protocol"]["metadata_policy"]: raise ValueError("metadata policy mismatch")
        reco=RecoModelTool(BaselineScorer(knn,popularity_weight=1e-6),users,items,corpus=corpus)
        query=QueryTool(corpus)
        popularity=np.asarray(knn.user_items.sum(axis=0)).ravel()
        popularity=np.pad(popularity,(0,len(items)-len(popularity)))
        ctx=dict(recent=recent,config=cfg,id2item={i:n for n,i in items.items()},item2id=items,
                 popular=np.argsort(-popularity,kind="stable"),
                 cf=ItemCFTool(knn,items,corpus=corpus),semantic=SemanticSearchTool(corpus),text=item_text_tables(corpus,True))
        warmed=set()
        progress=StageProgress("policy-chain:"+args.mode,len(chosen),every=100)
        position=0
        references={m:iter(_score_rows(args.source/"scored.jsonl",m)) for m in MERGES}
        with (args.source/"candidate_lists.jsonl").open(encoding="utf-8") as source:
            for line in source:
                template=json.loads(line)
                reference={m:next(s) for m,s in references.items()}
                if any(r["user_idx"]!=template["user_idx"] for r in reference.values()):
                    raise ValueError("source baseline alignment mismatch")
                if template["user_idx"] not in chosen: continue
                u,seg=template["user_idx"],template["segment"]
                if (u not in selected[seg] or users.get(template["user_id"])!=u or
                    set(template["targets"])!=target_by_user.get(u,set()) or
                    set(template["targets_unseen_in_fit"])!=target_by_user.get(u,set())-set(recent.get(u,[]))):
                    raise ValueError("source users/history/ground truth do not match validated splits")
                baseline=lambda pool: _baseline(reco,template["user_id"],pool)
                seen_items=reco.scorer.seen_items(u) if reco.scorer.is_known_user(u) else set()
                eligible=lambda pool:[i for i in pool if i in items and 0<=items[i]<reco.scorer.num_items and items[i] not in seen_items]
                fetch=lambda ids: query.execute(item_ids=ids,max_rows=len(ids))["items"] if ids else []
                if seg not in warmed:
                    warm_record=_fresh(template,ctx) if args.mode=="fresh" else template
                    for merge in MERGES: policy_chain_compare(warm_record,merge,baseline,fetch,seed=args.seed,warmup=True,eligible=eligible)
                    warmed.add(seg)
                if position<store.count("candidates"):
                    _,record=next(store.rows("candidates",start=position,batch_size=1))
                else:
                    record=_fresh(template,ctx) if args.mode=="fresh" else dict(template,retrieval_seconds=None)
                    store.append("candidates",[(position,record)])
                if record["user_idx"]!=u: raise ValueError("checkpoint user mismatch")
                for merge in MERGES:
                    if all(position<store.count(f"{merge}:{p}") for p in POLICIES): continue
                    results=policy_chain_compare(record,merge,baseline,fetch,seed=args.seed,eligible=eligible)
                    if args.mode=="frozen":
                        control=next(r for r in results if r["policy"]=="baseline")
                        original=reference[merge]
                        if (control["policy_error"] or control["ranked_ids"]!=original["ranked_ids"] or
                            not np.allclose(control["scores"],original["scores"],rtol=0,atol=1e-12)):
                            raise ValueError("frozen baseline failed per-user reproduction")
                    for r in results:
                        r["retrieval_seconds"]=record["retrieval_seconds"]
                        stream=f"{merge}:{r['policy']}"
                        if position>=store.count(stream): store.append(stream,[(position,r)])
                # Existing tool loggers must not retain every request in a long run.
                for tool in (reco,query,ctx["cf"],ctx["semantic"]): tool.logger.records.clear()
                position+=1
                progress.update(position)
        if position!=len(chosen): raise ValueError("incomplete source sample")
        progress.update(position,force=True)
        streams=[f"{m}:{p}" for m in MERGES for p in POLICIES]
        if any(store.count(s)!=position for s in streams): raise ValueError("incomplete policy streams")
        results=_summary(store,items,args.seed,args.bootstrap_samples)
        retrieval_timings=defaultdict(list)
        target_names=set()
        for _,record in store.rows("candidates"):
            target_names.update(ctx["id2item"][i] for i in record["targets_unseen_in_fit"])
        present=set()
        ordered_targets=sorted(target_names)
        for start in range(0,len(ordered_targets),100):
            present.update(r["item_id"] for r in query.execute(item_ids=ordered_targets[start:start+100],max_rows=100)["items"])
        query.logger.records.clear()
        loss_counts=defaultdict(Counter)
        fit_items=set(fit.item_idx.unique())
        for _,record in store.rows("candidates"):
            for group,counts in retrieval_loss_breakdown(record,ctx["id2item"],fit_items,present).items():
                loss_counts[record["segment"]+":"+group].update(counts)
            if args.mode=="fresh":
                for stage,seconds in record["source_latency_seconds"].items():
                    retrieval_timings[record["segment"]+":"+stage].append(seconds)
                retrieval_timings[record["segment"]+":total"].append(record["retrieval_seconds"])
        _verify(entries)
        if _source_fingerprint()!=run_identity["code"] or _environment_versions()!=run_identity["environment"]:
            raise ValueError("code/environment changed during run")
        root=paths.experiments_dir/"policy_chain_eval"
        root.mkdir(parents=True,exist_ok=True)
        output=next_experiment_dir(root)
        staging=store.path/("publication_"+uuid.uuid4().hex)
        save_experiment(staging,config=dict(source=str(args.source.resolve()),identity=run_identity,
                 policies=list(POLICIES),primary_merge="union_all",ks=[5,10,20],baseline_weight=1e-6,rrf_offset=60,
                 sampled_user_ids=selected,source_protocol=cfg["protocol"],metadata_coverage=coverage,
                 warmup="first request per segment/session, all policies, excluded",
                 fallback="none; failures recorded before quality aggregation",production_changed=False,
                 sample_scope="development prefix of source cohort; not untouched qualification"),
                 metrics=dict(comparison=results,mode=args.mode,timing_scope="active service stage sum; frozen retrieval unmeasured",
                              checkpoint_timing=store.timing(),
                              latency_caveat="resumed sessions may mix cache/hardware conditions; confirm latency in fresh repeated runs",
                              retrieval_loss_counts={k:dict(v) for k,v in loss_counts.items()},
                              retrieval_loss_scope="unique novel target pairs; metadata lookup after timing; no labels used in policies",
                              retrieval_stage_latency={k:{"n":len(v),"mean":float(np.mean(v)),"p95":float(np.percentile(v,95))}
                                                       for k,v in retrieval_timings.items()},
                              qualification="not production-qualified; development sample and timing stability not confirmed"),
                 seed=args.seed,dataset_info=dataset,runtime_seconds=store.timing()["committed_active_seconds"],
                 notes="Evaluation only. Production/cold baseline unchanged. Contract: src/configs/eval/policy_acceptance.yaml")
        readme=staging/"README.md"
        readme.write_text("# "+output.name+"\n"+readme.read_text(encoding="utf-8").split("\n",1)[1],encoding="utf-8")
        store.export(streams,staging/"policy_records.jsonl")
        store.export(["candidates"],staging/"candidate_lists.jsonl")
        if _source_fingerprint()!=run_identity["code"] or _environment_versions()!=run_identity["environment"]:
            raise ValueError("code/environment changed before publication")
        hashes={name:file_hash(staging/name) for name in
                ("config.yaml","metrics.json","policy_records.jsonl","candidate_lists.jsonl")}
        (staging/"artifact_hashes.json").write_text(json.dumps(hashes,indent=2),encoding="utf-8")
        store.put("publication_destination",str(output.resolve()))
        staging.rename(output)
        store.put("final_experiment",str(output.resolve()))
        print("Saved policy chain evaluation:",output,flush=True)


def _baseline(reco,user_id,pool):
    result=reco.execute(user_id=user_id,candidates=pool,top_k=len(pool),exclude_seen=True) if pool else {"ranked":[]}
    return dict(ids=[r["item_id"] for r in result["ranked"]],scores=[r["score"] for r in result["ranked"]])


if __name__=="__main__":
    main()
