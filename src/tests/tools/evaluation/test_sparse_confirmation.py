from copy import deepcopy
from types import SimpleNamespace

import pytest

from scripts.evaluation.sparse_seed_eval import _hit_regressions, _summarize
from package.config import load_config


def store():
    common=dict(history_unique_items=1,status='ok',chain_seconds=.01,metadata_missing_ids=[],
        candidates=['a','b'],eligible_candidates=2,events=[])
    baseline=[dict(common,user_idx=0,targets=[0,1],ranked_ids=['a']),
              dict(common,user_idx=1,targets=[0],ranked_ids=[]),
              dict(common,user_idx=2,targets=[],ranked_ids=['a'])]
    tuned=deepcopy(baseline)
    tuned[0]['ranked_ids']=['b']  # keeps a request hit but loses one baseline target
    tuned[1]['ranked_ids']=['a']
    streams={'variant_cf_1':baseline,'variant_cf_bm25_rrf':tuned}
    return SimpleNamespace(rows=lambda stream:enumerate(streams[stream])),streams


def test_hit_regressions_detect_item_loss_and_user_gain():
    s,_=store(); result=_hit_regressions(s,{'a':0,'b':1})['overall']
    assert result['eligible_users']==2
    assert result['baseline_hit_users']==1 and result['tuned_hit_users']==2
    assert result['retained_hit_users']==1 and result['lost_hit_users']==0
    assert result['lost_target_pairs']==1 and result['gained_target_pairs']==2
    assert _hit_regressions(s,{'a':0,'b':1},{0})['overall']['users']==1


def test_cohort_summary_uses_only_selected_users_and_gt_denominator():
    s,_=store(); protocol=dict(load_config('eval/sparse_content_eval')['sparse_content_eval'],variant_ids=['cf_1','cf_bm25_rrf'])
    result=_summarize(s,{'a':0,'b':1},protocol,42,1000,{1,2})
    assert result['variants']['cf_1']['users']==2
    assert result['variants']['cf_1']['eligible_users']==1
    assert result['variants']['cf_bm25_rrf']['metrics']['hit_rate@10']==1
    assert result['variants']['cf_bm25_rrf']['paired_ndcg10']['improved']==1


def test_paired_regression_rejects_changed_targets():
    s,streams=store();streams['variant_cf_bm25_rrf'][0]['targets']=[1]
    with pytest.raises(ValueError,match='target mismatch'):_hit_regressions(s,{'a':0,'b':1})


def test_saved_hit_diagnostic_attributes_rank_loss_not_retrieval_loss():
    from package.tools.evaluation.diagnose_hit_losses import diagnose_hit_losses
    from scripts.evaluation.sparse_content_replay import rrf
    cf=[f'cf{i}' for i in range(12)];bm=[f'bm{i}' for i in range(12)];pool=cf+bm
    items={x:i for i,x in enumerate(pool)}
    baseline=dict(user_idx=0,variant='cf_1',targets=[items['cf9']],ranked_ids=cf[:10],scores=[.1]*10)
    tuned=dict(user_idx=0,variant='cf_bm25_rrf',targets=baseline['targets'],status='ok',
        ranked_ids=rrf(pool,cf,bm)[:10],candidates=pool,excluded_seen=[],unscored_item_ids=[],
        history_unique_items=1,source_candidates=dict(item_cf=cf,bm25=bm))
    result=diagnose_hit_losses([baseline,tuned],items)
    assert result['counts']['demoted_by_rrf']==1
    detail=result['details'][0]
    assert detail['baseline_rank']==10 and detail['rrf_rank']==19
    assert detail['bm25_source_rank'] is None and detail['lost_all_request_hits']
    with pytest.raises(ValueError,match='incomplete'):diagnose_hit_losses([baseline],items)
