from unittest.mock import MagicMock

import pandas as pd
import pytest

from package.demo import DemoRequest, LiveBackend, adapt_from_plan_executor
from package.demo.samples import sample_users


def request():
    return DemoRequest(user_id="u",text="recommend",reflect_rounds=0,use_memory=False,mode="type1")


def backend():
    b=LiveBackend()
    b._initialized=True
    b._user_id_to_internal_id={"u":0}
    b._internal_id_to_item_id={0:"D::old",1:"D::recent"}
    b._fit_df=pd.DataFrame({"user_idx":[0,0],"item_idx":[1,0],"timestamp":[20,10]})
    b._type1_agent=MagicMock()
    return b


def test_type1_uses_latest_timestamp_and_fetched_metadata():
    b=backend()
    b._type1_agent.recommend.return_value={"ok":True,"items":[{"item_id":"D::outside_cache","title":"Fetched title","domain":"D","price":None}]}
    out=b.respond(request())
    b._type1_agent.recommend.assert_called_once_with("u",["D::recent"],top_k=10)
    assert out.status=="ok" and out.items[0].title=="Fetched title"


def test_type1_empty_success_is_no_result():
    b=backend(); b._type1_agent.recommend.return_value={"ok":True,"items":[]}
    assert b.respond(request()).status=="no_result"


def test_duplicate_events_do_not_change_segment_and_default_matches_eval():
    fit=pd.DataFrame({"user_idx":[0]*6+[1]*5,"item_idx":[0]*6+list(range(5))})
    samples=sample_users(fit,{"sparse":0,"warm":1,"cold":2})
    assert samples=={"cold":["cold"],"sparse":["sparse"],"warm":["warm"]}


def test_negative_sample_size_rejected():
    with pytest.raises(ValueError):
        sample_users(pd.DataFrame({"user_idx":[],"item_idx":[]}),{},n_per_segment=-1)


def test_adapter_uses_successful_tool_metadata_without_cache_and_preserves_missing():
    data=[{"tool":"RecoModelTool","ok":True,"data":{"ranked":[{"item_id":"D::x","score":1}]}},
          {"tool":"QueryTool","ok":True,"data":{"items":[{"item_id":"D::x","title":"Fetched","price":None}]}}]
    cache={"D::x":{"title":"Stale","price":999}}
    out=adapt_from_plan_executor(data,[],None,0,True,False,{},request(),cache)
    assert out.items[0].title=="Fetched" and out.items[0].price is None
    assert cache["D::x"]["price"]==999
    out=adapt_from_plan_executor(data,[],None,0,True,False,{},request(),{})
    assert out.items[0].title=="Fetched"


def test_failed_metadata_is_not_used():
    data=[{"tool":"RecoModelTool","ok":True,"data":{"ranked":[{"item_id":"D::x"}]}},
          {"tool":"QueryTool","ok":False,"data":{"items":[{"item_id":"D::x","title":"Invalid"}]}}]
    out=adapt_from_plan_executor(data,[],None,0,True,False,{},request(),{})
    assert out.items[0].title==""
