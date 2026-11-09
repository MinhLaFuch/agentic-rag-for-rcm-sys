"""Separate target availability from losses in the saved retrieval stages."""
from collections import Counter


def retrieval_loss_breakdown(record, id2item, fit_items, metadata_items=None):
    raw={name for ids in record["sources_raw"].values() for name in ids}
    filtered={name for ids in record["sources_after_seen_filter"].values() for name in ids}
    targets=set(record["targets_unseen_in_fit"])
    result={}
    for item in targets:
        name=id2item[item]
        for group in ("overall",name.split("::",1)[0]):
            c=result.setdefault(group,Counter())
            c["novel_target_pairs"]+=1
            c["not_in_fit_catalog"]+=item not in fit_items
            c["not_returned_by_any_source"]+=name not in raw
            c["returned_raw_but_lost_in_source_filter_or_budget"]+=name in raw and name not in filtered
            for merge,pool in record["candidate_sets"].items():
                c[merge+"_hits"]+=name in pool
                c[merge+"_merge_budget_loss"]+=name in filtered and name not in pool
            if metadata_items is not None:
                c["missing_metadata"]+=name not in metadata_items
    return {k:dict(v) for k,v in result.items()}
