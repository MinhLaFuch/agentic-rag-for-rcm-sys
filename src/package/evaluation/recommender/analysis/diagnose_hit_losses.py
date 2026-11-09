"""Read-only attribution of saved CF baseline target losses under source RRF60."""
from collections import Counter


def diagnose_hit_losses(records, items):
    from scripts.evaluation.sparse_content_replay import rrf
    baselines={}; seen=set(); details=[]; counts=Counter()
    for row in records:
        key=(row['user_idx'],row['variant'])
        if key in seen: raise ValueError('duplicate user/variant')
        seen.add(key)
        if row['variant']=='cf_1':
            baselines[row['user_idx']]={k:row[k] for k in ('targets','ranked_ids','scores')}
            continue
        if row['variant']!='cf_bm25_rrf': raise ValueError('RRF runtime source required')
        baseline=baselines.pop(row['user_idx'])
        if baseline['targets']!=row['targets']: raise ValueError('ground truth mismatch')
        counts['paired_users']+=1
        gt=set(row['targets'])
        old={i for i in baseline['ranked_ids'][:10] if items[i] in gt}
        lost=old-set(row['ranked_ids'][:10])
        if not lost: continue
        counts['users_losing_target_pairs']+=1
        cf=row.get('source_candidates',{}).get('item_cf',[])
        bm=row.get('source_candidates',{}).get('bm25',[])
        pool=[i for i in row['candidates'] if i not in row['excluded_seen']+row['unscored_item_ids']]
        ranked=rrf(pool,cf,bm) if row['status']=='ok' else []
        if ranked[:10]!=row['ranked_ids']: raise ValueError('RRF top10 mismatch')
        for item in sorted(lost):
            reason=('tool_error' if row['status']=='tool_error' else 'outside_pool' if item not in row['candidates']
                    else 'filtered' if item not in pool else 'demoted_by_rrf')
            counts[reason]+=1; counts['lost_target_pairs']+=1
            pos=baseline['ranked_ids'].index(item)
            details.append(dict(user_idx=row['user_idx'],history_unique_items=row['history_unique_items'],item_id=item,
                reason=reason,baseline_rank=pos+1,baseline_model_score=baseline['scores'][pos],
                cf_source_rank=cf.index(item)+1 if item in cf else None,
                bm25_source_rank=bm.index(item)+1 if item in bm else None,
                rrf_rank=ranked.index(item)+1 if item in ranked else None,
                lost_all_request_hits=not any(items[i] in gt for i in row['ranked_ids'][:10]),
                higher_ranked_sources=[('both' if i in cf and i in bm else 'cf_only' if i in cf else 'bm25_only')
                                       for i in ranked[:ranked.index(item)] ] if item in ranked else []))
    if baselines: raise ValueError('incomplete paired streams')
    return dict(counts=dict(counts),details=details)
