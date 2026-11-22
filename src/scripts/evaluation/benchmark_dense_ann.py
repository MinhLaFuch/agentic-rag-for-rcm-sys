"""CLI for optional exact-vs-ANN dense benchmark."""
from __future__ import annotations
import argparse,json,hashlib
from pathlib import Path
import numpy as np
from package.embeddings.ann_benchmark import benchmark_ann,load_benchmark_artifact,synthetic_queries

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--artifact',type=Path,required=True); p.add_argument('--queries',type=Path)
    p.add_argument('--history-matrix',type=Path); p.add_argument('--query-mode',choices=['latest_title','multi_history','recency_weighted'],default='latest_title')
    p.add_argument('--segment',choices=['cold','sparse','warm']); p.add_argument('--budget',type=int,default=100)
    p.add_argument('--corpus',type=Path); p.add_argument('--tag',default='multi_domain_v2_audit_20261030')
    p.add_argument('--synthetic',type=int,default=100); p.add_argument('--k',type=int,action='append',default=[50,100,200])
    p.add_argument('--index-type',choices=['flat_ip','hnsw_flat_ip'],default='hnsw_flat_ip')
    p.add_argument('--hnsw-m',type=int,default=32); p.add_argument('--ef-search',type=int)
    p.add_argument('--ef-sweep',type=int,nargs='+',help='Compare efSearch values on one HNSW index')
    p.add_argument('--profile-filters',action='store_true',help='Time both filtering paths on frozen ANN validation queries')
    p.add_argument('--warmup',type=int,default=1); p.add_argument('--repeats',type=int,default=3); p.add_argument('--seed',type=int,default=42)
    p.add_argument('--output',type=Path,required=True); args=p.parse_args()
    if args.output.exists(): raise SystemExit(f'output already exists: {args.output}')
    labels=None
    if args.profile_filters and (not args.history_matrix or args.ef_search is None or args.ef_search<=0
            or args.ef_sweep or args.index_type!='hnsw_flat_ip' or args.warmup<0 or args.repeats<1):
        p.error('Filter profile requires HNSW, frozen history, positive ef-search and repeats')
    if args.ef_sweep and (args.ef_search is not None or args.index_type!='hnsw_flat_ip'
            or min(args.ef_sweep)<=0 or len(set(args.ef_sweep))!=len(args.ef_sweep)):
        p.error('--ef-sweep needs distinct positive values, HNSW, and no --ef-search')
    if args.history_matrix and args.queries: p.error('Choose only one query source')
    ids,vectors,manifest=load_benchmark_artifact(args.artifact)
    seen_indices=None; users=None; matrix_hash=None; eligible_mask=np.ones(len(ids),dtype=bool); eligible_hash=None; encoder=None
    if args.history_matrix:
        from package.corpus import load_corpus
        from package.config import get_data_paths,get_domains,load_config
        from package.data.mapping import load_mappings
        from package.corpus.apply_metadata_policy import apply_metadata_policy
        from package.embeddings.history_query_benchmark import load_history_validation_queries,eligible_mask_from_ids,hash_eligible_ids,hash_seen_sets
        from scripts.data_pipeline.build_item_embeddings import load_validated_embeddings
        matrix_cfg=json.loads((args.history_matrix/'config.json').read_text(encoding='utf-8'))
        provenance=matrix_cfg['provenance']
        if (provenance['tag'] != args.tag or provenance['embeddings']['metadata_sha256'] != manifest['manifest_sha256']
                or provenance['protocol']['item_knn']['eval_on'] != 'validation'):
            raise ValueError('Expected validation matrix for the selected tag and embedding manifest')
        paths=get_data_paths(args.tag)
        args.corpus=args.corpus or paths.corpus_path
        user2id,item2id=load_mappings(paths.mapped_dir)
        del user2id
        evaluation=load_config('eval/candidate_recall')['candidate_recall']; domains=get_domains(); meta_files=[(d,str(paths.meta_path(d))) for d in domains]
        corpus,_=load_corpus(args.corpus,meta_files,item2id,float(evaluation['min_metadata_coverage']),allow_missing_sources=bool(evaluation['allow_missing_corpus_sources']))
        del item2id
        policy_info=matrix_cfg['provenance']['protocol']['metadata_policy']; policy=policy_info['name']; cutoff=policy_info['as_of_timestamp']
        if isinstance(cutoff,dict): raise ValueError('Matrix corpus policy must be fixed before benchmark')
        apply_metadata_policy(corpus,policy,as_of_timestamp=int(cutoff))
        from package.tools.retrieval.eligible_catalog_ids import eligible_catalog_ids
        eligible_ids=eligible_catalog_ids(corpus,ids)
        eligible_mask=eligible_mask_from_ids(ids,eligible_ids); eligible_hash=hash_eligible_ids(ids,eligible_mask)
        del eligible_ids
        store,encoder,_=load_validated_embeddings(args.artifact,args.corpus)
        queries,seen_indices,users,details=load_history_validation_queries(matrix_dir=args.history_matrix,encoder=encoder,item_ids=ids,dimension=vectors.shape[1],mode=args.query_mode,segment=args.segment,budget=args.budget)
        labels=[{'user_idx':u,'segment':d['segment']} for u,d in zip(users,details,strict=True)]
        seen_hash=hash_seen_sets(seen_indices); matrix_hash=hashlib.sha256((args.history_matrix/'candidate_sets.jsonl').read_bytes()).hexdigest()
    elif args.queries:
        queries=np.asarray(np.load(args.queries,allow_pickle=False),dtype=np.float32)
        seen_hash=None
    else:
        queries=synthetic_queries(vectors,args.synthetic,args.seed); seen_hash=None
    if args.profile_filters:
        from scripts.evaluation.ann_latency_profile import profile
        report=profile(args,ids,vectors,queries,eligible_mask,seen_indices,labels)
        report.update(eligible_hash=eligible_hash,seen_hash=seen_hash,build_id=manifest['build_id'])
    else:
        report=benchmark_ann(artifact=args.artifact,queries=queries,ks=sorted(set(args.k)),index_type=args.index_type,hnsw_m=args.hnsw_m,ef_search=args.ef_search,warmup=args.warmup,repeats=args.repeats,seed=args.seed,eligible_mask=eligible_mask,seen_indices=seen_indices,eligible_hash=eligible_hash,seen_hash=seen_hash,ef_sweep=args.ef_sweep,query_labels=labels)
    report['query_source']=str(args.history_matrix) if args.history_matrix else str(args.queries) if args.queries else 'synthetic'
    report['query_shape']=list(queries.shape); report['users']=users; report['history_matrix_sha256']=matrix_hash
    if args.history_matrix:
        report['history_selection']={'tag':args.tag,'mode':args.query_mode,'segment':args.segment,'budget':args.budget,
                                     'metadata_policy':policy_info,'no_text_policy':'excluded'}
    args.output.parent.mkdir(parents=True,exist_ok=True); args.output.mkdir(); (args.output/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8'); print(json.dumps(report.get('summary_p95', report),indent=2))
    return 0 if report['status'] in ('complete','unavailable') else 1
if __name__=='__main__': raise SystemExit(main())
