from __future__ import annotations

from array import array
from collections import Counter

import numpy as np

from .candidate_retrieval_metrics import candidate_retrieval_metrics
from .metrics import ranking_metrics_at_k


class RankingStreamSummary:

    def __init__(self, item2id, ks, segments=("cold", "sparse", "warm")):
        self.items, self.ks, self.segments = item2id, ks, segments
        self.n = len(item2id)
        self.retrieval, self.ranking = {}, {}
        self.latency = {(s,t): array("d") for s in segments for t in ("item_cf", "semantic")}
        self.health = {s: Counter() for s in segments}
        self.errors = {s: Counter() for s in segments}
        self.repeats = {s: 0. for s in segments}

    @staticmethod
    def _summary(values):
        if not len(values):
            return {"n": 0, "mean": None, "p50": None, "p95": None}
        v = np.asarray(values, dtype=np.float64)
        return {"n": len(v), "mean": float(v.mean()), "p50": float(np.percentile(v,50)), "p95": float(np.percentile(v,95))}

    def add_candidate(self, row):
        seg = row["segment"]
        h = self.health[seg]
        h["users"] += 1
        query = row.get("semantic_query", {})
        h["queries_changed"] += bool(query.get("changed"))
        h["queries_emptied"] += bool(query.get("empty_after_normalization"))
        h["queries_available"] += bool(query.get("sent", "").strip())
        for source in ("semantic", "item_cf"):
            error = row["source_failures"].get(source)
            h[source + "_errors"] += bool(error)
            if error:
                self.errors[seg][source + ": " + error] += 1
            self.latency[seg,source].append(row.get("source_latency_seconds", {}).get(source, 0.))
        self.repeats[seg] += len(row["targets_seen_in_fit"]) / max(1,len(row["targets"]))
        for merge, names in row["candidate_sets"].items():
            candidates = [self.items[i] for i in names]
            for condition, field in (("all_validation_targets", "targets"), ("unseen_validation_targets", "targets_unseen_in_fit")):
                state = self.retrieval.setdefault((merge,seg,condition),
                    {"users": 0, "target_interactions": 0, "recall_sum": 0., "hit_sum": 0., "hits": 0., "sizes": 0., "catalog": np.zeros(self.n, dtype=bool)})
                targets = set(row[field])
                one = candidate_retrieval_metrics([candidates], [targets], self.n)
                if one["users"]:
                    state["users"] += 1
                    state["target_interactions"] += len(targets)
                    state["recall_sum"] += one["recall"]
                    state["hit_sum"] += one["hit_rate"]
                    state["hits"] += len(set(candidates) & targets)
                    state["sizes"] += one["mean_candidate_set_size"]
                    state["catalog"][candidates] = True

    def add_scored(self, row):
        key = row["merge"], row["scorer"], row["segment"]
        state = self.ranking.setdefault(key, {
            "sampled": 0, "users": 0, "repeat": 0, "novel": 0, "sums": {str(k): Counter() for k in self.ks},
            "catalog": {str(k): np.zeros(self.n, dtype=bool) for k in self.ks},
            "loss": Counter(), "rank_latency": array("d"), "fetch_latency": array("d"),
            "fetch_success": 0, "tie_pair_rate": 0., "top_k_boundary_tie": 0.,
        })
        state["sampled"] += 1
        state["repeat"] += len(set(row["targets"]) - set(row["targets_unseen_in_fit"]))
        state["novel"] += len(row["targets_unseen_in_fit"])
        targets = set(row["targets_unseen_in_fit"])
        ids = [self.items[i] for i in row["ranked_ids"]]
        if targets:
            state["users"] += 1
            for k in self.ks:
                hits = np.zeros((1,k), dtype=np.float64)
                for j,i in enumerate(ids[:k]):
                    hits[0,j] = i in targets
                for metric, vals in ranking_metrics_at_k(hits, np.array([len(targets)]), k).items():
                    state["sums"][str(k)][metric] += float(vals[0])
                state["catalog"][str(k)][ids[:k]] = True
        loss = state["loss"]
        loss["input_candidates"] += len(row["candidate_ids"])
        loss["removed_seen"] += len(row["excluded_seen"])
        loss["removed_unscored"] += len(row["unscored_item_ids"])
        loss["returned_ranked"] += len(row["ranked_ids"])
        loss["retrieval_raw_union_candidates"] += row["retrieval_raw_union_count"]
        loss["retrieval_seen_dropped"] += row["retrieval_seen_dropped_count"]
        state["rank_latency"].append(row["ranking_latency_seconds"])
        state["fetch_latency"].append(row["fetch_latency_seconds"])
        state["fetch_success"] += row["fetch_success"]
        for field in ("tie_pair_rate", "top_k_boundary_tie"):
            state[field] += row[field]

    def result(self, merges, variants):
        retrieval = {}
        for merge in merges:
            retrieval[merge] = {}
            for seg in self.segments:
                r = {}
                for condition in ("all_validation_targets", "unseen_validation_targets"):
                    v = self.retrieval.get((merge,seg,condition))
                    n = v["users"] if v else 0
                    r[condition] = {"users": n, "target_interactions": v["target_interactions"] if v else 0,
                        "recall": v["recall_sum"]/n if n else None, "hit_rate": v["hit_sum"]/n if n else None,
                        "candidate_coverage": v["hits"]/v["target_interactions"] if n else None,
                        "mean_candidate_set_size": v["sizes"]/n if n else None,
                        "catalog_coverage": float(v["catalog"].mean()) if n else 0.}
                r["mean_target_same_user_repeat_fraction"] = self.repeats[seg]/self.health[seg]["users"] if self.health[seg]["users"] else None
                r["candidate_generation_latency_seconds"] = {t:self._summary(self.latency[seg,t]) for t in ("item_cf", "semantic")}
                retrieval[merge][seg] = r
        ranking = {m:{} for m in merges}
        for merge in merges:
            for variant, weight in variants.items():
                per_segment = {}
                for seg in self.segments:
                    v = self.ranking.get((merge,variant,seg))
                    if v is None:
                        per_segment[seg] = {"users": 0, "metrics": {}, "catalog_coverage": {str(k):None for k in self.ks}}
                        continue
                    n, sampled, loss = v["users"], v["sampled"], dict(v["loss"])
                    loss.update(retrieval_seen_loss_rate=loss["retrieval_seen_dropped"]/max(1,loss["retrieval_raw_union_candidates"]),
                                unscored_loss_rate=loss["removed_unscored"]/max(1,loss["input_candidates"]),
                                total_loss_rate_after_merge=(loss["removed_seen"]+loss["removed_unscored"])/max(1,loss["input_candidates"]))
                    per_segment[seg] = {
                        "users": n, "metrics": {k:{name:total/n for name,total in sums.items()} for k,sums in v["sums"].items()} if n else {},
                        "catalog_coverage": {k:float(mask.mean()) if n else None for k,mask in v["catalog"].items()},
                        "sampled_users": sampled, "users_with_unseen_targets": n, "users_without_unseen_targets": sampled-n,
                        "target_same_user_repeat_pairs": v["repeat"], "target_items_unseen_in_fit": v["novel"],
                        "filtering": loss, "ranking_latency_seconds": self._summary(v["rank_latency"]),
                        "metadata_fetch_latency_seconds": self._summary(v["fetch_latency"]),
                        "metadata_fetch_success_rate": v["fetch_success"]/sampled,
                        "ties": {field:v[field]/sampled for field in ("tie_pair_rate", "top_k_boundary_tie")},
                    }
                ranking[merge][variant] = {"popularity_weight": weight, "per_segment": per_segment}
        return {"k_values": self.ks, "catalog_size": self.n, "retrieval": retrieval, "ranking": ranking,
                "tool_health": {s:{**{key:int(self.health[s][key]) for key in ("users", "semantic_errors", "item_cf_errors", "queries_changed", "queries_emptied", "queries_available")},
                                   "errors_by_reason": dict(self.errors[s])} for s in self.segments}}
