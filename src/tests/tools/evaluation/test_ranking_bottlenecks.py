import numpy as np
import pytest

from scripts.evaluation.analyze_ranking_bottlenecks import _metrics, _paired, _replay_order


@pytest.mark.parametrize("policy,expected", [
    ("semantic_first", ["s","p","c","x"]),
    ("cf_first", ["c","x","s","p"]),
    ("popularity_first", ["p","c","x","s"]),
    ("rrf_60", ["p","c","s","x"]),
])
def test_replays_use_only_fixed_pool_source_order(policy,expected):
    pool=["p","c","s","x"]
    sources={"popularity":["p","p","c","outside"],"item_cf":["c","x"],"semantic":["s","p"]}
    result=_replay_order(pool,sources,policy)
    assert result==expected
    assert len(result)==len(set(result))==len(pool)
    assert set(result)==set(pool)


def test_existing_metric_implementation_and_short_lists():
    result=_metrics(["a","b"],{1,2},{"a":0,"b":1,"c":2},10)
    assert result["recall@10"]==.5
    assert result["hit_rate@10"]==1
    assert result["precision@10"]==.1


def test_paired_bootstrap_determinism_and_zero_differences():
    zero=_paired([0.,0.,0.],np.random.default_rng(42),100)
    assert zero["ci95"]==[0.,0.]
    assert zero["unchanged"]==3
    a=_paired([.1,-.2,0.,.3],np.random.default_rng(42),100)
    b=_paired([.1,-.2,0.,.3],np.random.default_rng(42),100)
    assert a==b
    assert a["improved"]==2 and a["worse"]==1
