#!/usr/bin/env python3
import csv, json, re, unicodedata
from pathlib import Path
from urllib.parse import urlparse, parse_qs

DATE = '2026-10-27'
ROOT = Path('index.html')
src = ROOT.read_text(encoding='utf-8')
start = src.index('const SEED=') + len('const SEED=')
end = src.index('];', start) + 1
seed = json.loads(src[start:end])
reference_start = src.index('const MERCHANT_REFERENCE=') + len('const MERCHANT_REFERENCE=Object.freeze(')
reference_end = src.index(');', reference_start)
reference = json.loads(src[reference_start:reference_end])
aliases = reference['canonicalAliases']
never = {frozenset(map(str.lower, pair)) for pair in reference.get('neverMerge', [])}

def norm(s):
    s = unicodedata.normalize('NFKD', str(s or ''))
    return re.sub(r'[^a-z0-9]', '', ''.join(c for c in s if not unicodedata.combining(c)).lower())

canon = {}
for name, values in aliases.items():
    for v in [name] + values:
        canon[norm(v)] = name
def canonical(name):
    return canon.get(norm(name), str(name or '').strip())
def same(a,b):
    ca,cb = canonical(a),canonical(b)
    return norm(ca) == norm(cb) and frozenset([str(a).lower(),str(b).lower()]) not in never

def csvrows(platform):
    with Path('updates/' + platform + '-2026-10-27.csv').open(encoding='utf-8-sig',newline='') as f:
        return list(csv.DictReader(f))
rp,rr,wi = csvrows('rp'), csvrows('rr'), csvrows('wi')
assert 1600 <= len(rp) <= 1700 and 1050 <= len(rr) <= 1150 and 2300 <= len(wi) <= 2500

FIELDS = {'rp': ['rp','rpId','rpLogo','rpDate'], 'rr':['rr','rrId','rrLogo','rrUrl','rate','rrDate'], 'wi':['wi','wiUrl','wiRate','wiDate','wiAliases','wiUrls']}
stats={p:{'source':len(rows),'new':[],'rate_changes':[],'unconfirmed_absences':[]} for p,rows in [('rp',rp),('rr',rr),('wi',wi)]}
events=[]
def split_ids(s):
    return [v.strip() for v in re.split('[;,]', str(s or '')) if v.strip()]

def lookup(p, name, identifier='', url=''):
    # Stable platform ID first; avoid accidentally joining different affiliates.
    idfield = p+'Id'
    if identifier and p != 'wi':
        found=[x for x in seed if identifier in split_ids(x.get(idfield))]
        if found: return found[0]
    if p=='wi' and url:
        found=[x for x in seed if x.get('wiUrl')==url or url in x.get('wiUrls',[])]
        if found: return found[0]
    found=[x for x in seed if any(same(name, n) for n in [x.get('name'),x.get('rp'),x.get('rr'),x.get('tc'),x.get('wi')]+x.get('rrAliases',[])+x.get('wiAliases',[])+x.get('tcAliases',[]) if n)]
    # Only merge on a unique canonical merchant.
    return found[0] if len(found)==1 else None

def get(p,name,identifier='',url=''):
    row=lookup(p,name,identifier,url)
    if row is None:
        row={'name':canonical(name),'rp':'','rr':'','tc':'','wi':'','match':'Ajout CSV 2026-10-27'}
        seed.append(row)
    return row

def add_id(row, field, new):
    prior=split_ids(row.get(field))
    if new not in prior: prior.append(new)
    row[field]=';'.join(prior)

prior = {p:[dict(x) for x in seed if x.get(p)] for p in ('rp','rr','wi')}
seen={'rp':set(),'rr':set(),'wi':set()}
for x in rp:
    name=(x.get('styles_item__header__QUAOK') or '').strip()
    if not name: continue
    url=x.get('styles_item__bottom__RIGw9 href','')
    identifier=parse_qs(urlparse(url).query).get('affiliate_id',[''])[0]
    if not identifier: continue
    seen['rp'].add(identifier)
    row=get('rp',name,identifier)
    newly=not row.get('rp')
    row['rp']=name
    add_id(row,'rpId',identifier)
    if x.get('styles_item__image__LQ1qQ src'): row['rpLogo']=x['styles_item__image__LQ1qQ src']
    row['rpDate']=DATE
    if newly:
        stats['rp']['new'].append(row['name'])
        events.append({'platform':'rp','name':row['name'],'id':identifier,'type':'add','date':DATE})
for x in rr:
    name=(x.get('marchand') or x.get('nom_a_verifier') or '').strip()
    url=(x.get('col-md-3 href') or '').strip()
    identifier=url.rstrip('/').split('/')[-1]
    if not name or not identifier.isdigit():continue
    seen['rr'].add(identifier)
    row=get('rr',name,identifier,url)
    newly=not row.get('rr')
    oldrate=row.get('rate','')
    row['rr']=name
    add_id(row,'rrId',identifier)
    row['rrUrl']=url
    if x.get('logo src'):row['rrLogo']=x['logo src']
    row['rate']=(x.get('percent_text') or '').strip()
    row['rrDate']=DATE
    if newly:
        stats['rr']['new'].append(row['name'])
        events.append({'platform':'rr','name':row['name'],'id':identifier,'type':'add','date':DATE})
    if oldrate and oldrate != row['rate']:
        stats['rr']['rate_changes'].append({'name':row['name'],'old':oldrate,'new':row['rate']})
for x in wi:
    name=(x.get('marchand') or '').strip()
    url=(x.get('url') or '').strip()
    if not name or not url:continue
    seen['wi'].add(url)
    row=get('wi',name,url=url)
    newly=not row.get('wi')
    oldrate=row.get('wiRate','')
    row['wi']=name
    row['wiUrl']=url
    row['wiUrls']=list(dict.fromkeys([*(row.get('wiUrls') or []),url]))
    row['wiAliases']=list(dict.fromkeys([*(row.get('wiAliases') or []),name]))
    # An empty Widilo scraped rate is unknown, not a confirmed zero.
    rate=(x.get('cashback') or '').strip()
    if rate:row['wiRate']=rate
    row['wiDate']=DATE
    if newly:
        stats['wi']['new'].append(row['name'])
        events.append({'platform':'wi','name':row['name'],'id':'','type':'add','date':DATE})
    if oldrate and rate and oldrate != rate:
        stats['wi']['rate_changes'].append({'name':row['name'],'old':oldrate,'new':rate})

confirmed=['HIGH FR','Omy maison FR','The Cool Republic','Médor et Cie']
removed=[]
for name in confirmed:
    candidates=[x for x in seed if x.get('rp') and any(same(name,v) for v in (x.get('rp'),x.get('name')))]
    if not candidates:
        continue
    for row in candidates:
        if row.get('rp'):
            # Do not duplicate the previously confirmed Médor et Cie event.
            if norm(name)!=norm('Médor et Cie'):
                events.append({'platform':'rp','name':row['name'],'id':split_ids(row.get('rpId'))[0] if split_ids(row.get('rpId')) else '','type':'remove','date':DATE})
            removed.append(row['name'])
            for field in ('rp','rpId','rpLogo','rpDate'):
                row[field]=''
for p in ('rp','rr','wi'):
    for row in prior[p]:
        if p=='rp':
            ids=split_ids(row.get('rpId'))
            present=any(i in seen[p] for i in ids)
            if not present and not any(same(row['name'],n) for n in confirmed):stats[p]['unconfirmed_absences'].append(row['name'])
        elif p=='rr':
            if not any(i in seen[p] for i in split_ids(row.get('rrId'))):
                stats[p]['unconfirmed_absences'].append(row['name'])
        else:
            if row.get('wiUrl') not in seen[p] and not any(u in seen[p] for u in row.get('wiUrls',[])):
                stats[p]['unconfirmed_absences'].append(row['name'])

# Do not remove a merchant card if it still exists on any platform.
seed=[x for x in seed if any(x.get(p) for p in ('rp','rr','wi','tc'))]
src=src[:start]+json.dumps(seed,ensure_ascii=False,separators=(',',':'))+src[end:]

# Update saved browser state on first visit after this deployment, keeping categories and all other user preferences.
js = """
// Import validé 2026-10-27 : priorité aux identifiants et aux fiches existantes.
try {
 const flag='cashback_platform_seed_20261027_v1';
 if(localStorage.getItem(flag)!=='1'){
  const norm27=s=>String(s||'').normalize('NFD').replace(/[\\u0300-\\u036f]/g,'').toLowerCase().replace(/[^a-z0-9]/g,'');
  const byKey=new Map(records.map(r=>[norm27(r.name),r]));
  const byRpId=new Map(),byRrId=new Map(),byWiUrl=new Map();
  for(const r of records){
   for(const i of String(r.rpId||'').split(/[;,]/).map(s=>s.trim()).filter(Boolean))byRpId.set(i,r);
   for(const i of String(r.rrId||'').split(/[;,]/).map(s=>s.trim()).filter(Boolean))byRrId.set(i,r);
   if(r.wiUrl)byWiUrl.set(r.wiUrl,r);
  }
  for(const source of SEED){
   const rpids=String(source.rpId||'').split(/[;,]/).map(s=>s.trim()).filter(Boolean);
   const rrids=String(source.rrId||'').split(/[;,]/).map(s=>s.trim()).filter(Boolean);
   const target=rpids.map(i=>byRpId.get(i)).find(Boolean)||rrids.map(i=>byRrId.get(i)).find(Boolean)||byWiUrl.get(source.wiUrl)||byKey.get(norm27(source.name));
   if(target){
    for(const p of ['rp','rr','wi']){
     if(source[p+'Date']==='2026-10-27'){
      for(const field of p==='rp'?['rp','rpId','rpLogo','rpDate']:p==='rr'?['rr','rrId','rrLogo','rrUrl','rate','rrDate']:['wi','wiUrl','wiRate','wiDate','wiAliases','wiUrls'])if(source[field]!==undefined)target[field]=source[field];
     }
    }
   }else if(['rp','rr','wi'].some(p=>source[p+'Date']==='2026-10-27'))records.push({...source});
  }
  // Retirer uniquement les quatre marchands RP confirmés, quel que soit leur état local.
  for(const r of records)if(['highfr','omymaisonfr','thecoolrepublic','medoretcie'].includes(norm27(r.rp)||norm27(r.name)))for(const f of ['rp','rpId','rpLogo','rpDate'])r[f]='';
  localStorage.setItem(STORAGE,JSON.stringify(records));localStorage.setItem(flag,'1');
 }
}catch(e){console.warn('Synchronisation CSV 27 octobre',e)}
"""
anchor='let page=0;const PAGE_SIZE='
assert anchor in src
src=src.replace(anchor,js+'\n'+anchor,1)
# Embed additions in the 10 most recent history events without losing old ones or duplicating Médor.
hist="const PLATFORM_CHANGES_20261027="+json.dumps(events,ensure_ascii=False,separators=(',',':'))+";\n"
anchor='const CHANGE_STORAGE='
assert anchor in src
src=src.replace(anchor,hist+anchor,1)
anchor='function platformSnapshot(rows,p)'
assert anchor in src
inject="""for(const event of PLATFORM_CHANGES_20261027){
 const normEvent=s=>String(s||'').normalize('NFD').replace(/[\\u0300-\\u036f]/g,'').toLowerCase().replace(/[^a-z0-9]/g,'');
 if(!changeHistory.some(e=>e.platform===event.platform&&e.type===event.type&&(event.id&&e.id===event.id||normEvent(e.name)===normEvent(event.name))))changeHistory.unshift(event);
}
changeHistory.sort((a,b)=>String(b.date||'').localeCompare(String(a.date||'')));
try{localStorage.setItem(CHANGE_STORAGE,JSON.stringify(changeHistory))}catch(e){}
"""
src=src.replace(anchor,inject+anchor,1)
ROOT.write_text(src,encoding='utf-8')
report={'date':DATE,'platforms':stats,'confirmed_rp_removed':removed,'new_history_events':events,'total_records':len(seed),'counts':{p:sum(bool(x.get(p)) for x in seed) for p in ('rp','rr','wi','tc')}}
Path('updates/report-2026-10-27.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'counts':report['counts'],'new':{p:len(stats[p]['new']) for p in stats},'unconfirmed':{p:len(stats[p]['unconfirmed_absences']) for p in stats},'removed':removed,'events':len(events)},ensure_ascii=False))
