import zipfile
from xml.etree import ElementTree as ET
NS={'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main','r':'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}
z=zipfile.ZipFile(r'DACNTT_2627.xlsx')
ss=[]
try:
    root=ET.fromstring(z.read('xl/sharedStrings.xml'))
    for si in root.findall('m:si',NS):
        ss.append(''.join(t.text or '' for t in si.iter('{%s}t'%NS['m'])))
except KeyError: pass
wb=ET.fromstring(z.read('xl/workbook.xml'))
rels=ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))
relmap={r.get('Id'):r.get('Target') for r in rels}
path='xl/worksheets/sheet2.xml'
# sheet rels for hyperlinks
try:
    srels=ET.fromstring(z.read('xl/worksheets/_rels/sheet2.xml.rels'))
    hmap={r.get('Id'):r.get('Target') for r in srels}
except KeyError:
    hmap={}
root=ET.fromstring(z.read(path))
for row in root.iter('{%s}row'%NS['m']):
    out=[]
    for c in row.findall('m:c',NS):
        ref=c.get('r'); v=c.find('m:v',NS); t=c.get('t')
        val=''
        if v is not None:
            val=v.text or ''
            if t=='s': val=ss[int(val)]
        hl=c.find('m:hyperlink',NS)
        link=''
        if hl is not None:
            rid=hl.get('{%s}id'%NS['r'])
            link=hmap.get(rid,'')
        out.append(f"{ref}:{val[:60]}[{link}]")
    line=' || '.join(out)
    if line.strip(' |:[]'): print(line)
