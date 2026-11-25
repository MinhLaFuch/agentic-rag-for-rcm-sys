import sqlite3, json
from collections import Counter, defaultdict

con=sqlite3.connect('file:resource/corpus/multi_domain/corpus_multi_domain.sqlite?mode=ro',uri=True)
tot=json.load(open('investigations/distill_phase05_1/_label_totals.json'))
Ns=[100,1000,10000,50000,100000,300000]
# leaf-up: deepest label with total>=N
lu_coarse={N:Counter() for N in Ns}; lu_pos={N:Counter() for N in Ns}
# root-down but SKIP pos1 (treat pos1 as fixed root): first label at pos>=2 with total>=N
skip_coarse={N:Counter() for N in Ns}; skip_pos={N:Counter() for N in Ns}
cur=con.execute('select item_id, category from item_categories order by rowid')
iid=None; seq=[]
def flush(iid,seq):
    for N in Ns:
        # leaf-up
        hit=None
        for p in range(len(seq),0,-1):
            s=seq[p-1]
            if tot.get(s,0)>=N: hit=(p,s); break
        if hit: lu_coarse[N][hit[1]]+=1; lu_pos[N][hit[0]]+=1
        else: lu_pos[N]['none']+=1
        # skip-root
        hit=None
        for p in range(2,len(seq)+1):
            s=seq[p-1]
            if tot.get(s,0)>=N: hit=(p,s); break
        if hit: skip_coarse[N][hit[1]]+=1; skip_pos[N][hit[0]]+=1
        else: skip_pos[N]['none']+=1
for iid2,cat in cur:
    if iid2!=iid:
        if iid is not None: flush(iid,seq)
        iid=iid2; seq=[]
    seq.append(cat)
if iid is not None: flush(iid,seq)

out={'leafup':{str(N):{'n_distinct':len(lu_coarse[N]),'pos':dict(lu_pos[N]),'top':lu_coarse[N].most_common(15),'sizes':sorted(lu_coarse[N].values())} for N in Ns},
     'skiproot':{str(N):{'n_distinct':len(skip_coarse[N]),'pos':dict(skip_pos[N]),'top':skip_coarse[N].most_common(15),'sizes':sorted(skip_coarse[N].values())} for N in Ns}}
json.dump(out, open('investigations/distill_phase05_1/_taxonomy_stats3.json','w'))
for N in Ns:
    d=out['leafup'][str(N)]; s=sorted(d['sizes']); n=len(s)
    print('LEAFUP N',N,'distinct',d['n_distinct'],'pos',d['pos'],'med',s[n//2],'p90',s[int(.9*(n-1))],'lt10',sum(1 for x in s if x<10))
    print('   top8',d['top'][:8])
for N in Ns:
    d=out['skiproot'][str(N)]; s=sorted(d['sizes']); n=len(s)
    print('SKIPROOT N',N,'distinct',d['n_distinct'],'pos',d['pos'],'med',s[n//2],'p90',s[int(.9*(n-1))],'lt10',sum(1 for x in s if x<10))
    print('   top8',d['top'][:8])
