import csv,json
from pathlib import Path
p=Path('index.html');s=p.read_text()
a=s.index('const SEED=')+11;b=s.index('];',a)+1
rows=json.loads(s[a:b])
with open('updates/rr-2026-10-29.csv',encoding='utf-8-sig') as f: data=list(csv.DictReader(f))
byid={v:i for i,r in enumerate(rows) for v in r.get('rrId','').split(';') if v}
for r in data:
 id=r['col-md-3 href'].rstrip('/').split('/')[-1]
 if id in byid:
  row=rows[byid[id]]
  if row.get('name')!='Geuther':row['rate']=r['percent_text']
  row['rrDate']='2026-10-29'
  continue
 if r['marchand']=='Dowinx':
  row=next(x for x in rows if x.get('name')=='Dowinx')
  row['rrId']=';'.join(dict.fromkeys(row['rrId'].split(';')+[id]))
rows=[r for i,r in enumerate(rows) if r.get('name')!='Dowinx' or not any(x.get('name')=='Dowinx' for x in rows[:i])]
p.write_text(s[:a]+json.dumps(rows,ensure_ascii=False,separators=(',',':'))+s[b:])
