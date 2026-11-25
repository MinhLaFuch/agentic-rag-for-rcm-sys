import zipfile, re, sys
from xml.etree import ElementTree as ET
NS={'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main','r':'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}
z=zipfile.ZipFile(r'DACNTT_2627.xlsx')
# shared strings
ss=[]
try:
    root=ET.fromstring(z.read('xl/sharedStrings.xml'))
    for si in root.findall('m:si',NS):
        ss.append(''.join(t.text or '' for t in si.iter('{%s}t'%NS['m'])))
except KeyError: pass
# sheet names
wb=ET.fromstring(z.read('xl/workbook.xml'))
rels=ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))
relmap={r.get('Id'):r.get('Target') for r in rels}
sheets=[]
for s in wb.iter('{%s}sheet'%NS['m']):
    rid=s.get('{%s}id'%NS['r']); tgt=relmap[rid]
    sheets.append((s.get('name'), 'xl/'+tgt.lstrip('/')))
print(sheets)
name=sys.argv[1] if len(sys.argv)>1 else sheets[0][0]
path=[p for n,p in sheets if n==name][0]
root=ET.fromstring(z.read(path))
for row in root.iter('{%s}row'%NS['m']):
    vals=[]
    for c in row.findall('m:c',NS):
        v=c.find('m:v',NS); t=c.get('t')
        if v is None: vals.append(''); continue
        val=v.text or ''
        if t=='s': val=ss[int(val)]
        vals.append(val.replace('\n',' | '))
    print(' || '.join(vals))
