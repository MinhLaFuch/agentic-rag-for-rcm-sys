"""Read-only semantic pilot readiness; no downloads, embeddings, or model fit."""
import importlib.metadata
import importlib.util
import json
from pathlib import Path
import shutil
import sqlite3

import yaml

from package.config import get_data_paths,load_config
from package.data.mapping import load_mappings
from package.tools.recommenders.file_hash import file_hash
from package.tools.recommenders.mapping_hash import mapping_hash


def main():
    protocol=load_config('eval/semantic_candidate_pilot')['semantic_candidate_pilot']
    source=Path(protocol['source']);cfg=yaml.safe_load((source/'config.yaml').read_text(encoding='utf-8'))
    d=cfg['run']['dataset'];hashes=json.loads((source/'artifact_hashes.json').read_text(encoding='utf-8'))
    for n in ('config.yaml','metrics.json','records.jsonl','requests.jsonl'):
        if file_hash(source/n)!=hashes[n]:raise ValueError('source provenance mismatch')
    if d['eval_on']!='validation' or d['tag']!=protocol['tag']:raise ValueError('source dataset/split mismatch')
    paths=get_data_paths(d['tag']);users,items=load_mappings(paths.mapped_dir)
    if mapping_hash(items)!=d['mapping_hash'] or mapping_hash(users)!=d['user_mapping_hash']:raise ValueError('mapping mismatch')
    selected=cfg['config']['sampled_user_ids']
    if len(selected)!=protocol['users'] or len(set(selected))!=len(selected):raise ValueError('sample mismatch')
    packages={}
    for name,module in [('sentence-transformers','sentence_transformers'),('torch','torch'),('transformers','transformers'),('faiss-cpu','faiss')]:
        available=importlib.util.find_spec(module) is not None
        try:version=importlib.metadata.version(name) if available else None
        except importlib.metadata.PackageNotFoundError:version='unknown'
        packages[name]=dict(import_spec_available=available,version=version)
    corpus=paths.corpus_path if hasattr(paths,'corpus_path') else Path('src/resource/corpus')/('corpus_'+d['tag']+'.sqlite')
    corpus=Path(corpus)
    conn=sqlite3.connect(corpus.resolve().as_uri()+'?mode=ro',uri=True)
    conn.execute('PRAGMA query_only=ON');catalog_items=conn.execute('SELECT COUNT(*) FROM items').fetchone()[0];conn.close()
    vector_bytes=catalog_items*protocol['dimensions']*4
    ready=all(packages[n]['import_spec_available'] for n in ('sentence-transformers','torch'))
    report=dict(status='encoder_install_and_artifact_build_required' if not ready else 'encoder_not_validated_embeddings_still_required',
        source_hashes=hashes,selected_users=len(selected),catalog_items=catalog_items,
        packages=packages,dense_vectors_bytes=vector_bytes,dense_vectors_gib=vector_bytes/1024**3,
        memory_scope='vectors only; excludes model, tokenization, search buffers and metadata; float32 memory-mapped blocks required',
        workspace_free_bytes=shutil.disk_usage(Path.cwd()).free,
        blockers=['no validated immutable encoder revision','no validated catalog embeddings artifact','no semantic quality results'],
        protocol=protocol,side_effects='none; no model download, package installation, encoding or production changes')
    print(json.dumps(report,indent=2,ensure_ascii=False))


if __name__=='__main__':main()
