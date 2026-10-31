"""Measure Type1 retrieval with history seeds or fixed-budget CF plus BM25.

Validation only. Existing validated ItemKNN is required; never refits. No LLM,
silent retrieval fallback or production policy changes. JSON/YAML only.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import random
import time
import uuid

import numpy as np
import pandas as pd
import yaml

from package.agents import Type1Agent,get_agent_limits
from package.agents.type1.recent_seed_items import recent_seed_items
from package.config import get_data_paths,get_domains,load_config
from package.data import build_first_seen_timestamps
from package.data.mapping import load_mappings
from package.tools import ItemCFTool,RecoModelTool,QueryTool,SemanticSearchTool
from package.tools.base import ToolResult
from package.tools.evaluation.normalize_query_text import normalize_query_text
from package.tools.score import BaselineScorer
from package.tools.corpus import build_corpus
from package.tools.evaluation import next_experiment_dir,save_experiment
from package.tools.evaluation.ranking_run_store import RankingRunStore
from package.tools.evaluation.stage_progress import StageProgress
from package.tools.evaluation.save_experiment import _source_fingerprint,_environment_versions
from package.tools.recommenders.file_hash import file_hash
from package.tools.recommenders.mapping_hash import mapping_hash
from package.tools.recommenders.load_item_knn import load_item_knn
from package.tools.retrieval.tokenize_search_query import tokenize_search_query
from package.tools.evaluation.history_title_query import history_title_query
from scripts.evaluation.analyze_ranking_bottlenecks import _metrics


class _ObservedTool:
    def __init__(self,tool,events): self.tool,self.events=tool,events
    def __call__(self,**kwargs):
        started=time.perf_counter()
        try:
            out=self.tool(**kwargs)
            self.events.append(dict(tool=self.tool.name,args=kwargs,ok=out.ok,data=out.data,error=out.error,
                                    seconds=time.perf_counter()-started))
            return out
        except Exception as exc:
            self.events.append(dict(tool=self.tool.name,args=kwargs,ok=False,data={},error=f"{type(exc).__name__}: {exc}",
                                    seconds=time.perf_counter()-started))
            raise


class _ContentRetriever:
    """Evaluation only: preserve one-seed CF and add title BM25 within total quota."""
    name="CFBM25Retriever"
    def __init__(self,cf,search,query,seen,history_items=None):
        self.cf,self.search,self.query,self.seen=cf,search,query,seen
        self.events=[]
        self.query_record={}
        self.fallback_reason=None
        self.history_items=history_items

    def __call__(self,*,items,top_k):
        self.events=[]; self.query_record={}; self.fallback_reason=None
        if top_k%2 or len(items)!=1:
            return ToolResult(ok=False,error="content experiment requires even budget and one latest seed")
        quota=top_k//2
        cf=_ObservedTool(self.cf,self.events)(items=items,top_k=quota)
        if not cf.ok: return cf
        query_items=self.history_items if self.history_items is not None else items
        meta=_ObservedTool(self.query,self.events)(item_ids=query_items,max_rows=len(query_items))
        if not meta.ok: return meta
        rows=meta.data.get("items",[])
        indexed={r['item_id']:r.get('title') for r in rows}
        titles=[indexed.get(i) for i in query_items]
        raw=titles[0] if len(titles)==1 else titles
        query=history_title_query(titles)
        self.query_record=dict(raw=raw,sent=query,source_item_ids=list(query_items),normalization="ascii_fold")
        if any(title is None for title in titles): return ToolResult(ok=False,error="fit history item has no title metadata")
        # Same tokenizer as the actual search. Never replace unusable text with
        # target metadata, other history, or a newly constructed query.
        if not tokenize_search_query(query):
            self.fallback_reason='no_searchable_title_tokens'
            self.events.append(dict(tool='ContentPolicy',args={'policy':'cf_only_on_no_title_tokens_v1'},
                ok=True,data={'fallback_reason':self.fallback_reason},error=None,seconds=0.))
            return ToolResult(ok=True,data={'candidates':cf.data['candidates'],
                'source_quotas':{'item_cf':quota,'bm25':quota},'fallback_reason':self.fallback_reason})
        found=_ObservedTool(self.search,self.events)(query=query,filters={"exclude_item_ids":list(self.seen)},limit=quota)
        if not found.ok: return found
        started=time.perf_counter()
        merged={}
        for row in cf.data["candidates"]+found.data["candidates"]:
            merged.setdefault(row["item_id"],row)
        if len(merged)>top_k: raise ValueError("combined candidate quota exceeded")
        self.events.append(dict(tool='CandidateMerge',args={'budget':top_k},ok=True,
            data={'candidate_count':len(merged)},error=None,seconds=time.perf_counter()-started))
        return ToolResult(ok=True,data={"candidates":list(merged.values()),"source_quotas":{"item_cf":quota,"bm25":quota}})


class _RRFModelTool:
    """Evaluation adapter: retain model eligibility filtering, then source-rank RRF60.

    The delegated model scoring is included in measured ranking latency. No model
    score participates in the final ordering; production RecoModelTool is unchanged.
    """
    name="RecoModelTool"
    def __init__(self,tool,provider): self.tool,self.provider=tool,provider
    def __call__(self,*,user_id,candidates,top_k):
        from scripts.evaluation.sparse_content_replay import rrf
        if self.provider.fallback_reason:
            # Preserve baseline scores/order rather than substituting CF source ranks.
            return self.tool(user_id=user_id,candidates=candidates,top_k=top_k)
        out=self.tool(user_id=user_id,candidates=candidates,top_k=len(candidates))
        if not out.ok: return out
        eligible={r['item_id']:r for r in out.data['ranked']}
        sources=[[r['item_id'] for r in e['data']['candidates']] for e in self.provider.events
                 if e['tool'] in ('ItemCFTool','SemanticSearchTool') and e['ok']]
        if len(sources)!=2: return ToolResult(ok=False,error='RRF requires both retrieval sources')
        pool=[i for i in candidates if i in eligible]
        ranked=rrf(pool,*sources)
        scores={i:sum(1/(60+source.index(i)+1) for source in sources if i in source) for i in pool}
        data=dict(out.data)
        data['ranked']=[dict(eligible[i],rank=n,score=scores[i]) for n,i in enumerate(ranked[:top_k],1)]
        data['model']='source_rrf60_after_model_eligibility'
        return ToolResult(ok=True,data=data)


def _run(tools,user_id,history,id2item,seed_count,k):
    events=[]
    agent=Type1Agent(*[_ObservedTool(t,events) for t in tools])
    start=time.perf_counter()
    seeds=recent_seed_items(history,id2item,seed_count)
    try:
        out=agent.recommend(user_id,seeds,top_k=k)
    except Exception as exc:
        out=dict(ok=False,stage=events[-1]["tool"] if events else "seed",error=f"{type(exc).__name__}: {exc}")
    elapsed=time.perf_counter()-start
    no_cf=out.get("stage")=="retrieve" and out.get("error")=="no candidates returned"
    status="ask_user" if no_cf else ("tool_error" if not out["ok"] else ("ok" if out["items"] else "no_result"))
    candidates=[r["item_id"] for r in events[0]["data"].get("candidates",[])] if events else []
    fetch=next((e for e in events if e["tool"]=="QueryTool"),None)
    ranked=next((e for e in events if e["tool"]=="RecoModelTool"),None)
    expected=[r["item_id"] for r in ranked["data"].get("ranked",[])] if ranked else []
    fetched=[r["item_id"] for r in fetch["data"].get("items",[])] if fetch else []
    excluded=ranked["data"].get("excluded_seen",[]) if ranked else []
    unscored=ranked["data"].get("unscored_item_ids",[]) if ranked else []
    return dict(seed_count=seed_count,seeds=seeds,actual_seed_count=len(seeds),status=status,
                ranked_ids=[r["item_id"] for r in out.get("items",[])],scores=[r["score"] for r in out.get("items",[])],
                candidates=candidates,chain_seconds=elapsed,events=events,
                excluded_seen=excluded,unscored_item_ids=unscored,
                eligible_candidates=len(candidates)-len(excluded)-len(unscored) if ranked else 0,
                metadata_missing_ids=sorted(set(expected)-set(fetched)),
                error=out.get("error") if status=="tool_error" else None)


def _summarize(store,items,protocol,seed,samples,user_ids=None):
    counts=protocol["variant_ids"] if "variant_ids" in protocol else protocol["seed_counts"]
    prefix=protocol.get("stream_prefix","seed_")
    result={}; per_user={}; base_ids=None; segments={}
    for count in counts:
        q=Counter(); outcomes=Counter(); timing=[]; cov=set(); ndcg=[]; users=[]; sizes=[]; effective=[]; retrieved=[]; missing=0
        stages={name:[] for name in ("ItemCFTool","RecoModelTool","QueryTool")}
        source_stages={}; source_sizes=Counter(); source_requests=0; shares=Counter(); final_items=0; fallbacks=Counter()
        for _,row in store.rows(f"{prefix}{count}"):
            if user_ids is not None and row['user_idx'] not in user_ids: continue
            users.append(row["user_idx"]); outcomes[row["status"]]+=1; timing.append(row["chain_seconds"])
            if row.get('fallback_reason'): fallbacks[row['fallback_reason']]+=1
            missing+=bool(row["metadata_missing_ids"]); sizes.append(len(row["candidates"]))
            effective.append(row["eligible_candidates"])
            for event in row["events"]: stages.setdefault(event["tool"],[]).append(event["seconds"])
            if "source_events" in row:
                source_requests+=1
                for event in row["source_events"]: source_stages.setdefault(event["tool"],[]).append(event["seconds"])
                cf=set(row.get("source_candidates",{}).get("item_cf",[]))
                bm=set(row.get("source_candidates",{}).get("bm25",[]))
                source_sizes.update(cf=len(cf),bm25=len(bm),bm25_unique=len(bm-cf))
                for item in row['ranked_ids'][:10]:
                    shares['both' if item in cf and item in bm else 'cf_only' if item in cf else 'bm25_only']+=1
                    final_items+=1
            gt=set(row["targets"])
            bucket=segments.setdefault(str(row["history_unique_items"]),{}).setdefault(str(count),
                dict(users=0,eligible_users=0,metrics=Counter(),outcomes=Counter()))
            bucket["users"]+=1; bucket["outcomes"][row["status"]]+=1
            if gt:
                for k in protocol["ks"]: q.update(_metrics(row["ranked_ids"],gt,items,k))
                bucket["eligible_users"]+=1
                for k in protocol["ks"]: bucket["metrics"].update(_metrics(row["ranked_ids"],gt,items,k))
                cov.update(row["ranked_ids"][:10])
                retrieved.append(len({items[i] for i in row["candidates"]}&gt)/len(gt))
                ndcg.append(_metrics(row["ranked_ids"],gt,items,10)["ndcg@10"])
            per_user.setdefault(row["history_unique_items"],Counter())[f"{prefix}{count}_{row['status']}"]+=1
        if base_ids is None: base_ids=users
        elif users!=base_ids: raise ValueError("variant user alignment mismatch")
        n=len(ndcg)
        result[str(count)]=dict(users=len(users),eligible_users=n,empty_ground_truth=len(users)-n,
            metrics={k:v/n for k,v in q.items()} if n else {},catalog_coverage_at10=len(cov)/len(items),
            outcomes=dict(outcomes),metadata_incomplete_requests=missing,
            tool_error_rate=outcomes.get('tool_error',0)/len(users),
            fallback_requests=sum(fallbacks.values()),fallback_rate=sum(fallbacks.values())/len(users),
            fallback_reasons=dict(fallbacks),fallback_policy='cf_only_on_no_title_tokens_v1; other retrieval errors remain visible',
            mean_candidates=float(np.mean(sizes)),mean_eligible_candidates=float(np.mean(effective)),
            candidate_recall=float(np.mean(retrieved)) if n else None,
            stage_latency={name:{"calls":len(v),"mean":float(np.mean(v)),"p95":float(np.percentile(v,95))} if v else {"calls":0,"mean":None,"p95":None}
                           for name,v in stages.items()},
            latency={"mean":float(np.mean(timing)),"p95":float(np.percentile(timing,95))})
        if source_requests:
            result[str(count)]["content_sources"]={"requests":source_requests,
                "top10_source_share":{k:shares[k]/final_items if final_items else None for k in ('cf_only','bm25_only','both')},
                "fallback_requests":sum(fallbacks.values()),
                "mean_sizes":{k:v/source_requests for k,v in source_sizes.items()},
                "stage_latency":{name:{"calls":len(v),"mean":float(np.mean(v)),"p95":float(np.percentile(v,95))}
                                 for name,v in source_stages.items()}}
        result[str(count)]["_ndcg"]=ndcg
    rng=np.random.default_rng(seed)
    baseline=result[str(counts[0])]
    for count in counts[1:]:
        r=result[str(count)]; d=np.array(r["_ndcg"])-baseline["_ndcg"]
        if not len(d): r["guardrails"]={"quality":"inconclusive: no novel ground truth"}; continue
        values,freq=np.unique(d,return_counts=True)
        means=rng.multinomial(len(d),freq/len(d),size=samples) @ values / len(d)
        alpha=protocol["family_alpha"]/protocol["comparisons"]
        interval=np.percentile(means,[100*alpha/2,100*(1-alpha/2)]).tolist()
        r["paired_ndcg10"]={"mean_delta":float(d.mean()),"familywise95_ci":interval,
                            "improved":int((d>0).sum()),"worse":int((d<0).sum()),"unchanged":int((d==0).sum())}
        r["guardrails"]=dict(ndcg_effect=float(d.mean())>=max(protocol["ndcg_absolute_min"],protocol["ndcg_relative_min"]*baseline["metrics"]["ndcg@10"]),
            paired_lower_positive=interval[0]>0,
            recall=r["metrics"]["recall@10"]>=protocol["recall_hit_retention_min"]*baseline["metrics"]["recall@10"],
            hit=r["metrics"]["hit_rate@10"]>=protocol["recall_hit_retention_min"]*baseline["metrics"]["hit_rate@10"],
            coverage=r["catalog_coverage_at10"]>=protocol["coverage_retention_min"]*baseline["catalog_coverage_at10"],
            latency=r["latency"]["p95"]<=protocol["chain_p95_ratio_max"]*baseline["latency"]["p95"],
            errors=r["outcomes"].get("tool_error",0)<=baseline["outcomes"].get("tool_error",0),
            missing_metadata=r["metadata_incomplete_requests"]<=baseline["metadata_incomplete_requests"])
    for r in result.values(): del r["_ndcg"]
    for variants in segments.values():
        for bucket in variants.values():
            n=bucket["eligible_users"]
            bucket["metrics"]={k:v/n for k,v in bucket["metrics"].items()} if n else {}
            bucket["outcomes"]=dict(bucket["outcomes"])
    return dict(variants=result,history_segments=segments,history_length_outcomes={str(k):dict(v) for k,v in per_user.items()},
                decision="development comparison only; no automatic production promotion")


def _hit_regressions(store,items,user_ids=None):
    """Pair actual ground truth, including lost items even if request remains a hit."""
    base={r['user_idx']:r for _,r in store.rows('variant_cf_1')
          if user_ids is None or r['user_idx'] in user_ids}
    counts=Counter(); segments={}
    for _,r in store.rows('variant_cf_bm25_rrf'):
        if user_ids is not None and r['user_idx'] not in user_ids: continue
        b=base.pop(r['user_idx']); gt=set(r['targets'])
        if b['targets']!=r['targets']: raise ValueError('paired target mismatch')
        old={items[i] for i in b['ranked_ids'][:10]}&gt
        new={items[i] for i in r['ranked_ids'][:10]}&gt
        values=dict(users=1,eligible_users=int(bool(gt)),baseline_hit_users=int(bool(old)),
            tuned_hit_users=int(bool(new)),gained_hit_users=int(not old and bool(new)),
            lost_hit_users=int(bool(old) and not new),retained_hit_users=int(bool(old) and bool(new)),
            lost_target_pairs=len(old-new),gained_target_pairs=len(new-old))
        counts.update(values)
        segments.setdefault(str(r['history_unique_items']),Counter()).update(values)
    if base: raise ValueError('incomplete paired regression streams')
    return dict(overall=dict(counts),history_segments={k:dict(v) for k,v in segments.items()})


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source",type=Path,required=True,help="Completed validation ranking experiment with fixed sparse sample")
    ap.add_argument("--item-knn",type=Path,required=True)
    ap.add_argument("--work-dir",type=Path,required=True)
    ap.add_argument("--resume",action="store_true")
    ap.add_argument("--users",type=int,default=100)
    ap.add_argument("--seed",type=int,default=42)
    ap.add_argument("--bootstrap-samples",type=int,default=10000)
    ap.add_argument("--retrieval-mode",choices=("seeds","cf_bm25","cf_bm25_rrf","cf_bm25_history"),default="seeds")
    ap.add_argument("--baseline-from",type=Path,help="Completed sparse_seed_eval experiment; required for cf_bm25 baseline confirmation")
    ap.add_argument('--pilot-from',type=Path,help='Prior RRF runtime pilot: report its users separately from remaining development users')
    args=ap.parse_args()
    if args.users<1 or args.bootstrap_samples<1000: ap.error("positive users and >=1000 bootstrap samples required")
    source=yaml.safe_load((args.source/"config.yaml").read_text(encoding="utf-8")); cfg=source["config"]; d=source["run"]["dataset"]
    if d["eval_on"]!="validation": raise ValueError("validation only")
    content=args.retrieval_mode in ("cf_bm25","cf_bm25_rrf","cf_bm25_history")
    history_content=args.retrieval_mode=='cf_bm25_history'
    runtime_rrf=args.retrieval_mode in ('cf_bm25_rrf','cf_bm25_history')
    if history_content and args.pilot_from: ap.error('history query pilot uses fixed source users; omit --pilot-from')
    if args.pilot_from and not runtime_rrf: ap.error('--pilot-from requires cf_bm25_rrf')
    if content and not args.baseline_from: ap.error("cf_bm25 requires --baseline-from")
    key="sparse_content_eval" if content else "sparse_seed_eval"
    protocol=load_config("eval/"+key)[key]
    if runtime_rrf:
        protocol=dict(protocol,variant_ids=['cf_1','cf_bm25_rrf'],ranking='equal_source_rrf60',exact_count=False)
    if content: protocol=dict(protocol,unsearchable_title_policy='cf_only_on_no_title_tokens_v1')
    if history_content:
        protocol=dict(protocol,variant_ids=['cf_1','cf_bm25_rrf','cf_bm25_history'],comparisons=2,
            query='latest title control vs round-robin fit-history titles; runtime token cap unchanged',
            primary_retrieval_comparison='cf_bm25_history vs cf_bm25_rrf')
    if not content and (protocol["seed_counts"]!=[1,2,4] or protocol["k"]!=10): raise ValueError("v1 protocol requires seeds 1/2/4, demo top-k 10")
    variants=protocol["variant_ids"] if content else protocol["seed_counts"]
    prefix=protocol.get("stream_prefix","seed_")
    paths=get_data_paths(d["tag"]); identity=cfg["checkpoint_identity"]
    entries=[v for s,v in identity["split_files"].items() if s in ("train","validation")]
    entries+=list(identity["metadata_files"].values())
    entries += [{"path":p,"sha256":h} for p,h in identity["mapping_files"].items()]
    entries += [{"path":str(p.resolve()),"sha256":file_hash(p)} for p in (args.source/"config.yaml",args.item_knn,args.item_knn.with_suffix(".meta.json"))]
    if content:
        for name,h in json.loads((args.baseline_from/"artifact_hashes.json").read_text()).items():
            entries.append({"path":str((args.baseline_from/name).resolve()),"sha256":h})
    pilot_users=set()
    if args.pilot_from:
        hashes=json.loads((args.pilot_from/'artifact_hashes.json').read_text(encoding='utf-8'))
        if not {'config.yaml','records.jsonl','requests.jsonl','metrics.json'}<=hashes.keys():
            raise ValueError('incomplete pilot manifest')
        for name,h in hashes.items():
            path=(args.pilot_from/name).resolve()
            if path.parent!=args.pilot_from.resolve() or file_hash(path)!=h: raise ValueError('pilot hash/path mismatch')
            entries.append(dict(path=str(path),sha256=h))
        pilot=yaml.safe_load((args.pilot_from/'config.yaml').read_text(encoding='utf-8'))
        if (pilot['run']['dataset']['mapping_hash']!=d['mapping_hash'] or
            pilot['run']['dataset']['user_mapping_hash']!=d['user_mapping_hash'] or
            pilot['run']['dataset']['eval_on']!='validation' or
            {k:v for k,v in pilot['config']['identity']['protocol'].items() if k!='unsearchable_title_policy'}!=
            {k:v for k,v in protocol.items() if k!='unsearchable_title_policy'}):
            raise ValueError('pilot dataset/protocol mismatch')
        pilot_users=set(pilot['config']['sampled_user_ids'])
    def verify():
        for e in entries:
            p=Path(e["path"])
            if (file_hash(p) if p.exists() else None)!=e["sha256"]: raise ValueError(f"input mismatch: {p}")
    print("[provenance] checking splits, metadata, mappings and existing model",flush=True); verify()
    run_identity=dict(source=entries,code=_source_fingerprint(),environment=_environment_versions(),
                      users=args.users,seed=args.seed,bootstrap_samples=args.bootstrap_samples,protocol=protocol,
                      retrieval_mode=args.retrieval_mode)
    run_identity['pilot_user_ids']=sorted(pilot_users)
    with RankingRunStore(args.work_dir,run_identity,resume=args.resume) as store:
        published=store.get("publication_destination")
        if published and Path(published).exists():
            p=Path(published)
            if any(file_hash(p/n)!=h for n,h in json.loads((p/"artifact_hashes.json").read_text()).items()): raise ValueError("published artifact mismatch")
            store.put("final_experiment",str(p.resolve()))
        if store.get("final_experiment"): print("Already complete:",store.get("final_experiment")); return
        users,items=load_mappings(paths.mapped_dir)
        if mapping_hash(users)!=d["user_mapping_hash"] or mapping_hash(items)!=d["mapping_hash"]: raise ValueError("mapping mismatch")
        selected=cfg["sampled_user_ids"]["sparse"][:args.users]
        if args.pilot_from and (not pilot_users or not pilot_users<set(selected)):
            raise ValueError('confirmation sample must strictly contain the pilot users')
        if len(selected)!=args.users or len(set(selected))!=len(selected): raise ValueError("source sparse sample too small or duplicate")
        train=pd.read_parquet(paths.split_path("train"),columns=["user_idx","item_idx","timestamp"])
        val=pd.read_parquet(paths.split_path("validation"),columns=["user_idx","item_idx"])
        histories={int(u):frame for u,frame in train[train.user_idx.isin(selected)].groupby("user_idx")}
        targets=val[val.user_idx.isin(selected)].groupby("user_idx").item_idx.apply(set).to_dict()
        sparse_max=int(load_config("eval/segment_thresholds")["segment_thresholds"]["sparse_max_history"])
        if any(u not in histories or not 1<=histories[u].item_idx.nunique()<=sparse_max for u in selected): raise ValueError("source users are not currently sparse")
        neighbors=int(load_config("eval/baselines")["baselines"]["item_knn"]["k"])
        if neighbors!=cfg["retrieval"]["item_knn_neighbors"]: raise ValueError("source/runtime neighbor mismatch")
        model=load_item_knn(args.item_knn,neighbors,train[["user_idx","item_idx"]],user2id=users,item2id=items,eval_on="validation",tag=d["tag"])
        if model._fit_data_hash!=cfg["retrieval"]["item_knn_fit_data_hash"]: raise ValueError("fit hash mismatch")
        print("[corpus] building current snapshot, matching live demo metadata policy",flush=True)
        meta_files = [(domain,str(paths.meta_path(domain))) for domain in get_domains()]
        first_seen_ts = build_first_seen_timestamps([(domain, paths.cleaned_path(domain)) for domain, _ in meta_files])
        corpus,_,coverage=build_corpus(meta_files,items,
                                       float(load_config("agent/agent_eval")["agent_eval"]["min_metadata_coverage"]),
                                       first_seen_ts=first_seen_ts)
        tools=(ItemCFTool(model,items,corpus=corpus),RecoModelTool(BaselineScorer(model),users,items,corpus=corpus),QueryTool(corpus))
        search=SemanticSearchTool(corpus,exact_count=not runtime_rrf) if content else None
        counted_search=SemanticSearchTool(corpus) if runtime_rrf else None
        id2item={v:k for k,v in items.items()}; id2user={v:k for k,v in users.items()}
        budget=max(10*get_agent_limits().type1_candidate_multiplier,get_agent_limits().type1_min_candidates)
        if runtime_rrf and budget!=50: raise ValueError('RRF v1 requires runtime candidate budget 50')
        references={}
        if content:
            if budget%2 or neighbors>budget//2:
                raise ValueError("half-CF quota could truncate control CF candidates; choose another preregistered design")
            with (args.baseline_from/"records.jsonl").open(encoding="utf-8") as source_records:
                for line in source_records:
                    row=json.loads(line)
                    if row["seed_count"]==1 and row["user_idx"] in selected:
                        references[row["user_idx"]]={k:row[k] for k in ("ranked_ids","scores","candidates","targets","seeds","status","candidate_budget")}
            if set(references)!=set(selected): raise ValueError("baseline reference does not cover the same users")
        progress=StageProgress("sparse-type1",len(selected),every=100); warmed=set()
        for pos,u in enumerate(selected):
            history=histories[u]; length=int(history.item_idx.nunique()); gt=sorted(targets.get(u,set())-set(history.item_idx))
            order=list(variants); random.Random(f"{args.seed}:{u}").shuffle(order)
            def run_variant(count):
                if not content or count=="cf_1": return _run(tools,id2user[u],history,id2item,1 if content else count,10)
                query_items=recent_seed_items(history,id2item,length) if count=='cf_bm25_history' else None
                provider=_ContentRetriever(tools[0],search,tools[2],[id2item[int(i)] for i in history.item_idx.unique()],query_items)
                ranker=_RRFModelTool(tools[1],provider) if runtime_rrf else tools[1]
                row=_run((provider,ranker,tools[2]),id2user[u],history,id2item,1,10)
                row.update(source_events=provider.events,query_provenance=provider.query_record,
                           fallback_reason=provider.fallback_reason,
                           source_quotas={"item_cf":budget//2,"bm25":budget//2})
                row["source_candidates"]={"item_cf":[r["item_id"] for e in provider.events if e["tool"]=="ItemCFTool" and e["ok"] for r in e["data"]["candidates"]],
                                          "bm25":[r["item_id"] for e in provider.events if e["tool"]=="SemanticSearchTool" and e["ok"] for r in e["data"]["candidates"]]}
                if runtime_rrf:
                    event=next((e for e in provider.events if e['tool']=='SemanticSearchTool' and e['ok']),None)
                    if event:
                        started=time.perf_counter(); checked=counted_search(**event['args'])
                        elapsed=time.perf_counter()-started
                        keys=('candidates','query_tokens','truncated','applied_filters')
                        if not checked.ok or any(checked.data[k]!=event['data'][k] for k in keys):
                            raise ValueError('exact-count omission changed BM25 output')
                        row['count_equivalence']=dict(equal=True,exact_count_total=checked.data['total_matches'],
                            counted_verification_seconds=elapsed,no_count_search_seconds=event['seconds'],
                            scope='verification outside timed chain; counted call always second, not a paired latency benchmark')
                # One-seed model has <=neighbors results: adding BM25 must not truncate CF.
                if provider.events and provider.events[0]["ok"]:
                    ids=[r["item_id"] for r in provider.events[0]["data"]["candidates"]]
                    if ids!=references[u]["candidates"]: raise ValueError("content branch altered the control CF candidate list")
                return row
            if length not in warmed:
                for count in order: run_variant(count)
                warmed.add(length)
            if pos>=store.count("requests"):
                store.append("requests",[(pos,dict(user_idx=u,user_id=id2user[u],history=history[["item_idx","timestamp"]].to_dict("records"),targets=gt))])
            for count in order:
                stream=f"{prefix}{count}"
                if pos<store.count(stream): continue
                row=run_variant(count)
                if content and count=="cf_1":
                    reference=references[u]
                    for field in ("ranked_ids","candidates","seeds","status"):
                        if row[field]!=reference[field]: raise ValueError(f"baseline reproduction failed: {field}")
                    if (gt!=reference["targets"] or reference["candidate_budget"]!=budget or
                        not np.allclose(row["scores"],reference["scores"],atol=1e-12,rtol=0)):
                        raise ValueError("baseline targets/budget/scores mismatch")
                if not row["events"] or row["events"][0]["args"]["top_k"]!=budget: raise ValueError("candidate budget changed")
                row.update(user_idx=u,user_id=id2user[u],history_unique_items=length,targets=gt,candidate_budget=budget)
                if content: row["variant"]=count
                store.append(stream,[(pos,row)])
            for tool in tools: tool.logger.records.clear()
            if search: search.logger.records.clear()
            if counted_search: counted_search.logger.records.clear()
            progress.update(pos+1)
        streams=[f"{prefix}{n}" for n in variants]
        if any(store.count(s)!=len(selected) for s in streams): raise ValueError("incomplete streams")
        metrics=_summarize(store,items,protocol,args.seed,args.bootstrap_samples)
        metrics["checkpoint_timing"]=store.timing()
        metrics["latency_scope"]="Type1 chain + recent-seed selection; excludes full-frame history lookup, UI, setup and warmup; resumed sessions may mix conditions"
        if runtime_rrf:
            metrics['latency_scope']+='; excludes separate exact-count equivalence verification; ranking includes delegated model eligibility/scoring overhead'
            metrics['title_policy_scope']='cf_only_on_no_title_tokens_v1; prior pilot used error-on-unsearchable-title; historical experiments are unchanged'
            metrics['count_equivalence_checks']=sum(bool(row.get('count_equivalence',{}).get('equal')) for _,row in store.rows(prefix+'cf_bm25_rrf'))
            if history_content:
                metrics['count_equivalence_checks_by_variant']={v:sum(bool(r.get('count_equivalence',{}).get('equal')) for _,r in store.rows(prefix+v))
                                                              for v in ('cf_bm25_rrf','cf_bm25_history')}
            metrics['hit_regressions']=_hit_regressions(store,items)
            if history_content:
                paired_protocol=dict(protocol,variant_ids=['cf_bm25_rrf','cf_bm25_history'],comparisons=1)
                metrics['retrieval_query_comparison']=_summarize(store,items,paired_protocol,args.seed,args.bootstrap_samples)
                metrics['retrieval_query_comparison_scope']='primary paired history-vs-latest query comparison; same RRF60, CF one seed, budgets and target set; inspected development users'
            if pilot_users:
                metrics['cohorts']={}
                for name,ids in [('inspected_pilot',pilot_users),('remaining_development',set(selected)-pilot_users)]:
                    report=_summarize(store,items,protocol,args.seed,args.bootstrap_samples,ids)
                    report['hit_regressions']=_hit_regressions(store,items,ids)
                    metrics['cohorts'][name]=report
                metrics['cohort_qualification']='remaining users exclude BM25 pilot; previously inspected CF/seed validation cohort, NOT untouched holdout'
                metrics['confirmation_primary_cohort']='remaining_development'
                metrics['production_decision']='not eligible unless original quality, uncertainty, coverage and latency guardrails all pass; no threshold relaxation'
        verify()
        if _source_fingerprint()!=run_identity["code"] or _environment_versions()!=run_identity["environment"]: raise ValueError("code/environment changed")
        output=next_experiment_dir(paths.experiments_dir/("sparse_content_eval" if content else "sparse_seed_eval"))
        staging=store.path/("publication_"+uuid.uuid4().hex)
        save_experiment(staging,config=dict(identity=run_identity,sampled_user_ids=selected,candidate_budget=budget,
            source_sampling_seed=source["run"]["seed"],order_and_bootstrap_seed=args.seed,
            sparse_max_unique_history=sparse_max,
            source_quotas={"control_cf":budget,"hybrid_cf":budget//2,"hybrid_bm25":budget//2} if content else None,
            content_query=protocol['query'] if content else None,
            metadata_policy="runtime_snapshot: current metadata, not historical causal",metadata_coverage=coverage,
            baseline="same Type1 library, recent_seed_items(count=1), no explicit intent; no-CF maps to ask_user",
            cold_warm_excluded=True,production_changed=False,warmup="first user per history length per session, excluded",
            qualification="source cohort already inspected; developmental"),metrics=metrics,seed=args.seed,
            dataset_info=d,runtime_seconds=store.timing()["committed_active_seconds"],write_readme=False)
        store.export(streams,staging/"records.jsonl"); store.export(["requests"],staging/"requests.jsonl")
        if _source_fingerprint()!=run_identity["code"]: raise ValueError("code changed before publication")
        hashes={name:file_hash(staging/name) for name in ("config.yaml","metrics.json","records.jsonl","requests.jsonl")}
        (staging/"artifact_hashes.json").write_text(json.dumps(hashes,indent=2),encoding="utf-8")
        store.put("publication_destination",str(output.resolve())); staging.rename(output)
        store.put("final_experiment",str(output.resolve()))
        print("Saved sparse comparison:",output,flush=True)


if __name__=="__main__": main()
