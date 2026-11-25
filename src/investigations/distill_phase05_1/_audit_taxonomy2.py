import sqlite3, json
from collections import Counter, defaultdict

con=sqlite3.connect('file:resource/corpus/multi_domain/corpus_multi_domain.sqlite?mode=ro',uri=True)
tot=json.load(open('investigations/distill_phase05_1/_label_totals.json'))
Ns=[10,100,1000,5000]
coarse={N:Counter() for N in Ns}
resolved_pos={N:Counter() for N in Ns}
pos_label_items=defaultdict(Counter)   # pos -> label -> items
seq_items=0
cur=con.execute('select item_id, category from item_categories order by rowid')
iid=None; seq=[]
def flush(iid,seq):
    global seq_items
    seq_items+=1
    for p,s in enumerate(seq,1):
        if p<=8: pos_label_items[p][s]+=1
    for N in Ns:
        hit=None
        for p,s in enumerate(seq,1):
            if tot.get(s,0)>=N:
                hit=(p,s); break
        if hit: coarse[N][hit[1]]+=1; resolved_pos[N][hit[0]]+=1
        else: resolved_pos[N]['none']+=1
for iid2,cat in cur:
    if iid2!=iid:
        if iid is not None: flush(iid,seq)
        iid=iid2; seq=[]
    seq.append(cat)
if iid is not None: flush(iid,seq)

out={'seq_items':seq_items,
 'pos_label_items':{str(p):dict(c) for p,c in pos_label_items.items()},
 'coarse':{str(N):dict(c.most_common()) for N,c in coarse.items()},
 'resolved_pos':{str(N):dict(c) for N,c in resolved_pos.items()},
 'coarse_n_distinct':{str(N):len(c) for N,c in coarse.items()},
}
json.dump(out, open('investigations/distill_phase05_1/_taxonomy_stats2.json','w'))
for N in Ns:
    print('N',N,'distinct coarse',len(coarse[N]),'resolved_pos',dict(resolved_pos[N]))
    print('  top10',coarse[N].most_common(10))
for p in sorted(pos_label_items):
    c=pos_label_items[p]; sizes=sorted(c.values())
    print('pos',p,'top',c.most_common(5),'n',len(c))
