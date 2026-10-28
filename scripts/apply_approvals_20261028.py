#!/usr/bin/env python3
"""Apply user-confirmed 28 October removals without interpreting missing CSV rows as removals.
Never reset canonical aliases, other platform memberships, or old event history."""
import json,re,unicodedata
from pathlib import Path
P=Path('index.html');s=P.read_text(encoding='utf-8')
tag='const SEED='
a=s.index(tag)+len(tag);b=s.index('];',a)+1
rows=json.loads(s[a:b])
def norm(x):
 t=unicodedata.normalize('NFKD',str(x or '').lower())
 return re.sub('[^a-z0-9]','', ''.join(c for c in t if not unicodedata.combining(c)))
def ids(x):return [v.strip() for v in re.split(r'[;,|]',str(x or '')) if v.strip()]
def add_ids(dest,src,p):
 f=p+'Id'
 dest[f]=';'.join(dict.fromkeys(ids(dest.get(f))+ids(src.get(f))))
# Confirmations scoped per platform, NOT global merchant deletion.
confirmed={'rp':{'footcenter','hailoshop','holy','lerobert'},
           'rr':{'footcenter','hailo','holy','thecoolrepubliccom'}}
removals=[]
for p,names in confirmed.items():
 fields={'rp':['rp','rpId','rpLogo','rpDate'],'rr':['rr','rrId','rrLogo','rrUrl','rate','rrDate']}[p]
 for r in rows:
  if r.get(p) and (norm(r[p]) in names or norm(r['name']) in names):
   removals.append({'platform':p,'name':r['name'],'id':ids(r.get(p+'Id'))[:1],'type':'remove','date':'2026-10-28'})
   for f in fields:r[f]=''
# Merge only explicit verified RP aliases, never by approximate similarity.
merge_names={
 'seeticketsfr':'seetickets','nuxefr':'nuxe','aosomfr':'aosom',
 'laboiterosefr':'laboiterose','vevorfr':'vevor','lesitedelapiece':'lesitedelapiece',
 'songmicsfr':'songmics','showroomprivefr':'showroomprive',
 'directrunningfr':'directrunning','marcorianfr':'marcorian',
 'bazarchicfr':'bazarchic','bobshopfr':'bobshop',
 'bebeboutikfr':'bebeboutik','desigualcom':'desigual',
 'bodycrossfr':'bodycross','msccruisesfr':'msccruises',
 'twentydcfr':'twentydc','storesdiscountfr':'storesdiscount'
}
merged=[]
for row in list(rows):
 if not row.get('rp'):continue
 k=norm(row.get('rp'))
 canonical=merge_names.get(k)
 if not canonical:continue
 matches=[r for r in rows if r is not row and norm(r.get('name'))==canonical]
 if len(matches)!=1:continue
 dest=matches[0]
 # Never merge two cards that have incompatible RP IDs and independent non-RP content.
 if not dest.get('rp'):
  dest['rp']=row['rp']
 else:
  add_ids(dest,row,'rp')
 if not dest.get('rpLogo'):dest['rpLogo']=row.get('rpLogo','')
 if row.get('rpDate') and row['rpDate']>dest.get('rpDate',''):dest['rpDate']=row['rpDate']
 if not dest.get('rpId'):add_ids(dest,row,'rp')
 for p in ['rr','tc','wi']:
  if row.get(p) and not dest.get(p):
   for f,v in row.items():
    if (f==p or f.startswith(p)) and not dest.get(f):dest[f]=v
  elif row.get(p) and dest.get(p):
   # Preserve both records when non-RP memberships conflict.
   break
 else:
  rows.remove(row);merged.append({'from':row['name'],'to':dest['name']})
# Preserve Monoprix Mode and Monoprix Courses; no generic Monoprix merge.
rows=[r for r in rows if any(r.get(p) for p in ('rp','rr','tc','wi'))]
s=s[:a]+json.dumps(rows,ensure_ascii=False,separators=(',',':'))+s[b:]
# The existing change history is deliberately untouched. Report approved removals
# for integration into history by the application once new uploads are available.
P.write_text(s,encoding='utf-8')
out={'date':'2026-10-28','confirmed_removals':removals,'merged_aliases':merged,
     'record_count':len(rows),'preserves_history':True,'monoprix_mode_requires_csv_review':True}
Path('updates/report-approvals-2026-10-28.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(out,ensure_ascii=False))
