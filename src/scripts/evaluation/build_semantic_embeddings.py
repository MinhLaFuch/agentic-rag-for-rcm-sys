"""Standalone semantic environment: pin/download encoder, then resumable encoding.

Requires numpy, PyYAML and sentence-transformers in a separate environment.
Does not import project runtime dependencies or change corpus/mappings/splits.
"""
import argparse
from contextlib import contextmanager
from datetime import datetime,timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import re
import sqlite3
import time

import numpy as np
import yaml

MODEL='sentence-transformers/all-MiniLM-L6-v2'
DIM=384
FILES=['config.json','config_sentence_transformers.json','modules.json','sentence_bert_config.json',
       'model.safetensors','tokenizer.json','tokenizer_config.json','special_tokens_map.json','vocab.txt','1_Pooling/config.json']


def digest(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def atomic(path,value):
    temp=path.with_name(path.name+'.tmp')
    temp.write_text(json.dumps(value,indent=2,ensure_ascii=False),encoding='utf-8');temp.replace(path)


def environment():
    return dict(python=platform.python_version(),packages=dict(sorted(
        (d.metadata['Name'].lower(),d.version) for d in importlib.metadata.distributions() if d.metadata['Name'])))


@contextmanager
def exclusive(path):
    """OS lock releases after hard kills; no stale-lock deletion is necessary."""
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('a+b') as lock:
        lock.seek(0,2)
        if lock.tell()==0:lock.write(b'0');lock.flush()
        lock.seek(0)
        if platform.system()=='Windows':
            import msvcrt
            msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
        else:
            import fcntl
            fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        try:yield
        finally:
            lock.seek(0)
            if platform.system()=='Windows':msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)
            else:fcntl.flock(lock.fileno(),fcntl.LOCK_UN)


def verify_lock(path):
    lock=json.loads(path.read_text(encoding='utf-8'))
    if lock.get('model_id')!=MODEL or not re.fullmatch('[0-9a-f]{40}',lock.get('revision','')):
        raise ValueError('immutable full encoder commit SHA required')
    if lock.get('status')!='ready':raise ValueError('encoder download incomplete; rerun pin')
    snapshot=Path(lock['snapshot'])
    if not lock.get('model_files') or any(digest(snapshot/n)!=h for n,h in lock['model_files'].items()):
        raise ValueError('encoder model file checksum mismatch')
    if lock['environment']!=environment():raise ValueError('semantic environment changed since pin; restore recorded package versions')
    return lock


def pin(args):
    from huggingface_hub import HfApi,snapshot_download
    args.lock.parent.mkdir(parents=True,exist_ok=True)
    with exclusive(args.lock.with_suffix('.lck')):
        if args.lock.exists():
            lock=json.loads(args.lock.read_text(encoding='utf-8'))
            if lock['environment']!=environment():raise ValueError('environment differs from existing encoder lock')
            if lock.get('status')=='ready':verify_lock(args.lock);print('Encoder already pinned:',lock['revision']);return
        else:
            revision=HfApi().model_info(MODEL).sha
            if not re.fullmatch('[0-9a-f]{40}',revision):raise ValueError('Hub did not return a full immutable SHA')
            lock=dict(model_id=MODEL,revision=revision,status='revision_selected',environment=environment(),
                      created_utc=datetime.now(timezone.utc).isoformat())
            # Commit the chosen revision BEFORE downloading; retries never follow main again.
            atomic(args.lock,lock)
        snapshot=Path(snapshot_download(repo_id=MODEL,revision=lock['revision'],cache_dir=str(args.cache_dir),allow_patterns=FILES))
        for required in ('modules.json','model.safetensors','config.json','1_Pooling/config.json'):
            if not (snapshot/required).is_file():raise ValueError('required encoder file missing: '+required)
        lock.update(status='ready',snapshot=str(snapshot.resolve()),model_files={str(p.relative_to(snapshot)).replace('\\','/'):digest(p)
            for p in snapshot.rglob('*') if p.is_file()})
        atomic(args.lock,lock)
        (args.lock.parent/'requirements.lock.txt').write_text('\n'.join(n+'=='+v for n,v in lock['environment']['packages'].items())+'\n',encoding='utf-8')
        print('Pinned encoder:',lock['revision'],flush=True)


def mapping_identity(path):
    mapping=json.loads(path.read_text(encoding='utf-8'))
    if any(type(v) is not int for v in mapping.values()) or sorted(mapping.values())!=list(range(len(mapping))):
        raise ValueError('mapping must have unique contiguous integer indices')
    payload=json.dumps(sorted(mapping.items()),ensure_ascii=False,separators=(',',':'))
    return mapping,hashlib.sha256(payload.encode('utf-8')).hexdigest()


def prepare(args):
    source=json.loads((args.source/'artifact_hashes.json').read_text(encoding='utf-8'))
    for n in ('config.yaml','metrics.json','records.jsonl','requests.jsonl'):
        if digest(args.source/n)!=source[n]:raise ValueError('source artifact mismatch')
    cfg=yaml.safe_load((args.source/'config.yaml').read_text(encoding='utf-8'))
    if cfg['run']['dataset']['eval_on']!='validation':raise ValueError('validation source required')
    mapping,mapping_hash=mapping_identity(args.mapping)
    if mapping_hash!=cfg['run']['dataset']['mapping_hash']:raise ValueError('source mapping mismatch')
    lock=verify_lock(args.lock)
    identity=dict(format_version=1,source_hashes=source,corpus_sha256=digest(args.corpus),
        mapping_file_sha256=digest(args.mapping),mapping_hash=mapping_hash,encoder_lock_sha256=digest(args.lock),
        builder_sha256=digest(Path(__file__)),model_id=lock['model_id'],revision=lock['revision'],
        model_files=lock['model_files'],environment=environment(),dimensions=DIM,dtype='float32',normalized=True,
        serialization='fts_fields_named_lines_whitespace_collapse_v1',
        document_fields=['title','store','main_category','categories'],metadata_policy='runtime_snapshot_not_historical_causal',
        metadata_equivalence='current SQLite snapshot; saved runtime source is an anchor, NOT verified full metadata equivalence; compare BM25 on this same snapshot',
        max_seq_length=256,seed=42,device=args.device,threads=args.threads,batch_size=args.batch_size,chunk_size=args.chunk_size,
        limit_items=args.limit_items,scope='technical_subset_NOT_quality_catalog' if args.limit_items else 'full_mapping_catalog')
    return mapping,identity,lock


def extract(args,mapping):
    conn=sqlite3.connect(args.corpus.resolve().as_uri()+'?mode=ro',uri=True);conn.execute('PRAGMA query_only=ON')
    sql='''SELECT items.item_id,items_fts.title,items_fts.store,items_fts.main_category,items_fts.categories
           FROM items JOIN items_fts ON items.rowid=items_fts.rowid ORDER BY items.item_id'''
    ids=[];seen=set();temp=args.out/'documents.jsonl.tmp'
    with temp.open('w',encoding='utf-8') as stream:
        for row in conn.execute(sql):
            item=row[0]
            if item not in mapping or item in seen:raise ValueError('corpus item not in mapping, or duplicate')
            seen.add(item);ids.append(item)
            values=[' '.join(str(v or '').split()) for v in row[1:]]
            text='\n'.join(k+': '+v for k,v in zip(['title','store','main_category','categories'],values) if v)
            stream.write(json.dumps(dict(item_id=item,text=text,valid=bool(text)),ensure_ascii=False)+'\n')
            if args.limit_items and len(ids)>=args.limit_items:break
    conn.close()
    if not ids or (not args.limit_items and seen!=set(mapping)):raise ValueError('full corpus/mapping item-set mismatch')
    temp.replace(args.out/'documents.jsonl');atomic(args.out/'item_ids.json',ids)
    return ids


def build(args,encoder_factory=None):
    if min(args.batch_size,args.chunk_size,args.threads)<1 or args.limit_items<0:raise ValueError('positive sizes/threads and nonnegative item limit required')
    args.out.mkdir(parents=True,exist_ok=True)
    with exclusive(args.out/'.build.lock'):
        print('[provenance] hashing source, corpus, mapping and encoder',flush=True)
        mapping,identity,lock=prepare(args);state_path=args.out/'checkpoint.json'
        if state_path.exists():
            if not args.resume:raise ValueError('checkpoint exists; use --resume or a new output directory')
            state=json.loads(state_path.read_text(encoding='utf-8'))
            if state['identity']!=identity:raise ValueError('checkpoint input/code/environment/protocol mismatch')
            for n,h in state['documents_hashes'].items():
                if digest(args.out/n)!=h:raise ValueError('document/row-order checksum mismatch')
            if (args.out/'manifest.json').exists():
                manifest=json.loads((args.out/'manifest.json').read_text(encoding='utf-8'))
                for n,h in manifest['artifact_hashes'].items():
                    if digest(args.out/n)!=h:raise ValueError('completed artifact checksum mismatch')
                print('Already complete:',args.out);return
            ids=json.loads((args.out/'item_ids.json').read_text(encoding='utf-8'))
            vectors=np.load(args.out/'vectors.npy',mmap_mode='r+');valid=np.load(args.out/'valid.npy',mmap_mode='r+')
            if vectors.shape!=(len(ids),DIM) or valid.shape!=(len(ids),) or vectors.dtype!=np.float32 or valid.dtype!=np.bool_:
                raise ValueError('checkpoint vector shape/dtype mismatch')
            previous=0
            for chunk in state['chunks']:
                a,b=chunk['start'],chunk['stop']
                if a!=previous or not a<b<=len(ids):raise ValueError('non-contiguous checkpoint chunks')
                if hashlib.sha256(vectors[a:b].tobytes()+valid[a:b].tobytes()).hexdigest()!=chunk['sha256']:
                    raise ValueError('committed vector chunk checksum mismatch')
                previous=b
            if previous!=state['completed']:raise ValueError('checkpoint completion/chunks mismatch')
        else:
            print('[documents] extracting fixed FTS fields, ordered by item_id',flush=True);ids=extract(args,mapping)
            vectors=np.lib.format.open_memmap(args.out/'vectors.npy',mode='w+',dtype=np.float32,shape=(len(ids),DIM))
            valid=np.lib.format.open_memmap(args.out/'valid.npy',mode='w+',dtype=np.bool_,shape=(len(ids),))
            state=dict(identity=identity,rows=len(ids),completed=0,chunks=[],
                documents_hashes={n:digest(args.out/n) for n in ('documents.jsonl','item_ids.json')})
            atomic(state_path,state)
        if encoder_factory:
            encoder=encoder_factory(lock)
        else:
            print('[encoder] loading locked local snapshot on CPU',flush=True)
            import torch
            from sentence_transformers import SentenceTransformer
            torch.manual_seed(42);torch.set_num_threads(args.threads)
            encoder=SentenceTransformer(lock['snapshot'],local_files_only=True,trust_remote_code=False,device=args.device)
            encoder.max_seq_length=256;encoder.eval()
            if encoder.get_sentence_embedding_dimension()!=DIM:raise ValueError('unexpected encoder dimension')
        started=time.perf_counter();initial=state['completed'];pending=[];offset=0
        def commit(documents,start):
            stop=start+len(documents);mask=np.array([d['valid'] for d in documents],dtype=bool)
            values=np.zeros((len(documents),DIM),dtype=np.float32)
            if mask.any():
                encoded=np.asarray(encoder.encode([d['text'] for d in documents if d['valid']],batch_size=args.batch_size,
                    normalize_embeddings=True,convert_to_numpy=True,show_progress_bar=False),dtype=np.float32)
                if encoded.shape!=(int(mask.sum()),DIM) or not np.isfinite(encoded).all() or not np.allclose(np.linalg.norm(encoded,axis=1),1,atol=1e-4):
                    raise ValueError('invalid encoder output: shape, finite values or unit norms')
                values[mask]=encoded
            vectors[start:stop]=values;valid[start:stop]=mask;vectors.flush();valid.flush()
            state['chunks'].append(dict(start=start,stop=stop,sha256=hashlib.sha256(values.tobytes()+mask.tobytes()).hexdigest()))
            state['completed']=stop;atomic(state_path,state)
            elapsed=time.perf_counter()-started;rate=(stop-initial)/elapsed
            print(f'[encode] {stop}/{len(ids)} items | {rate:.2f} items/s | ETA {(len(ids)-stop)/rate:.0f}s',flush=True)
        with (args.out/'documents.jsonl').open(encoding='utf-8') as stream:
            for index,line in enumerate(stream):
                if index<state['completed']:continue
                if not pending:offset=index
                pending.append(json.loads(line))
                if len(pending)>=args.chunk_size:commit(pending,offset);pending=[]
            if pending:commit(pending,offset)
        if state['completed']!=len(ids):raise ValueError('incomplete document stream')
        print('[validate] rechecking provenance and hashing completed vectors',flush=True)
        # Recheck external inputs before final publication, never publish changed data.
        if prepare(args)[1]!=identity:raise ValueError('input changed during encoding')
        artifacts={n:digest(args.out/n) for n in ('documents.jsonl','item_ids.json','vectors.npy','valid.npy')}
        atomic(args.out/'manifest.json',dict(identity=identity,rows=len(ids),valid_rows=int(valid.sum()),
            invalid_rows=int(len(valid)-valid.sum()),artifact_hashes=artifacts,
            item_id_row_order_sha256=artifacts['item_ids.json'],
            invalid_row_policy='zero vector, valid.npy false; MUST exclude from retrieval',
            status='complete',quality_evaluated=False))
        print('Complete:',args.out,'rows=',len(ids),'encoding_seconds=',round(time.perf_counter()-started,2),flush=True)


def main():
    ap=argparse.ArgumentParser(description=__doc__);sub=ap.add_subparsers(dest='command',required=True)
    p=sub.add_parser('pin');p.add_argument('--lock',type=Path,required=True);p.add_argument('--cache-dir',type=Path,required=True)
    b=sub.add_parser('build')
    for name in ('lock','source','corpus','mapping','out'):b.add_argument('--'+name,type=Path,required=True)
    b.add_argument('--device',choices=['cpu'],default='cpu');b.add_argument('--threads',type=int,default=4)
    b.add_argument('--batch-size',type=int,default=64);b.add_argument('--chunk-size',type=int,default=512)
    b.add_argument('--limit-items',type=int,default=0);b.add_argument('--resume',action='store_true')
    args=ap.parse_args();pin(args) if args.command=='pin' else build(args)


if __name__=='__main__':main()
