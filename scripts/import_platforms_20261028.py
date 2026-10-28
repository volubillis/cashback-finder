#!/usr/bin/env python3
"""Integrate the complete 2026-10-28 RP and RR CSVs, preserving all verified merges."""
import csv,json,re,unicodedata
from pathlib import Path
from urllib.parse import urlparse,parse_qs
root=Path('index.html')
s=root.read_text(encoding='utf-8')
a=s.index('const SEED=')+len('const SEED=')
b=s.index('];',a)+1
rows=json.loads(s[a:b])
r0=s.index('const MERCHANT_REFERENCE=Object.freeze(')+len('const MERCHANT_REFERENCE=Object.freeze(')
ref=json.loads(s[r0:s.index(');',r0)])
def norm(v):
 t=unicodedata.normalize('NFKD',str(v or '').lower())
 return re.sub(r'[^a-z0-9]','', ''.join(c for c in t if not unicodedata.combining(c)))
def ids(s):return [v.strip() for v in re.split('[;,|]',str(s or '')) if v.strip()]
canon={}
for name,vs in ref.get('canonicalAliases',{}).items():
 for x in [name]+vs:canon[norm(x)]=name
# Additional confirmed name aliases already discussed, only unique-target matching.
verified={'seeticketsfr':'seetickets','nuxefr':'nuxe','aosomfr':'aosom','twentydcfr':'twentydc',
'laboiterosefr':'laboiterose','vevorfr':'vevor','songmicsfr':'songmics',
'showroomprivefr':'showroomprive','directrunningfr':'directrunning','marcorianfr':'marcorian',
'bazarchicfr':'bazarchic','bobshopfr':'bobshop','storesdiscountfr':'storesdiscount',
'bebeboutikfr':'bebeboutik','desigualcom':'desigual','bodycrossfr':'bodycross',
'msccruisesfr':'msccruises'}
def canonical(name):
 k=norm(name)
 return norm(canon.get(k,name)) if k not in verified else verified[k]
never={frozenset((norm(a),norm(b))) for a,b in ref.get('neverMerge',[])}
def match(p,name,ident):
 found=[r for r in rows if ident in ids(r.get(p+'Id'))] if ident else []
 if len(found)==1:return found[0]
 possibles=[]
 for r in rows:
  ns=[r.get('name'),r.get('rp'),r.get('rr'),r.get('tc'),r.get('wi')]
  ns+=r.get('rrAliases',[])+r.get('wiAliases',[])+r.get('tcAliases',[])
  if any(canonical(z)==canonical(name) and frozenset((norm(name),norm(z))) not in never for z in ns if z):
   possibles.append(r)
 return possibles[0] if len(possibles)==1 else None
def add_id(r,p,i):
 if i:r[p+'Id']=';'.join(dict.fromkeys(ids(r.get(p+'Id'))+[i]))
removed={'rp':{'footcenter','hailoshop','holy','lerobert'},'rr':{'footcenter','hailo','holy','thecoolrepubliccom'}}
stats={}
for p in ('rp','rr'):
 with open(f'updates/{p}-2026-10-28.csv',encoding='utf-8-sig',newline='') as f:source=list(csv.DictReader(f))
 new=[];matched=0;skipped=0;seen=set()
 for raw in source:
  if p=='rp':
   name=(raw.get('styles_item__header__QUAOK') or '').strip()
   url=raw.get('styles_item__bottom__RIGw9 href','')
   ident=parse_qs(urlparse(url).query).get('affiliate_id',[''])[0]
  else:
   name=(raw.get('marchand') or raw.get('nom_a_verifier') or '').strip()
   url=raw.get('col-md-3 href','')
   ident=url.rstrip('/').split('/')[-1] if url else ''
   if not ident.isdigit():ident=''
  if not name or not ident:skipped+=1;continue
  if norm(name) in removed[p]:continue
  dedupe=(ident,p)
  if dedupe in seen:continue
  seen.add(dedupe)
  r=match(p,name,ident)
  if r is None:
   r={'name':canon.get(norm(name),name),'rp':'','rr':'','wi':'','tc':'','match':'CSV à vérifier 2026-10-28'}
   rows.append(r);new.append({'name':name,'id':ident})
  else:matched+=1
  add_id(r,p,ident)
  if p=='rp':
   if not r.get('rp'):r['rp']=name
   if raw.get('styles_item__image__LQ1qQ src'):r['rpLogo']=raw['styles_item__image__LQ1qQ src']
  else:
   if not r.get('rr'):r['rr']=name
   r['rrUrl']=url
   if raw.get('logo src'):r['rrLogo']=raw['logo src']
   rate=(raw.get('percent_text') or '').strip()
   if rate:r['rate']=rate
  r[p+'Date']='2026-10-28'
 stats[p]={'csv_rows':len(source),'unique_ids_processed':len(seen),'matched':matched,'unmatched_for_review':new,'skipped':skipped}
# Explicitly keep Monoprix Mode; no absence-based deletion.
s=s[:a]+json.dumps(rows,ensure_ascii=False,separators=(',',':'))+s[b:]
root.write_text(s,encoding='utf-8')
out={'date':'2026-10-28','stats':stats,'count':len(rows),'no_automatic_deletions':True,'history_untouched':True}
Path('updates/report-import-2026-10-28.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'rp':{k:v for k,v in stats['rp'].items() if k!='unmatched_for_review'},'rr':{k:v for k,v in stats['rr'].items() if k!='unmatched_for_review'},'unmatched':{p:len(stats[p]['unmatched_for_review']) for p in stats}},ensure_ascii=False))
