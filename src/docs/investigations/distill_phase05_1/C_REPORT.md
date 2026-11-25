# C_REPORT — Taxonomy audit: `category_coarse` vs `category_leaf`

**Date:** 2026-11-23 · **Workstream:** C of distill-phase05-1 · **Mode:** READ-ONLY audit
**DB:** `resource/corpus/multi_domain/corpus_multi_domain.sqlite` via `sqlite3.connect('file:...?mode=ro', uri=True)`, `.venv/Scripts/python`
**Prior numbers (REPORT.md §B):** 2,260 categories, median size 138, ~8.7% uncategorized — **all reproduced exactly** (items_with_cat = 2,407,801; seq-len hist identical).

**Decision context (given):** schema = `category_coarse` + `category_leaf`; labels are flat; an item's path = sequence of `item_categories` labels ordered by `rowid`; `_deepest_category` = last row. This audit defines/measures `category_coarse` candidates only — no code changes.

---

## 1. Reconstruction reliability of per-item label sequences

Method: streamed `SELECT rowid, item_id, category FROM item_categories ORDER BY rowid` (9,941,797 rows), grouping consecutive rows per `item_id`. Verified contiguity: **0 non-contiguous item blocks**; flushed-item count = 2,407,801 = the known categorized-item count exactly → rowid order partitions items cleanly.

| check | result |
|---|---|
| items with ≥1 category row | 2,407,801 (91.27% of 2,637,776 items) |
| duplicate label within one item's sequence | **0 items** |
| single-label items | **0** (min sequence length = 2) |
| sequence-length histogram | 2:91,051 · 3:596,728 · 4:805,094 · 5:756,405 · 6:142,677 · 7:15,720 · 8:126 |
| distinct label-multisets (sorted seq) | **2,769** across 2.4M items |
| multiset → rowid-order conflicts | **0** in 2,405,032 repeat occurrences — every multiset has exactly ONE observed order |
| labels containing `/`, `>`, `::` | 2,276 items (outliers, e.g. pre-composed path strings) |

**Verdict:** reconstruction is effectively unambiguous. The label *multiset* alone determines the rowid order (0 conflicts), there are no duplicate labels, and no single-label items. Caveat: consistency ≠ semantic correctness — nothing in the DB proves rowid order is root→leaf, but position-1 labels are ~99.3% domain roots (see §2), which strongly corroborates it.

**Anomaly:** position 1 has only **8 distinct labels**, of which 3 are domain roots (`Electronics` 1,479,550 · `Toys & Games` 786,764 · `Video Games` 124,608) and **5 are non-root labels** covering 16,879 items: `Remote & App Controlled Vehicles & Parts` (10,737), `Remote & App Controlled Vehicle Parts` (4,247), `Car & Vehicle Electronics` (1,593), `Amazon Devices & Accessories` (289), `Purchase Circles` (13). These items' sequences do not start with a domain root.

## 2. Per-depth statistics (item's depth-d label = d-th row)

Items with ≥d rows / total categorized items:

| depth | items w/ label | % | distinct labels at pos | min | median | p90 | max | % labels <10 items |
|---|---|---|---|---|---|---|---|---|
| 1 | 2,407,801 | 100.0% | **8** | 13 | 10,737 | 786,764 | 1,479,550 | 0.0% |
| 2 | 2,407,801 | 100.0% | 558 | 1 | **3** | 232 | 647,621 | **67.7%** |
| 3 | 2,316,750 | 96.2% | 564 | 1 | 111 | 7,656 | 230,281 | 34.0% |
| 4 | 1,720,022 | 71.4% | 672 | 1 | 393 | 5,845 | 145,652 | 12.5% |
| 5 | 914,928 | 38.0% | 501 | 1 | 343 | 4,618 | 83,712 | 10.2% |
| 6 | 158,523 | 6.6% | 129 | 2 | 210 | 2,616 | 29,234 | 7.0% |
| 7 | 15,846 | 0.66% | 21 | 33 | 219 | 2,055 | 3,947 | 0.0% |
| 8 | 126 | 0.005% | 3 | 3 | 40 | 40 | 83 | 33.3% |

Top labels per position (sanity): pos1 = domain roots; pos2 = `Computers & Accessories` (647,621), `Camera & Photo` (252,618), `Preschool` (136,542); pos3 = `Accessories` (230,281), `Computer Accessories & Peripherals` (166,194); pos4 = `Bags, Cases & Sleeves` (145,652), `Internal Components` (69,162).

**Key observation:** depth-2 is extremely fragmented — 558 labels, median bucket size **3 items**, 68% of labels cover <10 items (a few huge browse-nodes + a long tail of niche nodes). Depths 3–5 are progressively more balanced but still have 10–34% tiny labels. Depth 1 is trivially stable (8 labels ≈ domain).

## 3. Two "coarse" definitions compared

**(a) Fixed position k** — `coarse = seq[k-1]` (None if item shorter).

| k | distinct coarse | coverage of categorized items | granularity verdict |
|---|---|---|---|
| 1 | 8 | 100% | = domain-level; stable but nearly content-free |
| 2 | 558 | 100% | too fragmented: median 3 items/label, 68% <10 → noisy buckets |
| 3 | 564 | 96.2% | median 111, 34% <10 → still noisy |
| 4 | 672 | 71.4% | median 393, 12.5% <10; loses 29% of items |

Pros: dead simple, deterministic, O(1), no corpus statistics needed, stable across data refreshes if taxonomy stable. Cons: position ≠ semantic level — depth-2 mixes huge nodes and singletons; any fixed k either collapses to domain (k=1) or inherits the fragmentation tail (k≥2); coverage drops with k.

**(b) First/last ancestor label with ≥N items** — walk the sequence and pick the first (root-down) or deepest (leaf-up) label whose corpus frequency ≥N.

- **Root-down "first ≥N" collapses to position 1** for every feasible N: pos-1 roots have 124k–1.48M items, so N ≤ ~124k resolves ~100% of items at pos 1 (measured: N=10→8 labels, N=100→7 labels/13 unresolved, N=1,000→14 labels, N=5,000→12 labels — all ~domain-level). Only N > 1.48M escapes pos 1, which leaves nothing. Root-down is useless unless position 1 is excluded first.
- **Skip-root variant** (first label at pos ≥2 with total ≥N): N=1,000 → 88 labels, median bucket 2,385, 24 buckets <10 items, 99.65% resolved at pos 2; N=10,000 → 54 labels, median 20,958, 49,771 unresolved (2.1%). Decent, but buckets inherit pos-2 fragmentation for the tail.
- **Leaf-up "deepest label with total ≥N"** (most specific *populous* ancestor — the natural "coarse" reading):

| N | distinct coarse | % labels <10 | median bucket | p90 | unresolved |
|---|---|---|---|---|---|
| 100 | 1,190 | 9 (0.8%) | 590 | 4,668 | 13 |
| **1,000** | **609** | **0** | **1,993** | **8,170** | **225 (0.009%)** |
| 10,000 | 140 | 0 | 13,338 | 30,282 | 281 |
| 50,000 | 31 | 0 | 62,206 | 124,826 | 302 |
| 100,000 | 16 | 0 | 124,328 | 262,381 | 16,879 (0.7%) |

  Resolution depth for N=1,000 spreads across pos 2–7 (pos3: 636k, pos4: 787k, pos5: 699k items) — i.e., each item gets its *most specific label that is still well-populated*, which is exactly the semantics wanted for a coarse bucket. Top buckets: `Cases` (124k), `Action Figures` (47k), `Games` (47k), `Pre-Kindergarten Toys` (39k).

Pros of (b): adaptive granularity — dense taxonomy regions get deep buckets, sparse regions collapse upward automatically; zero tiny buckets at N≥1,000; bounded label vocabulary (~609) comparable to fixed-k but semantically meaningful. Cons: requires a corpus-frequency pass to compute (totals are cheap: one `GROUP BY category` — 2,260 rows, cached); threshold N is a magic constant; labels' totals must be recomputed if corpus changes; an item whose entire chain is niche (16.9k items at N=100k) needs a fallback.

### PROPOSAL (not a decision)

**`category_coarse` = deepest (leaf-up) label in the item's rowid-ordered sequence whose corpus item-count ≥ 1,000; fallback `main_category` (or domain) when no label qualifies or the item is uncategorized.**

Reasoning: N=1,000 is the smallest threshold with **zero** buckets <10 items while keeping 609 distinct coarse values and 99.99% coverage of categorized items — it sits at the knee where granularity (609 buckets, median ~2k items) meets stability. N=10,000 (140 buckets) is the more conservative alternative if 609 is too many for downstream consumers. Fixed-position k has no good setting: k=1 ≈ domain, k≥2 inherits the pos-2/3 fragmentation tail.

Recommended **`coarse_depth` parameter = "leaf-up frequency threshold N=1,000"** (equivalently expressed as dynamic depth). If the schema insists on a fixed integer depth instead, the least-bad is **k=3** (96% coverage, median bucket 111) — but it is strictly worse than the N-threshold on every axis except simplicity.

## 4. Oracle eval targets

Source: `experiments/agent_eval/campaigns/campaign_005/exp_5_*/run_1/requests.jsonl` — **152 requests, all 11 campaign_005 exps share the identical target set**. `targets` = item_idx → `item_id` via reversed `resource/mapped/multi_domain/item2id.json` (2,637,776 entries).

- **Real count: 196 unique target items** (196 target entries, all distinct; consistent across every exp_* run).
- **Denominator discrepancy explained:** the earlier audit's "155 oracle targets" is `n_targets: 155` in `investigations/q4_filter_orderings.json` / `q4b_traincount_ordering.json` — the **`experiments/candidate_recall/exp_003` oracle sample**, a *different artifact* (also cited in `INVESTIGATION_REPORT.md:39` as "42/155 oracle targets"). It is not the agent_eval request set. "152" is the agent_eval *request* count; the correct target-item count for that set is **196**, not 152 or 155. (Sub-counts: 60 rows have `oracle=true`, covering 46 unique targets; 116 rows have non-empty `targets`.)

Per-target category coverage (196 items):

| seq len | # targets |
|---|---|
| 0 (uncategorized) | 12 |
| 2 | 2 |
| 3 | 34 |
| 4 | 70 |
| 5 | 65 |
| 6 | 10 |
| 7 | 3 |

Label-at-depth coverage: d1 = 184/196 (93.9%), d2 = 184, d3 = 182, **d4 = 148 (75.5%)**, d5 = 78, d6 = 13, d7 = 3.
First labels: `Electronics` 127, `Toys & Games` 42, `Video Games` 13, none 12, other roots 2.

→ A depth-4-fixed `category_coarse` would be **undefined for 24.5% of eval targets**; the leaf-up N=1,000 coarse is defined for 184/196 (93.9%) with `main_category` fallback covering the 12 uncategorized.

## 5. Uncategorized items (~230k) — concentration

Total: **229,975 items** with zero `item_categories` rows (8.72% of corpus).

By domain (uncategorized / domain size / rate):

| domain | uncat | domain items | rate |
|---|---|---|---|
| Electronics | 128,428 | 1,609,860 | 8.0% |
| Toys_and_Games | 88,919 | 890,667 | **10.0%** |
| Video_Games | 12,628 | 137,249 | 9.2% |

By `main_category` (top): `Toys_and_Games::Toys & Games` 88,916 · `Electronics::All Electronics` 60,734 · `Electronics::Computers` 43,737 · `Video_Games::Video Games` 12,628 · `Electronics::Home Audio & Theater` 9,363 · `Camera & Photo` 5,434 · `Car Electronics` 2,923 · `Amazon Devices` 2,813.

**Verdict:** not sharply concentrated — rates are 8–10% in every domain, i.e. a roughly uniform source-data gap (consistent with prior finding that it skews to low-engagement items, rating_number<5 → 10.9% missing). Within Electronics it concentrates in the two broadest main_categories (`All Electronics`, `Computers` = 104k of 128k), but those are also the largest buckets, so proportionally it's spread. `main_category` coverage is ~91–97% per prior audit and is the right fallback for `category_coarse`/`category_leaf` on these items.

## Artifacts / methods

- `_audit_taxonomy.py` — pass 1: contiguity, dup/single-label, multiset→order consistency, seq-len & per-position label stats → `_taxonomy_stats.json`
- `_audit_taxonomy2.py` — pass 2: per-position label→item counts + root-down ancestor-N (N=10..5000) → `_taxonomy_stats2.json`
- `_audit_taxonomy3.py` — pass 3: leaf-up deepest-≥N and skip-root variants (N=100..300k) → `_taxonomy_stats3.json`
- `_label_totals.json` — `SELECT category, COUNT(*) … GROUP BY` (valid as item-counts because dup labels per item = 0)
- All queries `mode=ro`; no code edited, nothing committed.
