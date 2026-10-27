import json,re,unicodedata
from pathlib import Path
p=Path('index.html')
s=p.read_text(encoding='utf-8')
a=s.index('const SEED=')+len('const SEED=')
b=s.index('];',a)+1
seed=json.loads(s[a:b])
def norm(v):
    t=unicodedata.normalize('NFKD',str(v or '').lower())
    return re.sub('[^a-z0-9]','', ''.join(x for x in t if not unicodedata.combining(x)))
def base(v):
    return re.sub(r'(fr|france|com)$','',norm(v))
# Preserve first-run actual historical events; remove repeated empty injection.
found=re.findall(r'const PLATFORM_CHANGES_20261027=(\[[^\n]*?\]);',s)
assert found
events=json.loads(found[0])
s=re.sub(r'const PLATFORM_CHANGES_20261027=\[[^\n]*?\];\n','',s)
s=re.sub(r'for\(const event of PLATFORM_CHANGES_20261027\)\{.*?try\{localStorage.setItem\(CHANGE_STORAGE,JSON.stringify\(changeHistory\)\)\}catch\(e\)\{\}\n','',s,flags=re.S)
# Remove both obsolete migration snippets and insert only one safe migration.
s=re.sub(r'// Import validé 2026-10-27 : priorité aux identifiants et aux fiches existantes\..*?(?=let page=0;const PAGE_SIZE=)','',s,flags=re.S)
# Canonicalize RP names where a fresh FR variant duplicates an established merchant.
alias_merged=[]
for row in list(seed):
    if not row.get('rp') or row.get('rpDate')!='2026-10-27':continue
    new_name=row.get('name','')
    candidates=[dest for dest in seed if dest is not row and dest.get('rp') and norm(new_name)!=norm(dest.get('name')) and base(new_name)==base(dest.get('name')) and base(new_name)]
    if len(candidates)!=1:continue
    dest=candidates[0]
    if all(not row.get(k) for k in ('rr','wi','tc')):
        ids=list(dict.fromkeys([*(str(dest.get('rpId','')).split(';')),*(str(row.get('rpId','')).split(';'))]))
        dest['rpId']=';'.join(x for x in ids if x)
        if row.get('rpLogo') and not dest.get('rpLogo'):dest['rpLogo']=row['rpLogo']
        dest['rpDate']='2026-10-27'
        seed.remove(row)
        alias_merged.append(new_name)
        events=[e for e in events if not(e['platform']=='rp' and e['type']=='add' and norm(e['name'])==norm(new_name))]
# User-confirmed removals, only RP portion.
removed=[]
for row in seed:
    if base(row.get('rp')) in ('high','omymaison','thecoolrepublic') or base(row.get('name')) in ('high','omymaison','thecoolrepublic') and row.get('rp'):
        removed.append((row.get('name'),row.get('rpId')))
        if not any(e['platform']=='rp' and e['type']=='remove' and (norm(e['name'])==norm(row.get('name')) or str(e.get('id','')) in str(row.get('rpId',''))) for e in events):
            events.append({'platform':'rp','name':row.get('name'),'id':str(row.get('rpId','')).split(';')[0],'type':'remove','date':'2026-10-27'})
        for f in ('rp','rpId','rpLogo','rpDate'):row[f]=''
# Do not duplicate events that were already recorded before Oct 27.
preexisting=[('rp','Médor et Cie','remove'),('rr','HiBike','add'),('rr','Ava & May','add'),('rr','Cavissima','add'),('rr','LiberNovo','add')]
events=[e for e in events if not any(e['platform']==p and e['type']==typ and norm(e['name'])==norm(name) for p,name,typ in preexisting)]
unique={}
for ev in events:
    k=(ev['platform'],ev['type'],ev.get('id') or norm(ev['name']))
    unique[k]=ev
events=list(unique.values())
seed=[x for x in seed if any(x.get(k) for k in ('rp','rr','wi','tc'))]
s=s[:a]+json.dumps(seed,ensure_ascii=False,separators=(',',':'))+s[b:]
hist='const PLATFORM_CHANGES_20261027='+json.dumps(events,ensure_ascii=False,separators=(',',':'))+';\n'
s=s.replace('const CHANGE_STORAGE=',hist+'const CHANGE_STORAGE=',1)
hist_apply="""for(const event of PLATFORM_CHANGES_20261027){
 const same=(x,y)=>String(x||'').normalize('NFD').replace(/[\\u0300-\\u036f]/g,'').toLowerCase().replace(/[^a-z0-9]/g,'')===String(y||'').normalize('NFD').replace(/[\\u0300-\\u036f]/g,'').toLowerCase().replace(/[^a-z0-9]/g,'');
 if(!changeHistory.some(e=>e.platform===event.platform&&e.type===event.type&&(event.id&&e.id===event.id||same(e.name,event.name))))changeHistory.unshift(event);
}
changeHistory.sort((a,b)=>String(b.date||'').localeCompare(String(a.date||'')));
try{localStorage.setItem(CHANGE_STORAGE,JSON.stringify(changeHistory))}catch(e){}
"""
s=s.replace('function platformSnapshot(rows,p)',hist_apply+'function platformSnapshot(rows,p)',1)
migration="""// Reprise idempotente de la validation CSV du 27 octobre sans toucher aux catégories.
try{
 const flag='cashback_platform_seed_20261027_v2';
 if(localStorage.getItem(flag)!=='1'){
  const normalize=s=>String(s||'').normalize('NFD').replace(/[\\u0300-\\u036f]/g,'').toLowerCase().replace(/[^a-z0-9]/g,'');
  const map=new Map(records.map(r=>[normalize(r.name),r]));
  const byId=new Map(),byUrl=new Map();
  for(const r of records){
   for(const p of ['rp','rr'])for(const id of String(r[p+'Id']||'').split(/[;,]/).map(x=>x.trim()).filter(Boolean))byId.set(p+':'+id,r);
   if(r.wiUrl)byUrl.set(r.wiUrl,r);
  }
  for(const src of SEED){
   const ids=['rp','rr'].flatMap(p=>String(src[p+'Id']||'').split(/[;,]/).map(x=>x.trim()).filter(Boolean).map(id=>p+':'+id));
   const dest=ids.map(id=>byId.get(id)).find(Boolean)||byUrl.get(src.wiUrl)||map.get(normalize(src.name))||records.find(r=>normalize(r.name).replace(/(fr|france|com)$/,'')===normalize(src.name).replace(/(fr|france|com)$/,''));
   if(dest){
    for(const platform of ['rp','rr','wi'])if(src[platform+'Date']==='2026-10-27'){
     const fields=platform==='rp'?['rp','rpId','rpLogo','rpDate']:platform==='rr'?['rr','rrId','rrLogo','rrUrl','rate','rrDate']:['wi','wiUrl','wiRate','wiDate','wiAliases','wiUrls'];
     for(const field of fields)if(src[field]!==undefined)dest[field]=src[field];
    }
   }else if(['rp','rr','wi'].some(platform=>src[platform+'Date']==='2026-10-27')){records.push({...src});map.set(normalize(src.name),src)}
  }
  for(const r of records){
   if(['high','omymaison','thecoolrepublic','medoretcie'].includes(normalize(r.rp||'').replace(/(fr|france|com)$/,''))||['high','omymaison','thecoolrepublic','medoretcie'].includes(normalize(r.name).replace(/(fr|france|com)$/,'')))for(const field of ['rp','rpId','rpLogo','rpDate'])r[field]='';
  }
  localStorage.setItem(STORAGE,JSON.stringify(records));
  localStorage.setItem(flag,'1');
 }
}catch(e){console.warn('Migration CSV octobre 27',e)}
"""
anchor='let page=0;const PAGE_SIZE='
assert anchor in s
s=s.replace(anchor,migration+'\n'+anchor,1)
p.write_text(s,encoding='utf-8')
report={'date':'2026-10-27','corrected':True,'aliases_merged':alias_merged,'rp_confirmed_removed':removed,'history_events':events,'counts':{k:sum(bool(x.get(k)) for x in seed) for k in ('rp','rr','wi','tc')},'records':len(seed)}
Path('updates/report-final-2026-10-27.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
assert s.count('const PLATFORM_CHANGES_20261027=')==1 and s.count('cashback_platform_seed_20261027_v2')==1
print(json.dumps({'aliasesMerged':alias_merged,'removed':removed,'events':len(events),'counts':report['counts']},ensure_ascii=False))

# Trigger final corrective integration.
