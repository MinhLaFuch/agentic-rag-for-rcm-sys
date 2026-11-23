"""Domain- and main-category-aware popularity candidate generator built strictly from fit counts."""

from __future__ import annotations

from collections import Counter
from typing import Iterable, Sequence

import numpy as np


class DomainCategoryPopularity:
    """Precomputes top popular eligible items per domain and per (domain, main_category)."""

    def __init__(
        self,
        item_domains: dict[str, str],
        item_categories: dict[str, str],
        domain_buckets: dict[str, list[str]],
        category_buckets: dict[tuple[str, str], list[str]],
    ) -> None:
        self.item_domains = item_domains
        self.item_categories = item_categories
        self.domain_buckets = domain_buckets
        self.category_buckets = category_buckets

    @classmethod
    def from_corpus(
        cls,
        corpus,
        popularity_order: Sequence[str],
        eligible_ids: Iterable[str],
        *,
        max_per_domain: int = 600,
        max_per_category: int = 400,
        batch_size: int = 2048,
    ) -> "DomainCategoryPopularity":
        eligible = set(eligible_ids)
        item_domains: dict[str, str] = {}
        item_categories: dict[str, str] = {}
        ordered_eligible = [str(i) for i in popularity_order if str(i) in eligible]
        # Read domain and main_category from the policy-filtered TEMP items view in bounded ID chunks.
        # Only scan top popular items first for buckets, plus caller-supplied history items via lookup.
        scan_ids = sorted(eligible)
        for start in range(0, len(scan_ids), batch_size):
            chunk = scan_ids[start:start + batch_size]
            marks = ",".join("?" for _ in chunk)
            rows, _ = corpus.select(
                f"SELECT item_id, domain, main_category FROM items WHERE item_id IN ({marks})",
                chunk,
                max_rows=len(chunk),
            )
            for r in rows:
                iid = str(r["item_id"])
                if r.get("domain"):
                    item_domains[iid] = str(r["domain"])
                if r.get("main_category"):
                    item_categories[iid] = str(r["main_category"])

        domain_buckets: dict[str, list[str]] = {}
        category_buckets: dict[tuple[str, str], list[str]] = {}
        for iid in ordered_eligible:
            d = item_domains.get(iid, "")
            c = item_categories.get(iid, "")
            if d:
                b = domain_buckets.setdefault(d, [])
                if len(b) < max_per_domain:
                    b.append(iid)
            if d and c:
                b2 = category_buckets.setdefault((d, c), [])
                if len(b2) < max_per_category:
                    b2.append(iid)
        return cls(item_domains, item_categories, domain_buckets, category_buckets)

    def recommend(
        self,
        seen_items: Iterable[str],
        *,
        limit: int = 200,
        top_categories: int = 3,
        top_domains: int = 2,
    ) -> list[str]:
        if limit <= 0:
            raise ValueError("limit must be positive")
        seen_list = list(seen_items)
        if not seen_list:
            return []
        seen_set = set(seen_list)
        dom_cnt = Counter(self.item_domains[i] for i in seen_list if i in self.item_domains)
        cat_cnt = Counter(
            (self.item_domains[i], self.item_categories[i])
            for i in seen_list
            if i in self.item_domains and i in self.item_categories
        )
        cat_lists = []
        for key, _ in cat_cnt.most_common(top_categories):
            filtered = [x for x in self.category_buckets.get(key, []) if x not in seen_set]
            if filtered:
                cat_lists.append(filtered)
        dom_lists = []
        for key, _ in dom_cnt.most_common(top_domains):
            filtered = [x for x in self.domain_buckets.get(key, []) if x not in seen_set]
            if filtered:
                dom_lists.append(filtered)

        out: list[str] = []
        seen_out: set[str] = set()

        def _pull(lists: list[list[str]], cap: int) -> None:
            pos = 0
            while len(out) < cap:
                progressed = False
                for lst in lists:
                    if pos < len(lst):
                        cand = lst[pos]
                        if cand not in seen_out:
                            seen_out.add(cand)
                            out.append(cand)
                            if len(out) >= cap:
                                return
                        progressed = True
                if not progressed:
                    return
                pos += 1

        _pull(cat_lists, limit // 2)
        _pull(dom_lists, limit)
        _pull(cat_lists, limit)
        return out[:limit]

    def affinity_features(self, seen_items: Iterable[str], item_ids: Sequence[str]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Return (same_domain_flag, domain_affinity_ratio, cat_affinity_ratio) arrays for candidate items."""
        seen_list = list(seen_items)
        n = len(item_ids)
        if not seen_list or n == 0:
            z = np.zeros(n, dtype=np.float32)
            return z, z.copy(), z.copy()
        dom_cnt = Counter(self.item_domains[i] for i in seen_list if i in self.item_domains)
        cat_cnt = Counter(
            (self.item_domains[i], self.item_categories[i])
            for i in seen_list
            if i in self.item_domains and i in self.item_categories
        )
        tot_dom = float(sum(dom_cnt.values())) or 1.0
        tot_cat = float(sum(cat_cnt.values())) or 1.0
        same_dom = np.zeros(n, dtype=np.float32)
        dom_aff = np.zeros(n, dtype=np.float32)
        cat_aff = np.zeros(n, dtype=np.float32)
        for j, iid in enumerate(item_ids):
            d = self.item_domains.get(iid, "")
            c = self.item_categories.get(iid, "")
            if d and d in dom_cnt:
                same_dom[j] = 1.0
                dom_aff[j] = dom_cnt[d] / tot_dom
            if d and c and (d, c) in cat_cnt:
                cat_aff[j] = cat_cnt[(d, c)] / tot_cat
        return same_dom, dom_aff, cat_aff
