"""Report target transitions on a completed ANN validation matrix without retrieval."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path


def analyze(root):
    manifest = json.loads((root / 'artifact_hashes.json').read_bytes())
    if manifest['status'] != 'complete':
        raise ValueError('Incomplete matrix')
    for name in ('candidate_sets.jsonl', 'ranked.jsonl', 'config.json'):
        with (root / name).open('rb') as stream:
            if hashlib.file_digest(stream, 'sha256').hexdigest() != manifest['hashes'][name]:
                raise ValueError(f'Matrix checksum mismatch: {name}')
    config = json.loads((root / 'config.json').read_bytes())
    if config['provenance']['protocol']['item_knn']['eval_on'] != 'validation':
        raise ValueError('Expected validation data')
    ranked = {}
    with (root / 'ranked.jsonl').open(encoding='utf-8') as stream:
        for line in stream:
            r = json.loads(line)
            if (r['mode'], r['budget'], r['source'], r['scorer']) == ('recency_weighted', 200, 'ann_fused', 'baseline'):
                ranked[r['user_idx']] = set(r['ranked'][:10])
    counts, cases = defaultdict(Counter), []
    with (root / 'candidate_sets.jsonl').open(encoding='utf-8') as stream:
        for line in stream:
            r = json.loads(line)
            if (r['mode'], r['budget']) != ('recency_weighted', 200): continue
            u, gt = r['user_idx'], set(r['targets'])
            pop = gt.intersection(r['pools']['popularity'])
            fused = gt.intersection(r['pools']['ann_fused'])
            top = gt.intersection(ranked.pop(u))
            if not top <= fused: raise ValueError('Ranked hits outside frozen pool')
            for scope in ('all', r['segment']):
                counts[scope].update(users=1, popularity_hit_users=bool(pop), fused_hit_users=bool(fused),
                    ranked_hit_users=bool(top), lost_all_pop_users=bool(pop and not fused),
                    gained_users=bool(fused and not pop), lost_at_rank_users=bool(fused and not top),
                    dropped_pop_targets=len(pop-fused), added_targets=len(fused-pop),
                    dropped_at_rank_targets=len(fused-top))
            if pop or fused:
                cases.append(dict(user_idx=u, segment=r['segment'], lost_at_fusion=sorted(pop-fused),
                                  gained_at_fusion=sorted(fused-pop), lost_at_rank=sorted(fused-top),
                                  retained_top10=sorted(top)))
    if ranked or not counts: raise ValueError('Unpaired or empty validation cohort')
    return dict(matrix=str(root), hashes=manifest['hashes'], counts=counts, cases=cases)


if __name__ == '__main__':
    p=argparse.ArgumentParser()
    p.add_argument('matrix', type=Path)
    p.add_argument('output', type=Path)
    args=p.parse_args()
    result=analyze(args.matrix)
    args.output.parent.mkdir(exist_ok=True, parents=True)
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2)
    print(json.dumps(result['counts'], indent=2))
