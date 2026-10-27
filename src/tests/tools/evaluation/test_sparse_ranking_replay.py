import json

import pytest

from package.tools.evaluation.recent_priority_order import recent_priority_order
from scripts.evaluation.sparse_ranking_replay import _compare


@pytest.mark.parametrize("policy",["latest_top3_guard","latest_cf_first"])
def test_recent_priority_never_adds_missing_donor_candidates(policy):
    result=recent_priority_order(["a","b","c"],["b","c","a"],["outside","a"],["outside","a","b"],policy)
    assert result[0]=="a"
    assert set(result)=={"a","b","c"} and len(result)==3


def test_guard_prefix_reuses_current_ranking_and_does_not_impute_scores():
    pool=list("abcdefghijk")
    out=recent_priority_order(pool,list("bcdefghijk"),["a","b","c"],[],"latest_top3_guard")
    assert out[:10]==list("abcdefghij")
    with pytest.raises(ValueError,match="incomplete"):
        recent_priority_order(pool,["b"],["a"],[],"latest_top3_guard")


def test_replay_same_pool_oracle_and_empty_gt_denominators(tmp_path):
    pool=list("abcdefghijk"); rows=[]
    for n in [1,2,4]:
        for u in [0,1]:
            rows.append(dict(user_idx=u,seed_count=n,history_unique_items=2,targets=[0] if u==0 else [],
                ranked_ids=list("abcdefghij") if n==1 else list("bcdefghijk"),candidates=pool,
                candidate_budget=50,error=None,metadata_missing_ids=[],excluded_seen=[],unscored_item_ids=[],eligible_candidates=11))
    src=tmp_path/"source.jsonl"; src.write_text("\n".join(json.dumps(r) for r in rows))
    result=_compare(src,{i:n for n,i in enumerate(pool)},42,1000,tmp_path/"out.jsonl")
    seed2=result["comparison"]["2"]
    assert seed2["baseline"]["metrics"]["recall@10"]==0
    assert seed2["latest_top3_guard"]["metrics"]["recall@10"]==1
    assert seed2["latest_top3_guard"]["eligible_users"]==1
    assert seed2["latest_top3_guard"]["oracle_recall10_fixed_pool"]==1
    assert result["losses"]["2"]["baseline_hit_pairs_in_pool_below10"]==1
    assert not list(tmp_path.glob("*.md"))


def test_replay_rejects_misaligned_ground_truth(tmp_path):
    rows=[dict(user_idx=0,seed_count=1,targets=[0],history_unique_items=2),
          dict(user_idx=0,seed_count=2,targets=[1],history_unique_items=2)]
    src=tmp_path/"source.jsonl"; src.write_text("\n".join(json.dumps(r) for r in rows))
    with pytest.raises(ValueError,match="ground truth"):
        _compare(src,{"a":0},42,1000,tmp_path/"out.jsonl")
