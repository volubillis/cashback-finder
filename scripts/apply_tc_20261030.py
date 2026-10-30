import csv,json,re,unicodedata
from pathlib import Path
from urllib.parse import urlparse
DATE='2026-10-30'
p=Path('index.html');s=p.read_text(encoding='utf-8');a=s.index('const SEED=')+len('const SEED=');b=s.index('];',a)+1
seed=json.loads(s[a:b]);q=s.index('const MERCHANT_REFERENCE=Object.freeze(')+len('const MERCHANT_REFERENCE=Object.freeze(');ref=json.loads(s[q:s.index(');',q)])
def norm(v):
 t=unicodedata.normalize('NFKD',str(v or ''));return re.sub('[^a-z0-9]','', ''.join(c for c in t if not unicodedata.combining(c)).lower())
alias={};never={frozenset(map(norm,pair)) for pair in ref.get('neverMerge',[])}
for n,vs in ref.get('canonicalAliases',{}).items():
 for v in [n]+list(vs):alias[norm(v)]=n
def canon(n):return alias.get(norm(n),n)
def slug(u):return urlparse(str(u or '')).path.rstrip('/').rsplit('/',1)[-1].lower()
with Path('updates/tc-2026-10-30.csv').open(encoding='utf-8-sig',newline='') as f:data=list(csv.DictReader(f))
assert 1100<len(data)<1800
byurl={};bynorm={}
for r in seed:
 if r.get('tcUrl'):byurl.setdefault(slug(r['tcUrl']),[]).append(r)
 for v in [r.get('name'),r.get('rp'),r.get('rr'),r.get('tc'),r.get('wi')]+sum([r.get(k,[]) or [] for k in ('rrAliases','wiAliases','tcAliases')],[]):
  if v:bynorm.setdefault(norm(canon(v)),[]).append(r)
changes=[];added=[];ambiguous=[];seen=set();matched=set()
for x in data:
 name=x['cat-result-info__name'].strip();url=x['cat-result href'].strip();rate=x['cat-result-info__rate'].strip();sid=slug(url)
 if not url or not rate or not name or sid in seen:continue
 seen.add(sid);matches=byurl.get(sid,[])
 if not matches:
  matches=list({id(r):r for r in bynorm.get(norm(canon(name)),[]) if frozenset((norm(name),norm(r.get('name')))) not in never}.values())
 if len(matches)>1:ambiguous.append(name);continue
 if matches:r=matches[0]
 else:
  r={'name':canon(name),'rp':'','rr':'','tc':'','wi':'','match':'Ajout CSV 2026-10-30'}
  seed.append(r);added.append(r['name'])
 old=r.get('tcRate','')
 if old and old!=rate:changes.append({'name':r['name'],'old':old,'new':rate})
 if not r.get('tc') and r['name'] not in added:added.append(r['name'])
 r.update(tc=name,tcRate=rate,tcUrl=url,tcLogo=x.get('cat-result__logo-wrap src',''),tcDesc=x.get('cat-result-info__desc',''),tcDate=DATE)
 matched.add(sid)
absent=sorted({r['tc'] for r in seed if r.get('tc') and slug(r.get('tcUrl')) not in seen})
s=s[:a]+json.dumps(seed,ensure_ascii=False,separators=(',',':'))+s[b:]
js="""
try {
 const flag='cashback_tc_20261030_v1';
 if(localStorage.getItem(flag)!=='1'){
  const norm30=v=>String(v||'').normalize('NFD').replace(/[\\u0300-\\u036f]/g,'').toLowerCase().replace(/[^a-z0-9]/g,'');
  const slug30=v=>String(v||'').replace(/\\/$/,'').split('/').pop().toLowerCase();
  const bySlug=new Map(),byName=new Map();
  for(const r of records){if(r.tcUrl)bySlug.set(slug30(r.tcUrl),r);byName.set(norm30(r.name),r)}
  for(const source of SEED){if(source.tcDate!=='2026-10-30')continue;
   const target=bySlug.get(slug30(source.tcUrl))||byName.get(norm30(source.name));
   if(target){for(const f of ['tc','tcRate','tcUrl','tcLogo','tcDesc','tcDate'])target[f]=source[f]||''}
   else records.push({...source});
  }
  localStorage.setItem(STORAGE,JSON.stringify(records));localStorage.setItem(flag,'1');
 }
}catch(e){console.warn('TopCashback 30 octobre',e)}
"""
anchor='let page=0;const PAGE_SIZE='
assert anchor in s
s=s.replace(anchor,js+'\n'+anchor,1)
p.write_text(s,encoding='utf-8')
report={'date':DATE,'source_rows':len(data),'updated':len(matched),'new':added,'rate_changes':changes,'unconfirmed_absences':absent,'ambiguous':ambiguous,'removals_performed':0}
Path('updates/report-tc-2026-10-30.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'source':len(data),'new':len(added),'changed':len(changes),'absent':len(absent),'ambiguous':ambiguous},ensure_ascii=False))
