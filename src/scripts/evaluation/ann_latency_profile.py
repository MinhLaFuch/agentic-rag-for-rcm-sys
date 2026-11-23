"""Replay both seen-filter implementations on one warmed graph, not a quality gate."""
import json
import time
import numpy as np
from scripts.evaluation.ann_validation import filtered_search


def profile(args, ids, vectors, queries, eligible, exclusions, labels):
    import faiss
    import psutil
    process = psutil.Process()
    rss_before = process.memory_info().rss
    index = faiss.IndexHNSWFlat(vectors.shape[1], args.hnsw_m, faiss.METRIC_INNER_PRODUCT)
    index.add(vectors)
    index.hnsw.efSearch = args.ef_search
    limit = max(args.k)
    paths = [filtered_search(index, ids), filtered_search(index, ids, integer_seen=True)]
    with (args.history_matrix/'candidate_sets.jsonl').open(encoding='utf-8') as stream:
        original = {r['user_idx']:r['latency']['ann_search'] for line in stream
                    if (r:=json.loads(line))['mode']==args.query_mode and r['budget']==args.budget
                    and 'ann_search' in r['latency']}
    rows = []
    names = ('matrix_strings','benchmark_indices')
    for repeat in range(-args.warmup, args.repeats):
        for i,(query,seen,label) in enumerate(zip(queries, exclusions, labels, strict=True)):
            seen_names = {str(ids[j]) for j in seen}
            results = []
            for arm in ((0,1) if (repeat+i)%2==0 else (1,0)):
                stats = {}
                start = time.perf_counter()
                results.append(paths[arm](query,eligible,seen if arm else seen_names,limit,stats))
                stats['total_seconds'] = time.perf_counter()-start
                if repeat>=0:
                    rows.append(dict(**label, arm=names[arm], repeat=repeat,
                                     original_matrix_seconds=original[label['user_idx']], **stats))
            if results[0]!=results[1]:
                raise ValueError('Seen-filter implementations returned different candidates')
    summary = {}
    for arm in names:
        selected = [r for r in rows if r['arm']==arm]
        summary[arm] = {k:float(np.percentile([r[k] for r in selected],95))
                        for k in ('total_seconds','faiss_seconds','filter_seconds','fetch_total','retries','original_matrix_seconds')}
    return dict(status='complete',summary_p95=summary,samples=rows,
                environment=dict(faiss=faiss.__version__,threads=faiss.omp_get_max_threads(),
                                 rss_before_index=rss_before,rss_after_measurement=process.memory_info().rss,
                                 available_ram_after_measurement=psutil.virtual_memory().available),
                parameters=dict(limit=limit,m=args.hnsw_m,ef_search=args.ef_search,warmup=args.warmup,
                                repeats=args.repeats,alternating_order=True))
