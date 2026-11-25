import sqlite3, json, sys
from collections import Counter, defaultdict

DB='file:resource/corpus/multi_domain/corpus_multi_domain.sqlite?mode=ro'
con=sqlite3.connect(DB, uri=True)
cur=con.execute('select rowid, item_id, category from item_categories order by rowid')

lab2id={}; id2lab=[]
def lid(s):
    i=lab2id.get(s)
    if i is None:
        i=len(id2lab); lab2id[s]=i; id2lab.append(s)
    return i

n_items=0; n_rows=0
rows_per_item=Counter()
pos_item_count=Counter()          # pos -> #items with >=pos rows... actually items having label at pos
pos_label_items=defaultdict(Counter)  # pos -> label_id -> #items with that label at pos
label_itemset=defaultdict(set)    # label_id -> set of item seq ids? too heavy; use per-item flag approach below
# label->items count: accumulate per item set
label_items=Counter()
seqs_for_oracle={}                # item_id -> seq (filled later? no - collect all? too heavy)
multiset_order={}                 # key -> first order tuple
multiset_conflicts=0; multiset_multi=0
dup_label_items=0; single_label=0; weird_label_items=0
seq_len_hist=Counter()
first_label=Counter()
items_with_cat=0
item_block_noncontig=0
prev_iid=None; cur_iid=None; cur_seq=[]

def flush(iid, seq):
    global n_items, dup_label_items, single_label, weird_label_items, multiset_conflicts, multiset_multi
    n_items+=1
    L=len(seq)
    seq_len_hist[L]+=1
    if L==1: single_label+=1
    if len(set(seq))<L: dup_label_items+=1
    for l in set(seq):
        s=id2lab[l]
        if '/' in s or '>' in s or '::' in s:
            weird_label_items+=1; break
    for p,l in enumerate(seq, start=1):
        if p<=8:
            pos_label_items[p][l]+=1
    for p in range(1,9):
        if L>=p: pos_item_count[p]+=1
    for l in set(seq): label_items[l]+=1
    first_label[seq[0]]+=1
    key=tuple(sorted(seq)); order=tuple(seq)
    if key in multiset_order:
        if multiset_order[key]!=order:
            multiset_conflicts+=1
        multiset_multi+=1
    else:
        multiset_order[key]=order

for rowid,iid,cat in cur:
    n_rows+=1
    if iid!=cur_iid:
        if cur_iid is not None: flush(cur_iid, cur_seq)
        if prev_iid is not None and iid==prev_iid:
            item_block_noncontig+=1
        cur_iid=iid; cur_seq=[]
    prev_iid=iid
    cur_seq.append(lid(cat))
if cur_iid is not None: flush(cur_iid, cur_seq)
items_with_cat=n_items

out={
 'n_rows':n_rows,'items_with_cat':items_with_cat,
 'seq_len_hist':{str(k):v for k,v in sorted(seq_len_hist.items())},
 'pos_item_count':{str(k):v for k,v in sorted(pos_item_count.items())},
 'pos_label_n_distinct':{str(p):len(c) for p,c in pos_label_items.items()},
 'pos_label_sizes':{},  # filled below: per pos, sorted list of counts
 'dup_label_items':dup_label_items,'single_label_items':single_label,
 'weird_label_items':weird_label_items,
 'multiset_total_keys':len(multiset_order),'multiset_conflict_items':multiset_conflicts,
 'multiset_multi_seen_items':multiset_multi,
 'item_block_noncontig':item_block_noncontig,
 'n_labels':len(id2lab),
}
# per-position size distribution
import statistics
for p in sorted(pos_label_items):
    sizes=sorted(pos_label_items[p].values())
    n=len(sizes)
    out['pos_label_sizes'][str(p)]={
        'n_labels':n,'min':sizes[0],'median':sizes[n//2],
        'p90':sizes[int(0.9*(n-1))],'max':sizes[-1],
        'lt10':sum(1 for s in sizes if s<10),'lt10_pct':round(100*sum(1 for s in sizes if s<10)/n,2),
        'sizes':sizes,
    }
# label totals
sizes=sorted(label_items.values()); n=len(sizes)
out['label_total']={'n':n,'min':sizes[0],'median':sizes[n//2],'p90':sizes[int(0.9*(n-1))],'max':sizes[-1],'lt10':sum(1 for s in sizes if s<10)}
# top first-position labels
out['first_label_top']=[(id2lab[l],c) for l,c in first_label.most_common(15)]
out['first_label_n_distinct']=len(first_label)
# save id2lab for later use
json.dump({'out':out,'id2lab':id2lab}, open('investigations/distill_phase05_1/_taxonomy_stats.json','w'))
print(json.dumps({k:v for k,v in out.items() if k!='pos_label_sizes'}, indent=1)[:3000])
for p,d in out['pos_label_sizes'].items():
    print('pos',p,{k:v for k,v in d.items() if k!='sizes'})
